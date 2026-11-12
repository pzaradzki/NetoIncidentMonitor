"""In-memory preview and atomic addition using the existing filter schema."""
from urllib.parse import urljoin, urlparse

from neto_incident_monitor.service_now_urls import normalize_list_url, is_short_url, InvalidListURL

HOME = 'https://adeo.service-now.com/now/sow/home'
TENANT_ROOT = 'https://adeo.service-now.com/'


def classify(items, existing):
    seen = set()
    for entry in existing:
        try:
            seen.add(normalize_list_url(entry['url']))
        except ValueError:
            pass
    result = []
    for item in items:
        row = dict(item, url='', kind='', status='invalid', detail='Nieprawidłowy adres')
        try:
            # Polaris uses tenant-relative targets such as incident_list.do,
            # even when the menu is rendered under /now/sow/home.
            url = normalize_list_url(urljoin(TENANT_ROOT, item['href']))
            path = urlparse(url).path
            kind = {'/incident_list.do': 'INC', '/sc_task_list.do': 'SCTASK',
                    '/sc_request_list.do': 'REQ', '/sc_req_item_list.do': 'RITM'}.get(path, 'Skrót')
            row.update(url=url, kind=kind, status='existing' if url in seen else 'ready',
                       detail='Już istnieje' if url in seen else 'Do dodania — skrócony adres' if is_short_url(url) else 'Do dodania')
            seen.add(url)
        except ValueError as error:
            # urljoin itself can reject malformed authority syntax before the
            # tenant validator runs. Keep that row visible as invalid too.
            if getattr(error, 'reason', None) == 'unsupported_target':
                row.update(status='unsupported', detail='Nieobsługiwana — cel nie jest listą INC/SCTASK/REQ/RITM')
        result.append(row)
    return result


def commit_selection(app, items, selected):
    from neto_incident_monitor.app import CONFIG, read_json, load_filters
    settings = read_json(CONFIG, {})
    if ('filters' in settings or 'urls' in settings) and load_filters(settings, tolerate_invalid=True) != app.filters:
        raise ValueError('Konfiguracja filtrów zmieniła się. Otwórz import ponownie.')
    rows = classify(items, app.filters)
    additions = []
    for index, row in enumerate(rows):
        if index in selected and row['status'] == 'ready':
            additions.append(dict(name=row['name'], url=row['url'], enabled=False,
                notify_windows=False, notify_teams=False, notify_google_chat=False))
    if not additions:
        raise ValueError('Nie wybrano nowych, poprawnych filtrów.')
    old = app.filters
    app.filters = [*old, *additions]
    try:
        app.persist_filters()
    except Exception:
        app.filters = old
        raise
    return len(additions)
