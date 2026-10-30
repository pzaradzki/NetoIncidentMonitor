import queue
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.app import App
from neto_incident_monitor.threatened import KEYS, THREATENED_URL, read_threatened_dashboard
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled

TITLES = ('P1 – < 1 h / po terminie', 'P2 – < 2 h / po terminie',
          'P3 – < 4 h / po terminie', 'P4 – < 1 dzień / po terminie',
          'P5 – < 2 dni / po terminie', 'Podjęcie – < 5 min / po terminie')


def document(values):
    return ''.join('<div class="grid-stack-item-content"><h2>' + title.replace('<', '&lt;') + '</h2>'
                   '<now-score-basic><span class="now-score-value">' + str(value) + '</span></now-score-basic></div>'
                   for title, value in zip(TITLES, values))


class ThreatenedReaderTests(unittest.TestCase):
    def test_six_scores_ignore_additional_table_and_hidden_duplicate(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                html = document(range(6)) + '<div hidden>' + document([999] * 6) + '</div>'
                html += '<div class="grid-stack-item-content"><h2>Inna tabela</h2><span>999</span></div>'
                page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
                with patch('neto_incident_monitor.threatened.activate_dashboard_widgets', side_effect=AssertionError('Ready counters must not scroll')):
                    self.assertEqual(read_threatened_dashboard(page, threading.Event()), dict(zip(KEYS, range(6))))
            finally:
                browser.close()

    def test_missing_invalid_and_duplicate_score_never_return_partial_or_zero(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                for html in (document([0] * 5), document([0, 0, '...', 0, 0, 0]),
                             document([0] * 6) + document([0])):
                    with self.subTest(html_length=len(html)), patch('neto_incident_monitor.threatened.READ_TIMEOUT', 0.1):
                        page.route('**/*', lambda r, *, html=html: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
                        with self.assertRaises(ValueError):
                            read_threatened_dashboard(page, threading.Event())
                        page.unroute('**/*')
            finally:
                browser.close()

    def test_cancelled_before_navigation(self):
        stop = threading.Event()
        stop.set()
        page = Mock()
        with self.assertRaises(Cancelled):
            read_threatened_dashboard(page, stop)
        page.goto.assert_not_called()

    def test_card_replacement_timeout_retries_preparation_without_reloading(self):
        from neto_incident_monitor.dashboard import diagnostic_steps
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
        import json
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                loads = []
                def serve(route):
                    loads.append(True)
                    route.fulfill(body='<div class="grid-stack-item-content">Loading</div>', content_type='text/html; charset=utf-8')
                page.route('**/*', serve)
                attempts = []
                def prepare(page, stop):
                    attempts.append(True)
                    if len(attempts) == 1:
                        raise TimeoutError('Synthetic replaced widget')
                    page.set_content(document([0] * 6))
                with patch('neto_incident_monitor.threatened.activate_dashboard_widgets', side_effect=prepare), \
                        self.assertLogs(_logger, level='INFO') as logs, diagnostic_steps(LoginDiagnostics(source='dashboard', section='threatened')):
                    result = read_threatened_dashboard(page, threading.Event())
                self.assertEqual(result, dict.fromkeys(KEYS, 0))
                self.assertEqual(len(attempts), 2)
                self.assertEqual(len(loads), 1)
                events = [json.loads(r.getMessage()) for r in logs.records]
                self.assertEqual(sum(r['event'] == 'dashboard_widgets_retry' for r in events), 1)
                self.assertTrue(any(r.get('risk_tile') == 'P1' and r.get('tile_state') == 'ready' for r in events))
                self.assertNotIn('Synthetic replaced widget', str(logs.records))
            finally:
                browser.close()

    def test_lazy_widgets_are_rendered_before_reading(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 800, 'height': 500})
                cards = ''.join(f'<div class="grid-stack-item-content" data-id="{i}" style="height:220px;margin-top:500px"></div>' for i in range(6))
                import json
                html = cards + '<script>const titles=' + json.dumps(TITLES) + ''';
                const observer=new IntersectionObserver(entries=>{for(const e of entries) if(e.isIntersecting){
                  const card=e.target; const i=+card.dataset.id; const h=document.createElement('h2');
                  h.textContent=titles[i]; card.appendChild(h); const s=document.createElement('now-score-basic');
                  card.appendChild(s); s.attachShadow({mode:'open'}).innerHTML='<span class="now-score-value">0</span>';
                  observer.unobserve(card); }});
                document.querySelectorAll('.grid-stack-item-content').forEach(c=>observer.observe(c));</script>'''
                page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
                self.assertEqual(read_threatened_dashboard(page, threading.Event()), dict.fromkeys(KEYS, 0))
            finally:
                browser.close()


class ThreatenedPresentationTests(unittest.TestCase):
    def test_simulated_incident_does_not_cancel_pending_read_and_real_result_replaces_it(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder, patch('neto_incident_monitor.app.read_json', return_value={}), \
                    patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                app = App(root, history_path=Path(folder)/'history.json', apply_startup=False, enable_tray=False)
            panel = app.threatened_view
            panel.apply_result(panel.request_id, dict.fromkeys(KEYS, 0), 100)
            app.worker = Mock()
            app.worker.is_alive.return_value = True
            app.schedule = Mock()
            panel.set_monitoring(True)
            panel.request_refresh()
            request = panel.request_id
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
            self.assertTrue(app.threatened_incidents_button.alert)
            panel.apply_result(request, dict.fromkeys(KEYS, 0), 200)
            self.assertFalse(panel.simulated)
            self.assertFalse(app.threatened_incidents_button.alert)
            self.assertEqual([t.value_label.cget('text') for t in panel.tiles], ['0'] * 6)
            self.assertEqual(panel.last_read, 200)
        finally:
            root.destroy()

    def test_startup_request_is_queued_before_worker_exists_and_does_not_wake_filters(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder, patch('neto_incident_monitor.app.read_json', return_value={}), \
                    patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                app = App(root, history_path=Path(folder)/'history.json', apply_startup=False, enable_tray=False)
            app.schedule = Mock()
            self.assertIsNone(app.worker)
            app.threatened_view.request_refresh(automatic=True)
            self.assertEqual(app.threatened_requests.qsize(), 1)
            self.assertTrue(app.threatened_view.pending)
            self.assertFalse(app.threatened_view.refresh_button.enabled)
            app.schedule.request.assert_not_called()
            self.assertIn('przed dashboardem i filtrami', app.threatened_view.message.get())
        finally:
            root.destroy()

    def test_request_dedup_stale_events_stop_and_conservative_alarm(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder, patch('neto_incident_monitor.app.read_json', return_value={}), \
                    patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                app = App(root, history_path=Path(folder)/'history.json', apply_startup=False, enable_tray=False)
            panel = app.threatened_view
            self.assertFalse(app.threatened_incidents_button.alert)
            self.assertFalse(app.threatened_incidents_button.healthy)
            self.assertEqual([t.value_label.cget('text') for t in panel.tiles], ['—'] * 6)
            app.worker = Mock()
            app.worker.is_alive.return_value = True
            app.schedule = Mock()
            panel.set_monitoring(True)
            panel.request_refresh()
            panel.request_refresh()
            self.assertEqual(app.threatened_requests.qsize(), 1)
            self.assertFalse(panel.refresh_button.enabled)
            request = panel.request_id
            values = dict.fromkeys(KEYS, 0)
            values['P2'] = 3
            app.refresh_coordinator().finish()
            panel.apply_result(request, values, 100)
            self.assertTrue(app.threatened_incidents_button.alert)
            self.assertTrue(panel.refresh_button.enabled)
            for bad in (None, {}, {'P1': 0}, dict.fromkeys(KEYS, False)):
                panel.apply_result(request, bad, None)
                self.assertEqual(panel.values, values)
                self.assertEqual(panel.last_read, 100)
                self.assertTrue(app.threatened_incidents_button.alert)
            panel.apply_result(request - 1, dict.fromkeys(KEYS, 0), 200)
            self.assertTrue(app.threatened_incidents_button.alert)
            panel.apply_result(request, dict.fromkeys(KEYS, 0), 300)
            self.assertFalse(app.threatened_incidents_button.alert)
            self.assertTrue(app.threatened_incidents_button.healthy)
            panel.apply_result(request, None, None)
            self.assertFalse(app.threatened_incidents_button.healthy)
            self.assertFalse(app.threatened_incidents_button.alert)
            panel.apply_result(request, dict.fromkeys(KEYS, 0), 300)
            self.assertTrue(app.threatened_incidents_button.healthy)
            panel.set_monitoring(False)
            self.assertFalse(app.threatened_incidents_button.healthy)
            self.assertFalse(panel.refresh_button.enabled)
            panel.apply_result(request, values, 400)
            self.assertFalse(app.threatened_incidents_button.alert)
        finally:
            root.destroy()


class ThreatenedWorkerTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.stop, app.events, app.threatened_requests = threading.Event(), queue.Queue(), queue.Queue()
        app.threatened_requests.put(4)
        app.browser_runtime = Mock()
        app.monitor_settings = {'urls': ['https://adeo.service-now.com/incident_list.do']}
        app.restore_login = Mock(return_value=True)
        return app

    def test_session_recovery_retries_once_and_emits_complete_result(self):
        app = self.app()
        values = dict.fromkeys(KEYS, 0)
        with patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=[AuthenticationRequired(), values]) as read:
            app.read_threatened_request(Mock())
        self.assertEqual(read.call_count, 2)
        app.restore_login.assert_called_once()
        results = [v for k,v in app.events.queue if k == 'threatened_result']
        self.assertEqual(results[0][:2], (4, values))
        app.browser_runtime.set_activity.assert_called_with('filters')

    def test_startup_read_runs_after_login_before_dashboard_and_filters_only_once(self):
        from neto_incident_monitor.history import History
        with tempfile.TemporaryDirectory() as folder:
            app = self.app()
            url = app.monitor_settings['urls'][0]
            app.filters = [{'name': 'Test', 'url': url}]
            app.disabled_filter_urls = frozenset()
            app.schedule = Mock()
            app.schedule.woken_by_request = False
            app.history = History(Path(folder)/'history.json')
            settings = {'urls': [url], 'filters': app.filters, 'interval': 60, 'task_interval': 120}
            page = Mock(url=url)
            page.is_closed.return_value = False
            context = Mock(pages=[page])
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            order = []
            app.restore_login.side_effect = lambda *args: order.append('login') or True
            app.read_dashboard_request = Mock(side_effect=lambda page: order.append('dashboard'))
            def threats(*args):
                order.append('threatened')
                return dict.fromkeys(KEYS, 0)
            def filters(*args, **kwargs):
                order.append('filter')
                return {}, 1
            with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                    patch('neto_incident_monitor.browser_window.BrowserWindow'), \
                    patch('neto_incident_monitor.app.STATE', Path(folder)/'seen.json'), \
                    patch('neto_incident_monitor.app.navigate'), \
                    patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=threats), \
                    patch('neto_incident_monitor.app.read_all', side_effect=filters), \
                    patch('neto_incident_monitor.app.wait_for_browser_cycle', side_effect=[False, True]):
                app.monitor(settings)
            self.assertEqual(order[:4], ['login', 'threatened', 'dashboard', 'filter'])
            self.assertEqual(order.count('threatened'), 1)
            self.assertEqual(order.count('dashboard'), 2)

    def test_errors_do_not_emit_fake_values_and_stop_does_not_emit_error(self):
        for error in (ValueError('fixture'), Cancelled()):
            with self.subTest(error=type(error).__name__):
                app = self.app()
                with patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=error):
                    app.read_threatened_request(Mock())
                results = [v for k,v in app.events.queue if k == 'threatened_result']
                self.assertEqual(results, [] if isinstance(error, Cancelled) else [(4, None, None)])
                self.assertIn(('threatened_finished', 4), list(app.events.queue))
