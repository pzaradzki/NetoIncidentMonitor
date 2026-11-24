"""Build-only validation of the explicit inputs to the Windows package."""
import hashlib
import json
import stat
from importlib.metadata import distribution
from pathlib import Path

from neto_incident_monitor.analytics_config import group_name, lost_incidents_query, reference, request_queries
from neto_incident_monitor.dashboard_context import DashboardReadError


PARAMETER_KEYS = ('version', 'monthly_group', 'held_metric', 'l1_group_name', 'smartphone_variable',
                  'smartphone_description', 'threatened_group', 'lost_excluded_group')
BROWSER_MARKERS = {'DEPENDENCIES_VALIDATED', 'INSTALLATION_COMPLETE'}
MANIFEST = Path(__file__).resolve().parents[1] / 'scripts' / 'build-inputs.json'


class PackageInputError(ValueError):
    """A fixed reason suitable for a build report."""


def read_manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def sha256_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_dashboard(config):
    if (not isinstance(config, dict) or set(config) != set(PARAMETER_KEYS)
            or type(config['version']) is not int or config['version'] != 1):
        raise PackageInputError('dashboard_schema')
    try:
        for key in ('monthly_group', 'held_metric', 'smartphone_variable', 'threatened_group', 'lost_excluded_group'):
            reference(config, key)
        group_name(config)
        lost_incidents_query(config)
        request_queries({**config, 'assignees': ['1' * 32]})
    except DashboardReadError:
        raise PackageInputError('dashboard_schema') from None


def canonical_dashboard(config):
    validate_dashboard(config)
    return (json.dumps(config, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise PackageInputError('dashboard_schema')
    return result


def dashboard_payload(path, expected_digest):
    try:
        with path.open('rb') as stream:
            payload = stream.read(24_001)
    except OSError:
        raise PackageInputError('dashboard_unavailable') from None
    if len(payload) > 24_000:
        raise PackageInputError('dashboard_schema')
    try:
        config = json.loads(payload.decode('utf-8'), object_pairs_hook=unique_fields)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise PackageInputError('dashboard_schema') from None
    if canonical_dashboard(config) != payload:
        raise PackageInputError('dashboard_format')
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise PackageInputError('dashboard_digest')
    return payload


def browser_metadata(entries, expected):
    observed = {entry['name']: entry for entry in entries}
    for name, browser in expected.items():
        entry = observed.get(name, {})
        if (entry.get('revision') != browser['revision']
                or entry.get('browserVersion') != browser.get('version')):
            raise PackageInputError('browser_metadata')


def validate_playwright(expected):
    spec = distribution('playwright').locate_file('playwright/driver/package/browsers.json')
    try:
        entries = json.loads(spec.read_text(encoding='utf-8'))['browsers']
        browser_metadata(entries, expected)
    except (OSError, KeyError, TypeError, ValueError):
        raise PackageInputError('browser_metadata') from None


def reject_redirect(path):
    info = path.lstat()
    attributes = getattr(info, 'st_file_attributes', 0)
    if path.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise PackageInputError('browser_redirect')
    return info


def browser_files(folder):
    """List only ordinary files. Installer marker files are not part of the binary input."""
    reject_redirect(folder)
    paths = []
    for path in folder.rglob('*'):
        info = reject_redirect(path)
        if path.name in BROWSER_MARKERS and path.parent == folder and stat.S_ISREG(info.st_mode):
            continue
        if stat.S_ISREG(info.st_mode):
            paths.append(path)
        elif not stat.S_ISDIR(info.st_mode):
            raise PackageInputError('browser_file_type')
    return sorted(paths, key=lambda path: path.relative_to(folder).as_posix())


def browser_digest(folder):
    digest = hashlib.sha256()
    for path in browser_files(folder):
        digest.update(path.relative_to(folder).as_posix().encode('utf-8') + b'\0')
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def verified_browser_folders(cache, expected):
    result = []
    for name, entry in expected.items():
        folder = cache / f"{name}-{entry['revision']}"
        try:
            if not folder.is_dir() or not (folder / entry['executable']).is_file():
                raise PackageInputError('browser_unavailable')
            if browser_digest(folder) != entry['sha256']:
                raise PackageInputError('browser_digest')
        except OSError:
            raise PackageInputError('browser_unavailable') from None
        result.append(folder)
    return result
