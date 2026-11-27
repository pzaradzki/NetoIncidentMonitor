import json
import tkinter as tk
import unittest
import ssl
from threading import Event
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from unittest.mock import Mock, patch

from neto_incident_monitor import release_check as checks
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import MainWindowPresentation, current_grab_path


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ReleaseCheckTests(unittest.TestCase):
    def wait_for(self, root, condition):
        deadline = monotonic() + 3
        while not condition() and monotonic() < deadline:
            root.update()
            sleep(0.01)
        self.assertTrue(condition(), 'Sprawdzanie aktualizacji nie zakończyło się w czasie próby.')

    def test_errors_distinguish_certificate_network_and_server_failures(self):
        self.assertIn('bezpiecznego', checks.failure_message(URLError(ssl.SSLCertVerificationError('certificate'))))
        self.assertIn('połączyć', checks.failure_message(URLError(TimeoutError())))
        self.assertIn('ograniczył', checks.failure_message(HTTPError(checks.API, 403, '', {'X-RateLimit-Remaining': '0'}, None)))
        self.assertIn('odrzucony', checks.failure_message(HTTPError(checks.API, 403, '', {}, None)))
        self.assertIn('Nie znaleziono', checks.failure_message(HTTPError(checks.API, 404, '', {}, None)))
        self.assertIn('HTTP 502', checks.failure_message(HTTPError(checks.API, 502, '', {}, None)))

    def test_version_comparison_and_validated_release_link(self):
        for tag, newer in [('v1.6.0', False), ('v1.5.9', False), ('v1.10.0', True), ('v2.0.0', True)]:
            with self.subTest(tag=tag), patch.object(checks, '__version__', '1.6.0'), patch.object(checks, 'urlopen') as fetch:
                fetch.return_value.__enter__.return_value.read.return_value = json.dumps({'tag_name': tag}).encode()
                self.assertEqual(checks.latest_release(), (newer, checks.RELEASES + tag))
                self.assertEqual(fetch.call_args.kwargs['timeout'], 15)
        for data in [{'tag_name': 'https://evil.test'}, {'tag_name': 'v2.0.0', 'prerelease': True}, {}]:
            with patch.object(checks, 'urlopen') as fetch:
                fetch.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
                with self.assertRaises(ValueError):
                    checks.latest_release()

    def test_rate_limit_uses_official_release_redirect(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = checks.RELEASES + 'v2.0.0'
        error = HTTPError(checks.API, 403, '', {'X-RateLimit-Remaining': '0'}, None)
        with patch.object(checks, 'urlopen', side_effect=[error, response]):
            self.assertEqual(checks.latest_release(), (True, checks.RELEASES + 'v2.0.0'))
        with patch.object(checks, 'urlopen', side_effect=HTTPError(checks.API, 403, '', {}, None)) as fetch:
            with self.assertRaises(HTTPError):
                checks.latest_release()
            self.assertEqual(fetch.call_count, 1)
        response.geturl.return_value = 'https://adeo.service-now.com/releases/tag/v2.0.0'
        with patch.object(checks, 'urlopen', return_value=response):
            with self.assertRaises(ValueError):
                checks.release_page_tag()

    def test_experimental_build_compares_against_stable_releases(self):
        with patch.object(checks, '__version__', '1.12.0-experimental.1'), patch.object(checks, 'urlopen') as fetch:
            response = fetch.return_value.__enter__.return_value
            for tag, newer in [('v1.11.2', False), ('v1.12.0', True)]:
                with self.subTest(tag=tag):
                    response.read.return_value = json.dumps({'tag_name': tag}).encode()
                    response.geturl.return_value = checks.RELEASES + tag
                    self.assertEqual(checks.latest_release(), (newer, checks.RELEASES + tag))
                    self.assertEqual(checks.release_page_tag(), (newer, checks.RELEASES + tag))
            response.read.return_value = b'{"tag_name":"v1.12.0-experimental.2"}'
            with self.assertRaises(ValueError):
                checks.latest_release()

    def test_result_buttons_open_only_on_user_click(self):
        root = tk.Tk()
        try:
            for newer, labels in [(False, ['Ok']), (True, ['Otwórz Github', 'Anuluj'])]:
                with patch.object(checks.webbrowser, 'open', return_value=True) as browser:
                    checks.show_result(root, newer, checks.RELEASES + 'v2.0.0')
                    dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                    buttons = [w for w in descendants(dialog) if isinstance(w, RoundedButton)]
                    self.assertEqual([w.text for w in buttons], labels)
                    browser.assert_not_called()
                    buttons[0].invoke()
                    if newer:
                        browser.assert_called_once_with(checks.RELEASES + 'v2.0.0')
            with patch.object(checks, 'latest_release', side_effect=OSError('offline')):
                button = RoundedButton(root, text='Sprawdź', command=lambda: None)
                checks.ReleaseCheck(root).check_updates(root, button)
                self.assertFalse(button.enabled)
                root.after(250, root.quit)
                root.mainloop()
                self.assertTrue(button.enabled)
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                self.assertIn('Nie udało', next(w.cget('text') for w in descendants(dialog) if w.winfo_class() == 'TLabel'))
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()

    def test_startup_update_is_visible_without_restoring_window_or_taking_grab(self):
        for state in ('normal', 'iconic', 'withdrawn'):
            with self.subTest(state=state):
                root = tk.Tk()
                try:
                    root.update()
                    if state == 'iconic':
                        root.iconify()
                    elif state == 'withdrawn':
                        root.withdraw()
                    login = tk.Toplevel(root)
                    login.title('Syntetyczne potwierdzenie logowania')
                    root.update()
                    login.grab_set()
                    checker = checks.ReleaseCheck(root)
                    url = checks.RELEASES + 'v2.0.0'
                    with patch.object(checks, 'latest_release', return_value=(True, url)) as lookup, \
                            patch.object(checks.webbrowser, 'open', return_value=True) as browser:
                        checker.schedule_startup()
                        self.wait_for(root, lambda: checker.dialog is not None and checker.dialog.winfo_viewable())
                        dialog = checker.dialog
                        self.assertEqual(root.state(), state)
                        self.assertEqual(str(dialog.transient()), str(root) if state == 'normal' else '')
                        self.assertNotIn(MainWindowPresentation(dialog).inspect().exposure, ('hidden', 'minimized'))
                        self.assertEqual(str(current_grab_path(root)), str(login))
                        browser.assert_not_called()
                        login.destroy()
                        actions = {w.text: w for w in descendants(dialog) if isinstance(w, RoundedButton)}
                        actions['Otwórz Github'].invoke()
                        browser.assert_called_once_with(url)
                        self.assertFalse(dialog.winfo_exists())
                        lookup.assert_called_once()
                finally:
                    root.destroy()

    def test_startup_up_to_date_is_silent_even_after_restoring_window(self):
        for hidden in (False, True):
            with self.subTest(hidden=hidden):
                root = tk.Tk()
                try:
                    if hidden:
                        root.withdraw()
                    root.update()
                    checker = checks.ReleaseCheck(root)
                    with patch.object(checks, 'latest_release', return_value=(False, None)) as fetch:
                        checker.check_updates()
                        self.wait_for(root, lambda: checker.results is None)
                        fetch.assert_called_once()
                    self.assertIsNone(checker.dialog)
                    self.assertIsNone(checker.deferred)
                    root.deiconify()
                    root.update()
                    self.assertIsNone(checker.dialog)
                finally:
                    root.destroy()

    def test_startup_error_waits_for_main_window(self):
        root = tk.Tk()
        root.withdraw()
        try:
            checker = checks.ReleaseCheck(root)
            with patch.object(checks, 'latest_release', side_effect=OSError('offline')):
                checker.check_updates()
                self.wait_for(root, lambda: checker.deferred is not None)
            self.assertIsNone(checker.dialog)
            root.deiconify()
            self.wait_for(root, lambda: checker.dialog is not None and checker.dialog.winfo_viewable())
            labels = [w.cget('text') for w in descendants(checker.dialog) if w.winfo_class() == 'TLabel']
            self.assertIn('Nie udało się połączyć z GitHubem.', labels[0])
            self.assertIsNone(checker.deferred)
        finally:
            root.destroy()

    def test_manual_joins_startup_and_next_click_starts_fresh(self):
        root = tk.Tk()
        finish = Event()
        try:
            settings = tk.Toplevel(root)
            checker = checks.ReleaseCheck(root)
            button = RoundedButton(settings, text='Sprawdź', command=lambda: checker.check_updates(settings, button))
            button.pack()
            root.update()

            def lookup(**_):
                if not finish.wait(timeout=3):
                    raise TimeoutError()
                return False, None

            with patch.object(checks, 'latest_release', side_effect=lookup) as fetch:
                checker.check_updates()
                button.invoke()
                self.assertFalse(button.enabled)
                finish.set()
                self.wait_for(root, lambda: checker.dialog is not None)
                first = checker.dialog
                self.assertIs(first.master, settings)
                labels = [w.cget('text') for w in descendants(first) if w.winfo_class() == 'TLabel']
                self.assertIn('Najnowsza wersja aplikacji jest zainstalowana', labels)
                self.assertTrue(button.enabled)
                fetch.assert_called_once()
                first.destroy()
                button.invoke()
                self.wait_for(root, lambda: checker.dialog is not first)
                self.assertIs(checker.dialog.master, settings)
                self.assertTrue(button.enabled)
                self.assertEqual(fetch.call_count, 2)
        finally:
            finish.set()
            root.destroy()

    def test_close_settings_detaches_and_shutdown_discards_late_results(self):
        root = tk.Tk()
        finish, finished = Event(), Event()
        try:
            settings = tk.Toplevel(root)
            button = RoundedButton(settings, text='Sprawdź', command=lambda: None)
            checker = checks.ReleaseCheck(root)

            def delayed(**_):
                try:
                    if not finish.wait(timeout=3):
                        raise TimeoutError()
                    return True, checks.RELEASES + 'v2.0.0'
                finally:
                    finished.set()

            with patch.object(checks, 'latest_release', side_effect=delayed), \
                    self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
                checker.check_updates()
                checker.check_updates(settings, button)
                self.assertFalse(button.enabled)
                checker.detach(settings)
                self.assertTrue(button.enabled)
                settings.destroy()
                timer = checker.poll_timer
                checker.close()
                finish.set()
                self.assertTrue(finished.wait(timeout=3))
                root.update()
            self.assertIsNone(checker.dialog)
            self.assertNotIn(timer, root.tk.splitlist(root.tk.call('after', 'info')))
            events = [json.loads(e.getMessage()) for e in logs.records if '"event": "release_check"' in e.getMessage()]
            self.assertEqual([e['outcome'] for e in events], ['started', 'cancelled'])
            self.assertEqual(events[0]['read_id'], events[1]['read_id'])
        finally:
            finish.set()
            root.destroy()

    def test_release_diagnostics_correlate_http_fallback_and_hide_response_details(self):
        root = tk.Tk()
        try:
            rate_limit = HTTPError(checks.API, 403, 'Synthetic secret', {'X-RateLimit-Remaining': '0'}, None)
            refused = HTTPError('https://example.test/synthetic-secret', 502, 'Synthetic secret', {}, None)
            with patch.object(checks, 'urlopen', side_effect=[rate_limit, refused]) as fetch, \
                    self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
                checker = checks.ReleaseCheck(root)
                checker.check_updates()
                self.wait_for(root, lambda: checker.results is None)
            events = [json.loads(record.getMessage()) for record in logs.records]
            start, end = (event for event in events if event['event'] == 'release_check')
            self.assertEqual((start['read_id'], start['run_id']), (end['read_id'], end['run_id']))
            self.assertEqual((start['release_trigger'], start['outcome']), ('startup', 'started'))
            self.assertEqual((end['outcome'], end['release_error'], end['http_status'], end['release_fallback_status']),
                             ('error', 'http', 502, 403))
            self.assertGreaterEqual(end['duration_ms'], 0)
            self.assertEqual(fetch.call_count, 2)
            self.assertNotIn('synthetic', '\n'.join(logs.output).lower())
        finally:
            root.destroy()
