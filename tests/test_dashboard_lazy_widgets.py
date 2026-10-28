import html
import threading
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.dashboard import (
    DASHBOARD_URL, TITLES, HELD_TITLES, read_dashboard, read_held_dashboard,
)


def lazy_cards(titles):
    cards = '<div style="height:1500px">Zawartość przed kafelkami</div>'
    cards += ''.join('<div class="grid-stack-item-content lazy" style="height:180px;margin:120px 0" '
                     f'data-title="{html.escape(title, quote=True)}" data-value="{index}"></div>'
                     for index, title in enumerate(titles))
    return cards + '''<script>
        window.activated = 0;
        const observer = new IntersectionObserver(entries => {
            for (const entry of entries) if (entry.isIntersecting) {
                const card = entry.target;
                const heading = document.createElement('h2');
                heading.textContent = card.dataset.title; card.appendChild(heading);
                const score = document.createElement('button');
                score.textContent = card.dataset.value;
                score.setAttribute('aria-label', card.dataset.title + ', ' + card.dataset.value);
                card.appendChild(score); window.activated++;
                observer.unobserve(card);
            }
        });
        for (const card of document.querySelectorAll('.lazy')) observer.observe(card);
        </script>'''


class DashboardLazyWidgetTests(unittest.TestCase):
    def test_sla_initializes_all_eleven_offscreen_tiles_after_period_and_filters(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 900, 'height': 600})
                controls = '''<button id="period" aria-label="Filtr Okres otwarcia z typem daterange">Okres</button>
                    <input id="start" aria-label="Data rozpoczęcia">
                    <input id="end" aria-label="Data zakończenia">
                    <button onclick="document.getElementById('period').setAttribute('aria-label',
                    'Filtr Okres otwarcia z typem daterange. Wybrane wartości to: ' +
                    document.getElementById('start').value + ' - ' + document.getElementById('end').value)">Zastosuj</button>'''
                page.route('**/*', lambda route: route.fulfill(
                    body=controls + lazy_cards(TITLES), content_type='text/html; charset=utf-8'))
                page.goto(DASHBOARD_URL)
                self.assertEqual(page.get_by_role('heading', name=TITLES[0], exact=True).count(), 0)
                def categories(*args):
                    self.assertEqual(page.locator('#start').input_value(), '2026-10-01')
                    self.assertEqual(page.locator('#end').input_value(), '2026-10-31')
                    self.assertEqual(page.evaluate('window.activated'), 0)
                with patch('neto_incident_monitor.dashboard.ensure_all_categories', side_effect=categories) as ensure:
                    result = read_dashboard(page, 2026, 10, threading.Event())
                ensure.assert_called_once()
                self.assertEqual(result, dict(zip(TITLES, range(len(TITLES)))))
                self.assertEqual(page.evaluate('window.activated'), 11)
            finally:
                browser.close()

    def test_held_initializes_both_offscreen_tiles_after_all_agents_check(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 900, 'height': 600})
                controls = '''<button role="tab" aria-selected="true">Wstrzymane L1</button>
                    <sn-component-filter><h3>Agent L1</h3>
                    <label><input type="checkbox" checked>Wybierz wszystko</label></sn-component-filter>'''
                page.route('**/*', lambda route: route.fulfill(
                    body=controls + lazy_cards(HELD_TITLES), content_type='text/html; charset=utf-8'))
                page.goto(DASHBOARD_URL)
                self.assertEqual(page.get_by_role('heading', name=HELD_TITLES[0], exact=True).count(), 0)
                result = read_held_dashboard(page, threading.Event())
                self.assertEqual(result, dict(zip(HELD_TITLES, range(2))))
                self.assertEqual(page.evaluate('window.activated'), 2)
            finally:
                browser.close()
