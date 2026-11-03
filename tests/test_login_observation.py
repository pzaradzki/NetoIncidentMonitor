"""Stage A: minimal synthetic structures derived from the observed SSO UI."""
import json
import unittest
from unittest.mock import Mock

from playwright.sync_api import sync_playwright
from neto_incident_monitor.authentication import authenticated_session, authentication_required
from neto_incident_monitor.login_observation import COUNTS, FLAGS, observe_login, origin_kind
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger, safe_facts

TARGET = 'https://adeo.service-now.com/incident_list.do'


def signals(**overrides):
    return {**dict.fromkeys(COUNTS, 0), **dict.fromkeys(FLAGS, False), **overrides}


def page_with(*frames, url=TARGET):
    page = Mock(url=url, frames=list(frames))
    page.context.pages = [page]
    return page


def frame_with(url=TARGET, **facts):
    frame = Mock(url=url)
    frame.evaluate.return_value = signals(**facts)
    return frame


class LoginObservationTests(unittest.TestCase):
    def test_exact_secure_origins_only(self):
        for url in (TARGET, TARGET.replace('https:', 'https:').replace('.com/', '.com:443/')):
            self.assertEqual(origin_kind(url), 'servicenow')
        self.assertEqual(origin_kind('https://idpb2e.adeo.com/idp/SSO.saml2'), 'adeo_identity')
        for url in ('http://idpb2e.adeo.com/', 'https://idpb2e.adeo.com:444/',
                    'https://user@idpb2e.adeo.com/', 'https://idpb2e.adeo.com.evil/',
                    'https://adeo.service-now.com:444/', 'https://adeo.service-now.com:bad/', None):
            self.assertEqual(origin_kind(url), 'other')

    def test_password_in_other_frame_vetoes_stale_session(self):
        page = page_with(frame_with(session_signal=True), frame_with(password_count=1))
        self.assertEqual(observe_login(page, TARGET).state, 'authentication')
        self.assertTrue(authentication_required(page, TARGET))
        self.assertFalse(authenticated_session(page, TARGET))

    def test_logout_vetoes_stale_user_even_if_dom_disappears(self):
        for broken in (False, True):
            frame = frame_with(session_signal=True)
            if broken:
                frame.evaluate.side_effect = RuntimeError('PRIVATE_SECRET')
            page = page_with(frame, url='https://adeo.service-now.com/external_logout_complete.do')
            self.assertEqual(observe_login(page, TARGET).state, 'logout')
            self.assertFalse(authenticated_session(page, TARGET))

    def test_partial_inspection_never_confirms_session(self):
        broken = frame_with()
        broken.evaluate.side_effect = RuntimeError('PRIVATE_SECRET')
        page = page_with(frame_with(session_signal=True), broken)
        observed = observe_login(page, TARGET)
        self.assertEqual(observed.state, 'unknown')
        self.assertTrue(observed.requires_authentication)
        self.assertFalse(observed.session_ready)

    def test_first_failure_is_safe_and_observation_never_performs_actions(self):
        first, second = frame_with(), frame_with()
        first.evaluate.side_effect = RuntimeError('net::ERR_NAME_NOT_RESOLVED PRIVATE_TOKEN')
        second.evaluate.side_effect = type('PRIVATE_CLASS', (Exception,), {})('PRIVATE_PASSWORD')
        page = page_with(first, second)
        observed = observe_login(page, TARGET, generation=4, surface='owned_popup')
        self.assertEqual(observed.state, 'unknown')
        self.assertEqual(observed.facts['error_category'], 'network_dns')
        self.assertEqual(observed.generation, 4)
        self.assertEqual(observed.surface, 'owned_popup')
        self.assertNotIn('PRIVATE_', json.dumps(observed.__dict__))
        page.goto.assert_not_called()
        page.bring_to_front.assert_not_called()
        first.locator.assert_not_called()

    def test_empty_and_malformed_observations_are_unknown(self):
        for result in (None, True, {}, signals(password_count='PRIVATE_SECRET')):
            frame = frame_with()
            frame.evaluate.return_value = result
            self.assertEqual(observe_login(page_with(frame), TARGET).state, 'unknown')
        self.assertEqual(observe_login(page_with(), TARGET).state, 'unknown')

    def test_fresh_session_and_target_without_identity_are_distinct(self):
        self.assertEqual(observe_login(page_with(frame_with()), TARGET).state, 'target')
        self.assertTrue(authenticated_session(page_with(frame_with(session_signal=True)), TARGET))

    def test_only_owned_open_popup_vetoes_session(self):
        page = page_with(frame_with(session_signal=True))
        popup = page_with(frame_with(url='https://idpb2e.adeo.com/', password_count=1),
                          url='https://idpb2e.adeo.com/')
        popup.is_closed.return_value = False
        page.context.pages.append(popup)
        popup.opener.return_value = None
        self.assertTrue(authenticated_session(page, TARGET))
        popup.opener.return_value = page
        self.assertFalse(authenticated_session(page, TARGET))
        popup.is_closed.return_value = True
        self.assertTrue(authenticated_session(page, TARGET))

    def test_transitions_are_correlated_and_allowlisted(self):
        frame = frame_with(password_count=1)
        page = page_with(frame)
        with self.assertLogs(_logger, level='INFO') as captured:
            log = LoginDiagnostics()
            log.inspect(page, None)
            log.inspect(page, None)
            frame.evaluate.return_value = signals(session_signal=True)
            log.inspect(page, None)
        events = [json.loads(record.getMessage()) for record in captured.records]
        changes = [event for event in events if event['event'] == 'login_state_changed']
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[-1]['previous_login_state'], 'authentication')
        self.assertEqual(changes[-1]['login_state'], 'session')
        self.assertEqual(changes[0]['read_id'], changes[-1]['read_id'])
        self.assertEqual(changes[0]['run_id'], changes[-1]['run_id'])
        self.assertEqual(safe_facts({'login_state': 'PRIVATE_SECRET', 'login_surface': 'PRIVATE_SECRET'}), {})


class LoginDOMObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_real_dom_minimal_forms_and_no_secret_export(self):
        fixtures = (
            ('<form><input type=password value=PRIVATE_PASSWORD><a id=signOnButton>Sign in</a></form>'
             '<footer>invalid PRIVATE_USER PRIVATE_TOKEN</footer>', 'authentication', False),
            ('<form><input type=password><span role=alert>Invalid password PRIVATE_TOKEN</span></form>',
             'authentication', True),
            ('<input autocomplete=one-time-code>', 'authentication', True),
            ('<script>window.g_user={userID:"PRIVATE_USER"}</script>', 'session', False),
            ('<div id=existingAccountsSelectionList><li class=identifier-first__account-item>'
             '<span class=identifier-first__account-name>PRIVATE_USER</span></li></div>',
             'authentication', False),
        )
        for html, state, intervention in fixtures:
            with self.subTest(state=state, intervention=intervention):
                page = self.browser.new_page()
                try:
                    page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html'))
                    page.goto(TARGET + '?SAMLRequest=PRIVATE_TOKEN')
                    observed = observe_login(page, TARGET)
                    self.assertEqual(observed.state, state)
                    self.assertEqual(observed.facts['intervention'], intervention)
                    self.assertNotIn('PRIVATE_', json.dumps(observed.__dict__))
                finally:
                    page.close()


class OriginAndOwnershipTests(unittest.TestCase):
    def test_blank_or_foreign_without_auth_controls_is_unknown(self):
        for url in ('about:blank','chrome-error://chromewebdata/','https://other.example/'):
            page=page_with(frame_with(url=url),url=url)
            self.assertEqual(observe_login(page,TARGET).state,'unknown')
    def test_owned_grandchild_vetoes_stale_main_and_parent_identity(self):
        page=page_with(frame_with(session_signal=True))
        parent=page_with(frame_with(session_signal=True));parent.is_closed.return_value=False;parent.opener.return_value=page
        child=page_with(frame_with(url='https://idpb2e.adeo.com/login',password_count=1),url='https://idpb2e.adeo.com/login')
        child.is_closed.return_value=False;child.opener.return_value=parent
        foreign=page_with(frame_with(password_count=1));foreign.is_closed.return_value=False;foreign.opener.return_value=None
        page.context.pages=[page,parent,foreign,child]
        self.assertEqual(observe_login(page,TARGET).state,'authentication')
        from neto_incident_monitor.authentication import login_surface
        self.assertIs(login_surface(page,TARGET),child)
        child.is_closed.return_value=True
        self.assertTrue(observe_login(page,TARGET).session_ready)

    def test_foreign_container_cannot_borrow_trusted_frame_session(self):
        page=page_with(frame_with(session_signal=True),url='https://other.example/')
        self.assertEqual(observe_login(page,TARGET).state,'unknown')
