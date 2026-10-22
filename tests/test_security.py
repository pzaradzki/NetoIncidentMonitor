import unittest
from unittest.mock import Mock
from urllib.parse import quote

from neto_incident_monitor.service_now_urls import normalize_list_url, safe_record_url
from neto_incident_monitor.app import load_filters, navigate, collect
from neto_incident_monitor.teams_notifications import payload
from neto_incident_monitor.google_chat_notifications import payloads

BASE = 'https://adeo.service-now.com'


class SecurityTests(unittest.TestCase):
    def test_saved_invalid_filter_is_preserved_disabled_without_blocking_ui(self):
        import tempfile
        import tkinter as tk
        from pathlib import Path
        from unittest.mock import patch
        from neto_incident_monitor.app import App
        settings = {'filters': [{'name': 'Old', 'url': 'https://evil.test/admin'},
                                {'name': 'Valid', 'url': BASE + '/incident_list.do'}]}
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder, patch('neto_incident_monitor.app.read_json', return_value=settings):
                app = App(root, history_path=Path(folder)/'history.json', enable_tray=False, apply_startup=False)
            root.update()
            self.assertFalse(app.filters[0]['enabled'])
            self.assertEqual(app.filters[0]['url'], 'https://evil.test/admin')
            self.assertIn('1', app.status.get())
            with patch('neto_incident_monitor.app.messagebox.showerror') as error:
                app.toggle_filter('0')
                error.assert_called_once()
            self.assertFalse(app.filters[0]['enabled'])
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()

    def test_list_policy_rejects_untrusted_inputs_at_config_and_navigation(self):
        bad = [
            'https://attacker.invalid/incident_list.do', 'https://localhost/incident_list.do',
            'https://127.0.0.1/incident_list.do', 'https://10.0.0.1/incident_list.do',
            'https://[::1]/incident_list.do', 'http://adeo.service-now.com/incident_list.do',
            BASE + ':8443/incident_list.do', BASE + ':bad/incident_list.do',
            BASE + '/admin', BASE + '/incident_list.do#fragment', BASE + '/incident_list.do#',
            BASE.replace('https://', 'https://:secret@') + '/incident_list.do',
            BASE.replace('https://', 'https://@') + '/incident_list.do',
            BASE + '.evil.test/incident_list.do', BASE + '/incident_list.do;other',
            BASE + '/incident_list.do?x=%0d%0aHeader', BASE + '/incident_list.do\n',
            BASE + '/now/nav/ui/classic/params/target/' + quote('https://attacker.invalid/incident_list.do', safe=''),
            BASE + '/now/nav/ui/classic/params/target/' + quote('incident_list.do#fragment', safe=''),
        ]
        for value in bad:
            with self.subTest(value=value):
                page = Mock()
                with self.assertRaises(ValueError):
                    navigate(page, value)
                page.goto.assert_not_called()
                with self.assertRaises(ValueError):
                    load_filters({'filters': [{'name': 'Filter', 'url': value}]})
        for path in ('incident_list.do', 'sc_task_list.do'):
            target = path + '?sysparm_query=locationLIKESTORE%20003%5Estate%3D1'
            self.assertEqual(normalize_list_url(BASE + ':443/' + target), BASE + '/' + target)
            wrapped = BASE + '/now/nav/ui/classic/params/target/' + quote(target, safe='')
            self.assertEqual(normalize_list_url(wrapped), BASE + '/' + target)

    def test_record_links_are_restricted_in_both_channels(self):
        record = BASE + '/incident.do?sys_id=abc'
        for bad in [record.replace('adeo.service-now.com', 'evil.test'),
                    record.replace('https://', 'https://user:pass@'),
                    record.replace('.com/', '.com:8443/'), record + '#fragment',
                    record.replace('/incident.do', '/sc_task.do'),
                    record.replace('/incident.do', '/admin'), record + '%0a', 'javascript:alert(1)']:
            with self.subTest(url=bad):
                self.assertEqual(safe_record_url(bad, 'INC123', BASE + '/incident_list.do'), '')
                self.assertNotIn('href=', payload('Filter', 'INC123 - Opis', {'INC123': bad})['text'])
                self.assertNotIn('|INC123>', payloads('Filter', 'INC123 - Opis', {'INC123': bad})[0]['text'])
        self.assertEqual(safe_record_url(record, 'INC123', BASE + '/incident_list.do'), record)

    def test_untrusted_frames_are_not_collected_and_bad_links_become_plain(self):
        foreign = Mock(url='https://evil.test/incident_list.do')
        trusted = Mock(url=BASE + '/incident_list.do')
        trusted.locator.return_value.evaluate_all.return_value = [
            {'label': 'INC1234567', 'href': 'https://evil.test/incident.do',
             'fields': {'short_description': 'Opis'}}]
        result = collect(Mock(frames=[foreign, trusted]))
        foreign.locator.assert_not_called()
        self.assertEqual(result['INC1234567']['url'], '')
        self.assertEqual(result['INC1234567']['summary'], 'Opis')

    def test_external_text_cannot_create_markdown_links_or_mentions(self):
        text = 'INC123 - [kliknij](https://evil.test) *pilne* _test_ ~x~ `x` \x00\u202e'
        card = payload('[Tytuł](https://evil.test)', text, {'INC123': BASE + '/incident.do'})
        body = card['attachments'][0]['content']['body']
        self.assertIn('[INC123](https://adeo.service-now.com/incident.do)', body[1]['text'])
        self.assertIn(r'\[kliknij\]', body[1]['text'])
        self.assertNotIn('https://evil.test', body[1]['text'])
        self.assertNotIn('\x00', body[1]['text'])
        self.assertNotIn('\u202e', body[1]['text'])
        self.assertIn(r'\[Tytuł\]', body[0]['text'])
        chat = payloads('<users/all>', 'INC123 - *x* <https://evil.test|kliknij>')[0]['text']
        self.assertNotIn('<users/all>', chat)
        self.assertNotIn('*x*', chat)
        self.assertNotIn('<https://evil.test', chat)
