import tempfile
import unittest
from pathlib import Path

from neto_incident_monitor.history import History
from neto_incident_monitor.threatened import DETAILS, DETAILS_TITLE, KEYS, parse_details


class ThreatenedDetailsTests(unittest.TestCase):
    def test_shadow_dom_pager_refuses_partial_page(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content('<h2>Zagrożone i po terminie – posortowane wg czasu do przekroczenia SLA</h2>'
                                 '<sn-par-analytics-list-base></sn-par-analytics-list-base>')
                page.evaluate("""() => {
                    const host = document.querySelector('sn-par-analytics-list-base');
                    const root = host.attachShadow({mode: 'open'});
                    root.innerHTML = '<table class="now-list-table" role="grid"><tbody></tbody></table>'
                        + '<now-pagination-control></now-pagination-control>';
                    root.querySelector('now-pagination-control').attachShadow({mode: 'open'}).innerHTML =
                        '<span>Pokazywanie 1-10 z 12</span><button aria-label="Następna strona"></button>';
                }""")
                facts = page.evaluate(DETAILS, DETAILS_TITLE)
                self.assertEqual(facts['range'], [1, 10, 12])
                self.assertFalse(facts['terminal'])
                self.assertIsNone(parse_details(facts, dict.fromkeys(KEYS, 0)))
                page.evaluate("""() => {
                    const root = document.querySelector('sn-par-analytics-list-base').shadowRoot;
                    const pager = root.querySelector('now-pagination-control').shadowRoot;
                    pager.querySelector('span').textContent = 'Pokazywanie 1-1 z 1';
                    pager.querySelector('button').disabled = true;
                    const values = {
                        'task': '<a href="https://adeo.service-now.com/task.do?sys_id='
                            + 'b'.repeat(32) + '">INC0001</a>',
                        'task.priority': '3 — umiarkowane',
                        'sla.target': 'Rozwiązanie',
                        'planned_end_time': '2026-11-03 12:00:00',
                        'business_time_left': '0 s',
                        'business_percentage': '109.7 %',
                    };
                    const row = root.querySelector('tbody').insertRow();
                    row.dataset.key = 'a'.repeat(32);
                    for (const [key, value] of Object.entries(values)) {
                        const cell = row.insertCell();
                        cell.dataset.columnKey = key;
                        cell.innerHTML = value;
                    }
                }""")
                scores = dict.fromkeys(KEYS, 0)
                scores['P3'] = 1
                self.assertEqual(parse_details(page.evaluate(DETAILS, DETAILS_TITLE), scores)
                                 ['INC0001']['percent'], 109.7)
            finally:
                browser.close()

    def test_only_complete_consistent_snapshot_can_change_presence(self):
        row = dict(id='a' * 32, number='INC0001',
                   url='https://adeo.service-now.com/task.do?sys_id=' + 'b' * 32,
                   priority='3 — umiarkowane', target='Rozwiązanie',
                   deadline='2026-11-03 12:00:00', remaining='0 s', percent='109.7 %')
        second = dict(row, id='c' * 32, target='Odpowiedź',
                      deadline='2026-11-03 12:05:00', percent='102,16 %')
        scores = dict.fromkeys(KEYS, 0)
        scores.update({'P3': 1, 'Podjęcie': 1})
        page = dict(empty=False, range=[1, 2, 2], terminal=True, rows=[row, second])
        snapshot = parse_details(page, scores)
        self.assertEqual(snapshot['INC0001']['categories'], ['P3', 'Podjęcie'])
        self.assertEqual(snapshot['INC0001']['percent'], 109.7)
        self.assertIsNone(parse_details(dict(page, terminal=False), scores))
        self.assertIsNone(parse_details(dict(page, range=[1, 2, 3]), scores))
        self.assertIsNone(parse_details(page, dict(scores, P3=2)))
        self.assertEqual(parse_details(dict(empty=True, rows=[]), dict.fromkeys(KEYS, 0)), {})

    def test_history_and_outbox_survive_restart_and_rollback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'history.json'
            snapshot = {'INC0001': {'number': 'INC0001'}}
            def prepare(rows):
                return [{'channel': 'windows', 'count': len(rows)}]
            def checkpoint():
                pass
            history = History(path)
            self.assertEqual(history.commit_threatened(snapshot, 1, checkpoint, prepare)[1], 1)
            history = History(path)
            self.assertEqual(history.commit_threatened(snapshot, 2, checkpoint, prepare)[1], 0)
            self.assertEqual(len(history.pending_alerts()), 1)
            history.commit_threatened({}, 3, checkpoint, prepare)
            self.assertFalse(history.threatened_snapshot()['INC0001']['present'])
            calls = iter((None, RuntimeError('cancelled')))
            def interrupted():
                if error := next(calls):
                    raise error
            with self.assertRaises(RuntimeError):
                history.commit_threatened(snapshot, 4, interrupted, prepare)
            self.assertFalse(history.threatened_snapshot()['INC0001']['present'])
            self.assertEqual(len(history.pending_alerts()), 1)
            self.assertEqual(history.commit_threatened(snapshot, 5, checkpoint, prepare)[0]
                             ['INC0001']['appearances'], 2)
            self.assertEqual(len(history.pending_alerts()), 2)
