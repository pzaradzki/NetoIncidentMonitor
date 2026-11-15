"""Bind ServiceNow list metadata to one visible classic table."""
import json
import re
from urllib.parse import urlparse

from neto_incident_monitor.service_now_urls import trusted_url

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
    """The matching ServiceNow table could not be identified uniquely."""


class ListTarget:
    def __init__(self, frame, table):
        self.frame, self.table = frame, table

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
                primary = info['list'] == expected_table or info['id'] == expected_table + '_table'
                matches.append((2 if primary else 1, cls(frame, table)))
        if matches:
            best = max(score for score, _ in matches)
            matches = [target for score, target in matches if score == best]
        if len(matches) > 1:
            raise ListStateError('ambiguous_list')
        return matches[0] if matches else None
