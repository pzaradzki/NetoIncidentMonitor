import threading
import time
import tkinter as tk
import unittest
import queue
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.pagination import list_total, read_all, LargeListRejected
from neto_incident_monitor.widgets import RoundedButton


class LargeListTests(unittest.TestCase):
    def test_timeout_skips_read_without_disabling_filter(self):
        app = App.__new__(App)
        app.filters = [{"url": "url", "enabled": True}]
        app.events = queue.Queue()
        app.stop = threading.Event()
        with patch("neto_incident_monitor.app.time.monotonic", side_effect=[0, 16]):
            self.assertFalse(app.approve_large_list("url", "A", 2000))
        self.assertTrue(app.filters[0]["enabled"])
        _, request = app.events.get_nowait()
        self.assertTrue(request["done"].is_set())

    def test_pager_count_and_rejection_before_next_page(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                url = "https://example.test/sc_task_list.do"
                page.route("https://example.test/**", lambda route: route.fulfill(
                    content_type="text/html; charset=utf-8", body='<div class="list2_paging">1 do 20 z 81 527</div>'))
                page.goto(url)
                self.assertEqual(list_total(page, url), 81527)
                approve = Mock(return_value=False)
                with self.assertRaises(LargeListRejected):
                    read_all(page, url, threading.Event(), lambda _: {"SCTASK1234567": {}},
                             lambda *_: False, lambda *_: False, lambda *_: None, approve_large=approve)
                approve.assert_called_once_with(81527)
            finally:
                browser.close()

    def test_reject_disables_filter_and_remember_persists_permission(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = App.__new__(App)
            app.root = root
            app.quitting = False
            app.stop = threading.Event()
            app.filters = [{"url": "url", "name": "A", "enabled": True}]
            app.persist_filters = Mock()
            app.refresh_filters = Mock()
            def children(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from children(child)
            for reject in (True, False):
                request = {"url": "url", "name": "A", "count": 81527, "deadline": time.monotonic()+15,
                           "done": threading.Event(), "accepted": False}
                app.show_large_list_prompt(request)
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                if not reject:
                    next(w for w in children(dialog) if w.winfo_class()=="TCheckbutton").invoke()
                button = "Odrzuć" if reject else "Pobierz"
                next(w for w in children(dialog) if isinstance(w, RoundedButton) and w.text==button).invoke()
                self.assertTrue(request["done"].is_set())
                self.assertEqual(request["accepted"], not reject)
            self.assertFalse(app.filters[0]["enabled"])
            self.assertTrue(app.filters[0]["allow_large_list"])
            self.assertEqual(app.persist_filters.call_count, 2)
        finally:
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()
