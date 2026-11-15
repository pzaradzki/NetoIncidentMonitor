"""Read the signed-in user's complete navigator favorites in one request."""
from neto_incident_monitor import analytics_api
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError


MAX_NODES = 1000
MAX_GROUP_DEPTH = 8


class FavoritesPayloadError(DashboardReadError):
    def __init__(self, reason, check):
        super().__init__(reason, retryable=False)
        self.check = check


def read_favorites(page, stop, diagnostics):
    reply = analytics_api.get(page, stop, diagnostics, 'favorites', analytics_api.FAVORITES_ROUTE, {})
    rows, seen = [], set()
    group_count = 0

    def collect(nodes, groups):
        nonlocal group_count
        if not isinstance(nodes, list):
            raise FavoritesPayloadError('api_schema', 'shape')
        if len(nodes) > MAX_NODES - len(seen):
            raise FavoritesPayloadError('api_incomplete', 'limit')
        for node in nodes:
            if len(seen) >= MAX_NODES:
                raise FavoritesPayloadError('api_incomplete', 'limit')
            if not isinstance(node, dict):
                raise FavoritesPayloadError('api_schema', 'shape')
            identity, title = node.get('id'), node.get('title')
            if not all(isinstance(value, str) and value.strip() for value in (identity, title)):
                raise FavoritesPayloadError('api_schema', 'fields')
            identity = identity.strip()
            if identity in seen:
                raise FavoritesPayloadError('api_incomplete', 'record_identity')
            seen.add(identity)
            if 'favorites' in node:
                if node.get('url') not in (None, ''):
                    raise FavoritesPayloadError('api_schema', 'shape')
                if len(groups) >= MAX_GROUP_DEPTH:
                    raise FavoritesPayloadError('api_incomplete', 'limit')
                group_count += 1
                collect(node['favorites'], (*groups, title.strip()))
            else:
                href = node.get('url')
                if not isinstance(href, str) or not href.strip():
                    raise FavoritesPayloadError('api_schema', 'fields')
                rows.append({'source_id': identity, 'name': title.strip(), 'href': href,
                             'groups': list(groups)})

    try:
        if reply['next'] or reply.get('total') is not None:
            raise FavoritesPayloadError('api_incomplete', 'next_page')
        result = reply['result']
        if not isinstance(result, dict):
            raise FavoritesPayloadError('api_schema', 'shape')
        collect(result.get('favorites'), ())
    except FavoritesPayloadError as error:
        measured_record(diagnostics, 'favorites_api_result', outcome='error', read_reason=error.reason,
                        api_list_check=error.check, item_count=len(rows), group_count=group_count)
        raise
    measured_record(diagnostics, 'favorites_api_result', outcome='returned', item_count=len(rows),
                    group_count=group_count)
    return rows
