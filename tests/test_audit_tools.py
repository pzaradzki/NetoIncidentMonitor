import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


class AuditToolsTests(unittest.TestCase):
    def test_preview_completes_with_synthetic_data_and_isolated_output(self):
        from tools import preview_ui
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'preview.png'
            with patch.object(preview_ui, 'OUTPUT', output, create=True), \
                    patch.object(preview_ui.ImageGrab, 'grab', return_value=Image.new('RGB', (20, 20))):
                preview_ui.main()
            self.assertTrue(output.is_file())

    def test_runner_fails_on_callback_error_without_secret_in_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result = subprocess.run([sys.executable, '-B', '-m', 'tools.run_regression', '--child',
                'tests.runner_fixture', str(folder/'result.json'), str(folder/'data')],
                capture_output=True, text=True, timeout=30,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(result.returncode, 1)
            summary = (folder/'result.json').read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE_SECRET', summary)
            self.assertEqual(json.loads(summary)['callback_errors'], ['RuntimeError'])


if __name__ == '__main__':
    unittest.main()
