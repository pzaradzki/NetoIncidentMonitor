"""Bounded login diagnostics containing structural facts, never form values."""
import json
import logging
from neto_incident_monitor.safe_logging import DiagnosticFileHandler
from threading import Lock
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4
from contextvars import ContextVar

from neto_incident_monitor.runtime_paths import DATA

_lock = Lock()
_logger = logging.getLogger('neto.login_diagnostics')
_logger.propagate = False
_logger.setLevel(logging.INFO)
TRACE = ContextVar('authentication_trace', default=None)
READ = ContextVar('diagnostic_read', default=None)
RUN_ID = uuid4().hex


def diagnostic_read(function):
    # A new actual execution gets an ID even when periodic work reuses a UI ID.
    from functools import wraps
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = READ.set(uuid4().hex)
        try:
            return function(*args, **kwargs)
        finally:
            READ.reset(token)
    return wrapped


from neto_incident_monitor.login_observation import SIGNALS as SNAPSHOT

FIELDS = ('password_count', 'password_filled', 'password_enabled', 'password_autofilled',
          'password_manual_edit', 'identity_count', 'identity_locked', 'login_button_count',
          'login_button_enabled', 'account_count', 'welcome', 'intervention', 'document_ready')

# Only explicitly approved structural fields may reach disk. Unknown text is
# discarded rather than redacted after the fact.
NUMERIC_FIELDS = set(FIELDS) | {'manual_account_selections', 'window_visible', 'foreground_confirmed', 'auto_login', 'minimize', 'hidden', 'minimize_browser', 'hide_browser', 'elapsed_s',
    'auto_blocked', 'auto_submitted', 'account_selected', 'blocked', 'supported_origin',
    'password_ready', 'button_count', 'aria_or_class_disabled', 'attempt',
    'delivery_observer', 'timeout_ms', 'delay_s', 'automatic_blocked', 'autofilled',
    'locked_account', 'manual', 'submitted', 'frame_count', 'page_count', 'http_status', 'reused', 'loading', 'button_available', 'widget_count', 'activated_count',
    'filter_index', 'outside_schedule', 'page_index', 'first_row', 'last_row', 'total_rows', 'page_size', 'previous_page_size',
    'row_count', 'records_read', 'duration_ms', 'request_id', 'expected_count', 'ready_count', 'tile_index', 'lateness_ms', 'year', 'month', 'os_errno', 'winerror', 'context_confirmed', 'category_count', 'active_ms', 'login_wait_ms', 'final_failure', 'ack_count', 'payload_bytes', 'cleanup_errors', 'document_generation', 'session_signal', 'logout_signal', 'authentication_path'}
TEXT_FIELDS = {
    'queue_scope': {'all', 'dashboard', 'threatened', 'filter', 'favorites'},
    'queue_state': {'queued', 'merged', 'running', 'waiting_login', 'finished', 'cancelled'},
    'visibility_reason': {'initial_login', 'login_required', 'reconnect', 'session_confirmed', 'initial_main_window'},
    'url_kind': {'direct', 'wrapper', 'short'},
    'validation_result': {'accepted', 'rejected'},
    'validation_reason': {'none', 'unsafe', 'unsupported_target', 'conflicting_parameters'},
    'query_comparison': {'exact', 'known_alias', 'mismatch'},
    'query_alias': {'none', 'last_7_days'},
    'request_state': {'queued', 'running', 'retrying', 'finished', 'cancelled',
                      'queue_error', 'locked', 'unlocked', 'blocked', 'idle_changed',
                      'stale_id', 'period_mismatch'},
    'rendering_scope': {'dashboard', 'login', 'favorites'},
    'recovery_reason': {'logout', 'network', 'stalled', 'popup_closed'},
    'login_state': {'authentication', 'session', 'target', 'unknown', 'logout'},
    'previous_login_state': {'authentication', 'session', 'target', 'unknown', 'logout', 'initial'},
    'login_evidence': {'logout_document', 'authentication_surface', 'observation_failed', 'session_confirmed', 'session_unconfirmed', 'context_unconfirmed'},
    'login_surface': {'main', 'owned_popup'},
    'rendering_reason': {'start_failed', 'ack_failed', 'context_left', 'authentication', 'session_unconfirmed', 'page_closed', 'not_needed', 'page_changed', 'read_finished', 'runtime_closed'},
    'refresh_mode': {'observed','document_fallback'},
    'read_reason': {'rendering_unavailable', 'wrong_dashboard','wrong_tab','wrong_period','wrong_filter','ambiguous_period',
                    'ambiguous_widget','incomplete_widgets','definition_changed','timeout','document_changed',
                    'navigation_interrupted','network_connection','network_dns','element_unavailable','unexpected',
                    'authentication_required'},
    'cache_result': {'saved','failed','restored','invalid','skipped'},
    'delay_reason': {'filter','dashboard','login','browser','idle'},
    'outcome': {'returned', 'error', 'cancelled', 'authentication'},
    'wait_reason': {'loading', 'missing', 'invalid', 'unstable', 'ready', 'observation_failed'},
    'risk_tile': {'P1', 'P2', 'P3', 'P4', 'P5', 'Podjęcie'},
    'tile': {'Otwarte wnioski L1', 'Wnioski L1 >7 dni', 'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1', 'Wnioski Smartfon – start >3 dni'},
    'tile_state': {'ready', 'missing', 'ambiguous', 'invalid', 'unavailable', 'loading'},
    'score_source': {'widget_value', 'button', 'none'},
    'activity': {'login', 'dashboard', 'filters'},
    'readiness_reason': {'covered', 'unstable', 'disabled', 'hidden', 'detached', 'outside_viewport', 'unavailable'},
    'origin': {'adeo_identity', 'servicenow', 'other'},
    'filter_outcome': {'success', 'error', 'cancelled', 'discarded', 'waiting_login', 'interrupted', 'rejected'},
    'source': {'dashboard', 'monitor', 'pagination', 'configuration'},
    'pagination_stage': {'navigate', 'resolve_url', 'read_rows', 'first_page', 'list_total', 'page_size',
                         'next_page', 'verify_complete', 'retry', 'prepare', 'history_write'},
    'pagination_mode': {'ranged', 'unpaginated'},
    'page_size_result': {'checking_menu', 'confirmed', 'unconfirmed', 'menu_unavailable', 'control_unavailable'},
    'pager_direction': {'first', 'next'},
    'pagination_reason': {'ready', 'loading', 'page_unavailable', 'ambiguous_list',
        'pager_disagreement', 'invalid_metadata', 'metadata_missing', 'range_mismatch',
        'row_count_mismatch', 'record_type_mismatch', 'schema_changed', 'query_mismatch', 'view_mismatch', 'list_changed', 'missing_pager', 'premature_end',
        'overlapping_rows', 'total_mismatch', 'document_changed', 'page_timeout',
        'read_timeout', 'resolve_timeout', 'large_list_rejected', 'unexpected',
        'timeout', 'element_unavailable', 'network_connection'},
    'section': {'sla', 'held', 'requests', 'threatened'},
    'category': {'status', 'location', 'assigned', 'agent', 'other'},
    'category_state': {'mixed', 'none', 'all'},
    'operation': {'document_ready', 'navigate', 'open_tab', 'open_period', 'fill_start', 'fill_end', 'period_ready', 'commit_period', 'period_confirm', 'refresh_cards', 'category_select', 'category_apply', 'category_confirm', 'prepare_widgets', 'read_scores'},
    'network_error': {'aborted', 'timeout', 'dns', 'connection', 'certificate', 'other'},
    'error_category': {'timeout', 'browser_closed', 'profile_locked', 'browser_missing',
        'access_denied', 'network_dns', 'network_connection', 'network_tls',
        'document_changed', 'navigation_interrupted', 'ambiguous_locator', 'element_unavailable', 'file_access', 'unexpected'},
    'delivery': {'observed', 'not_observed', 'unknown'},
    'error_type': {'Error', 'TimeoutError', 'TargetClosedError', 'RuntimeError',
                   'ValueError', 'OSError', 'PermissionError', 'LoginTargetUnavailable'},
    'reason': {'wykryto ręczną obsługę formularza', 'wymagany wybór spośród wielu kont',
        'logowanie w osobnym oknie wymaga obsługi użytkownika',
        'formularz zawiera wiele pól hasła', 'formularz logowania został zastąpiony',
        'pole hasła nie zostało rozpoznane jako autouzupełnione',
        'strona wymaga interwencji użytkownika lub zgłasza błąd',
        'brak zakończenia logowania przez 30 sekund po zatwierdzeniu',
        'nie udało się wykonać kliknięcia logowania po trzech próbach',
        'wybór konta nie przeszedł do formularza po trzech próbach',
        'wybór konta nie spowodował przejścia do formularza',
        'nierozpoznany krok logowania wymaga obsługi użytkownika'},
}
EVENTS = set('''threatened_details_complete threatened_details_incomplete browser_visibility_repaired login_recovery login_user_required login_form_changed account_awaiting_result login_state_changed rendering_start rendering_stop rendering_error rendering_deferred category_check_recovered category_check_failed category_partial_resolved dashboard_context dashboard_refresh section_read_retry dashboard_cache threatened_schedule browser_cleanup_error dashboard_stage_end dashboard_observation pagination_start pagination_attempt pagination_bound pagination_state pagination_page pagination_stage_complete
filter_read_start filter_read_resumed filter_read_end filter_read_error filter_links_degraded filter_commit_start filter_commit_complete
filter_url_validation pagination_query_comparison pagination_approval_wait pagination_action pagination_page_size pagination_retry pagination_complete pagination_error pagination_cancelled pagination_waiting_login
start blocked automatic_skipped awaiting_submission_result dashboard_widgets_retry
waiting_password_fill waiting_remembered_form submit_unavailable submit_retry_cancelled
submit_attempt submit_error submit_retry_scheduled submit_clicked account_selection_ambiguous
account_click_attempt account_click_error account_waiting_ready submit_waiting_ready account_clicked browser_closed automatic_login_step_error
manual_login_show_attempt manual_login_shown manual_login_show_retry manual_login_show_failed
target_unavailable login_complete reopen_requested_list login_loop_error login_cancelled
page_state login_still_waiting inspection_error section_read_attempt section_read_complete section_read_partial
dashboard_scores_attempt dashboard_scores_error dashboard_scores_retry dashboard_tile_state dashboard_tile_missing dashboard_widgets_activated
session_expired navigation document_response document_failed initial_navigation_attempt initial_navigation_error
authentication_popup dashboard_operation dashboard_navigation section_read_error browser_options_changed browser_activity visibility_deferred authentication_popup_closed session_confirmed browser_launch_attempt browser_launched monitor_error monitor_finished browser_restart_limited browser_restart_delay'''.split())


NUMERIC_FIELDS.update({
    'active_request_id', 'expected_year', 'expected_month'})
EVENTS.update({'dashboard_request_state', 'dashboard_period_state', 'dashboard_result_rejected', 'dashboard_complete'})
EVENTS.add('alert_delivery')
EVENTS.add('startup_validation')
EVENTS.add('dashboard_ui_state')
TEXT_FIELDS['ui_state'] = {'reading', 'retrying', 'waiting_login', 'error'}
EVENTS.update({'section_login_recovery_start', 'section_login_recovery_end'})
EVENTS.update({'session_visibility', 'session_connection_error', 'refresh_queue'})
EVENTS.add('password_save_prompt')
TEXT_FIELDS['password_save_choice'] = {'waiting', 'saved', 'disabled', 'cancelled', 'save_error'}
TEXT_FIELDS['data_area'] = {'configuration', 'history'}
TEXT_FIELDS['validation_result'].update({'invalid', 'unavailable'})
NUMERIC_FIELDS.add('accepted_parts')
NUMERIC_FIELDS.update({'item_count', 'group_count', 'duplicate_count', 'rejected_count'})
TEXT_FIELDS['source'].add('favorites')
TEXT_FIELDS['import_stage'] = {'page', 'open', 'snapshot', 'complete', 'cleanup', 'viewport_read', 'viewport_natural'}
TEXT_FIELDS['import_reason'] = {'unsupported', 'incomplete', 'empty_unconfirmed', 'context',
    'search_changed', 'timeout', 'document_changed', 'navigation_interrupted',
    'network_connection', 'network_dns', 'element_unavailable', 'unexpected'}
EVENTS.update({'browser_cleanup_error', 'favorites_stage', 'favorites_attempt',
    'favorites_login_start', 'favorites_login_end', 'favorites_read_error',
    'favorites_error', 'favorites_end', 'favorites_preview', 'favorites_save_error',
    'favorites_saved', 'favorites_dialog_end'})
TEXT_FIELDS.update({
    'delivery_stage': {'read', 'route', 'claim', 'send', 'finish', 'worker'},
    'delivery_outcome': {'started', 'retry', 'error', 'cancelled', 'complete', 'accepted', 'uncertain'},
    'channel': {'windows', 'teams', 'google_chat'},
})


def readiness_facts(error):
    """Return fixed actionability codes; never retain the Playwright call log."""
    message = str(error).lower()
    reason = next((code for marker, code in (
        ('intercepts pointer events', 'covered'), ('not stable', 'unstable'),
        ('not enabled', 'disabled'), ('not visible', 'hidden'),
        ('not attached', 'detached'), ('outside of the viewport', 'outside_viewport'),
    ) if marker in message), 'unavailable')
    return {'readiness_reason': reason, **error_facts(error)}


def error_facts(error):
    """Classify in memory, retaining neither the message nor URL/form values."""
    message = str(error).lower()
    category = next((code for markers, code in (
        (('targetclosed', 'target page, context or browser has been closed'), 'browser_closed'),
        (('processsingleton', 'profile in use', 'user data directory is already in use'), 'profile_locked'),
        (("executable doesn't exist", 'executable not found'), 'browser_missing'),
        (('err_name_not_resolved',), 'network_dns'),
        (('err_cert_',), 'network_tls'),
        (('err_connection_', 'err_internet_disconnected'), 'network_connection'),
        (('interrupted by another navigation', 'err_aborted'), 'navigation_interrupted'),
        (('execution context was destroyed', 'cannot find context', 'frame was detached', 'frame has been detached'), 'document_changed'),
        (('strict mode violation',), 'ambiguous_locator'),
        (('not attached to the dom', 'element is not visible', 'element is not enabled'), 'element_unavailable'),
        (('access denied', 'permission denied'), 'access_denied'),
        (('timeout', 'timed out'), 'timeout'),
    ) if any(marker in message for marker in markers)), None)
    if category is None:
        category = 'timeout' if type(error).__name__ in ('TimeoutError', 'BudgetExpired') else 'file_access' if isinstance(error, OSError) else 'unexpected'
    return {'error_type': type(error).__name__, 'error_category': category}


def safe_facts(facts):
    from neto_incident_monitor import __version__
    clean = {}
    for key, value in facts.items():
        if key in NUMERIC_FIELDS and type(value) in (bool, int, float):
            clean[key] = value
        elif key in TEXT_FIELDS and isinstance(value, str) and value in TEXT_FIELDS[key]:
            clean[key] = value
        elif key == 'error_type':
            clean[key] = 'Error'
        elif key in ('action_id', 'import_id') and isinstance(value, str):
            import re
            if re.fullmatch(r'[a-f0-9]{32}', value):
                clean[key] = value
        elif key == 'app_version' and value == __version__:
            clean[key] = value
    return clean


class LoginDiagnostics:
    def __init__(self, **options):
        self.context = safe_facts(options)
        self.read_id = READ.get() or uuid4().hex
        self.warned = False
        self.session = uuid4().hex[:12]
        self.started = perf_counter()
        self.previous = {}
        self.sequence = 0
        self.trace = TRACE.get() or uuid4().hex
        self.network_error = None
        self.document_status = None
        from neto_incident_monitor import __version__
        self.record('start', app_version=__version__, **options)

    def attach(self, page):
        def navigation(frame):
            if frame == page.main_frame:
                host = urlparse(frame.url).hostname or ''
                origin = 'adeo_identity' if host.endswith('.adeo.com') else 'servicenow' if host.endswith('.service-now.com') else 'other'
                self.record('navigation', origin=origin)
        def response(result):
            if result.request.resource_type == 'document':
                try:
                    main = result.request.frame == page.main_frame
                except Exception:
                    main = False
                if main:
                    self.document_status = result.status
                    if result.status < 400:
                        self.network_error = None
                self.record('document_response', http_status=result.status)
        def failed(request):
            if request.resource_type == 'document':
                failure = request.failure or ''
                # Convert the browser's message to a fixed category; never store it.
                category = next((code for marker, code in (
                    ('ABORTED', 'aborted'), ('TIMED_OUT', 'timeout'),
                    ('NAME_NOT_RESOLVED', 'dns'), ('CERT_', 'certificate'),
                    ('CONNECTION_', 'connection')) if marker in failure), 'other')
                try:
                    if request.frame == page.main_frame:
                        self.network_error = category
                except Exception:
                    pass
                self.record('document_failed', network_error=category)
        listeners = [('framenavigated', navigation), ('response', response), ('requestfailed', failed)]
        for event, callback in listeners:
            page.on(event, callback)
        def detach():
            for event, callback in listeners:
                try:
                    page.remove_listener(event, callback)
                except Exception:
                    pass  # Browser shutdown must not mask the original outcome.
        return detach

    def record(self, event, **facts):
        try:
            if event not in EVENTS:
                return
            facts = {**self.context, **safe_facts(facts)}
            if event == 'section_read_attempt':
                self.context.update({k: v for k, v in facts.items() if k == 'attempt'})
            # Callers supply fixed event codes and booleans/counts, never DOM text.
            now = perf_counter()
            signature = json.dumps(facts, sort_keys=True)
            previous = self.previous.get(event)
            if previous and previous[0] == signature and now - previous[1] < 10:
                return
            self.previous[event] = (signature, now)
            self.sequence += 1
            with _lock:
                if not _logger.handlers:
                    DATA.mkdir(parents=True, exist_ok=True)
                    handler = DiagnosticFileHandler(DATA / 'login-diagnostics.jsonl',
                                                  maxBytes=2_000_000, backupCount=3, encoding='utf-8')
                    handler.setFormatter(logging.Formatter('%(message)s'))
                    _logger.addHandler(handler)
            from datetime import datetime, timezone
            _logger.info(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                    'run_id': RUN_ID, 'read_id': self.read_id,
                                    'session': self.session, 'trace': self.trace, 'sequence': self.sequence,
                                    'elapsed_s': round(now - self.started, 1),
                                    'event': event, **facts}, ensure_ascii=False))
        except Exception:
            # Diagnostics must never interrupt authentication or print unsafe exceptions.
            if not self.warned:
                self.warned = True
                try:
                    logging.getLogger('servicenow').warning('Nie udało się zapisać diagnostyki logowania.')
                except Exception:
                    pass

    def inspect(self, page, automatic, target='https://adeo.service-now.com/', surface_alias='main'):
        try:
            from neto_incident_monitor.authentication import login_observation
            observed = login_observation(page, target, surface=surface_alias)
            facts = observed.facts
            state_key = (observed.state, observed.evidence, observed.generation)
            previous = getattr(self, '_login_observation_key', None)
            if state_key != previous:
                self.record('login_state_changed', login_state=observed.state,
                            previous_login_state=previous[0] if previous else 'initial',
                            login_evidence=observed.evidence, login_surface=observed.surface,
                            document_generation=observed.generation)
                self._login_observation_key = state_key
            self.record('page_state', origin=observed.origin, **facts,
                        frame_count=observed.frame_count, page_count=len(page.context.pages),
                        auto_blocked=bool(automatic and automatic.blocked),
                        auto_submitted=bool(automatic and automatic.submitted),
                        account_selected=bool(automatic and automatic.account_clicked))
            if perf_counter() - self.started >= 30:
                self.record('login_still_waiting')
        except Exception as error:
            self.record('inspection_error', **error_facts(error))


def close_diagnostics():
    with _lock:
        for handler in list(_logger.handlers):
            _logger.removeHandler(handler)
            handler.close()
