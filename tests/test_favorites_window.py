import threading
import json
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger


class FavoritesPageTests(unittest.TestCase):
    def test_single_startup_blank_is_reused(self):
        from neto_incident_monitor.favorites_worker import select_import_page
        context=Mock();blank=Mock(url='about:blank');context.pages=[blank]
        self.assertIs(select_import_page(context),blank)
        context.new_page.assert_not_called()

    def test_restored_pages_are_not_navigated_or_closed(self):
        from neto_incident_monitor.favorites_worker import select_import_page
        context=Mock();saved=Mock(url='https://example.test/saved');context.pages=[saved]
        self.assertIs(select_import_page(context),context.new_page.return_value)
        saved.close.assert_not_called();saved.goto.assert_not_called()

    def test_multiple_pages_including_blank_are_preserved(self):
        from neto_incident_monitor.favorites_worker import select_import_page
        context=Mock();context.pages=[Mock(url='about:blank'),Mock(url='https://example.test/saved')]
        self.assertIs(select_import_page(context),context.new_page.return_value)
        for page in context.pages:page.close.assert_not_called()


class FavoritesViewportTests(unittest.TestCase):
    def test_authentication_is_checked_before_resizing(self):
        from neto_incident_monitor.favorites_reader import read_favorites
        page=Mock()
        with patch('neto_incident_monitor.favorites_reader.check_session',side_effect=AuthenticationRequired()):
            with self.assertRaises(AuthenticationRequired):
                read_favorites(page,threading.Event())
        page.context.new_cdp_session.assert_not_called()

    def test_natural_viewport_is_restored_after_read_error_login_and_stop(self):
        from neto_incident_monitor.favorites_reader import menu_viewport
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                context=browser.new_context(no_viewport=True)
                page=context.new_page()
                original=page.evaluate('() => [innerWidth,innerHeight]')
                for error in (None,TimeoutError('synthetic'),AuthenticationRequired(),Cancelled()):
                    try:
                        with menu_viewport(page):
                            self.assertEqual(page.evaluate('() => [innerWidth,innerHeight]'),[751,884])
                            if error:raise error
                    except (TimeoutError,AuthenticationRequired,Cancelled):
                        pass
                    page.wait_for_function('expected => innerWidth===expected[0] && innerHeight===expected[1]',arg=original,timeout=2000)
                    self.assertEqual(page.evaluate('() => [innerWidth,innerHeight]'),original)
                    self.assertIsNone(page.viewport_size)
            finally:
                browser.close()

    def test_viewport_diagnostics_have_fixed_stages_and_no_page_data(self):
        from neto_incident_monitor.favorites_reader import menu_viewport
        page=Mock(viewport_size=None)
        with self.assertLogs(_logger,level='INFO') as captured:
            log=LoginDiagnostics(source='favorites',import_id='a'*32)
            with self.assertRaises(TimeoutError),menu_viewport(page,log):
                raise TimeoutError('SYNTHETIC_SECRET')
        rows=[json.loads(r.getMessage()) for r in captured.records if json.loads(r.getMessage())['event']=='favorites_stage']
        self.assertEqual([r['import_stage'] for r in rows],['viewport_read','viewport_natural'])
        self.assertTrue(all(r['import_id']=='a'*32 for r in rows))
        self.assertNotIn('SYNTHETIC_SECRET',str(captured.output))
