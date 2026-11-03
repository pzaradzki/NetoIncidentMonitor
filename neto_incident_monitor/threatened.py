"""Read SLA-risk counters and the confirmed aggregate list."""
from neto_incident_monitor.dashboard import authenticated_read

THREATENED_URL = (
    'https://adeo.service-now.com/now/platform-analytics-workspace/dashboards/params/edit/false/'
    'tab-sys-id/54154e7fadc41fd030fd4a7e9f322595/sys-id/22361ad72b6a8b504b98f4c2c891bfab/'
    '__state__/b64-tiny~MwXI59oDkaQ8SM4vFHJzNp3mnHkKbaoo'
)
KEYS = ('P1', 'P2', 'P3', 'P4', 'P5', 'Podjęcie')
DETAILS_TITLE = 'Zagrożone i po terminie – posortowane wg czasu do przekroczenia SLA'


@authenticated_read
def read_threatened_dashboard(page, stop):
    from neto_incident_monitor.dashboard import read_section_cards
    titles = tuple('P' + str(p) + ' – < ' + threshold + ' / po terminie'
                   for p, threshold in enumerate(('1 h', '2 h', '4 h', '1 dzień', '2 dni'), 1))
    titles += ('Podjęcie – < 5 min / po terminie',)
    values = read_section_cards(page, 'threatened', titles, stop)
    return {key: values[title] for key, title in zip(KEYS, titles)}

# Selectors verified on the aggregate NOW-LIST in the authenticated dashboard.
DETAILS = r"""title => {
    function nodes(root) {
        return Array.from(root.querySelectorAll('*')).flatMap(
            el => el.shadowRoot ? [el, ...nodes(el.shadowRoot)] : [el]);
    }
    const documentNodes = nodes(document);
    const headings = documentNodes.filter(el => el.tagName === 'H2' && el.textContent.trim() ===
        title);
    const widgets = documentNodes.filter(el => el.tagName === 'SN-PAR-ANALYTICS-LIST-BASE');
    if (headings.length !== 1 || widgets.length !== 1) return null;
    const widget = widgets[0];
    const local = [...nodes(widget), ...(widget.shadowRoot ? nodes(widget.shadowRoot) : [])];
    const tables = local.filter(el => el.matches('table.now-list-table[role="grid"]'));
    if (tables.length !== 1 || local.some(el => el.getAttribute('aria-busy') === 'true' ||
        (el.matches('now-loader, [role="progressbar"]') && !el.closest('tbody')))) return null;
    const rows = Array.from(tables[0].querySelectorAll('tbody tr[data-key]'));
    const pagers = local.filter(el => el.tagName === 'NOW-PAGINATION-CONTROL');
    const controls = pagers.length === 1
        ? [...nodes(pagers[0]), ...(pagers[0].shadowRoot ? nodes(pagers[0].shadowRoot) : [])] : [];
    const ranges = controls.filter(el => !el.children.length &&
        /^Pokazywanie\s+\d+\s*[-–]\s*\d+\s+z\s+\d+$/.test(el.textContent.trim()));
    const next = controls.filter(el => el.matches('button[aria-label="Następna strona"]'));
    return {
        empty: local.some(el => el.tagName === 'H3' && el.textContent.trim() === 'Brak dostępnych danych.'),
        range: ranges.length === 1 ? ranges[0].textContent.match(/\d+/g).map(Number) : null,
        terminal: next.length === 1 && next[0].disabled,
        rows: rows.map(row => {
            const cell = key => row.querySelector('[data-column-key="' + key + '"]');
            const value = key => cell(key)?.textContent.trim() || '';
            const links = Array.from(cell('task')?.querySelectorAll('a') || [])
                .filter(link => /^INC\d+$/.test(link.textContent.trim()));
            return {
                id: row.getAttribute('data-key'),
                number: links.length === 1 ? links[0].textContent.trim() : '',
                url: links.length === 1 ? links[0].href : '',
                priority: value('task.priority'), target: value('sla.target'),
                deadline: value('planned_end_time'), remaining: value('business_time_left'),
                percent: value('business_percentage')
            };
        })
    };
}"""


def parse_details(observation, scores):
    import re
    from datetime import datetime
    from urllib.parse import urlsplit
    from neto_incident_monitor.service_now_urls import safe_record_url, trusted_url

    if not observation:
        return None
    rows = observation['rows']
    if observation['empty']:
        return {} if not rows and not any(scores.values()) else None
    if not rows or not observation['terminal'] or observation['range'] != [1, len(rows), len(rows)]:
        return None

    incidents, seen = {}, set()
    counts = dict.fromkeys(KEYS, 0)
    for row in rows:
        key, number = row['id'], row['number']
        if not re.fullmatch(r'[a-f0-9]{32}', key or '', re.I) or key.lower() in seen:
            return None
        seen.add(key.lower())
        if not trusted_url(row['url']):
            return None
        link = urlsplit(row['url'])
        if link.path not in ('/task.do', '/incident.do'):
            return None
        url = safe_record_url(link._replace(path='/incident.do', fragment='').geturl(), number)
        priority = re.match(r'([1-5])(?:\b|$)', row['priority'])
        target = row['target'].casefold()
        category = ('Podjęcie' if target in ('odpowiedź', 'response') else
                    'P' + priority[1] if priority and target in ('rozwiązanie', 'resolution') else None)
        percent = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%', row['percent'])
        if not url or not category or not percent or not row['remaining']:
            return None
        try:
            deadline = datetime.strptime(row['deadline'], '%Y-%m-%d %H:%M:%S').isoformat()
        except ValueError:
            return None
        counts[category] += 1
        current = incidents.get(number)
        if current and current['url'] != url:
            return None
        categories = set(current['categories']) if current else set()
        categories.add(category)
        if current is None or (deadline, key) < (current['deadline'], current['sla']):
            incidents[number] = dict(number=number, url=url, deadline=deadline, sla=key,
                                     remaining=row['remaining'], percent=float(percent[1].replace(',', '.')))
        incidents[number]['categories'] = [name for name in KEYS if name in categories]
    return incidents if counts == scores else None


@authenticated_read
def read_threatened_details(page, stop, scores):
    import time
    from neto_incident_monitor.browser_actions import checkpoint
    from neto_incident_monitor.dashboard import check_session, verify_context
    from neto_incident_monitor.read_budget import remaining_ms
    from playwright.sync_api import TimeoutError

    deadline = time.monotonic() + 5
    scrolled = False
    while True:
        checkpoint(stop)
        check_session(page)
        verify_context(page, 'threatened')
        result = parse_details(page.evaluate(DETAILS, DETAILS_TITLE), scores)
        if result is not None or time.monotonic() >= deadline:
            return result
        if not scrolled:
            heading = page.get_by_role('heading', name=DETAILS_TITLE, exact=True)
            if heading.count() == 1:
                scrolled = True
                try:
                    heading.scroll_into_view_if_needed(timeout=remaining_ms(1200))
                except TimeoutError:
                    pass
        page.wait_for_timeout(200)
