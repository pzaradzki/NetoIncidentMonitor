import queue
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.threatened import KEYS, THREATENED_URL
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled

class ThreatenedPresentationTests(unittest.TestCase):
    def test_sidebar_activity_badge_fits_with_warning_icons(self):
        from neto_incident_monitor.widgets import ThreatenedIncidentsButton

        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        button = ThreatenedIncidentsButton(root)
        button.redraw()
        label = next(item for item in button.find_all() if button.type(item) == 'text')
        left, _, right, _ = button.bbox(label)
        label_width = right - left
        button.set_alert(True)
        button.set_updating(True)

        for available, stacked in ((label_width + 170, False), (label_width + 60, True)):
            with self.subTest(stacked=stacked), patch.object(button, 'winfo_width', return_value=available):
                button.redraw()
                label, badge = [button.bbox(item) for item in button.find_all() if button.type(item) == 'text']
                self.assertTrue(all(0 <= left < right <= available for left, _, right, _ in (label, badge)))
                if stacked:
                    self.assertLessEqual(label[3], badge[1])
                else:
                    self.assertLess(label[2], badge[0])

    def test_tiles_have_dark_content_before_first_hover_and_after_remapping(self):
        from neto_incident_monitor.threatened_ui import RiskTile, CATEGORIES
        from neto_incident_monitor.theme import SURFACE
        root = tk.Tk()
        self.addCleanup(root.destroy)
        # A light Tk default must never leak through a newly constructed card.
        root.option_add('*Label.background', '#f0f0f0')
        for title, description, accent in CATEGORIES:
            tile = RiskTile(root, title, description, accent)
            tile.pack()
            tile.value_label.configure(text='0')
            root.update_idletasks()
            tile.pack_forget()
            tile.pack()
            root.update_idletasks()
            self.assertIsNone(tile.timer)
            for child in (tile, *tile.labels):
                self.assertEqual(child.cget('background'), SURFACE)
                self.assertEqual(child.cget('cursor'), 'arrow')
                self.assertFalse(child.bind('<ButtonRelease-1>'))
            self.assertEqual(int(tile.cget('takefocus')), 0)

    def test_hover_animates_risk_tile_and_restores_its_colors(self):
        from neto_incident_monitor.threatened_ui import RiskTile, CATEGORIES
        from neto_incident_monitor.theme import SURFACE
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        title, description, accent = CATEGORIES[0]
        tile = RiskTile(root, title, description, accent)
        tile.pack()
        root.update_idletasks()
        outside = tk.Event()
        outside.x_root = tile.winfo_rootx() - 1
        outside.y_root = tile.winfo_rooty()

        with patch('neto_incident_monitor.widgets.monotonic', side_effect=(0, 0, 0.15, 1, 1, 1.15)):
            tile.enter(None)
            self.assertEqual(tile.cget('highlightbackground'), accent)
            self.assertIsNotNone(tile.timer)
            root.tk.call('after', 25)
            root.update()
            self.assertEqual(tile.cget('background'), '#303947')

            tile.leave(outside)
            self.assertFalse(tile.hovered)
            self.assertIsNotNone(tile.timer)
            root.tk.call('after', 25)
            root.update()
            self.assertTrue(all(widget.cget('background') == SURFACE for widget in (tile, *tile.labels)))

    def ready_app(self):
        root = tk.Tk()
        root.withdraw()
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(root.destroy)
        with patch('neto_incident_monitor.config_io.read_json', return_value={}), \
                patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
            app = App(root, history_path=folder / 'history.json', apply_startup=False, enable_tray=False)
        self.addCleanup(app.teams_sender.stop)
        self.addCleanup(app.google_chat_sender.stop)
        self.addCleanup(app.alert_writer.shutdown)
        self.addCleanup(app.history_writer.shutdown)
        app.session.ready_once = True
        app.window_restoring = False
        app.handle_session_event('session_ready', None)
        app.session.log = Mock()
        return app

    def start_read(self, app):
        part, source = app.session.next_part(None)
        self.assertEqual((part.scope, source), ('threatened', 'manual'))
        token = object()
        app.events.put(('session_part_started', (token, part)))
        prepared = {'part': part, 'stop': app.session.closed, 'done': threading.Event(), 'value': None}
        app.events.put(('session_prepare_read', prepared))
        app.drain()
        self.assertEqual(app.threatened_view.request_id, prepared['value'])
        return prepared['value'], token, part

    def finish_read(self, app, request, token, part):
        app.session.work.complete_part(part, manual=True, success=True)
        app.session.finish_manual_job(None)
        app.events.put(('session_part_finished', token))
        app.events.put(('threatened_finished', request))
        app.drain()

    def test_simulated_incident_does_not_cancel_pending_read_and_real_result_replaces_it(self):
        app = self.ready_app()
        panel = app.threatened_view
        panel.apply_result(panel.request_id, dict.fromkeys(KEYS, 0), 100)
        self.assertTrue(app.request_refresh('threatened'))
        request, token, part = self.start_read(app)
        filters = list(app.filters)
        with patch('neto_incident_monitor.threatened_ui.random.choice', return_value='P4'):
            self.assertEqual(panel.simulate_read(), 'break')
        self.assertEqual(panel.values['P4'], 1)
        self.assertEqual(sum(panel.values.values()), 1)
        self.assertTrue(panel.simulated)
        self.assertEqual(panel.status_pill.status_text, 'Dane testowe')
        self.assertTrue(app.threatened_incidents_button.alert)
        self.assertTrue(panel.pending)
        self.assertEqual(panel.request_id, request)
        self.assertEqual(panel.last_read, 100)
        self.assertFalse(panel.refresh_button.enabled)
        self.assertEqual(app.filters, filters)
        panel.apply_result(request, None, None)
        self.assertTrue(panel.simulated)
        self.assertIn('dane testowe', panel.message.get())
        empty = dict.fromkeys(KEYS, 0)
        app.events.put(('threatened_result', (request, empty, 200)))
        app.events.put(('threatened_details', (request, {}, 20)))
        self.finish_read(app, request, token, part)
        self.assertFalse(panel.simulated)
        self.assertFalse(app.threatened_incidents_button.alert)
        self.assertEqual([tile.value_label.cget('text') for tile in panel.tiles], ['0'] * 6)
        self.assertEqual(panel.last_full_read, 200)
        self.assertTrue(panel.refresh_button.enabled)
        self.assertTrue(app.request_refresh('threatened'))
        request, token, part = self.start_read(app)
        panel.apply_result(request, empty, 300)
        panel.apply_details(request, None)
        self.finish_read(app, request, token, part)
        self.assertEqual(panel.last_full_read, 200)
        self.assertIn('Zachowano ostatnią', panel.message.get())

    def test_request_dedup_stale_events_stop_and_conservative_alarm(self):
        app = self.ready_app()
        panel = app.threatened_view
        button = app.threatened_incidents_button
        self.assertFalse(button.alert)
        self.assertFalse(button.healthy)
        self.assertEqual([tile.value_label.cget('text') for tile in panel.tiles], ['—'] * 6)
        app.request_refresh('threatened')
        app.request_refresh('threatened')
        self.assertEqual(len(app.session.work.pending), 1)
        self.assertFalse(panel.refresh_button.enabled)
        request, token, part = self.start_read(app)
        self.assertTrue(button.updating)
        values = dict.fromkeys(KEYS, 0)
        values['P2'] = 3
        panel.apply_result(request, values, 100)
        panel.apply_details(request, {})
        for bad in (None, {}, {'P1': 0}, dict.fromkeys(KEYS, False)):
            panel.apply_result(request, bad, None)
            self.assertEqual(panel.values, values)
            self.assertEqual(panel.last_full_read, 100)
            self.assertTrue(button.alert)
        app.cycle_active = True
        app.session.start_cycle([], {'inc': 60, 'task': 120})
        app.stop_monitoring()
        self.assertFalse(app.cycle_active)
        self.assertFalse(app.session.closed.is_set())
        self.assertTrue(button.updating)
        empty = dict.fromkeys(KEYS, 0)
        panel.apply_result(request - 1, empty, 200)
        self.assertTrue(button.alert)
        panel.apply_result(request, empty, 300)
        panel.apply_details(request, {})
        self.finish_read(app, request, token, part)
        self.assertFalse(button.updating)
        self.assertFalse(button.alert)
        self.assertTrue(button.healthy)
        panel.apply_result(request, values, 400)
        self.assertEqual(panel.last_full_read, 300)
        self.assertFalse(button.alert)


class ThreatenedWorkerTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.stop, app.events = threading.Event(), queue.Queue()
        app.browser_runtime = Mock()
        app.session = Mock(threatened_delay_reason='idle')
        app.session.authenticate.return_value = True
        app.session.finish_threatened_read.side_effect = lambda request: app.events.put(('threatened_finished', request))
        app.history = Mock()
        app.history.commit_threatened.return_value = ({}, 0)
        app.submit_alert_delivery = Mock()
        return app

    def test_session_recovery_retries_once_and_emits_complete_result(self):
        app = self.app()
        values = dict.fromkeys(KEYS, 0)
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.threatened_api.read_threats', side_effect=[AuthenticationRequired(), (values, {})]) as read:
            app.read_threatened_request(Mock(), request=4, stop=app.stop)
        self.assertEqual(read.call_count, 2)
        app.session.authenticate.assert_called_once()
        states = [value for kind, value in app.events.queue if kind == 'threatened_state']
        self.assertEqual(states, [(4, 'W trakcie aktualizacji'), (4, 'Oczekuje'), (4, 'Ponawianie odczytu')])
        results = [v for k,v in app.events.queue if k == 'threatened_result']
        self.assertEqual(results[0][:2], (4, values))
        app.history.commit_threatened.assert_called_once()
        app.submit_alert_delivery.assert_not_called()
        app.browser_runtime.set_activity.assert_not_called()

    def test_errors_do_not_emit_fake_values_and_stop_does_not_emit_error(self):
        for error in (ValueError('fixture'), Cancelled()):
            with self.subTest(error=type(error).__name__):
                app = self.app()
                with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                        patch('neto_incident_monitor.threatened_api.read_threats', side_effect=error):
                    app.read_threatened_request(Mock(), request=4, stop=app.stop)
                results = [v for k,v in app.events.queue if k == 'threatened_result']
                self.assertEqual(results, [] if isinstance(error, Cancelled) else [(4, None, None)])
                self.assertIn(('threatened_finished', 4), list(app.events.queue))
                app.history.commit_threatened.assert_not_called()
