import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
import contextlib
import sys

from neto_incident_monitor import updates
from neto_incident_monitor import update_installer


def asset(name, size=1):
    return {'name': name, 'size': size,
            'browser_download_url': f'https://github.com/{updates.REPO}/releases/download/v2.0.0/{name}'}


def package():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as bundle:
        for name in (updates.EXE, updates.HELPER, '_internal/test.dll'):
            bundle.writestr('Neto Incident Monitor/' + name, b'new')
    return buffer.getvalue()


class UpdateTests(unittest.TestCase):
    def test_publish_manifest_contains_exact_hash_size_and_asset_name(self):
        from tools.update_manifest import main
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            archive, output = Path(directory) / 'app.zip', Path(directory) / 'update-manifest.json'
            raw = package()
            archive.write_bytes(raw)
            with patch.object(sys, 'argv', ['manifest', str(archive), '--output', str(output)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                main()
            result = json.loads(output.read_text())
            self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result['size'], len(raw))
            self.assertEqual(result['asset_name'], 'Neto.Incident.Monitor.zip')

    def test_newer_stable_release_requires_matching_manifest_and_asset(self):
        manifest = {'version': '2.0.0', 'asset_name': 'Neto.Incident.Monitor.zip', 'size': 123,
                    'sha256': 'a' * 64}
        release = {'tag_name': 'v2.0.0', 'assets': [asset('update-manifest.json'), asset(manifest['asset_name'], 123)]}
        with patch.object(updates, 'fetch_json', side_effect=[release, manifest]):
            result = updates.check_release('1.9.9')
        self.assertEqual(result['version'], '2.0.0')
        self.assertEqual(result['sha256'], 'a' * 64)
        for changed in ({'sha256': 'bad'}, {'version': '3.0.0'}, {'size': 124}, {'asset_name': '../evil.zip'}):
            with self.subTest(changed=changed), patch.object(updates, 'fetch_json', side_effect=[release, {**manifest, **changed}]):
                with self.assertRaises(updates.UpdateError):
                    updates.check_release('1.9.9')
        with patch.object(updates, 'fetch_json', return_value={'tag_name': 'v2.0.0', 'assets': []}):
            with self.assertRaises(updates.UpdateError):
                updates.check_release('1.0.0')

    def test_equal_older_and_prerelease_are_not_updates(self):
        for release in ({'tag_name': 'v1.4.3'}, {'tag_name': 'v1.3.9'}, {'prerelease': True, 'tag_name': 'v2.0.0'}, {'draft': True}):
            with patch.object(updates, 'fetch_json', return_value=release):
                self.assertIsNone(updates.check_release('1.4.3'))
        self.assertGreater(updates.version('1.10.0'), updates.version('1.9.9'))

    def test_download_urls_and_redirects_cannot_leave_github_https(self):
        with self.assertRaises(updates.UpdateError):
            updates.asset_url({'name': 'x.zip', 'browser_download_url': 'https://evil.test/x.zip'}, 'v2.0.0')
        for url in ('http://github.com/file', 'https://evil.test/file', 'https://user@github.com/file'):
            with self.assertRaises(updates.UpdateError):
                updates.SecureRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_bad_zip_paths_links_and_case_collisions_are_rejected(self):
        for name in ('../escaped', '/absolute', 'Neto Incident Monitor/../escaped',
                     'Neto Incident Monitor/C:/escaped', 'Neto Incident Monitor\\..\\escaped',
                     'Neto Incident Monitor/CON.txt', 'Neto Incident Monitor/file.'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                archive = Path(directory) / 'test.zip'
                with zipfile.ZipFile(archive, 'w') as bundle:
                    entry = zipfile.ZipInfo()
                    entry.filename = name
                    bundle.writestr(entry, 'unsafe')
                with self.assertRaises(updates.UpdateError):
                    updates.extract_package(archive, Path(directory) / 'out')
                self.assertFalse((Path(directory) / 'out').exists())
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            archive = Path(directory) / 'test.zip'
            for kind in ('link', 'duplicate'):
                with zipfile.ZipFile(archive, 'w') as bundle:
                    entry = zipfile.ZipInfo('Neto Incident Monitor/file')
                    entry.external_attr = 0o120777 << 16 if kind == 'link' else 0
                    bundle.writestr(entry, 'data')
                    if kind == 'duplicate':
                        bundle.writestr('Neto Incident Monitor/FILE', 'data')
                with self.assertRaises(updates.UpdateError):
                    updates.extract_package(archive, Path(directory) / 'out')

    def test_download_hash_is_checked_before_staging_or_installation(self):
        raw = package()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            target, data = root / 'app', root / 'user-data'
            target.mkdir()
            (target / updates.EXE).write_bytes(b'old')
            (target / '_internal').mkdir()
            helper = target / updates.HELPER
            helper.write_bytes(b'helper')
            info = {'version': '2.0.0', 'size': len(raw), 'sha256': '0' * 64, 'url': 'ignored'}
            with patch.object(updates, 'open_url', return_value=io.BytesIO(raw)):
                with self.assertRaises(updates.UpdateError):
                    updates.prepare_update(info, target, data, helper)
            self.assertFalse(list(root.glob('.neto-update-*')))
            info['sha256'] = hashlib.sha256(raw).hexdigest()
            with patch.object(updates, 'open_url', return_value=io.BytesIO(raw)):
                job = updates.prepare_update(info, target, data, helper)
            details = json.loads(job.read_text())
            self.assertEqual((Path(details['payload']) / updates.EXE).read_bytes(), b'new')
            self.assertEqual(helper.read_bytes(), b'helper')
            self.assertTrue((job.parent / updates.HELPER).is_file())

    def make_job(self, root):
        target = root / 'app'
        target.mkdir()
        (target / updates.EXE).write_text('old')
        stage = root / '.neto-update-test'
        payload = stage / 'Neto Incident Monitor'
        (payload / '_internal').mkdir(parents=True)
        (payload / updates.EXE).write_text('new')
        return {'target': str(target), 'stage': str(stage), 'payload': str(payload), 'version': '2.0.0'}

    def test_transaction_installs_and_keeps_backup_without_touching_user_data(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            data = root / 'user-data'
            data.mkdir()
            (data / 'history.json').write_text('preserved')
            job = self.make_job(root)
            health, restart = Mock(), Mock()
            backup = update_installer.install(job, data, health, restart)
            self.assertEqual((Path(job['target']) / updates.EXE).read_text(), 'new')
            self.assertEqual((backup / updates.EXE).read_text(), 'old')
            self.assertEqual((data / 'history.json').read_text(), 'preserved')
            health.assert_called_once()
            restart.assert_called_once_with(Path(job['target']))

    def test_failed_health_check_restores_previous_installation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            job = self.make_job(root)
            restart = Mock()
            with self.assertRaises(RuntimeError):
                update_installer.install(job, root, Mock(side_effect=RuntimeError('unhealthy')), restart)
            self.assertEqual((Path(job['target']) / updates.EXE).read_text(), 'old')
            self.assertEqual((Path(job['stage']) / 'failed' / updates.EXE).read_text(), 'new')
            restart.assert_called_once_with(Path(job['target']))

    def test_failed_swap_restores_old_folder_and_restarts_it(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            job = self.make_job(root)
            original = Path.rename
            def rename(path, target):
                if path == Path(job['payload']):
                    raise PermissionError('test failure')
                return original(path, target)
            restart = Mock()
            with patch.object(Path, 'rename', new=rename), self.assertRaises(PermissionError):
                update_installer.install(job, root, restart=restart)
            self.assertEqual((Path(job['target']) / updates.EXE).read_text(), 'old')
            restart.assert_called_once_with(Path(job['target']))

    def test_invalid_stage_and_portable_user_data_block_installation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            job = self.make_job(root)
            with self.assertRaises(ValueError):
                update_installer.validate_job({**job, 'payload': str(root / 'outside')})
            (Path(job['target']) / 'data').mkdir()
            with self.assertRaises(ValueError):
                update_installer.validate_job(job)
