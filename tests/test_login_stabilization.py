"""Observed SSO structures; fixture autofill is mocked, not called genuine autofill."""
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.authentication import install_input_guard, manual_handoff
from neto_incident_monitor.automatic_login import AutomaticLogin

FORM = '<form><input type=password value="SYNTHETIC_SECRET"><a id=signOnButton tabindex=0 onclick="window.clicks=(window.clicks||0)+1">Sign in</a></form>'
CARD = '<li class=identifier-first__account-item onclick="window.selections=(window.selections||0)+1"><span class=identifier-first__account-name>Test</span><button class=identifier-first__remove-account>Remove</button></li>'

class StabilizedAutomaticTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(headless=True)
 @classmethod
 def tearDownClass(cls):
  cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.ctx=self.browser.new_context();install_input_guard(self.ctx);self.page=self.ctx.new_page()
  self.page.route('**/*',lambda r:r.fulfill(body='<body></body>',content_type='text/html'))
  self.page.goto('https://idpb2e.adeo.com/login')
 def content(self,html):self.page.evaluate('html=>document.body.innerHTML=html',html)
 def tearDown(self):self.ctx.close()
 def automatic(self,autofilled=False,diagnostics=None):
  auto=AutomaticLogin(diagnostics);auto.autofilled=Mock(return_value=autofilled);return auto
 def test_selected_account_is_not_autofill_evidence(self):
  self.content(FORM);auto=AutomaticLogin();auto.account_clicked=True;auto.step(self.page)
  self.assertFalse(auto.submitted);self.assertTrue(auto.needs_user)
  self.assertFalse(self.page.evaluate('!!window.clicks'))
 def test_late_autofill_can_resume_before_human_edits(self):
  self.content(FORM);auto=self.automatic();auto.step(self.page)
  self.assertTrue(auto.needs_user);self.assertFalse(auto.blocked)
  auto.autofilled.return_value=True;auto.step(self.page);auto.step(self.page)
  self.assertTrue(auto.submitted);self.assertEqual(self.page.evaluate('window.clicks'),1)
 def test_empty_field_grace_does_not_depend_on_click_trial(self):
  self.content(FORM.replace(' value="SYNTHETIC_SECRET"','')+'<div style="position:fixed;inset:0"></div>')
  auto=self.automatic()
  with patch('neto_incident_monitor.automatic_login.monotonic',return_value=0) as clock:
   auto.step(self.page);clock.return_value=5.1;auto.step(self.page)
  self.assertTrue(auto.autofill_wait_expired);self.assertTrue(auto.needs_user)
 def test_manual_selection_from_multiple_accounts_is_narrow_handoff(self):
  self.content('<ul id=existingAccountsSelectionList>'+CARD+CARD+'</ul>');auto=self.automatic(True)
  auto.step(self.page);self.assertTrue(auto.needs_user);self.assertFalse(auto.blocked)
  self.page.locator('.identifier-first__account-name').first.click()
  self.assertFalse(manual_handoff(self.page))
  from neto_incident_monitor.authentication import login_observation
  self.assertEqual(login_observation(self.page,'https://adeo.service-now.com/').facts['manual_account_selections'],1)
  self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  auto.step(self.page);self.assertTrue(auto.submitted)
 def test_typing_has_priority_even_after_selection(self):
  self.content(FORM);auto=self.automatic(True)
  self.page.locator('input').press('x');auto.step(self.page)
  self.assertTrue(auto.blocked);self.assertFalse(auto.submitted)
  self.page.locator('#signOnButton').click();self.assertEqual(self.page.evaluate('window.clicks'),1)
 def test_delivered_account_is_not_selected_again_on_stalled_document(self):
  self.content('<ul id=existingAccountsSelectionList>'+CARD+'</ul>');auto=self.automatic()
  with patch('neto_incident_monitor.automatic_login.monotonic',return_value=0) as clock:
   auto.step(self.page);clock.return_value=6;auto.step(self.page);clock.return_value=31;auto.step(self.page)
  self.assertEqual(self.page.evaluate('window.selections'),1);self.assertTrue(auto.needs_user)
 def test_component_replacement_without_submission_is_not_fatal(self):
  self.content(FORM.replace(' value="SYNTHETIC_SECRET"',''));auto=self.automatic(True);auto.step(self.page)
  self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  auto.step(self.page);self.assertTrue(auto.submitted);self.assertFalse(auto.blocked)
 def test_unknown_identity_origin_and_nonstandard_port_are_never_clicked(self):
  for url in ('https://idp-other.adeo.com/login','https://idpb2e.adeo.com:444/login'):
   self.page.goto(url);self.content(FORM);auto=self.automatic(True);auto.step(self.page)
   self.assertFalse(auto.submitted);self.assertFalse(self.page.evaluate('!!window.clicks'))
 def test_unrelated_invalid_text_does_not_veto_but_scoped_mfa_does(self):
  self.content(FORM+'<footer>invalid sample text</footer>');auto=self.automatic(True);auto.step(self.page)
  self.assertTrue(auto.submitted)
  self.page.goto('https://idpb2e.adeo.com/login');self.content(FORM.replace('</form>','<input autocomplete=one-time-code></form>'))
  auto=self.automatic(True);auto.step(self.page);self.assertTrue(auto.blocked);self.assertFalse(auto.submitted)
 def test_broken_diagnostic_does_not_break_guard_or_duplicate_submit(self):
  self.content(FORM);log=Mock();log.record.side_effect=OSError('SYNTHETIC_SECRET')
  auto=self.automatic(True,log);auto.step(self.page);auto.step(self.page)
  self.assertEqual(self.page.evaluate('window.clicks'),1)


class InputOwnershipScopeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(headless=True)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.ctx=self.browser.new_context();install_input_guard(self.ctx);self.page=self.ctx.new_page()
  self.page.route('**/*',lambda r:r.fulfill(body='<input type=text><button type=button>Apply</button>',content_type='text/html'))
  self.page.goto('https://adeo.service-now.com/dashboard')
 def tearDown(self):self.ctx.close()
 def test_dashboard_edit_and_button_do_not_poison_later_login(self):
  self.page.locator('input').press('x');self.page.locator('button').click();self.page.wait_for_timeout(50)
  self.assertFalse(manual_handoff(self.page));self.assertFalse(self.page.evaluate('window.__netoInputGuard.manual'))
  self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  auto=AutomaticLogin();auto.autofilled=Mock(return_value=True);auto.step(self.page)
  self.assertTrue(auto.needs_user)  # Only the observed IdP may be automated.
  self.page.goto('https://idpb2e.adeo.com/password');self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  auto.step(self.page);self.assertTrue(auto.submitted)
 def test_unknown_login_surface_edit_is_owned_only_during_login(self):
  from neto_incident_monitor.authentication import set_login_activity,clear_login_activity
  self.page.goto('https://unknown.example/challenge');self.page.locator('input').press('x');self.page.wait_for_timeout(50)
  self.assertFalse(manual_handoff(self.page))
  set_login_activity(self.page);self.page.locator('input').press('y');self.page.wait_for_timeout(50)
  self.assertTrue(manual_handoff(self.page));self.assertTrue(self.page.evaluate('window.__netoInputGuard.manual'))
  clear_login_activity(self.page)
 def test_hidden_relay_does_not_claim_manual_password_submission_does(self):
  self.page.goto('https://idpb2e.adeo.com/relay')
  self.page.evaluate('''() => {document.body.innerHTML='<form><input type=hidden></form>';document.querySelector('form').addEventListener('submit',e=>e.preventDefault());document.querySelector('form').requestSubmit()}''')
  self.assertFalse(manual_handoff(self.page));self.assertFalse(self.page.evaluate('window.__netoInputGuard.submitted'))
  self.page.evaluate('''() => {document.querySelector('input').type='password';document.querySelector('form').requestSubmit()}''')
  self.assertTrue(self.page.evaluate('window.__netoInputGuard.submitted'))
 def test_confirmed_session_clears_ownership_for_next_transaction(self):
  from neto_incident_monitor.authentication import finish_authentication
  self.page.goto('https://idpb2e.adeo.com/password');self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  self.page.locator('input').press('x');self.assertTrue(manual_handoff(self.page))
  finish_authentication(self.page)
  self.assertFalse(manual_handoff(self.page));self.assertFalse(self.page.evaluate('window.__netoInputGuard.manual'))
 def test_enter_and_manual_submit_preserve_ownership(self):
  self.page.goto('https://idpb2e.adeo.com/password');self.page.evaluate('html=>document.body.innerHTML=html',FORM)
  self.page.locator('input').press('Enter');self.assertTrue(manual_handoff(self.page))
  auto=AutomaticLogin();auto.autofilled=Mock(return_value=True);auto.step(self.page)
  self.assertTrue(auto.blocked);self.assertFalse(self.page.evaluate('!!window.clicks'))

 def test_password_entry_survives_navigation_and_excludes_other_input(self):
  from neto_incident_monitor.authentication import set_login_activity, take_manual_password_entry
  self.page.goto('https://idpb2e.adeo.com/password')
  self.page.evaluate('html=>document.body.innerHTML=html',
                     '<input type="password" autocomplete="one-time-code"><input id="pwd" type="password">')
  set_login_activity(self.page)
  self.page.locator('[autocomplete=one-time-code]').press('1')
  self.page.locator('#pwd').evaluate("""el => el.dispatchEvent(new InputEvent('beforeinput',
      {bubbles:true,inputType:'insertText'}))""")
  self.assertFalse(take_manual_password_entry(self.page))
  self.page.locator('#pwd').press('x')
  self.page.goto('https://adeo.service-now.com/dashboard')
  self.assertTrue(take_manual_password_entry(self.page))
  self.assertFalse(take_manual_password_entry(self.page))

 def test_password_entry_on_owned_popup_is_delivered_to_main_page(self):
  from neto_incident_monitor.authentication import set_login_activity, take_manual_password_entry
  self.ctx.route('https://idpb2e.adeo.com/password', lambda r:
                 r.fulfill(body='<input type="password">', content_type='text/html'))
  set_login_activity(self.page)
  with self.page.expect_popup() as opened:
   self.page.evaluate("() => { window.open('https://idpb2e.adeo.com/password'); }")
  popup = opened.value
  popup.locator('input').press('x')
  popup.close()
  self.assertTrue(take_manual_password_entry(self.page))

 def test_password_save_prompt_is_skipped_with_auto_login_disabled(self):
  from threading import Event
  from neto_incident_monitor.app import wait_for_login
  from neto_incident_monitor.authentication import set_login_activity
  self.page.route('https://idpb2e.adeo.com/password', lambda r:
                  r.fulfill(body='<input type="password">', content_type='text/html'))
  self.page.goto('https://idpb2e.adeo.com/password')
  set_login_activity(self.page)
  self.page.locator('[type=password]').press('x')
  target = 'https://adeo.service-now.com/now/sow/home'
  self.page.goto(target)
  self.page.evaluate('window.g_user = {userID:"fixture"}')
  prompt = Mock()
  self.assertTrue(wait_for_login(self.page, target, Event(), auto_login=False, on_password_save=prompt))
  prompt.assert_not_called()


class LoginRenderingScopeTests(unittest.TestCase):
 def setUp(self):
  from neto_incident_monitor.browser_rendering import HiddenRendering
  self.page=Mock(url='https://idpb2e.adeo.com/login');self.page.is_closed.return_value=False
  self.log=Mock();self.guard=HiddenRendering(self.log,scope='login')
  self.observation=patch('neto_incident_monitor.authentication.login_observation')
  self.observe=self.observation.start();self.addCleanup(self.observation.stop);self.addCleanup(self.guard.close)
  self.observe.return_value=Mock(state='authentication',facts={'intervention':False,'password_manual_edit':False})
 def test_only_confirmed_known_identity_page_can_start(self):
  for url in ('https://idp-other.adeo.com/','https://idpb2e.adeo.com:444/','https://user@idpb2e.adeo.com/','http://idpb2e.adeo.com/'):
   self.page.url=url;self.guard.sync(self.page,True)
  self.page.context.new_cdp_session.assert_not_called()
  self.page.url='https://idpb2e.adeo.com/login';self.guard.sync(self.page,True)
  self.page.context.new_cdp_session.assert_called_once()
 def test_intervention_and_unknown_do_not_capture(self):
  for state,facts in (('unknown',{}),('session',{}),('authentication',{'intervention':True}),('authentication',{'password_manual_edit':True})):
   self.observe.return_value=Mock(state=state,facts=facts);self.guard.sync(self.page,True)
  self.page.context.new_cdp_session.assert_not_called()
 def test_exact_small_parameters_and_no_payload_inspection(self):
  self.guard.sync(self.page,True);client=self.page.context.new_cdp_session.return_value
  client.send.assert_called_with('Page.startScreencast',{'format':'jpeg','quality':0,'maxWidth':1,'maxHeight':1,'everyNthFrame':60})
  class NoData(dict):
   def get(self,key,*args):
    if key=='data':raise AssertionError('Authentication payload inspected')
    return super().get(key,*args)
  self.guard.frame(NoData(sessionId=1));self.guard.close()
  self.assertEqual(self.guard.payload_bytes,0)
  self.assertTrue(any(c.kwargs.get('rendering_scope')=='login' for c in self.log.record.call_args_list))
 def test_every_navigation_stops_and_rechecks_new_document(self):
  self.guard.sync(self.page,True);client=self.page.context.new_cdp_session.return_value
  self.guard.navigation(self.page.main_frame);self.assertIsNone(self.guard.client);client.detach.assert_called_once()
 def test_start_failure_not_retried_until_scope_reset(self):
  from neto_incident_monitor.browser_rendering import LoginRenderingUnavailable
  self.page.context.new_cdp_session.return_value.send.side_effect=RuntimeError('SYNTHETIC_SECRET')
  for _ in range(2):
   with self.assertRaises(LoginRenderingUnavailable):self.guard.sync(self.page,True)
  self.page.context.new_cdp_session.assert_called_once()
  self.assertNotIn('SYNTHETIC_SECRET',str(self.log.record.call_args_list))


class LoginCoordinatorTests(unittest.TestCase):
 def test_confirmed_session_never_reads_filter_records(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  page=page_with(frame_with(session_signal=True));page.is_closed.return_value=False
  with patch('neto_incident_monitor.app.collect',side_effect=AssertionError('No list during login')):
   self.assertTrue(wait_for_login(page,'https://adeo.service-now.com/incident_list.do',threading.Event()))
 def test_unknown_waits_and_recovers_until_stop_not_false_success(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  page=page_with(frame_with());page.is_closed.return_value=False;stop=threading.Event();ticks=[0]
  def pulse(_):
   ticks[0]+=1
   if ticks[0]>=4:stop.set()
  page.wait_for_timeout.side_effect=pulse
  with patch('neto_incident_monitor.app.time.monotonic',side_effect=lambda:ticks[0]*200),patch('neto_incident_monitor.app.navigate') as navigate,patch('neto_incident_monitor.app.set_chromium_window_state',return_value=True):
   self.assertFalse(wait_for_login(page,'https://adeo.service-now.com/incident_list.do',stop))
  self.assertGreaterEqual(navigate.call_count,1);self.assertLessEqual(navigate.call_count,3)
 def test_logout_recovers_with_safe_target_get(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  target='https://adeo.service-now.com/incident_list.do';page=page_with(frame_with(session_signal=True),url='https://adeo.service-now.com/external_logout_complete.do')
  page.is_closed.return_value=False
  def navigate(*_):page.url=target
  with patch('neto_incident_monitor.app.navigate',side_effect=navigate) as call,patch('neto_incident_monitor.app.set_chromium_window_state',return_value=True):
   self.assertTrue(wait_for_login(page,target,threading.Event()))
  call.assert_called_once();self.assertEqual(call.call_args.args[1],target)
 def test_manual_wait_focus_once_and_stop_is_honored(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  page=page_with(frame_with(url='https://idpb2e.adeo.com/login',password_count=1),url='https://idpb2e.adeo.com/login')
  page.is_closed.return_value=False;stop=threading.Event();ticks=[0];window=Mock();window.show.return_value=True
  def pulse(_):
   ticks[0]+=1
   if ticks[0]>=4:stop.set()
  page.wait_for_timeout.side_effect=pulse
  self.assertFalse(wait_for_login(page,'https://adeo.service-now.com/incident_list.do',stop,browser_window=window))
  window.show.assert_called_once_with(activate=True)
 def test_runtime_preference_matrix_and_manual_handoff(self):
  from neto_incident_monitor.browser_policy import BrowserRuntime,BrowserOptions
  for auto,hide in ((True,True),(True,False),(False,True),(False,False)):
   page=Mock(url='about:blank');window=Mock();window.show.return_value=True
   runtime=BrowserRuntime(page,BrowserOptions({'auto_login':auto,'hide_browser':hide}),lambda:window,Mock(),Mock(),Mock())
   try:
    runtime.set_activity('login')
    if auto and hide:window.hide.assert_called_once();window.show.assert_not_called()
    else:window.show.assert_called_once_with(activate=not auto)
    runtime.manual_required=True;runtime.tick();runtime.tick()
    self.assertLessEqual(sum(c.kwargs.get('activate') is True for c in window.show.call_args_list),2)
   finally:runtime.close()


class RecoverySafetyTests(unittest.TestCase):
 def test_uncertain_submission_prevents_logout_reopening(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  page=page_with(frame_with(),url='https://adeo.service-now.com/external_logout_complete.do')
  page.is_closed.return_value=False;stop=threading.Event();page.wait_for_timeout.side_effect=lambda _:stop.set()
  auto=Mock(blocked=False,needs_user=False,submitted=True,pending_delivery_token=None)
  with patch('neto_incident_monitor.automatic_login.AutomaticLogin',return_value=auto),patch('neto_incident_monitor.app.navigate') as navigate,patch('neto_incident_monitor.app.set_chromium_window_state',return_value=True):
   self.assertFalse(wait_for_login(page,'https://adeo.service-now.com/incident_list.do',stop,auto_login=True))
  navigate.assert_not_called()
 def test_certificate_failure_is_handed_off_without_retry_or_bypass(self):
  import threading
  from tests.test_login_observation import page_with,frame_with
  from neto_incident_monitor.app import wait_for_login
  from neto_incident_monitor.browser_policy import BrowserRuntime,BrowserOptions
  page=page_with(frame_with(url='chrome-error://chromewebdata/'),url='chrome-error://chromewebdata/')
  page.is_closed.return_value=False;stop=threading.Event();page.wait_for_timeout.side_effect=lambda _:stop.set()
  window=Mock();window.show.return_value=True
  runtime=BrowserRuntime(page,BrowserOptions({'auto_login':True,'hide_browser':True}),lambda:window,Mock(),Mock(),Mock())
  runtime.navigation_error='network_tls'
  try:
   with patch('neto_incident_monitor.app.navigate') as navigate:
    self.assertFalse(wait_for_login(page,'https://adeo.service-now.com/incident_list.do',stop,runtime=runtime))
   navigate.assert_not_called();window.show.assert_called_with(activate=True)
  finally:runtime.close()


class DiagnosticSafetyTests(unittest.TestCase):
 def test_block_reason_cannot_leak_unapproved_caller_text(self):
  import logging
  auto=AutomaticLogin()
  with self.assertLogs('servicenow',level=logging.WARNING) as logs:
   auto.block('SYNTHETIC_PRIVATE_PASSWORD')
  self.assertNotIn('SYNTHETIC_PRIVATE_PASSWORD',' '.join(logs.output))
 def test_login_renderer_does_not_report_unmeasured_payload_as_zero(self):
  import json
  from neto_incident_monitor.browser_rendering import HiddenRendering
  from neto_incident_monitor.login_diagnostics import LoginDiagnostics,_logger
  page=Mock(url='https://idpb2e.adeo.com/login');page.is_closed.return_value=False
  observed=Mock(state='authentication',facts={})
  with self.assertLogs(_logger,level='INFO') as logs,patch('neto_incident_monitor.authentication.login_observation',return_value=observed):
   guard=HiddenRendering(LoginDiagnostics(),scope='login');guard.sync(page,True)
   guard.frame({'sessionId':1,'data':'SYNTHETIC_PRIVATE_PASSWORD'});guard.close()
  rows=[json.loads(row.getMessage()) for row in logs.records]
  end=next(row for row in rows if row['event']=='rendering_stop')
  self.assertEqual(end['frame_count'],1);self.assertEqual(end['ack_count'],1)
  self.assertNotIn('payload_bytes',end);self.assertNotIn('SYNTHETIC_PRIVATE_PASSWORD',' '.join(logs.output))


class ManualRevealOrderingTests(unittest.TestCase):
 def test_auth_rendering_stops_before_manual_window_is_shown(self):
  from neto_incident_monitor.browser_policy import BrowserRuntime,BrowserOptions
  page=Mock(url='about:blank');window=Mock();state={'capturing':False}
  runtime=BrowserRuntime(page,BrowserOptions({'auto_login':True,'hide_browser':True}),lambda:window,Mock(),Mock(),Mock())
  renderer=Mock()
  def sync(_,enabled):state['capturing']=enabled
  renderer.sync.side_effect=sync;runtime.login_rendering=renderer
  def show(**_):
   self.assertFalse(state['capturing']);return True
  window.show.side_effect=show
  runtime.set_activity('login');self.assertTrue(state['capturing'])
  runtime.manual_required=True;runtime.tick();window.show.assert_called_once_with(activate=True)
  runtime.close()


class NativeVisibilityReconciliationTests(unittest.TestCase):
 def test_native_reappearance_is_hidden_even_if_cached_policy_is_unchanged(self):
  from neto_incident_monitor.browser_policy import BrowserRuntime,BrowserOptions
  page=Mock(url='about:blank');window=Mock();window.is_hidden.return_value=True
  runtime=BrowserRuntime(page,BrowserOptions({'auto_login':True,'hide_browser':True}),lambda:window,Mock(),Mock(),Mock())
  try:
   runtime.set_activity('login');self.assertEqual(window.hide.call_count,1)
   window.is_hidden.return_value=False;runtime.tick();self.assertEqual(window.hide.call_count,2)
   window.is_hidden.return_value=True;runtime.tick();self.assertEqual(window.hide.call_count,2)
   runtime.commands.put('show');runtime.tick();self.assertEqual(window.hide.call_count,2)
  finally:runtime.close()


class DiagnosticRotationFailureTests(unittest.TestCase):
 def test_rotation_failure_never_dumps_record_or_retries_in_a_tight_loop(self):
  import logging,tempfile,io,contextlib
  from pathlib import Path
  from neto_incident_monitor.safe_logging import DiagnosticFileHandler
  with tempfile.TemporaryDirectory() as folder:
   handler=DiagnosticFileHandler(Path(folder)/'diagnostic.jsonl',maxBytes=1,backupCount=1)
   record=logging.LogRecord('test',logging.INFO,'',0,'SYNTHETIC_PRIVATE_PASSWORD',(),None)
   stderr=io.StringIO()
   try:
    with patch.object(handler,'doRollover',side_effect=OSError('SYNTHETIC_PRIVATE_TOKEN')) as rotate,patch('neto_incident_monitor.safe_logging.monotonic',return_value=0),contextlib.redirect_stderr(stderr),self.assertLogs('servicenow',level='WARNING') as logs:
     handler.emit(record);handler.emit(record)
    rotate.assert_called_once();self.assertEqual(len(logs.output),1)
    self.assertNotIn('SYNTHETIC_PRIVATE',stderr.getvalue()+' '.join(logs.output))
    with patch('neto_incident_monitor.safe_logging.monotonic',return_value=31),self.assertLogs('servicenow',level='INFO') as recovered:
     handler.emit(logging.LogRecord('test',logging.INFO,'',0,'safe',(),None))
    self.assertEqual(len(recovered.output),1)
    self.assertEqual((Path(folder)/'diagnostic.jsonl').read_text().strip(),'safe')
   finally:handler.close()


class PostSubmissionRedirectTests(unittest.TestCase):
 def test_origin_change_after_delivery_waits_without_showing_or_inspecting_foreign_page(self):
  page=Mock(url='https://adeo.service-now.com/auth_redirect.do');auto=AutomaticLogin()
  auto.submitted=True;auto.submitted_at=0
  with patch('neto_incident_monitor.automatic_login.monotonic',return_value=1):
   auto.step(page)
  self.assertFalse(auto.needs_user);self.assertTrue(auto.submitted)
  page.evaluate.assert_not_called();page.locator.assert_not_called()
  with patch('neto_incident_monitor.automatic_login.monotonic',return_value=31):
   auto.step(page)
  self.assertTrue(auto.needs_user);self.assertTrue(auto.submitted)
 def test_origin_change_preserves_uncertain_pending_activation(self):
  page=Mock(url='https://adeo.service-now.com/auth_redirect.do');auto=AutomaticLogin()
  auto.pending_delivery_token='synthetic-token';auto.last_submit_attempt=0
  with patch('neto_incident_monitor.automatic_login.monotonic',return_value=1):auto.step(page)
  self.assertTrue(auto.submitted);self.assertIsNone(auto.pending_delivery_token)
  self.assertFalse(auto.needs_user);page.evaluate.assert_not_called()
