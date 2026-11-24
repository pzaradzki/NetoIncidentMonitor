import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_package
from tools.package_inputs import (PackageInputError, browser_digest, browser_metadata, canonical_dashboard,
                                  dashboard_payload, verified_browser_folders)


PARAMETERS = dict(version=1, monthly_group='1' * 32, held_metric='2' * 32, l1_group_name='Synthetic L1',
                  smartphone_variable='3' * 32, smartphone_description='Synthetic Task',
                  threatened_group='4' * 32, lost_excluded_group='5' * 32)


class PackageInputsTests(unittest.TestCase):
    def test_checked_dashboard_requires_canonical_approved_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dashboard-api.json'
            payload = canonical_dashboard(PARAMETERS)
            digest = hashlib.sha256(payload).hexdigest()
            with self.assertRaisesRegex(PackageInputError, '^dashboard_unavailable$'):
                dashboard_payload(path, digest)
            path.write_bytes(payload)
            self.assertEqual(dashboard_payload(path, digest), payload)
            path.write_bytes(canonical_dashboard({**PARAMETERS, 'l1_group_name': 'Synthetic L2'}))
            with self.assertRaisesRegex(PackageInputError, '^dashboard_digest$'):
                dashboard_payload(path, digest)
            path.write_text(json.dumps(PARAMETERS), encoding='utf-8')
            with self.assertRaisesRegex(PackageInputError, '^dashboard_format$'):
                dashboard_payload(path, digest)

    def test_dashboard_refuses_private_fields_legacy_and_invalid_parameters(self):
        legacy = {key: value for key, value in PARAMETERS.items() if key != 'lost_excluded_group'}
        for data in (legacy, {**PARAMETERS, 'assignees': ['synthetic-secret']},
                     {**PARAMETERS, 'locations': ['synthetic-secret']}, {**PARAMETERS, 'version': True},
                     {**PARAMETERS, 'held_metric': 'synthetic-secret'},
                     {**PARAMETERS, 'lost_excluded_group': PARAMETERS['monthly_group']}):
            with self.subTest(keys=sorted(data)), self.assertRaisesRegex(PackageInputError, '^dashboard_schema$'):
                canonical_dashboard(data)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            for malformed in ('{"version":1,"version":1}', 'synthetic-secret', ' ' * 24_001):
                path.write_text(malformed, encoding='utf-8')
                with self.assertRaisesRegex(PackageInputError, '^dashboard_schema$'):
                    dashboard_payload(path, 'unused')

    def test_browser_metadata_requires_the_declared_revision_and_version(self):
        expected = {'chromium': {'revision': '1243', 'version': '153.0'}}
        browser_metadata([dict(name='chromium', revision='1243', browserVersion='153.0')], expected)
        for metadata in ([], [dict(name='chromium', revision='1234', browserVersion='153.0')],
                         [dict(name='chromium', revision='1243', browserVersion='154.0')]):
            with self.assertRaisesRegex(PackageInputError, '^browser_metadata$'):
                browser_metadata(metadata, expected)

    def test_browser_cache_requires_exact_file_content_and_ignores_install_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            folder = cache / 'chromium-1243'
            folder.mkdir()
            binary = folder / 'browser.exe'
            binary.write_bytes(b'browser')
            (folder / 'resources.pak').write_bytes(b'resource')
            expected = {'chromium': {'revision': '1243', 'executable': 'browser.exe',
                                     'sha256': browser_digest(folder)}}
            (folder / 'INSTALLATION_COMPLETE').touch()
            self.assertEqual(verified_browser_folders(cache, expected), [folder])
            (folder / 'resources.pak').write_bytes(b'wrong')
            with self.assertRaisesRegex(PackageInputError, '^browser_digest$'):
                verified_browser_folders(cache, expected)
            binary.unlink()
            with self.assertRaisesRegex(PackageInputError, '^browser_unavailable$'):
                verified_browser_folders(cache, expected)

    def test_python_toolchain_rejects_unpinned_version_and_unsupported_architecture(self):
        manifest = {'python': '3.12.6'}
        with patch.object(build_package.sys, 'platform', 'win32'), patch.object(
                build_package.platform, 'machine', return_value='AMD64'), patch.object(
                build_package.platform, 'python_version', return_value='3.12.7'):
            with self.assertRaisesRegex(PackageInputError, '^python_version_or_architecture$'):
                build_package.toolchain(manifest)
        with patch.object(build_package.platform, 'machine', return_value='ARM64'):
            with self.assertRaisesRegex(PackageInputError, '^python_version_or_architecture$'):
                build_package.toolchain(manifest)

    def test_zip_contents_are_independent_of_local_modification_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'test.txt'
            path.write_bytes(b'example')
            files = {'test.txt': hashlib.sha256(b'example').hexdigest()}
            first, second = root / 'first.zip', root / 'second.zip'
            build_package.archive_candidate(root, first, files)
            os.utime(path, (1_700_000_000, 1_700_000_000))
            build_package.archive_candidate(root, second, files)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            path.write_bytes(b'changed between scanning and packing')
            with self.assertRaisesRegex(PackageInputError, '^archive_check$'):
                build_package.archive_candidate(root, root / 'mismatch.zip', files)
