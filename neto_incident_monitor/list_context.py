"""Bind classic list rows, navigation and metadata to one visible table."""
from dataclasses import dataclass, field
import json
import re
from urllib.parse import urlparse

from neto_incident_monitor.service_now_urls import trusted_url

ROW_INPUT = 'input.list2_page, input.list_row_number_input, input[data-type="list_nav_input"], input[name="sysparm_first_row"]'
PAGER = '[data-type^="list_nav"], input.list2_page, input.list_row_number_input, .list2_paging, button.list_nav'


def _ordered_conditions(query):
    if query is None:
        return None
    parts = query.split("^")
    while parts and (parts[-1] == "EQ" or
                     re.fullmatch(r"ORDERBY(?:DESC)?[a-zA-Z_][\w.]*", parts[-1])):
        parts.pop()
    return parts


# Only a complete comparison value can use the observed date alias.
_DATE_ALIAS = re.compile(r'((?:OR|NQ)?(?:GOTO)?sys_updated_on(?:<=|>=|!=|=|<|>))'
                         r'javascript:gs\.daysAgoStart\(7\)')


def list_conditions(query):
    """Preserve ordered logic, accepting only the observed seven-day date alias."""
    parts = _ordered_conditions(query)
    if parts is None:
        return None
    return '^'.join((match[1] + 'javascript:gs.beginningOfLast7Days()')
                    if (match := _DATE_ALIAS.fullmatch(part)) else part for part in parts)


def compare_list_conditions(requested, observed):
    if observed is None or list_conditions(requested) != list_conditions(observed):
        return 'mismatch'
    return 'exact' if _ordered_conditions(requested) == _ordered_conditions(observed) else 'known_alias'


class ListStateError(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        message = ('Nie rozpoznano przycisku następnej strony.' if reason == 'missing_pager' else
                   'Nie udało się odczytać kompletnej, spójnej listy (' + reason + ').')
        super().__init__(message + ' Nie zapisano częściowego wyniku.')


def button_selector(direction):
    english, polish = ('First page', 'Pierwsza strona') if direction == 'first' else ('Next page', 'Następna strona')
    return ', '.join(f'{tag}[{attribute}{operator}"{value}" i]'
        for tag in ('button', 'a')
        for attribute, operator, value in (
            ('data-type', '=', 'list_nav_' + direction),
            ('title', '*=', english), ('aria-label', '*=', english),
            ('title', '*=', polish), ('aria-label', '*=', polish),
            ('onclick', '*=', direction + 'Page')))


def disabled(button):
    return button.evaluate("""el => !el.isConnected || !!(el.disabled ||
        el.getAttribute('aria-disabled') === 'true' ||
        el.closest('[disabled], [aria-disabled=true], .disabled'))""")


@dataclass(frozen=True)
class ListState:
    identity: tuple
    first: int | None
    last: int | None
    total: int | None
    size: int | None
    count: int
    busy: bool
    cursor: int | None
    next_disabled: bool | None
    first_disabled: bool | None
    has_pager: bool
    query: str | None = field(default=None, compare=False)

    @property
    def ranged(self):
        return any(value is not None for value in (self.first, self.last, self.total, self.size))


class _FrameView:
    def __init__(self, target):
        self.target = target

    @property
    def url(self):
        return self.target.frame.url

    def locator(self, selector):
        if selector == 'table:visible':
            return self.target.table
        return self.target.container.locator(selector)

    def get_by_text(self, *args, **kwargs):
        return self.target.container.get_by_text(*args, **kwargs)


class ListView:
    """The collector sees only the selected table, not sibling lists/frames."""
    def __init__(self, target):
        self.frames = [_FrameView(target)]


class ListTarget:
    def __init__(self, frame, table, container):
        self.frame, self.table, self.container = frame, table, container
        self.view = ListView(self)

    @classmethod
    def find(cls, page, url):
        expected_path = urlparse(url).path
        expected_table = expected_path.removeprefix('/').removesuffix('_list.do')
        matches = []
        for frame in page.frames:
            if not trusted_url(frame.url) or urlparse(frame.url).path != expected_path:
                continue
            if frame.parent_frame is not None and not frame.frame_element().is_visible():
                continue
            tables = frame.locator('table:visible')
            descriptors = tables.evaluate_all("""tables => tables.map(t => ({
                id: t.id, list: t.getAttribute('data-list_id'), type: t.getAttribute('glide_table'),
                classic: t.classList.contains('list_table'),
                number: [...t.querySelectorAll('th')].some(h => h.closest('table') === t &&
                    (/^(?:(?:incident|sc_task|sc_request|sc_req_item)\\.)?number$/.test(h.getAttribute('glide_field') || h.getAttribute('name') || '') ||
                     /^(Numer|Number)$/i.test(h.textContent.trim())))
            }))""")
            for index, info in enumerate(descriptors):
                if info['type'] and info['type'] != expected_table:
                    continue
                if not info['classic'] and not info['number']:
                    continue
                table = frame.locator('table[id=' + json.dumps(info['id']) + ']') if info['id'] else tables.nth(index)
                container = table.locator("xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' list-container ')][1]")
                if not container.count():
                    container = table.locator("xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' tabs2_list ')][1]")
                if not container.count():
                    container = frame.locator('body')
                primary = info['list'] == expected_table or info['id'] == expected_table + '_table'
                matches.append((2 if primary else 1, cls(frame, table, container)))
        if matches:
            best = max(score for score, _ in matches)
            matches = [target for score, target in matches if score == best]
        if len(matches) > 1:
            raise ListStateError('ambiguous_list')
        return matches[0] if matches else None

    def button(self, direction):
        buttons = self.container.locator(button_selector(direction))
        visible = [buttons.nth(i) for i in range(buttons.count()) if buttons.nth(i).is_visible()]
        states = [bool(disabled(button)) for button in visible]
        if states and any(state != states[0] for state in states):
            raise ListStateError('pager_disagreement')
        return (visible[0], states[0]) if visible else (None, None)

    def cursor(self):
        fields = self.container.locator(ROW_INPUT)
        visible = [fields.nth(i) for i in range(fields.count()) if fields.nth(i).is_visible()]
        values = [field.input_value(timeout=500).strip() for field in visible]
        if any(not value.isdigit() for value in values) or len(set(values)) > 1:
            raise ListStateError('pager_disagreement')
        return (visible[0], int(values[0])) if visible else (None, None)

    def state(self):
        raw = self.table.evaluate("""t => {
            const visible = el => !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
            const headers = [...t.querySelectorAll('th')].filter(h => h.closest('table') === t && visible(h) &&
                !h.closest('.list_header_search_row'));
            const number = headers.find(h => /^(?:(?:incident|sc_task|sc_request|sc_req_item)\\.)?number$/.test(
                h.getAttribute('glide_field') || h.getAttribute('name') || '') || /^(Numer|Number)$/i.test(h.textContent.trim()));
            const rows = [...t.rows].filter(r => r.closest('table') === t && visible(r) && number &&
                r.cells[number.cellIndex]?.tagName === 'TD' && [...r.cells[number.cellIndex].querySelectorAll('a')]
                    .some(a => visible(a) && /^(INC|SCTASK|REQ|RITM)\\d+$/i.test(a.innerText.trim())));
            return {id: t.id, list: t.getAttribute('data-list_id'), query: t.getAttribute('query'),
                sort: t.getAttribute('sort'), direction: t.getAttribute('sort_dir'),
                first: t.getAttribute('first_row'), last: t.getAttribute('last_row'),
                total: t.getAttribute('total_rows'), size: t.getAttribute('rows_per_page'),
                count: rows.length, busy: t.getAttribute('aria-busy') === 'true'};
        }""", timeout=1000)
        def integer(key):
            value = raw[key]
            if value is None:
                return None
            if not value.isdigit():
                raise ListStateError('invalid_metadata')
            return int(value)
        _, next_disabled = self.button('next')
        _, first_disabled = self.button('first')
        has_pager = bool(self.container.locator(PAGER).count()) or next_disabled is not None or first_disabled is not None
        if has_pager and next_disabled is None and raw['total'] != '0':
            raise ListStateError('missing_pager')
        _, cursor = self.cursor()
        return ListState((raw['id'], raw['list'], list_conditions(raw['query']), raw['sort'], raw['direction']),
            *(integer(key) for key in ('first', 'last', 'total', 'size')), raw['count'],
            raw['busy'], cursor, next_disabled, first_disabled, has_pager, query=raw['query'])
