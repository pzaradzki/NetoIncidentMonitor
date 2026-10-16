"""Release discovery and verified staging; never modifies the running installation."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4
import zipfile

REPO = 'pzaradzki/NetoIncidentMonitor'
API = f'https://api.github.com/repos/{REPO}/releases/latest'
EXE = 'Neto Incident Monitor.exe'
HELPER = 'Neto Update Helper.exe'
MAX_ZIP = 1_000_000_000


class UpdateError(Exception):
    pass


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise UpdateError('Nieprawidłowy numer wersji wydania.')
    return tuple(map(int, value.lstrip('v').split('.')))


class SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.hostname not in (
                'github.com', 'api.github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'):
            raise UpdateError('Nieprawidłowe przekierowanie pobierania aktualizacji.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    return build_opener(SecureRedirect()).open(Request(url, headers={
        'User-Agent': 'NetoIncidentMonitor-Updater', 'Accept': 'application/vnd.github+json'}), timeout=20)


def fetch_json(url):
    with open_url(url) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise UpdateError('Zbyt duży manifest aktualizacji.')
    return json.loads(raw)


def asset_url(asset, tag):
    name = asset.get('name', '')
    expected = f'https://github.com/{REPO}/releases/download/{quote(tag, safe="")}/{quote(name, safe="")}'
    if asset.get('browser_download_url') != expected:
        raise UpdateError('Załącznik nie pochodzi z oczekiwanego wydania.')
    return expected


def check_release(current):
    release = fetch_json(API)
    if release.get('draft') or release.get('prerelease'):
        return None
    tag = release.get('tag_name', '')
    if version(tag) <= version(current):
        return None
    assets = release.get('assets', [])
    manifests = [a for a in assets if a.get('name') == 'update-manifest.json']
    if len(manifests) != 1:
        raise UpdateError(f'Wydanie {tag} nie zawiera manifestu automatycznej aktualizacji.')
    manifest = fetch_json(asset_url(manifests[0], tag))
    if version(manifest.get('version')) != version(tag):
        raise UpdateError('Wersja manifestu nie zgadza się z wydaniem.')
    name, digest, size = (manifest.get(k) for k in ('asset_name', 'sha256', 'size'))
    if not isinstance(name, str) or not re.fullmatch(r'Neto[ .]Incident[ .]Monitor\.zip', name, re.I):
        raise UpdateError('Nieprawidłowa nazwa paczki aktualizacji.')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise UpdateError('Manifest nie zawiera poprawnej sumy SHA256.')
    packages = [a for a in assets if a.get('name') == name]
    if type(size) is not int or not 0 < size <= MAX_ZIP or len(packages) != 1 or packages[0].get('size') != size:
        raise UpdateError('Rozmiar paczki nie zgadza się z manifestem.')
    return {'version': tag.lstrip('v'), 'url': asset_url(packages[0], tag),
            'sha256': digest.lower(), 'size': size}


def extract_package(archive, destination):
    """Reject traversal, Windows aliases, links and ZIP bombs before writing anything."""
    with zipfile.ZipFile(archive) as bundle:
        names, entries, total = set(), bundle.infolist(), 0
        if len(entries) > 50_000:
            raise UpdateError('Paczka zawiera zbyt wiele plików.')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            parts = entry.filename.rstrip('/').split('/')
            if (path.is_absolute() or '\\' in entry.filename or not parts or parts[0] != 'Neto Incident Monitor'
                    or any(part in ('', '.', '..') or re.search(r'[:*?"<>|\x00-\x1f]', part) or part.endswith((' ', '.'))
                           or re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', part.split('.')[0].rstrip(' '), re.I)
                           for part in parts)
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise UpdateError('Nieprawidłowa ścieżka w paczce aktualizacji.')
            key = '/'.join(parts).casefold()
            if key in names:
                raise UpdateError('Powtórzona ścieżka w paczce aktualizacji.')
            names.add(key)
            total += entry.file_size
            if entry.flag_bits & 1 or total > 2_000_000_000:
                raise UpdateError('Nieprawidłowy rozmiar lub szyfrowana paczka.')
        bundle.extractall(destination)
    payload = Path(destination) / 'Neto Incident Monitor'
    if not (payload / EXE).is_file() or not (payload / '_internal').is_dir() or not (payload / HELPER).is_file():
        raise UpdateError('Paczka nie zawiera kompletnej aplikacji i aktualizatora.')
    return payload


def prepare_update(info, target, data, helper):
    target, data = Path(target).resolve(), Path(data).resolve()
    if not (target / EXE).is_file() or not (target / '_internal').is_dir():
        raise UpdateError('Nie można automatycznie zaktualizować tej lokalizacji aplikacji.')
    if data.is_relative_to(target) or (target / 'data').exists():
        raise UpdateError('Folder aplikacji zawiera dane użytkownika. Wymagana aktualizacja ręczna.')
    if not Path(helper).is_file():
        raise UpdateError('Brak programu aktualizującego. Wymagana aktualizacja ręczna.')
    work = data / 'updates' / uuid4().hex
    work.mkdir(parents=True)
    archive = work / 'package.zip'
    stage = None
    try:
        digest, size = hashlib.sha256(), 0
        with open_url(info['url']) as response, archive.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > info['size']:
                    raise UpdateError('Pobrana paczka jest większa niż zadeklarowano.')
                digest.update(chunk)
                output.write(chunk)
        if size != info['size'] or digest.hexdigest() != info['sha256']:
            raise UpdateError('Weryfikacja SHA256 paczki nie powiodła się.')
        # Sibling staging permits atomic renames even when installed on another drive.
        stage = Path(tempfile.mkdtemp(prefix='.neto-update-', dir=target.parent))
        payload = extract_package(archive, stage)
        shutil.copy2(helper, work / HELPER)
        job = {'target': str(target), 'stage': str(stage), 'payload': str(payload),
               'version': info['version'], 'pid': os.getpid()}
        job_path = work / 'job.json'
        job_path.write_text(json.dumps(job), encoding='utf-8')
        return job_path
    except Exception:
        if stage is not None:
            shutil.rmtree(stage)
        raise
    finally:
        archive.unlink(missing_ok=True)
