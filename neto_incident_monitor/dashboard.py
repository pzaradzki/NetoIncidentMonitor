"""Read analytics scores through the authenticated browser UI."""
import calendar
import re
import time
from decimal import Decimal
from playwright.sync_api import TimeoutError, expect

DASHBOARD_URL = ('https://adeo.service-now.com/now/platform-analytics-workspace/dashboards/params/edit/false/'
                 'tab-sys-id/ba36dad72b6a8b504b98f4c2c891bf73/sys-id/22361ad72b6a8b504b98f4c2c891bfab/'
                 'unified-filters-param/tinyurl/__state__/b64-tiny~WKEf3X0ASg6M0LcR1kiqt049NKRrAV35')
TITLES = ('Liczba zgłoszeń',) + tuple(f'Zgłoszenia P{i}' for i in range(1, 6)) + tuple(f'Przekroczone P{i}' for i in range(1, 6))
HELD_TITLES = ('Wstrzymane L1 >14 dni', 'Wstrzymane L1 >7 dni')
REQUEST_TITLES = ('Otwarte wnioski L1', 'Wnioski L1 >7 dni',
                  'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1')


def read_requests_dashboard(page, stop):
    if stop.is_set():
        raise RuntimeError('Odczyt dashboardu przerwany.')
    page.goto(DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73',
                                   '17fcfee03dcc5310e5e0b24c4676861c'),
              wait_until='domcontentloaded', timeout=60000)
    page.get_by_role('tab', name='Wnioski L1', exact=True).click(timeout=30000)
    deadline = time.monotonic() + 20
    previous, stable_since = None, None
    values = {}
    while time.monotonic() < deadline:
        if stop.is_set():
            raise RuntimeError('Odczyt dashboardu przerwany.')
        current = {}
        for title in REQUEST_TITLES:
            try:
                current[title] = parse_score(page.get_by_role('button', name=score_pattern(title)).inner_text(timeout=300))
            except (TimeoutError, ValueError):
                pass
        loading = page.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).count()
        if not loading and current:
            if current != previous:
                previous, stable_since = current, time.monotonic()
            elif time.monotonic() - stable_since >= 1:
                values = current
                if len(values) == len(REQUEST_TITLES):
                    return values
        else:
            previous = stable_since = None
            values = {}
        page.wait_for_timeout(200)
    if not values:
        raise ValueError('Nie udało się odczytać kafelków Wnioski L1.')
    return values


def calculate_wjruw(values):
    """Weighted SLA score from the same complete snapshot as the tiles."""
    weights = {1: 50, 2: 10, 3: 5, 4: 2, 5: 1}
    required = [f'{kind} P{p}' for kind in ('Zgłoszenia', 'Przekroczone') for p in weights]
    if any(not isinstance(values.get(key), int) or values[key] < 0 for key in required):
        return None
    total = sum(values[f'Zgłoszenia P{p}'] * weight for p, weight in weights.items())
    exceeded = sum(values[f'Przekroczone P{p}'] * weight for p, weight in weights.items())
    return Decimal(100) - Decimal(exceeded) * 100 / Decimal(total) if total else None


def month_range(year, month):
    last = calendar.monthrange(year, month)[1]
    return f'{year:04}-{month:02}-01', f'{year:04}-{month:02}-{last:02}'


def parse_score(text):
    value = re.sub(r'[\s\u00a0\u202f]', '', text)
    if not re.fullmatch(r'\d+', value):
        raise ValueError('Widżet nie zwrócił pełnej wartości liczbowej.')
    return int(value)


def score_pattern(title):
    # ServiceNow can leave whitespace at the end of the configured widget title.
    return re.compile(r'^\s*' + r'\s+'.join(re.escape(part) for part in title.split()) + r'\s*,')


def ensure_all_categories(page, stop, categories=('Status zgłoszenia', 'Lokalizacja', 'Przypisany do')):
    """Apply each category separately, scoped by its heading rather than order."""
    for category in categories:
        if stop.is_set():
            raise RuntimeError('Odczyt dashboardu przerwany.')
        container = page.locator('sn-component-filter').filter(
            has=page.get_by_text(category, exact=True))
        checkbox = container.get_by_role('checkbox', name='Wybierz wszystko', exact=True)
        checkbox.wait_for(state='attached', timeout=30000)
        if not checkbox.evaluate('(element) => element.checked && !element.indeterminate'):
            checkbox.check(timeout=15000)
            expect(checkbox).to_be_checked(timeout=15000)
            container.get_by_role('button', name='Zastosuj', exact=True).click(timeout=15000)
            expect(checkbox).to_be_checked(timeout=15000)
            if checkbox.evaluate('(element) => element.indeterminate'):
                raise ValueError(f'Nie udało się zaznaczyć wszystkich pozycji: {category}.')


def read_held_dashboard(page, stop):
    if stop.is_set():
        raise RuntimeError('Odczyt dashboardu przerwany.')
    page.goto(DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73',
                                   'c228c7d455c81f90211a1d000e482311'),
              wait_until='domcontentloaded', timeout=60000)
    page.get_by_role('tab', name='Wstrzymane L1', exact=True).click(timeout=30000)
    ensure_all_categories(page, stop, ('Agent L1',))
    deadline = time.monotonic() + 60
    previous = None
    stable_since = None
    while time.monotonic() < deadline:
        if stop.is_set():
            raise RuntimeError('Odczyt dashboardu przerwany.')
        try:
            if page.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).count():
                raise ValueError('Trwa ładowanie.')
            values = {title: parse_score(page.get_by_role('button', name=score_pattern(title)).inner_text(timeout=500)) for title in HELD_TITLES}
            if values == previous and time.monotonic() - stable_since >= 1:
                return values
            if values != previous:
                previous, stable_since = values, time.monotonic()
        except (ValueError, TimeoutError):
            previous = stable_since = None
        page.wait_for_timeout(200)
    raise ValueError('Nie udało się odczytać kafelków Wstrzymane L1.')


def read_dashboard(page, year, month, stop):
    if stop.is_set():
        raise RuntimeError('Odczyt dashboardu przerwany.')
    start, end = month_range(year, month)
    page.goto(DASHBOARD_URL, wait_until='domcontentloaded', timeout=60000)
    page.get_by_role('button', name=re.compile(r'^Filtr Okres otwarcia z typem daterange')).click(timeout=60000)
    first = page.get_by_role('textbox', name='Data rozpoczęcia', exact=True)
    last = page.get_by_role('textbox', name='Data zakończenia', exact=True)
    first.fill(start)
    last.fill(end)
    last.press('Tab')
    page.wait_for_timeout(150)
    # The popover lives in a separate shadow root, outside the dialog host.
    apply = page.get_by_role('button', name='Zastosuj', exact=True).filter(visible=True).last
    if apply.is_enabled():
        apply.click()
    else:
        page.get_by_role('button', name='Anuluj', exact=True).filter(visible=True).last.click()
    page.get_by_role('button', name=f'Filtr Okres otwarcia z typem daterange. Wybrane wartości to: {start} - {end}', exact=True).wait_for(timeout=15000)
    ensure_all_categories(page, stop)
    deadline = time.monotonic() + 60
    previous = None
    stable_since = None
    while time.monotonic() < deadline:
        if stop.is_set():
            raise RuntimeError('Odczyt dashboardu przerwany.')
        try:
            if page.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).count():
                raise ValueError('Trwa ładowanie.')
            values = {title: parse_score(page.get_by_role('button', name=score_pattern(title)).inner_text(timeout=500)) for title in TITLES}
            if values == previous:
                if time.monotonic() - stable_since >= 1:
                    return values
            else:
                previous, stable_since = values, time.monotonic()
        except (ValueError, TimeoutError):
            previous = stable_since = None
        page.wait_for_timeout(200)
    raise ValueError('Nie udało się odczytać wszystkich kafelków dashboardu. Sprawdź sesję ServiceNow i spróbuj ponownie.')
