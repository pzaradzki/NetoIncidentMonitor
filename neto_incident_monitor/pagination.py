"""Read complete classic ServiceNow lists; never return a partial traversal."""
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import re
from neto_incident_monitor.service_now_urls import normalize_list_url, trusted_url, is_short_url, resolved_list_url, LIST_PATHS


class AuthenticationRequired(Exception):
    pass


class Cancelled(Exception):
    pass


class LargeListRejected(Exception):
    pass


def list_total(page, url):
    """Read the visible classic list pager, never a number from a task row."""
    for frame in page.frames:
        if not trusted_url(frame.url) or urlparse(frame.url).path != urlparse(url).path:
            continue
        texts = frame.locator('.list2_paging, [data-type="list_nav_total"], [id$="_total_rows"]').evaluate_all(
            "els => els.filter(el => el.getClientRects().length).map(el => el.innerText || el.textContent)")
        for text in texts:
            match = re.search(r'(?:\bz\s+|\bof\s+)([\d\s\u00a0,.]+)', text, re.I)
            value = match.group(1) if match else text.strip()
            if re.fullmatch(r'[\d\s\u00a0,.]+', value):
                digits = re.sub(r'\D', '', value)
                if digits:
                    return int(digits)
    return None


def first_page(url):
    url = normalize_list_url(url)
    if is_short_url(url):
        return url
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key != "sysparm_first_row"]
    query.append(("sysparm_first_row", "1"))
    return urlunparse(parsed._replace(query=urlencode(query)))


def navigation_button(page, direction):
    for frame in page.frames:
        if not trusted_url(frame.url) or urlparse(frame.url).path not in LIST_PATHS:
            continue
        english, polish = ("First page", "Pierwsza strona") if direction == "first" else ("Next page", "Następna strona")
        selector = ", ".join(
            f'{tag}[{attribute}{operator}"{value}" i]'
            for tag in ("button", "a")
            for attribute, operator, value in (
                ("data-type", "=", f"list_nav_{direction}"),
                ("title", "*=", english), ("aria-label", "*=", english),
                ("title", "*=", polish), ("aria-label", "*=", polish),
                ("onclick", "*=", f"{direction}Page")))
        buttons = frame.locator(selector)
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if not button.is_visible():
                continue
            disabled = button.evaluate("""el => !!(el.disabled || el.getAttribute('aria-disabled') === 'true'
                || el.closest('[disabled], [aria-disabled=true], .disabled'))""")
            return button, disabled
    return None, False


def next_button(page):
    return navigation_button(page, "next")


def row_input(page):
    for frame in page.frames:
        if not trusted_url(frame.url) or urlparse(frame.url).path not in LIST_PATHS:
            continue
        inputs = frame.locator('input.list2_page, input.list_row_number_input, input[data-type="list_nav_input"], input[name="sysparm_first_row"]')
        for index in range(inputs.count()):
            control = inputs.nth(index)
            if control.is_visible():
                value = control.input_value().strip()
                if value.isdigit():
                    return control, int(value)
    return None, None


def activate_pager(button, stop):
    """Use a bounded input action, skipping animation/stability checks."""
    from neto_incident_monitor.browser_actions import checkpoint
    checkpoint(stop)
    disabled = button.evaluate("""el => !el.isConnected || !!(el.disabled
        || el.getAttribute('aria-disabled') === 'true'
        || el.closest('[disabled], [aria-disabled=true], .disabled'))""")
    if disabled:
        raise RuntimeError('Przycisk paginacji nie jest gotowy. Nie zapisano częściowego wyniku.')
    # Do not evaluate el.click(): synchronous page handlers can block that
    # evaluation indefinitely. Never retry an input whose delivery is uncertain.
    button.click(force=True, timeout=5000, no_wait_after=True)
    checkpoint(stop)


PAGE_WAIT_SECONDS = 15
MAX_READ_SECONDS = 1800
MAX_ATTEMPTS = 2
PREFERRED_PAGE_SIZE = 100
PAGE_SIZE_CONFIRM_SECONDS = 4


def select_page_size(target, check):
    """Use the classic list menu once, leaving confirmation to the reader."""
    from playwright.sync_api import Error
    from playwright._impl._errors import TargetClosedError
    from neto_incident_monitor.read_budget import BudgetExpired, remaining_ms

    action = target.container.locator('button[id$="_control_button"]').filter(visible=True)
    if action.count() != 1 or not action.is_enabled(timeout=remaining_ms(750)):
        return 'control_unavailable'
    show = target.frame.get_by_role('menuitem', name=re.compile(r'^Pokaż(?:\s|$)')).filter(visible=True)
    option = target.frame.get_by_role('menuitem', name=f'{PREFERRED_PAGE_SIZE} wiersz./str.',
                                      exact=True).filter(visible=True)
    selecting = False
    try:
        check()
        action.click(timeout=remaining_ms(1200), no_wait_after=True)
        show.wait_for(state='visible', timeout=remaining_ms(1000))
        check()
        if show.get_attribute('aria-expanded', timeout=remaining_ms(750)) != 'true':
            show.press('ArrowRight', timeout=remaining_ms(1000))
        option.wait_for(state='visible', timeout=remaining_ms(1000))
        check()
        selecting = True
        option.click(timeout=remaining_ms(1200), no_wait_after=True)
    except (BudgetExpired, TargetClosedError):
        raise
    except Error:
        return 'click_uncertain' if selecting else 'menu_unavailable'
    return 'requested'


def _metadata_reason(state, rows, expected_first, total, size):
    if state.busy:
        return 'loading'
    if not state.ranged:
        if state.has_pager or state.next_disabled is not None:
            return 'missing_pager' if state.next_disabled is None else 'metadata_missing'
        return 'metadata_missing'
    if any(v is None for v in (state.first, state.last, state.total, state.size)):
        return 'metadata_missing'
    if state.size < 1 or state.first < 1 or state.total < 0 or state.last > state.total:
        return 'invalid_metadata'
    if total is not None and (state.total != total or state.size != size):
        return 'list_changed'
    if state.first != expected_first:
        return 'range_mismatch'
    if state.cursor is not None and state.cursor != state.first:
        return 'pager_disagreement'
    expected_count = max(0, state.last - state.first + 1)
    if state.total == 0:
        return None if state.first == 1 and state.last == 0 and not rows and state.count == 0 else 'row_count_mismatch'
    if expected_count < 1 or expected_count > state.size:
        return 'invalid_metadata'
    if state.last != min(state.first + state.size - 1, state.total):
        return 'range_mismatch'
    if state.count != expected_count or len(rows) != expected_count:
        return 'row_count_mismatch'
    if state.has_pager and state.next_disabled is None:
        return 'missing_pager'
    if state.last < state.total and state.next_disabled is not False:
        return 'premature_end'
    if state.last == state.total and state.next_disabled is False:
        return 'pager_disagreement'
    return None


def _read_attempt(page, url, stop, collect, authentication_page, navigate,
                  stage, emit, approve, progress, budget, change_page_size):
    from time import monotonic
    from playwright.sync_api import TimeoutError
    from neto_incident_monitor.browser_actions import checkpoint
    from neto_incident_monitor.list_context import ListTarget, ListStateError, compare_list_conditions

    def check(authenticate=True):
        checkpoint(stop)
        if page.is_closed() is True:
            from playwright._impl._errors import TargetClosedError
            raise TargetClosedError()
        if authenticate and authentication_page(page, url):
            raise AuthenticationRequired()
        if monotonic() >= budget.end:
            raise ListStateError('read_timeout')

    stage('navigate', 1)
    check(authenticate=page.url != 'about:blank')
    navigate(page, first_page(url))
    if is_short_url(url):
        stage('resolve_url', 1)
        until = min(budget.end, monotonic() + PAGE_WAIT_SECONDS)
        while monotonic() < until:
            check()
            direct = resolved_list_url(page, url)
            if direct:
                url = direct
                navigate(page, first_page(url))
                break
            page.wait_for_timeout(100)
        else:
            raise ListStateError('resolve_timeout')

    from urllib.parse import parse_qs
    requested_parameters = parse_qs(urlparse(url).query, keep_blank_values=True)
    requested_queries = requested_parameters.get("sysparm_query", [])
    requested_views = requested_parameters.get("sysparm_view", [])
    comparisons_logged = set()

    def wait_page(index, first, total=None, size=None, identity=None, allow_restored=False,
                  prepare_size=False, confirm_size_until=None):
        stage('read_rows', index)
        until = min(budget.end, monotonic() + PAGE_WAIT_SECONDS)
        stable, repeats, reason = None, 0, 'page_unavailable'
        last_observation = None
        while monotonic() < until:
            check()
            try:
                target = ListTarget.find(page, url)
                if target is None:
                    stable, repeats = None, 0
                    page.wait_for_timeout(250)
                    continue
                before = target.state()
                if requested_views and requested_views != [""]:
                    observed_views = parse_qs(urlparse(target.frame.url).query, keep_blank_values=True).get("sysparm_view", [])
                    if len(requested_views) != 1 or observed_views != requested_views:
                        raise ListStateError("view_mismatch")
                if requested_queries:
                    comparison = (compare_list_conditions(requested_queries[0], before.query)
                                  if len(requested_queries) == 1 else 'mismatch')
                    if comparison not in comparisons_logged:
                        emit('pagination_query_comparison', page_index=index, query_comparison=comparison,
                             query_alias='last_7_days' if comparison == 'known_alias' else 'none')
                        comparisons_logged.add(comparison)
                    if comparison == 'mismatch':
                        raise ListStateError("query_mismatch" if identity is None else "list_changed")
                if identity is not None and not before.busy and before.identity != identity:
                    raise ListStateError('list_changed')
                if (confirm_size_until is not None and before.size != PREFERRED_PAGE_SIZE
                        and monotonic() < confirm_size_until):
                    page.wait_for_timeout(100)
                    continue
                if (prepare_size and not before.busy and before.size is not None
                        and before.size > 0 and before.size != PREFERRED_PAGE_SIZE):
                    return target, before, None
                if allow_restored and not before.busy and (
                        (before.first is not None and before.first > 1) or
                        (before.cursor is not None and before.cursor > 1) or before.first_disabled is False):
                    return target, before, None
                rows = collect(target.view)
                after = target.state()
                if before != after:
                    reason, stable, repeats = 'document_changed', None, 0
                else:
                    reason = _metadata_reason(after, rows, first, total, size)
                    if identity is not None and after.identity != identity:
                        reason = 'list_changed'
                    if not rows and after.total != 0:
                        reason = reason or 'page_unavailable'
                    observation = (reason, after.first, after.last, after.total, after.size, after.count,
                                   after.next_disabled, after.busy)
                    if observation != last_observation:
                        emit('pagination_state', page_index=index, pagination_reason=reason or 'ready',
                             first_row=after.first, last_row=after.last, total_rows=after.total,
                             page_size=after.size, row_count=after.count, loading=after.busy)
                        last_observation = observation
                    if reason == 'list_changed':
                        raise ListStateError(reason)
                    if reason:
                        stable, repeats = None, 0
                    else:
                        signature = (after, rows)
                        repeats = repeats + 1 if signature == stable else 1
                        stable = signature
                        if repeats >= 3:
                            return target, after, rows
            except ListStateError as error:
                if error.reason in ('list_changed', 'record_type_mismatch', 'schema_changed', 'query_mismatch', 'view_mismatch'):
                    raise
                reason, stable, repeats = error.reason, None, 0
                observation = (reason,)
                if observation != last_observation:
                    emit('pagination_state', page_index=index, pagination_reason=reason)
                    last_observation = observation
            except Exception as error:
                if isinstance(error, (Cancelled, AuthenticationRequired)):
                    raise
                from neto_incident_monitor.login_diagnostics import error_facts
                category = error_facts(error)['error_category']
                if isinstance(error, TimeoutError) or category in ('document_changed', 'element_unavailable'):
                    reason, stable, repeats = 'document_changed', None, 0
                else:
                    raise
            page.wait_for_timeout(250)
        check()
        raise ListStateError(reason or 'page_timeout')

    target, state, rows = wait_page(1, 1, allow_restored=True, prepare_size=change_page_size is not None)
    resized_from = None
    if (rows is None and change_page_size is not None and state.size is not None
            and 0 < state.size != PREFERRED_PAGE_SIZE):
        resized_from = state
        stage('page_size', 1)
        emit('pagination_page_size', page_index=1, page_size=state.size, page_size_result='checking_menu')
        selection = change_page_size(target, check)
        check()
        confirming = selection in ('requested', 'click_uncertain')
        if selection == 'menu_unavailable':
            # Reopen the same list to dismiss a partially opened menu.
            navigate(page, first_page(url))
        target, state, rows = wait_page(1, 1, identity=resized_from.identity, allow_restored=True,
            confirm_size_until=min(budget.end, monotonic() + PAGE_SIZE_CONFIRM_SECONDS) if confirming else None)
        result = 'confirmed' if state.size == PREFERRED_PAGE_SIZE else 'unconfirmed' if confirming else selection
        emit('pagination_page_size', page_index=1, page_size=state.size, page_size_result=result,
             previous_page_size=resized_from.size)
    if rows is None:
        stage('first_page', 1)
        emit('pagination_action', pager_direction='first', page_index=1)
        button, is_disabled = target.button('first')
        if button is not None and not is_disabled:
            activate_pager(button, stop)
        else:
            cursor, _ = target.cursor()
            if cursor is None:
                raise ListStateError('missing_pager')
            cursor.fill('1', timeout=1000)
            cursor.press('Enter', timeout=1000, no_wait_after=True)
        if progress:
            progress(0, 0)
        target, state, rows = wait_page(1, 1, identity=resized_from.identity if resized_from else None)
    emit('pagination_bound', pagination_mode='ranged' if state.ranged else 'unpaginated',
         page_size=state.size, total_rows=state.total)
    identity, total, size = state.identity, state.total, state.size
    result, index = {}, 1
    while True:
        check()
        if set(result).intersection(rows):
            raise ListStateError('overlapping_rows')
        result.update(rows)
        approve(total if total is not None else len(result))
        emit('pagination_page', page_index=index, first_row=state.first, last_row=state.last,
             total_rows=total, page_size=size, row_count=len(rows), records_read=len(result))
        if progress:
            progress(index, len(result))
        finished = not state.ranged or state.last == total or total == 0
        if finished:
            stage('verify_complete', index)
            # Re-observe after callbacks (including the large-list prompt).
            check()
            if target.state() != state or collect(target.view) != rows:
                raise ListStateError('document_changed')
            if total is not None and len(result) != total:
                raise ListStateError('total_mismatch')
            return result, index
        stage('next_page', index)
        button, is_disabled = target.button('next')
        if button is None or is_disabled:
            raise ListStateError('premature_end')
        emit('pagination_action', pager_direction='next', page_index=index)
        activate_pager(button, stop)
        expected_first = state.last + 1
        index += 1
        target, state, rows = wait_page(index, expected_first, total, size, identity)


def read_all(page, url, stop, collect, empty_list, authentication_page, navigate, progress=None,
             approve_large=None, on_stage=None, diagnostics=None, filter_index=None):
    """Return only a validated traversal; discard and restart one inconsistent read."""
    from time import monotonic
    from neto_incident_monitor.browser_actions import checkpoint
    from neto_incident_monitor.list_context import ListStateError
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts
    diagnostics = diagnostics or LoginDiagnostics(source='pagination', filter_index=filter_index)
    started = monotonic()
    from neto_incident_monitor.read_budget import Budget, CURRENT, budget_scope
    budget = CURRENT.get() or Budget(MAX_READ_SECONDS)
    current_stage, current_page = 'navigate', 1
    stage_started = started
    approved = False
    page_size_attempted = False
    diagnostic_warning = False

    def emit(event, **facts):
        nonlocal diagnostic_warning
        try:
            diagnostics.record(event, pagination_stage=current_stage, **facts)
        except Exception:
            if not diagnostic_warning:
                diagnostic_warning = True
                try:
                    import logging
                    logging.getLogger('servicenow').warning('Nie udało się zapisać diagnostyki paginacji.')
                except Exception:
                    pass  # A diagnostic sink must not change the traversal outcome.

    def stage(name, index):
        nonlocal current_stage, current_page, stage_started
        if (name, index) != (current_stage, current_page):
            now = monotonic()
            emit('pagination_stage_complete', page_index=current_page,
                 duration_ms=round((now - stage_started) * 1000))
            stage_started = now
        current_stage, current_page = name, index
        if on_stage:
            on_stage(name, index)

    def approve(total):
        nonlocal approved
        if approve_large is not None and total > 1000 and not approved:
            stage('list_total', current_page)
            waiting_since = monotonic()
            try:
                accepted = approve_large(total)
            finally:
                waited = monotonic() - waiting_since
                budget.end += waited
                emit("pagination_approval_wait", duration_ms=round(waited * 1000))
            if not accepted:
                raise LargeListRejected()
            approved = True

    def change_page_size(target, check):
        nonlocal page_size_attempted
        page_size_attempted = True
        return select_page_size(target, check)

    emit('pagination_start')
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            checkpoint(stop)
            emit('pagination_attempt', attempt=attempt)
            try:
                with budget_scope(budget):
                    result = _read_attempt(page, url, stop, collect, authentication_page,
                        navigate, stage, emit, approve, progress, budget,
                        None if page_size_attempted else change_page_size)
                emit('pagination_complete', attempt=attempt, records_read=len(result[0]),
                     page_count=result[1], duration_ms=round((monotonic() - started) * 1000))
                return result
            except Exception as error:
                category = error_facts(error)['error_category']
                retry = isinstance(error, ListStateError) or category in (
                    'timeout', 'document_changed', 'element_unavailable', 'network_connection')
                if isinstance(error, (Cancelled, AuthenticationRequired, LargeListRejected)) or not retry:
                    raise
                if attempt == MAX_ATTEMPTS or monotonic() >= budget.end:
                    raise
                emit('pagination_retry', attempt=attempt, page_index=current_page,
                     pagination_reason=error.reason if isinstance(error, ListStateError) else category,
                     **error_facts(error))
                stage('retry', current_page)
                if progress:
                    progress(0, 0)
                # Restart the whole read from row 1; never repeat an uncertain
                # Next click or combine rows from different attempts.
        raise ListStateError('read_timeout')
    except Cancelled:
        emit('pagination_cancelled', duration_ms=round((monotonic() - started) * 1000))
        raise
    except AuthenticationRequired:
        emit('pagination_waiting_login')
        raise
    except Exception as error:
        emit('pagination_error', page_index=current_page,
             pagination_reason=error.reason if isinstance(error, ListStateError) else
                 'large_list_rejected' if isinstance(error, LargeListRejected) else 'unexpected',
             duration_ms=round((monotonic() - started) * 1000), **error_facts(error))
        raise
