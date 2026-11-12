import tempfile
import queue
import json
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.dashboard_ui import build_dashboard
from neto_incident_monitor.dashboard_cache import load_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.root.destroy)
        self.path = Path(self.temp.name)/'cache.json'
        self.app = SimpleNamespace(dashboard_requests=queue.Queue())
        self.panel = build_dashboard(self.root, self.app, self.path)

    def result(self, section, titles, time='2026-10-01T12:00:00+02:00', value=1):
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, '',
            {'section': section, 'values': dict.fromkeys(titles, value), 'read_at': time, 'diagnostics': Mock()}))

    def test_fresh_sla_does_not_retimestamp_held_or_replace_its_value(self):
        self.result('held', HELD_TITLES)
        old = dict(self.panel.section_snapshots['held'])
        self.result('sla', TITLES, '2026-10-02T12:00:00+02:00', 9)
        self.assertEqual(self.panel.section_snapshots['held'], old)
        self.assertEqual(load_snapshot(self.path)['sections']['held'], old)
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, '',
            {'section': 'held', 'error': True, 'diagnostics': Mock()}))
        self.assertEqual(self.panel.section_snapshots['held']['read_at'], old['read_at'])
        self.assertEqual(self.panel.values[HELD_TITLES[0]].get(), '1')

    def test_partial_section_and_stale_request_do_not_replace_snapshot(self):
        self.result('requests', REQUEST_TITLES)
        old = dict(self.panel.section_snapshots['requests'])
        self.result('requests', REQUEST_TITLES[:-1], value=8)
        self.assertEqual(self.panel.section_snapshots['requests'], old)
        self.panel.apply_result((self.panel.request_id - 1, 2026, 10, {}, None, '',
            {'section': 'requests', 'values': dict.fromkeys(REQUEST_TITLES, 8), 'read_at': 'bad', 'diagnostics': Mock()}))
        self.assertEqual(self.panel.section_snapshots['requests'], old)

    def test_cache_failure_keeps_values_and_warning_after_final_message(self):
        with patch('neto_incident_monitor.dashboard_cache.os.replace', side_effect=PermissionError('PRIVATE_SECRET')):
            self.result('sla', TITLES)
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, ''))
        self.assertEqual(self.panel.values[TITLES[0]].get(), '1')
        self.assertIn('Nie udało się zapisać', self.panel.message.get())
        self.assertNotIn('PRIVATE_SECRET', self.panel.message.get())

    def test_restored_sections_keep_dates_but_start_stale(self):
        self.result('sla', TITLES)
        restored = build_dashboard(self.root, SimpleNamespace(), self.path)
        self.assertEqual(restored.values[TITLES[0]].get(), '1')
        self.assertEqual(restored.section_states['Dashboard SLA'], 'Dane nieaktualne')
        self.assertEqual(restored.section_snapshots['sla']['read_at'], '2026-10-01T12:00:00+02:00')
        card = restored.value_labels[TITLES[0]].master
        self.assertEqual(card.cget('cursor'), 'arrow')
        self.assertEqual(int(card.cget('takefocus')), 0)

    def complete_read(self):
        self.panel.year.set('2026')
        self.panel.month.set('Październik')
        self.panel.request_refresh(automatic=True)
        for section, titles in (('sla', TITLES), ('held', HELD_TITLES), ('requests', REQUEST_TITLES)):
            self.result(section, titles)
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, ''))
        self.panel.set_updating(*self.panel.active_request, 'finished')

    def test_single_timestamp_advances_only_after_full_read_and_survives_restart(self):
        self.complete_read()
        stamp = self.panel.last_complete_read_at
        self.assertIsNotNone(stamp)
        self.assertRegex(self.panel.last_read_text, r'^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}$')
        self.assertNotIn('Dashboard SLA:', self.panel.message.get())
        self.assertNotIn('Wstrzymane L1:', self.panel.message.get())
        self.assertNotIn('Wnioski L1:', self.panel.message.get())
        self.assertEqual(load_snapshot(self.path)['last_complete_read_at'], stamp)
        restored = build_dashboard(self.root, SimpleNamespace(), self.path)
        self.assertEqual(restored.last_complete_read_at, stamp)
        self.assertEqual(restored.last_read_text, self.panel.last_read_text)

    def test_partial_or_failed_read_does_not_advance_complete_timestamp(self):
        self.complete_read()
        stamp = self.panel.last_complete_read_at
        self.panel.request_refresh(automatic=True)
        self.result('sla', TITLES, '2026-10-02T12:00:00+02:00')
        self.assertEqual(self.panel.last_complete_read_at, stamp)
        self.result('held', HELD_TITLES)
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, '',
            {'section':'requests','error':True,'diagnostics':Mock()}))
        self.panel.apply_result((self.panel.request_id, 2026, 10, {}, None, 'Niepełny odczyt.'))
        self.assertEqual(self.panel.last_complete_read_at, stamp)
        self.assertEqual(load_snapshot(self.path)['last_complete_read_at'], stamp)
        self.assertEqual(self.panel.section_snapshots['sla']['read_at'], '2026-10-02T12:00:00+02:00')

    def test_old_cache_without_full_timestamp_does_not_invent_one(self):
        self.result('sla', TITLES)
        data = json.loads(self.path.read_text(encoding='utf-8'))
        data.pop('last_complete_read_at', None)
        for invalid in (None, 'SYNTHETIC_SECRET'):
            with self.subTest(marker=invalid):
                if invalid is not None:
                    data['last_complete_read_at'] = invalid
                self.path.write_text(json.dumps(data), encoding='utf-8')
                restored = build_dashboard(self.root, SimpleNamespace(), self.path)
                self.assertIsNone(restored.last_complete_read_at)
                self.assertEqual(restored.last_read_text, '—')
                self.assertEqual(restored.values[TITLES[0]].get(), '1')

    def test_legacy_four_request_tiles_keep_other_sections(self):
        self.complete_read()
        data = json.loads(self.path.read_text(encoding='utf-8'))
        del data['sections']['requests']['values'][REQUEST_TITLES[-1]]
        self.path.write_text(json.dumps(data), encoding='utf-8')
        restored = build_dashboard(self.root, SimpleNamespace(), self.path)
        self.assertEqual(set(restored.section_snapshots), {'sla', 'held'})
        self.assertIsNone(restored.last_complete_read_at)
        self.assertTrue(all(restored.values[title].get() == '—' for title in REQUEST_TITLES))

    def test_request_tiles_share_one_row_in_title_order(self):
        cards = [self.panel.value_labels[title].master for title in REQUEST_TITLES]
        self.assertEqual([int(card.grid_info()['row']) for card in cards], [0] * 5)
        self.assertEqual([int(card.grid_info()['column']) for card in cards], list(range(5)))
        self.assertEqual({card.master.grid_columnconfigure(i)['uniform'] for i, card in enumerate(cards)},
                         {'requests'})

    def test_tiles_keep_hover_without_click_actions_after_refresh(self):
        self.complete_read()
        for title, value_label in self.panel.value_labels.items():
            with self.subTest(title=title):
                card = value_label.master
                self.assertEqual(int(card.cget('takefocus')), 0)
                self.assertFalse(card.bind('<KeyRelease-Return>'))
                self.assertFalse(card.bind('<KeyRelease-space>'))
                for widget in (card, *card.labels):
                    self.assertEqual(widget.cget('cursor'), 'arrow')
                    self.assertTrue(widget.bind('<Enter>'))
                    self.assertTrue(widget.bind('<Leave>'))
                    self.assertFalse(widget.bind('<ButtonPress-1>'))
                    self.assertFalse(widget.bind('<ButtonRelease-1>'))
