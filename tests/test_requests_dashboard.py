import json
import html
import queue
import threading
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import (
    DASHBOARD_URL, REQUEST_TITLES, TITLES, HELD_TITLES,
    read_requests_dashboard, diagnostic_steps, _request_tile, activate_dashboard_widgets,
)
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from neto_incident_monitor.pagination import Cancelled, AuthenticationRequired


def tiles(titles=REQUEST_TITLES):
    return ''.join(f'<button aria-label="{title.replace(">", "> ")}, {index}">{index}</button>'
                   for index, title in enumerate(titles))


def fixture(scores, checked=True):
    return ('<button role="tab" aria-selected="true">Wnioski L1</button>'
            '<div hidden><sn-component-filter><h3>Agent L1</h3>'
            '<label><input type="checkbox">Wybierz wszystko</label></sn-component-filter></div>'
            '<sn-component-filter><h3>Agenci L1</h3><label><input id="agents" type="checkbox" '
            + ('checked' if checked else '') + '>Zaznacz wszystko</label>'
            '<button onclick="window.applied=(window.applied||0)+1;'
            'document.getElementById(\'scores\').innerHTML=window.scores">Zastosuj</button>'
            '</sn-component-filter><div id="scores">' + scores + '</div>')


class RequestsDashboardTests(unittest.TestCase):
    def test_first_tab_entry_initializes_titleless_offscreen_cards_by_scrolling(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 900, 'height': 600})
                cards = '<div style="height:1500px">Inna zawartość dashboardu</div>'
                cards += ''.join('<div class="grid-stack-item-content lazy" style="height:220px;margin:220px 0" '
                                 f'data-title="{html.escape(title, quote=True)}" data-value="{index}"><component-renderer></component-renderer></div>'
                                 for index, title in enumerate(REQUEST_TITLES))
                document = fixture(cards) + '''<script>
                    window.activated = 0;
                    const observer = new IntersectionObserver(entries => {
                        for (const entry of entries) if (entry.isIntersecting) {
                            const card = entry.target;
                            card.querySelector('component-renderer').remove();
                            const heading = document.createElement('h2');
                            heading.textContent = card.dataset.title; card.appendChild(heading);
                            const score = document.createElement('now-score-basic');
                            card.appendChild(score);
                            score.attachShadow({mode:'open'}).innerHTML =
                                '<span class="now-score-value">' + card.dataset.value + '</span>';
                            window.activated++; observer.unobserve(card);
                        }
                    });
                    for (const card of document.querySelectorAll('.lazy')) observer.observe(card);
                    </script>'''
                page.route('**/*', lambda route: route.fulfill(body=document, content_type='text/html; charset=utf-8'))
                page.goto(DASHBOARD_URL)
                self.assertEqual(page.get_by_role('heading', name=REQUEST_TITLES[0], exact=True).count(), 0)
                self.assertEqual(page.locator('.now-score-value').count(), 0)
                result = read_requests_dashboard(page, threading.Event())
                self.assertEqual(result, dict(zip(REQUEST_TITLES, range(4))))
                self.assertEqual(page.evaluate('window.activated'), 4)
            finally:
                browser.close()

    def test_widget_activation_stops_between_scrolls(self):
        stop = threading.Event()
        page = Mock(url=DASHBOARD_URL, frames=[])
        cards = page.locator.return_value.filter.return_value
        cards.count.return_value = 2
        items = [Mock(), Mock()]
        cards.nth.side_effect = lambda index: items[index]
        for index, card in enumerate(items):
            card.bounding_box.return_value = {'x': 0, 'y': index * 500}
        items[0].scroll_into_view_if_needed.side_effect = lambda **kwargs: stop.set()
        with self.assertRaises(Cancelled):
            activate_dashboard_widgets(page, stop)
        items[0].scroll_into_view_if_needed.assert_called_once()
        items[1].scroll_into_view_if_needed.assert_not_called()

    def test_rendered_scores_in_shadow_widgets_do_not_wait_for_button_metadata_or_other_charts(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                scores = ''.join('<div class="grid-stack-item-content"><h2>' + title +
                                 f'</h2><now-score-basic data-value="{index}"></now-score-basic></div>'
                                 for index, title in enumerate(REQUEST_TITLES))
                # Unrelated chart is still loading. Interactive metadata on the
                # four rendered counters is deliberately delayed by 20 seconds.
                scores += '<div class="grid-stack-item-content"><h2>Inny wykres</h2><div role="progressbar">Trwa ładowanie danych wizualizacji</div>99999</div>'
                html = fixture(scores) + '''<script>
                    for (const host of document.querySelectorAll('now-score-basic')) {
                        const root = host.attachShadow({mode:'open'});
                        root.innerHTML = '<button aria-label="Przygotowywanie interakcji"><span class="now-score-value" aria-hidden="true">' + host.dataset.value + '&nbsp;</span></button>';
                        setTimeout(() => root.querySelector('button').setAttribute('aria-label',
                            host.parentElement.querySelector('h2').textContent + ', ' + host.dataset.value), 20000);
                    }
                    </script>'''
                page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html; charset=utf-8'))
                page.goto(DASHBOARD_URL)
                with diagnostic_steps(LoginDiagnostics()), self.assertLogs(_logger, level='INFO') as logs:
                    values = read_requests_dashboard(page, threading.Event())
                self.assertEqual(values, dict(zip(REQUEST_TITLES, range(4))))
                facts = _request_tile(page, REQUEST_TITLES[0])
                self.assertEqual(facts['score_source'], 'widget_value')
                self.assertFalse(facts['button_available'])
                self.assertTrue(any('"score_source": "widget_value"' in r.getMessage() for r in logs.records))
            finally:
                browser.close()

    def test_widget_loader_blocks_old_number_until_refresh_finishes(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                html = ('<div class="grid-stack-item-content"><h2>Otwarte wnioski L1</h2>'
                        '<div id="busy" role="progressbar">Trwa ładowanie danych wizualizacji</div>'
                        '<now-score-basic><span class="now-score-value">777</span></now-score-basic></div>')
                page.set_content(html)
                facts = _request_tile(page, REQUEST_TITLES[0])
                self.assertEqual(facts['state'], 'loading')
                self.assertIsNone(facts['value'])
                page.locator('#busy').evaluate('el => el.remove()')
                self.assertEqual(_request_tile(page, REQUEST_TITLES[0])['value'], 777)
                page.locator('.grid-stack-item-content').evaluate('el => el.setAttribute("aria-busy", "true")')
                self.assertIsNone(_request_tile(page, REQUEST_TITLES[0])['value'])
            finally:
                browser.close()

    def test_duplicate_or_invalid_widget_scores_are_never_guessed(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                card = ('<div class="grid-stack-item-content"><h2>Otwarte wnioski L1</h2>'
                        '<now-score-basic><span class="now-score-value">Brak danych</span></now-score-basic></div>')
                page.set_content(card)
                self.assertEqual(_request_tile(page, REQUEST_TITLES[0])['state'], 'invalid')
                page.set_content(card + card)
                self.assertEqual(_request_tile(page, REQUEST_TITLES[0])['state'], 'ambiguous')
                page.set_content(card.replace('Brak danych', '4').replace('</now-score-basic>',
                    '<span class="now-score-value">5</span></now-score-basic>'))
                self.assertEqual(_request_tile(page, REQUEST_TITLES[0])['state'], 'ambiguous')
            finally:
                browser.close()

    def test_applies_all_agents_before_reading_new_layout(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(
                    body=fixture('', checked=False), content_type='text/html; charset=utf-8'))
                page.goto(DASHBOARD_URL)
                page.evaluate('html => window.scores = html', tiles())
                values = read_requests_dashboard(page, threading.Event())
                self.assertEqual(values, dict(zip(REQUEST_TITLES, range(4))))
                self.assertEqual(page.evaluate('window.applied'), 1)
                self.assertTrue(page.locator('#agents').is_checked())
                self.assertFalse(page.locator('div[hidden] input').is_checked())
            finally:
                browser.close()

    def test_retries_once_and_returns_complete_snapshot_after_reload(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                loads = []
                def serve(route):
                    loads.append(True)
                    scores = tiles(REQUEST_TITLES[:-1] if len(loads) == 1 else REQUEST_TITLES)
                    route.fulfill(body=fixture(scores), content_type='text/html; charset=utf-8')
                page.route('**/*', serve)
                page.goto(DASHBOARD_URL)
                with patch('neto_incident_monitor.dashboard.REQUEST_READ_TIMEOUT', 2), \
                        self.assertLogs(_logger, level='INFO') as logs, diagnostic_steps(LoginDiagnostics()):
                    values = read_requests_dashboard(page, threading.Event())
                self.assertEqual(len(values), 4)
                self.assertEqual(len(loads), 2)
                records = [json.loads(r.getMessage()) for r in logs.records]
                self.assertEqual(sum(r['event'] == 'dashboard_scores_retry' for r in records), 1)
                self.assertTrue(any(r['event'] == 'dashboard_tile_state' and
                                    r.get('tile') == REQUEST_TITLES[-1] and r.get('tile_state') == 'missing'
                                    for r in records))
            finally:
                browser.close()

    def test_partial_result_is_bounded_and_not_logged_as_complete(self):
        app = App.__new__(App)
        app.stop, app.events, app.dashboard_requests = threading.Event(), queue.Queue(), queue.Queue()
        app.dashboard_requests.put((1, 2026, 10))
        with patch('neto_incident_monitor.dashboard.read_dashboard', return_value=dict.fromkeys(TITLES, 0)), \
                patch('neto_incident_monitor.dashboard.read_held_dashboard', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                patch('neto_incident_monitor.dashboard.read_requests_dashboard', return_value=dict.fromkeys(REQUEST_TITLES[:-1], 0)), \
                self.assertLogs(_logger, level='INFO') as logs:
            app.read_dashboard_request(Mock())
        records = [json.loads(r.getMessage()) for r in logs.records]
        partial = next(r for r in records if r['event'] == 'section_read_partial')
        self.assertFalse(any(r['event'] == 'section_read_complete' and r['session'] == partial['session'] for r in records))
        self.assertTrue(any(r['event'] == 'dashboard_tile_missing' and r['tile'] == REQUEST_TITLES[-1] for r in records))

    def test_persistent_missing_tile_retries_only_once(self):
        partial = dict.fromkeys(REQUEST_TITLES[:-1], 0)
        page = Mock(url=DASHBOARD_URL, frames=[])
        with patch('neto_incident_monitor.dashboard.open_dashboard_tab'), \
                patch('neto_incident_monitor.dashboard.activate_dashboard_widgets'), \
                patch('neto_incident_monitor.dashboard.ensure_all_categories') as ensure, \
                patch('neto_incident_monitor.dashboard._read_request_scores', return_value=partial) as scores, \
                patch('neto_incident_monitor.dashboard.navigate_page') as navigate:
            self.assertEqual(read_requests_dashboard(page, threading.Event()), partial)
        self.assertEqual(scores.call_count, 2)
        self.assertEqual(ensure.call_count, 2)
        navigate.assert_called_once()

    def test_cancel_and_session_expiry_are_not_retried_as_score_errors(self):
        for error in (Cancelled(), AuthenticationRequired()):
            with self.subTest(error=type(error).__name__), \
                    patch('neto_incident_monitor.dashboard.open_dashboard_tab'), \
                    patch('neto_incident_monitor.dashboard.activate_dashboard_widgets'), \
                    patch('neto_incident_monitor.dashboard.ensure_all_categories'), \
                    patch('neto_incident_monitor.dashboard._read_request_scores', side_effect=error), \
                    patch('neto_incident_monitor.dashboard.navigate_page') as navigate:
                page = Mock(url=DASHBOARD_URL, frames=[])
                with self.assertRaises(type(error)):
                    read_requests_dashboard(page, threading.Event())
                navigate.assert_not_called()
