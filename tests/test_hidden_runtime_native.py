"""Real Windows/Chromium runtime with local synthetic authentication only."""
import sys,tempfile,threading,unittest
from playwright.sync_api import sync_playwright
from neto_incident_monitor.app import wait_for_login
from neto_incident_monitor.browser_policy import BrowserRuntime,BrowserOptions
from neto_incident_monitor.browser_window import BrowserWindow
from neto_incident_monitor.browser_actions import ACTION_TICK,ready_control
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.pagination import Cancelled
from playwright._impl._errors import TargetClosedError

@unittest.skipUnless(sys.platform=='win32','Windows integration')
class NativeHiddenRuntimeTests(unittest.TestCase):
 def test_manual_handoff_visibility_options_and_stop(self):
  with tempfile.TemporaryDirectory(prefix='neto-runtime-fixture-') as profile,sync_playwright() as p:
   context=p.chromium.launch_persistent_context(profile,headless=False,no_viewport=True)
   page=context.pages[0];window=BrowserWindow(context.browser);stop=threading.Event()
   options=BrowserOptions({'hide_browser':True,'auto_login':False})
   log=LoginDiagnostics(source='dashboard',section='sla')
   runtime=BrowserRuntime(page,options,lambda:window,lambda *a:None,log,lambda *a:None)
   def route(r):
    if '/login.do' in r.request.url:
     body='<input type=password><script>setTimeout(()=>location.href='+repr(HOME)+',2000)</script>'
    else:body='<script>window.g_user={userID:"synthetic"}</script><button disabled>Ready</button>'
    r.fulfill(content_type='text/html',body=body)
   context.route('**/*',route)
   try:
    page.goto('https://adeo.service-now.com/login.do')
    self.assertTrue(wait_for_login(page,HOME,stop,runtime=runtime,browser_window=window))
    self.assertFalse(runtime.manual_required)
    self.assertFalse(window.is_visible())  # Confirmed login resumes hidden filters.
    with runtime.favorites_read(page,log):
     self.assertFalse(window.is_visible());self.assertIsNotNone(runtime.favorites_rendering.client)
     options.toggle_debug_browser();runtime.tick()
     self.assertTrue(window.is_visible());self.assertIsNone(runtime.favorites_rendering.client)
     options.toggle_debug_browser();runtime.tick()
     self.assertFalse(window.is_visible());self.assertIsNotNone(runtime.favorites_rendering.client)
     runtime.commands.put('show');runtime.tick()
     self.assertTrue(window.is_visible())
    with runtime.favorites_read(page,log):
     self.assertTrue(window.is_visible())
    runtime.commands.put('hide');runtime.tick()
    with self.assertRaises(Cancelled):
     with runtime.favorites_read(page,log):
      token=ACTION_TICK.set(lambda:stop.set())
      try:ready_control(page.get_by_role('button',name='Ready'),stop)
      finally:ACTION_TICK.reset(token)
    self.assertIsNone(runtime.favorites_rendering.client)
   finally:
    runtime.close()
    try:context.close()
    except TargetClosedError:pass  # Closing the last persistent page can close its context.

 def test_closing_real_page_detaches_active_rendering(self):
  with tempfile.TemporaryDirectory(prefix='neto-runtime-fixture-') as profile,sync_playwright() as p:
   context=p.chromium.launch_persistent_context(profile,headless=False,no_viewport=True)
   page=context.pages[0];window=BrowserWindow(context.browser)
   log=LoginDiagnostics(source='dashboard',section='sla')
   runtime=BrowserRuntime(page,BrowserOptions({'hide_browser':True}),lambda:window,lambda *a:None,log,lambda *a:None)
   context.route('**/*',lambda r:r.fulfill(content_type='text/html',body='<script>window.g_user={userID:"synthetic"}</script>'))
   try:
    page.goto(HOME)
    with runtime.favorites_read(page,log):
     self.assertIsNotNone(runtime.favorites_rendering.client)
     with self.assertNoLogs('asyncio',level='ERROR'):
      page.close()
     self.assertIsNone(runtime.favorites_rendering.client)
    self.assertIsNone(runtime.favorites_rendering.client)
   finally:
    runtime.close()
    try:context.close()
    except TargetClosedError:pass  # The test deliberately closed the last page above.
