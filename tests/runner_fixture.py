"""Intentional callback failure, loaded only by the runner's own regression test."""
import tkinter as tk
import unittest


class CallbackFixture(unittest.TestCase):
    def test_callback_failure(self):
        root = tk.Tk()
        root.withdraw()
        root.report_callback_exception = lambda *args: None
        def fail():
            raise RuntimeError('PRIVATE_SECRET')
        root.after(0, fail)
        root.update()
        root.destroy()
