"""Integrated owner/runtime on isolated Windows profiles; all web content synthetic."""
import sys,tempfile,threading,time,unittest
from urllib.parse import urlsplit
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.app import wait_for_login
from neto_incident_monitor.authentication import install_input_guard
from neto_incident_monitor.automatic_login import AutomaticLogin
from neto_incident_monitor.browser_policy import BrowserOptions,BrowserRuntime
from neto_incident_monitor.browser_window import BrowserWindow
from neto_incident_monitor.browser_icon import browser_launch_options
from neto_incident_monitor.browser_actions import ACTION_TICK
from neto_incident_monitor.login_diagnostics import LoginDiagnostics

TARGET='https://adeo.service-now.com/native-fixture'
CHOICE='https://idpb2e.adeo.com/choice'
PASSWORD='https://idpb2e.adeo.com/password'
FORM='<form method=post action="'+TARGET+'"><input type=password data-test-autofill=yes value="synthetic"><a id=signOnButton tabindex=0 onclick="this.closest(\'form\').requestSubmit()">Sign in</a></form>'

@unittest.skipUnless(sys.platform=='win32','Windows integration')
class LoginRuntimeNativeTests(unittest.TestCase):
 def run_fixture(self,empty=False,options_test=False):
  result={'posts':0,'native_visible':[],'elapsed':0,'states':[]}
  with tempfile.TemporaryDirectory(prefix='neto-login-integration-') as profile,sync_playwright() as pw:
   ctx=pw.chromium.launch_persistent_context(profile,headless=False,no_viewport=True,**browser_launch_options())
   install_input_guard(ctx);page=ctx.pages[0];window=BrowserWindow(ctx.browser)
   options=BrowserOptions({'auto_login':True,'hide_browser':True});stop=threading.Event()
   log=LoginDiagnostics(source='monitor');runtime=BrowserRuntime(page,options,lambda:window,lambda *a:None,log,lambda *a:None)
   token=ACTION_TICK.set(runtime.tick)
   timer=threading.Timer(20,stop.set);timer.start()
   def route(r):
    address=r.request.url
    if r.request.method=='POST':result['posts']+=1
    if address==TARGET and r.request.method!='POST' and not empty:
     body='<script>location.href='+repr(CHOICE)+'</script>'
    elif address==CHOICE:
     body='<form method=post action="'+PASSWORD+'"><ul id=existingAccountsSelectionList><li class=identifier-first__account-item onclick="this.closest(\'form\').requestSubmit()"><div class=identifier-first__account-name>Test</div><button class=identifier-first__remove-account type=button>Remove</button></li></ul></form>'
    elif address==PASSWORD or empty:
     body=FORM.replace(' value="synthetic"','') if empty else FORM
    else:body='<script>window.g_user={userID:"synthetic"}</script><p>Ready</p>'
    r.fulfill(content_type='text/html',body=body)
   ctx.route('**/*',route)
   def navigation(frame):
    if frame==page.main_frame:result['native_visible'].append(window.is_visible())
   page.on('framenavigated',navigation)
   original_wait=page.wait_for_timeout;ticks=[0]
   def pulse(ms):
    ticks[0]+=1
    if options_test:
     if ticks[0]==1:options.update(auto_login=False)
     elif ticks[0]==2:
      result['states'].append(('manual',window.is_visible()))
      options.update(auto_login=True);page.locator('input[type=password]').press('x')
     elif ticks[0]==3:
      result['states'].append(('typed',window.is_visible()));stop.set()
    elif empty:stop.set()
    return original_wait(ms)
   try:
    runtime.set_activity('login')
    page.goto(PASSWORD if empty else TARGET,wait_until='domcontentloaded')
    with patch.object(AutomaticLogin,'autofilled',lambda _,field:field.evaluate('el=>el.dataset.testAutofill==="yes"')),patch.object(page,'wait_for_timeout',side_effect=pulse):
     start=time.monotonic();result['returned']=wait_for_login(page,TARGET,stop,auto_login=True,runtime=runtime)
     result['elapsed']=time.monotonic()-start
    result['render_stopped']=runtime.login_rendering.client is None
    result['hidden_final']=not window.is_visible()
   finally:
    timer.cancel();timer.join();runtime.close();ACTION_TICK.reset(token);ctx.close()
  return result
 def test_hidden_document_transitions_deliver_one_account_and_one_submission(self):
  result=self.run_fixture()
  self.assertTrue(result['returned'],result);self.assertEqual(result['posts'],2,result)
  self.assertFalse(any(result['native_visible']),result);self.assertTrue(result['hidden_final'],result)
  self.assertTrue(result['render_stopped'],result)
 def test_stop_in_empty_form_releases_renderer_promptly(self):
  result=self.run_fixture(empty=True)
  self.assertFalse(result['returned']);self.assertEqual(result['posts'],0)
  self.assertLess(result['elapsed'],1.5,result);self.assertTrue(result['render_stopped'])
 def test_live_options_and_manual_typing_keep_ownership(self):
  result=self.run_fixture(empty=True,options_test=True)
  self.assertEqual(result['posts'],0,result);self.assertFalse(result['returned'])
  self.assertEqual(result['states'],[('manual',True),('typed',True)],result)
  self.assertTrue(result['render_stopped'])
