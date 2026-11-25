import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dynamic_columns import update_profile
from neto_incident_monitor.login_diagnostics import _logger
from neto_incident_monitor.widgets import FilterList


URLS = [f'https://adeo.service-now.com/incident_list.do?fixture={letter}' for letter in ('a', 'b')]


class FilterCardCountTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.geometry('1280x800')
        self.settings = {'filters': [{'name': name, 'url': url} for name, url in zip(('A', 'B'), URLS)]}
        self.history_path = Path(folder.name) / 'history.json'
        with patch('neto_incident_monitor.config_io.read_json', return_value=self.settings):
            self.app = App(self.root, history_path=self.history_path,
                           enable_tray=False, apply_startup=False)
        schema = [{'key': 'number', 'label': 'Numer'}]
        self.app.column_profiles = {url: update_profile(None, schema) for url in URLS}
        self.addCleanup(self.app.stop_table_loads)
        self.root.update()

    def submit(self, index, numbers, *, outside_schedule=False, revision=None, timing=None):
        app = self.app
        url = URLS[index]
        snapshot = {number: {'number': number, 'url': '', 'short_description': 'synthetic-body'}
                    for number in numbers}
        revision = app.filter_revisions.get(url) if revision is None else revision
        app.events.put(('snapshot', (url, snapshot, revision, app.monitor_generation,
                                    outside_schedule, False, app.session.layout_generation, timing)))
        app.drain()

    def count(self, index):
        return self.app.filter_table.counts[str(index)]

    def click(self, index):
        table = self.app.filter_table
        event = SimpleNamespace(x=35, y=int(index * table.ROW + 15 - table.canvasy(0)))
        table.select_at(event)
        table.drag_end(event)
        self.root.update()

    def wait(self, predicate):
        deadline = time.monotonic() + 8
        while not predicate():
            self.root.update()
            if time.monotonic() >= deadline:
                self.fail('The expected filter view was not displayed.')
            time.sleep(.005)

    def test_unseen_only_contains_current_rows_and_is_independent_per_filter(self):
        self.assertEqual(self.count(0), (None, 0))
        with self.assertLogs(_logger, level='INFO') as output:
            self.submit(0, ['INC1', 'INC2', 'INC3', 'INC4'])
            self.submit(1, ['INC1'])
            self.assertEqual(self.count(0), (4, 4))
            self.submit(0, ['INC1', 'INC4'])
            self.assertEqual(self.count(0), (2, 2))
            self.click(0)
            self.assertEqual(self.count(0), (2, 0))
            self.assertEqual(self.count(1), (1, 1))
            self.app.show_dashboard_view()
            self.submit(0, ['INC1', 'INC4', 'INC5', 'INC6', 'INC7'])
            self.assertEqual(self.count(0), (5, 3))
            self.submit(0, ['INC1', 'INC4', 'INC7'])
            self.assertEqual(self.count(0), (3, 1))
            self.submit(0, ['INC1'])
            self.assertEqual(self.count(0), (1, 0))
            self.submit(0, ['INC1', 'INC4'])
            self.assertEqual(self.count(0), (2, 1))
            self.submit(0, [], revision=object())
            self.assertEqual(self.count(0), (2, 1))
            self.app.update_filter_read_result(URLS[0], error='synthetic failure')
            self.assertEqual(self.count(0), (2, 1))
            self.submit(0, [])
            self.assertEqual(self.count(0), (0, 0))
        events = [json.loads(record.getMessage()) for record in output.records]
        rows = [event for event in events if event['event'] == 'filter_card_count']
        self.assertTrue(any(row['count_reason'] == 'displayed' and row['not_displayed_count'] == 0
                            and row['total_rows'] == 2 and 'duration_ms' in row for row in rows))
        self.assertNotIn('INC4', str(rows))
        self.assertNotIn('synthetic-body', str(rows))
        self.assertNotIn(URLS[0], str(rows))

    def test_history_and_hidden_window_acknowledge_only_when_showing_current_rows(self):
        app = self.app
        self.submit(0, ['INC10'])
        app.tabs.select(1)
        self.click(0)
        self.assertEqual(self.count(0), (1, 1))
        app.tabs.select(0)
        self.wait(lambda: self.count(0) == (1, 0))
        self.root.withdraw()
        self.root.update()
        self.submit(0, ['INC10', 'INC11'])
        self.root.update()
        self.assertEqual(self.count(0), (2, 1))
        self.root.deiconify()
        self.wait(lambda: self.count(0) == (2, 0))
        self.submit(0, ['INC10', 'INC11', 'INC12'])
        self.wait(lambda: self.count(0) == (3, 0))
        self.submit(1, ['INC20'])
        app.filter_table.selection_set('1')
        self.root.update()
        self.assertEqual(self.count(1), (1, 1))
        app.filter_table.move(0)
        self.wait(lambda: self.count(1) == (1, 0))

    def test_interrupted_large_load_and_replacement_only_acknowledge_visible_snapshot(self):
        app = self.app
        self.click(0)
        self.submit(0, [f'INC{value:07d}' for value in range(350)])
        old_load = app._table_jobs[app.current_table]
        self.assertEqual(self.count(0), (350, 350))
        self.click(1)
        self.assertTrue(old_load['cancel'].is_set())
        self.assertEqual(self.count(0), (350, 350))
        self.click(0)
        self.submit(0, ['INC9999999'])
        self.wait(lambda: self.count(0) == (1, 0))
        self.assertEqual(app.filter_displayed[URLS[0]], {'INC9999999'})

    def test_two_results_before_tk_is_idle_acknowledge_only_the_latest(self):
        self.click(0)
        with self.assertLogs(_logger, level='INFO') as output:
            self.submit(0, ['INC1'])
            self.submit(0, ['INC2'])
            self.wait(lambda: self.count(0) == (1, 0))
        self.assertEqual(self.app.filter_displayed[URLS[0]], {'INC2'})
        rows = [json.loads(record.getMessage()) for record in output.records]
        self.assertTrue(any(row.get('count_reason') == 'stale' for row in rows))

    def test_reorder_preserves_counts_on_the_correct_filter(self):
        app = self.app
        self.submit(0, ['INC1', 'INC2'])
        self.submit(1, ['INC9'])
        table = app.filter_table
        click = SimpleNamespace(x=35, y=15)
        drop = SimpleNamespace(x=35, y=table.ROW * 2 - 4)
        with patch.object(app, 'persist_filters'):
            table.select_at(click)
            table.drag_motion(drop)
            self.root.update()
            table.drag_end(drop)
            self.root.update()
            self.assertEqual([entry['url'] for entry in app.filters], list(reversed(URLS)))
            self.assertEqual(app.active_view, 'dashboard')
            self.assertEqual(self.count(1), (2, 2))
            self.assertEqual(self.count(0), (1, 1))

    def test_schedule_toggle_retains_rows_and_allows_manual_refresh(self):
        app = self.app
        url = URLS[0]
        app.filter_revisions[url] = object()
        app.update_session_filters()
        self.submit(0, ['INC1'])
        self.click(0)
        app.show_dashboard_view()
        self.submit(0, ['INC1', 'INC2'], timing=(time.time(), 50))
        snapshot = app.snapshots[1]
        status = app.filter_read_status[url]
        app.column_availability[1] = {'number'}
        old_part = app.session.manual_filter_parts[url]
        table = app.filter_table
        switch = SimpleNamespace(x=table.winfo_width() - 15, y=15)

        with patch('neto_incident_monitor.config_io.save_json') as save, self.assertLogs(_logger, level='INFO') as log:
            table.select_at(switch)
            self.assertFalse(save.call_args.args[1]['filters'][0]['enabled'])
            self.assertFalse(table.enabled_rows['0'])
            self.assertIs(app.snapshots[1], snapshot)
            self.assertIs(app.filter_read_status[url], status)
            self.assertEqual(app.column_availability[1], {'number'})
            self.assertEqual(self.count(0), (2, 1))
            disabled_part = app.session.manual_filter_parts[url]
            self.assertNotEqual(disabled_part, old_part)
            self.assertNotIn(disabled_part, app.full_refresh_parts())

            self.submit(0, [], outside_schedule=True, revision=old_part.target[1])
            self.submit(0, [])
            self.assertIs(app.snapshots[1], snapshot)
            self.click(0)
            self.assertEqual(set(app.current_table.set(row, 'number') for row in app.current_table.get_children()),
                             {'INC1', 'INC2'})
            self.assertEqual(self.count(0), (2, 0))

            app.session.ready_once = True
            app.session_state = 'ready'
            self.assertTrue(app.request_refresh('filter'))
            self.assertIn(disabled_part, app.session.work.pending_refreshes()[1])
            self.submit(0, ['INC3'], outside_schedule=True, timing=(time.time(), 70))
            self.wait(lambda: self.count(0) == (1, 0))
            manual_snapshot = app.snapshots[1]
            displayed_rows = app.current_table.get_children()

            table.select_at(switch)
            self.assertTrue(save.call_args.args[1]['filters'][0]['enabled'])
            self.assertTrue(table.enabled_rows['0'])
            self.assertIs(app.snapshots[1], manual_snapshot)
            self.assertEqual(app.current_table.get_children(), displayed_rows)
            self.assertEqual(app.filter_read_status[url].duration_ms, 70)
            self.assertIn(app.session.manual_filter_parts[url], app.full_refresh_parts())
            self.submit(0, ['INC4'])
            self.assertEqual(set(app.snapshots[1]), {'INC4'})

        events = [json.loads(record.getMessage()) for record in log.records]
        changes = [event for event in events if event['event'] == 'filter_config_change']
        self.assertEqual([event['outcome'] for event in changes], ['started', 'returned', 'started', 'returned'])
        completed = [event for event in changes if event['outcome'] == 'returned']
        self.assertEqual([(event['filter_change'], event['total_rows']) for event in completed],
                         [('disable_schedule', 2), ('enable_schedule', 1)])
        self.assertTrue(all(event['run_id'] and event['filter_index'] == 1 and 'duration_ms' in event
                            for event in completed))
        self.assertNotIn(url, str(changes))

    def test_rename_retains_display_state_and_url_replacement_clears_it(self):
        app = self.app
        self.submit(0, ['INC1'])
        self.click(0)
        renamed = dict(app.filters[0], name='Nowa nazwa')
        replacement = 'https://adeo.service-now.com/incident_list.do?fixture=other'
        with patch('neto_incident_monitor.config_io.save_json'):
            app.save_filter_change([renamed, app.filters[1]], 'edit', URLS[0])
            self.assertEqual(self.count(0), (1, 0))
            app.save_filter_change([dict(renamed, url=replacement), app.filters[1]], 'edit', replacement)
        self.assertEqual(self.count(0), (None, 0))
        self.assertNotIn(URLS[0], app.filter_displayed)

    def test_new_app_restarts_the_count_with_the_same_local_history(self):
        self.submit(0, ['INC1'])
        self.click(0)
        self.assertEqual(self.count(0), (1, 0))
        root = tk.Tk()
        try:
            with patch('neto_incident_monitor.config_io.read_json', return_value=self.settings):
                reopened = App(root, history_path=self.history_path, enable_tray=False, apply_startup=False)
            reopened.events.put(('snapshot', (URLS[0], {'INC1': {'number': 'INC1'}})))
            reopened.drain()
            self.assertEqual(reopened.filter_table.counts['0'], (1, 1))
        finally:
            root.destroy()


class FilterCounterLayoutTests(unittest.TestCase):
    def test_counter_is_visible_without_collisions_and_changes_in_place(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        channels = ('windows', 'google_chat', 'teams')
        for scale in (1.0, 1.25):
            for width, notifications in ((200, channels), (310, channels), (310, ())):
                with self.subTest(scale=scale, width=width, notifications=notifications):
                    root.tk.call('tk', 'scaling', 96 / 72 * scale)
                    table = FilterList(root)
                    table.configure(width=width)
                    table.pack()
                    table.notification_channels = notifications
                    table.notification_rows['0'] = (False, False, False)
                    table.notification_rows['2'] = (True, True, True)
                    table.updating_item = '0'
                    table.queued_items = {'1'}
                    table.insert('', 'end', '0', ('Bardzo długa nazwa filtra do sprawdzenia',))
                    table.insert('', 'end', '1', ('Moje - Nowe / W trakcie',))
                    table.insert('', 'end', '2', ('Filtr bez statusu',))
                    root.update()
                    table.set_count('0', (1000, 1000))
                    total, partial, _ = table.count_items['0']
                    self.assertEqual(table.itemcget(total, 'text'), '1000')
                    self.assertEqual(table.itemcget(partial, 'text'), '(1000)')
                    badge, compact = table.badge_layout(table.winfo_width())
                    labels = [item for item in table.find_all() if table.type(item) == 'text']
                    label = next(item for item in labels if table.itemcget(item, 'text').startswith('Bar'))
                    running = next(item for item in labels if table.itemcget(item, 'text') == 'Aktualizuje')
                    queued = next(item for item in labels if table.itemcget(item, 'text') == 'W kolejce')
                    self.assertEqual((badge[1] + badge[3]) / 2, 22)
                    self.assertEqual(table.coords(running)[1], 22)
                    self.assertEqual(table.coords(queued)[1], table.ROW + 22)
                    self.assertLessEqual(table.coords(total)[1] - table.coords(label)[1], 17)
                    self.assertLessEqual(table.bbox(label)[3], table.bbox(total)[1])
                    self.assertLessEqual(table.bbox(label)[2], badge[0])
                    self.assertLessEqual(table.bbox(partial)[2], badge[0])
                    icons = table.find_withtag('notification_icon')
                    self.assertEqual(len(icons), 2 * len(notifications))
                    for icon in icons[:len(notifications)]:
                        left, top, right, bottom = table.bbox(icon)
                        self.assertTrue(right <= badge[0] or badge[2] <= left or bottom <= badge[1])
                        if not compact:
                            self.assertEqual((top + bottom) / 2, 22)
                    for icon in icons[len(notifications):]:
                        _, top, _, bottom = table.bbox(icon)
                        self.assertEqual((top + bottom) / 2, 2 * table.ROW + 22)
                    unchanged = table.find_all()
                    self.assertTrue(table.set_count('0', (1000, 0)))
                    self.assertFalse(table.set_count('0', (1000, 0)))
                    self.assertEqual(unchanged, table.find_all())
                    self.assertEqual(table.itemcget(partial, 'state'), 'hidden')
                    table.destroy()
