import json
import unittest
from urllib.parse import quote, urlencode, urlsplit, parse_qsl
from unittest.mock import patch

from neto_incident_monitor.app import validate_urls, load_filters
from neto_incident_monitor.service_now_urls import normalize_list_url, InvalidListURL
from neto_incident_monitor.pagination import first_page
from neto_incident_monitor.login_diagnostics import _logger
from tests.test_query_date_alias import QUERY

BASE = 'https://adeo.service-now.com/'
PREFIX = BASE + 'now/nav/ui/classic/params/target/'


def wrapper(pairs, suffix=''):
    return PREFIX + quote('incident_list.do?' + urlencode(pairs), safe='') + suffix


class WrappedListURLTests(unittest.TestCase):
    def test_legacy_single_encoded_complex_filter_keeps_logic_and_attached_parameters(self):
        address = PREFIX + quote('incident_list.do?sysparm_query=' + QUERY, safe='')
        address += '&sysparm_first_row=21&sysparm_view=default'
        normalized = validate_urls(address)[0]
        self.assertNotIn(' ', normalized)
        expected = [('sysparm_query', QUERY), ('sysparm_first_row', '21'), ('sysparm_view', 'default')]
        self.assertEqual(parse_qsl(urlsplit(normalized).query), expected)
        self.assertEqual(normalize_list_url(normalized), normalized)
        self.assertEqual(load_filters({'filters': [{'name': 'Synthetic', 'url': normalized}]} )[0]['url'], normalized)
        self.assertEqual(dict(parse_qsl(urlsplit(first_page(normalized)).query))['sysparm_first_row'], '1')

    def test_nested_parameter_encoding_preserves_reserved_and_unicode_characters(self):
        for value in ('a b', 'Zażółć gęślą', 'C++ & a=b 100%', 'literal%20sequence', '#value?', 'a;b'):
            pairs = [('sysparm_query', 'short_descriptionLIKE' + value), ('sysparm_view', 'default')]
            normalized = normalize_list_url(wrapper(pairs))
            self.assertEqual(parse_qsl(urlsplit(normalized).query), pairs)
            self.assertEqual(normalize_list_url(normalized), normalized)

    def test_inner_and_outer_parameters_merge_without_losing_view(self):
        address = wrapper([('sysparm_query', 'active=true')], '?sysparm_view=default&sysparm_first_row=21')
        self.assertEqual(dict(parse_qsl(urlsplit(normalize_list_url(address)).query)),
                         dict(sysparm_query='active=true',sysparm_view='default',sysparm_first_row='21'))
        identical = wrapper([('sysparm_view', 'default')], '?sysparm_view=default')
        self.assertEqual(parse_qsl(urlsplit(normalize_list_url(identical)).query), [('sysparm_view', 'default')])

    def test_conflicts_and_unsafe_targets_fail_without_exposing_values(self):
        for key in ('sysparm_query', 'sysparm_view', 'sysparm_first_row'):
            with self.assertRaises(InvalidListURL) as raised:
                normalize_list_url(wrapper([(key, 'SYNTHETIC_PRIVATE_A')], '?' + urlencode({key:'SYNTHETIC_PRIVATE_B'})))
            self.assertEqual(raised.exception.reason, 'conflicting_parameters')
            self.assertNotIn('SYNTHETIC_PRIVATE', str(raised.exception))
        for address in (PREFIX + quote('https://evil.test/incident_list.do',safe=''),
                        PREFIX + quote('//evil.test/incident_list.do',safe=''),
                        PREFIX + quote('admin.do?sysparm_query=active=true',safe=''),
                        wrapper([('sysparm_query','a\nb')]), wrapper([('sysparm_query','a\\b')]),
                        wrapper([('sysparm_query','active=true')])+'#fragment',
                        wrapper([('sysparm_query','active=true')]).replace('https://','https://secret@')):
            with self.subTest(address=address), self.assertRaises(ValueError):
                normalize_list_url(address)

    def test_direct_urls_keep_existing_identity_and_diagnostics_are_safe(self):
        direct = BASE + 'incident_list.do?sysparm_query=locationNOT%20LIKESTORE&sysparm_view=default'
        self.assertEqual(normalize_list_url(direct), direct)
        with self.assertLogs(_logger,level='INFO') as captured:
            validate_urls(wrapper([('sysparm_query','short_descriptionLIKESYNTHETIC_PRIVATE')]))
            with self.assertRaises(ValueError):
                validate_urls(wrapper([('sysparm_query','SYNTHETIC_PRIVATE')], '?sysparm_query=other'))
        records=[json.loads(r.getMessage()) for r in captured.records]
        checks=[r for r in records if r['event']=='filter_url_validation']
        self.assertEqual([r['validation_result'] for r in checks], ['accepted','rejected'])
        self.assertEqual(checks[-1]['validation_reason'],'conflicting_parameters')
        self.assertEqual({r['url_kind'] for r in checks},{'wrapper'})
        self.assertNotIn('SYNTHETIC_PRIVATE','\n'.join(captured.output))

    def test_diagnostic_failure_does_not_change_validation(self):
        with patch('neto_incident_monitor.login_diagnostics.LoginDiagnostics',side_effect=OSError('PRIVATE')):
            self.assertEqual(validate_urls(wrapper([('sysparm_query','active=true')])),
                             [BASE+'incident_list.do?sysparm_query=active%3Dtrue'])
            with self.assertRaises(ValueError):
                validate_urls('https://evil.test/incident_list.do')


class WrappedFilterDialogTests(unittest.TestCase):
    def test_add_save_restart_and_rejected_conflict_leave_config_intact(self):
        import tempfile
        import tkinter as tk
        from tkinter import ttk
        from pathlib import Path
        from neto_incident_monitor.app import App
        from neto_incident_monitor.secret_config import load_config
        from neto_incident_monitor.widgets import RoundedButton

        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as directory, \
                patch('neto_incident_monitor.app.DATA', Path(directory)), \
                patch('neto_incident_monitor.app.CONFIG', Path(directory) / 'config.json'), \
                patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
            path = Path(directory) / 'config.json'
            path.write_text('{"filters": []}', encoding='utf-8')
            app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False, apply_startup=False)
            def submit(address):
                app.edit_filter()
                dialog = next(w for w in root.winfo_children()
                              if isinstance(w, tk.Toplevel) and w.title() == 'Dodaj filtr')
                next(w for w in dialog.winfo_children() if isinstance(w,ttk.Entry)).insert(0,'Synthetic')
                field=next(w for w in dialog.winfo_children() if isinstance(w,tk.Text))
                field.delete('1.0','end');field.insert('1.0',address)
                next(w for w in dialog.winfo_children() if isinstance(w,RoundedButton)).invoke()
                return dialog
            address=wrapper([('sysparm_query',QUERY)],'&sysparm_first_row=1&sysparm_view=default')
            submit(address)
            restored=load_filters(load_config(path,{},migrate_plaintext=False))
            self.assertEqual(restored,app.filters)
            self.assertEqual(dict(parse_qsl(urlsplit(restored[0]['url']).query))['sysparm_query'],QUERY)
            saved=path.read_bytes()
            with patch('neto_incident_monitor.app.messagebox.showerror') as error:
                dialog=submit(wrapper([('sysparm_query','active=true')],'?sysparm_query=active=false'))
            error.assert_called_once()
            self.assertEqual(path.read_bytes(),saved)
            self.assertEqual(app.filters,restored)
            dialog.destroy()
