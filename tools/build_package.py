"""Build a Windows candidate in a fresh directory and record its verified inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from time import monotonic
import venv
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from neto_incident_monitor import __version__
from tools.package_inputs import (BROWSER_MARKERS, MANIFEST, PackageInputError, browser_metadata,
                                  dashboard_payload, read_manifest, sha256_file, verified_browser_folders)


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'scripts' / 'Neto Incident Monitor.spec'
LOCK = ROOT / 'requirements-build.txt'
APP = 'Neto Incident Monitor'
PRIVATE_FILES = {'config.json', 'dashboard-cache.json', 'filter-layouts.json', 'history.json', 'seen.json',
                 'cookies', 'login data', 'local state', 'preferences'}


def command(args, *, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          check=True).stdout


def toolchain(manifest):
    if (sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64')
            or struct.calcsize('P') != 8 or platform.python_implementation() != 'CPython'
            or platform.python_version() != manifest['python']):
        raise PackageInputError('python_version_or_architecture')


def install_wheels(python, wheelhouse, env):
    args = [python, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check']
    source = ['--no-index', '--find-links', str(wheelhouse)] if wheelhouse else ['--index-url', 'https://pypi.org/simple']
    command([*args, 'install', '--no-input', '--no-cache-dir', '--only-binary=:all:', '--require-hashes',
             *source, '-r', str(LOCK)], env=env)
    command([*args, 'check'], env=env)
    return json.loads(command([*args, 'list', '--format=json'], env=env))


def prepare_browsers(python, cache, source, expected, env):
    metadata_file = python.parents[1] / 'Lib/site-packages/playwright/driver/package/browsers.json'
    browser_metadata(json.loads(metadata_file.read_text(encoding='utf-8'))['browsers'], expected)
    if source is None:
        command([python, '-I', '-m', 'playwright', 'install', '--no-shell', '--no-progress', 'chromium'], env=env)
    else:
        for folder in verified_browser_folders(source, expected):
            shutil.copytree(folder, cache / folder.name, ignore=shutil.ignore_patterns(*BROWSER_MARKERS))
    verified_browser_folders(cache, expected)


def inventory(bundle, payload, browsers):
    internal = bundle / '_internal'
    if not (bundle / f'{APP}.exe').is_file():
        raise PackageInputError('package_executable')
    seed = internal / 'defaults' / 'dashboard-api.json'
    if seed.read_bytes() != payload:
        raise PackageInputError('package_dashboard')
    verified_browser_folders(internal / 'browsers', browsers)
    files = {}
    for path in sorted(bundle.rglob('*')):
        if not path.is_file():
            continue
        if (path.name.lower() in PRIVATE_FILES or (path.name == 'dashboard-api.json' and path != seed)
                or path.suffix.lower() in ('.log', '.xlsx', '.sqlite', '.sqlite3', '.db', '.jsonl')):
            raise PackageInputError('package_private_file')
        files[path.relative_to(bundle).as_posix()] = sha256_file(path)
    return files


def archive_candidate(bundle, destination, files):
    # ZIP metadata does not depend on the paths or modification times of the build machine.
    with ZipFile(destination, 'x', ZIP_DEFLATED) as archive:
        for name in sorted(files):
            entry = ZipInfo(f'{APP}/{name}')
            entry.compress_type = ZIP_DEFLATED
            with (bundle / name).open('rb') as source, archive.open(entry, 'w', force_zip64=True) as target:
                shutil.copyfileobj(source, target)
    with ZipFile(destination) as archive:
        if sorted(archive.namelist()) != [f'{APP}/{name}' for name in sorted(files)]:
            raise PackageInputError('archive_check')
        for name, expected in files.items():
            # Reading each member also verifies the ZIP CRC.
            with archive.open(f'{APP}/{name}') as member:
                if hashlib.file_digest(member, 'sha256').hexdigest() != expected:
                    raise PackageInputError('archive_check')


def build(args, report):
    stage_started = monotonic()

    def advance(stage):
        nonlocal stage_started
        now = monotonic()
        if 'stage' in report:
            report['stage_seconds'][report['stage']] = round(now - stage_started, 2)
        report['stage'] = stage
        stage_started = now

    advance('input_validation')
    manifest = read_manifest()
    toolchain(manifest)
    payload = dashboard_payload(args.dashboard_parameters, manifest['dashboard']['sha256'])
    report['commit'] = command(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    report['clean_checkout'] = not command(['git', 'status', '--porcelain', '--untracked-files=normal'])
    report['input_hashes'] = {'manifest': sha256_file(MANIFEST), 'wheels_lock': sha256_file(LOCK),
                              'dashboard_parameters': hashlib.sha256(payload).hexdigest()}
    report['dashboard_revision'] = manifest['dashboard']['revision']
    report['browsers'] = manifest['browsers']
    epoch = command(['git', 'show', '-s', '--format=%ct', 'HEAD']).decode('ascii').strip()
    cache = args.output / 'browsers'
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PYTHON', 'PLAYWRIGHT_', 'PIP_'))}
    env.update(PYTHONHASHSEED='0', PYTHONNOUSERSITE='1', SOURCE_DATE_EPOCH=epoch,
               PYINSTALLER_CONFIG_DIR=str(args.output / 'pyinstaller-cache'),
               PLAYWRIGHT_BROWSERS_PATH=str(cache), NETO_BUILD_DASHBOARD_PARAMETERS=str(args.dashboard_parameters))

    advance('dependencies')
    print('Przygotowanie zależności...', flush=True)
    environment = args.output / 'venv'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / 'Scripts/python.exe'
    report['dependencies'] = install_wheels(python, args.wheelhouse, env)
    if {'name': 'pip', 'version': manifest['bootstrap_pip']} not in report['dependencies']:
        raise PackageInputError('pip_version')

    advance('browsers')
    print('Weryfikacja Chromium i FFmpeg...', flush=True)
    prepare_browsers(python, cache, args.browser_cache, manifest['browsers'], env)
    report['browser_source'] = 'verified_cache' if args.browser_cache else 'playwright_download'

    advance('pyinstaller')
    print('Budowa EXE...', flush=True)
    target = args.output / 'dist'
    command([python, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', str(target),
             '--workpath', str(args.output / 'work'), str(SPEC)], env=env)

    advance('archive')
    print('Kontrola plików i archiwum...', flush=True)
    bundle = target / APP
    files = inventory(bundle, payload, manifest['browsers'])
    path = args.output / f'Neto.Incident.Monitor-{__version__}.zip'
    archive_candidate(bundle, path, files)
    (args.output / 'package-files.json').write_text(json.dumps(files, indent=2, sort_keys=True), encoding='utf-8')
    report['package'] = {'archive': path.name, 'files': len(files), 'sha256': sha256_file(path)}
    advance('complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option, required in (('output', True), ('dashboard-parameters', True), ('wheelhouse', False),
                             ('browser-cache', False)):
        parser.add_argument(f'--{option}', type=lambda path: Path(path).absolute(), required=required)
    args = parser.parse_args()
    try:
        args.output.mkdir(parents=True)
    except OSError:
        print('Podaj nowy, zapisywalny katalog wyniku.', file=sys.stderr)
        return 1

    started = monotonic()
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
              'app_version': __version__, 'python': platform.python_version(),
              'windows': platform.version(), 'architecture': platform.machine(), 'pointer_bits': 8 * struct.calcsize('P'),
              'stage_seconds': {}}
    try:
        build(args, report)
        report['status'] = 'ok'
        print(f"Gotowe. Raport w build-report.json. ZIP: {report['package']['archive']}.")
    except PackageInputError as error:
        report['reason'] = str(error)
    except subprocess.CalledProcessError as error:
        report['reason'], report['exit_code'] = 'tool_failed', error.returncode
    except BadZipFile:
        report['reason'] = 'archive_check'
    except (OSError, ValueError, KeyError, TypeError):
        report['reason'] = 'configuration_or_file_access'
    except KeyboardInterrupt:
        report['status'], report['reason'] = 'cancelled', 'interrupted'
    finally:
        report['duration_s'] = round(monotonic() - started, 2)
        if report['stage'] != 'complete':
            completed = sum(report['stage_seconds'].values())
            report['stage_seconds'][report['stage']] = round(max(0, report['duration_s'] - completed), 2)
        (args.output / 'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if report['status'] != 'ok':
        print(f"Budowa przerwana. Etap: {report['stage']}, przyczyna: {report['reason']}. "
              "Szczegóły w build-report.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
