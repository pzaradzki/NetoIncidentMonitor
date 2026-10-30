import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.history import History
from neto_incident_monitor.browser_policy import BrowserRuntime, BrowserOptions


class HistoryBatchTests(unittest.TestCase):
    def test_bulk_arrivals_commit_once_and_keep_filter_specific_read_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            history = History(Path(folder) / 'history.json')
            rows = [dict(number=f'INC{i:07d}', summary='fixture') for i in range(528)]
            with patch.object(history, '_commit', wraps=history._commit) as commit:
                self.assertEqual(len(history.add_many(rows, 'A', 'a', reappeared=True)), 528)
                commit.assert_called_once()
            history.mark_read([rows[0]['number']], 'a')
            history.add_many(rows[:1], 'B', 'b', reappeared=True)
            self.assertTrue(history.snapshot('a')[rows[0]['number']]['read'])
            self.assertFalse(history.snapshot('b')[rows[0]['number']]['read'])
            self.assertEqual(len(History(history.path).snapshot('a')), 528)
            with patch.object(history, '_commit', side_effect=OSError('fixture')):
                with self.assertRaises(OSError):
                    history.add_many([dict(number='INC9999999')], 'A', 'a')
            self.assertNotIn('INC9999999', history.snapshot('a'))

    def test_ui_snapshot_does_not_wait_for_writer_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            history = History(Path(folder) / 'history.json')
            history.add(dict(number='INC1'), 'A', 'a')
            done = threading.Event()
            result = []
            with history.lock:
                reader = threading.Thread(target=lambda: (result.append(history.snapshot('a')), done.set()))
                reader.start()
                completed = done.wait(1)
            reader.join(timeout=2)
            self.assertTrue(completed)
            self.assertIn('INC1', result[0])

    def test_show_browser_posts_native_request_without_playwright_tick(self):
        page = Mock()
        runtime = BrowserRuntime(page, BrowserOptions({}), Mock(), Mock(), Mock(), Mock())
        runtime.window = Mock()
        runtime.request_show()
        runtime.window.reveal.assert_called_once_with()
        self.assertEqual(runtime.commands.get_nowait(), 'show')
        page.bring_to_front.assert_not_called()
        runtime.window.show.assert_not_called()
