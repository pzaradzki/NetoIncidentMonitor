import queue
import threading
import tkinter as tk
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.dashboard_progress import (
    DashboardProgress, DashboardProgressBar, STEPS, completed_step, progress_steps,
)
from neto_incident_monitor.pagination import Cancelled


class DashboardProgressTests(unittest.TestCase):
    def test_main_window_bar_receives_only_current_request_events(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder, \
                    patch('neto_incident_monitor.app.read_json', return_value={}), \
                    patch('neto_incident_monitor.tray.Tray'):
                app = App(root, history_path=Path(folder) / 'history.json', apply_startup=False)
                app.worker = Mock()
                app.worker.is_alive.return_value = True
                app.dashboard_view.request_refresh()
                request_id = app.dashboard_view.request_id
                app.events.put(('dashboard_progress', (request_id, 67, 'Wstrzymane L1', 'running')))
                app.drain()
                self.assertEqual(app.dashboard_progress.percent, 67)
                app.events.put(('dashboard_progress', (request_id, 100, 'Gotowe', 'complete')))
                app.drain()
                self.assertIsNotNone(app.dashboard_progress.hide_timer)
                app.dashboard_view.request_refresh()
                self.assertEqual(app.dashboard_progress.percent, 0)
                app.events.put(('dashboard_progress', (request_id, 100, 'Stary odczyt', 'complete')))
                app.drain()
                self.assertEqual(app.dashboard_progress.percent, 0)
                self.assertIsNone(app.dashboard_progress.hide_timer)
        finally:
            root.destroy()

    def test_only_completed_steps_advance_and_retries_never_move_backwards(self):
        updates = []
        progress = DashboardProgress(lambda *value: updates.append(value))
        with progress_steps(progress, 'Dashboard SLA'):
            completed_step('navigate')
            completed_step('navigate')  # Retry: same completed step counted once.
            completed_step('unknown')
        self.assertEqual(len(updates), 2)
        for section in STEPS:
            progress.section_done(section)
        self.assertEqual(progress.percent, 99)
        progress.waiting()
        progress.finish(True)
        self.assertEqual(updates[-1][0], 100)
        self.assertEqual(updates[-1][2], 'complete')
        self.assertEqual([v[0] for v in updates], sorted(v[0] for v in updates))

    def test_worker_reports_full_success_partial_failure_and_cancellation(self):
        for mode in ('complete', 'partial', 'error', 'cancelled'):
            with self.subTest(mode=mode):
                app = App.__new__(App)
                app.stop, app.events, app.dashboard_requests = threading.Event(), queue.Queue(), queue.Queue()
                app.dashboard_requests.put((7, 2026, 10))
                failure = ValueError('fixture') if mode == 'error' else Cancelled() if mode == 'cancelled' else None
                with patch('neto_incident_monitor.dashboard.read_dashboard', return_value=dict.fromkeys(TITLES, 0), side_effect=failure), \
                        patch('neto_incident_monitor.dashboard.read_held_dashboard', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                        patch('neto_incident_monitor.dashboard.read_requests_dashboard',
                              return_value=dict.fromkeys(REQUEST_TITLES[:-1] if mode == 'partial' else REQUEST_TITLES, 0)):
                    app.read_dashboard_request(Mock())
                updates = [v for k, v in app.events.queue if k == 'dashboard_progress']
                self.assertTrue(all(v[0] == 7 for v in updates))
                if mode == 'complete':
                    self.assertEqual((updates[-1][1], updates[-1][3]), (100, 'complete'))
                else:
                    self.assertLess(updates[-1][1], 100)
                    self.assertEqual(updates[-1][3], 'warning')

    def test_bar_hides_three_seconds_after_complete_and_old_timer_cannot_hide_new_read(self):
        root = tk.Tk()
        root.withdraw()
        try:
            bar = DashboardProgressBar(root)
            bar.start(1)
            self.assertEqual(bar.winfo_manager(), 'pack')
            with patch.object(bar, 'after', return_value='test-timer') as after, \
                    patch.object(bar, 'after_cancel') as cancel:
                bar.apply(1, 100, 'Gotowe', 'complete')
                self.assertEqual(after.call_args.args[0], 3000)
                old_dismiss = after.call_args.args[1]
                self.assertEqual(bar.winfo_manager(), 'pack')
                bar.start(2)
                cancel.assert_called_once_with('test-timer')
                old_dismiss()
                self.assertEqual(bar.winfo_manager(), 'pack')
                bar.apply(1, 100, 'Stary wynik', 'complete')
                self.assertEqual(bar.percent, 0)
                bar.apply(2, 100, 'Gotowe', 'complete')
                after.call_args.args[1]()
                self.assertEqual(bar.winfo_manager(), '')
                bar.start(3)
                bar.apply(3, 40, 'Błąd', 'warning')
                self.assertEqual(bar.winfo_manager(), 'pack')
                self.assertIsNone(bar.hide_timer)
                bar.hide()
                self.assertEqual(bar.winfo_manager(), '')
            bar.destroy()
        finally:
            root.destroy()
