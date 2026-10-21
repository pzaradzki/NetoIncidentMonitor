import json
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor import release_check as checks
from neto_incident_monitor.widgets import RoundedButton


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ReleaseCheckTests(unittest.TestCase):
    def test_version_comparison_and_validated_release_link(self):
        for tag, newer in [('v1.6.0', False), ('v1.5.9', False), ('v1.10.0', True), ('v2.0.0', True)]:
            with self.subTest(tag=tag), patch.object(checks, '__version__', '1.6.0'), patch.object(checks, 'urlopen') as fetch:
                fetch.return_value.__enter__.return_value.read.return_value = json.dumps({'tag_name': tag}).encode()
                self.assertEqual(checks.latest_release(), (newer, checks.RELEASES + tag))
                self.assertEqual(fetch.call_args.kwargs['timeout'], 15)
        for data in [{'tag_name': 'https://evil.test'}, {'tag_name': 'v2.0.0', 'prerelease': True}, {}]:
            with patch.object(checks, 'urlopen') as fetch:
                fetch.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
                with self.assertRaises(ValueError):
                    checks.latest_release()

    def test_result_buttons_open_only_on_user_click(self):
        root = tk.Tk()
        try:
            for newer, labels in [(False, ['Ok']), (True, ['Otwórz Github', 'Anuluj'])]:
                with patch.object(checks.webbrowser, 'open', return_value=True) as browser:
                    checks.show_result(root, newer, checks.RELEASES + 'v2.0.0')
                    dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                    buttons = [w for w in descendants(dialog) if isinstance(w, RoundedButton)]
                    self.assertEqual([w.text for w in buttons], labels)
                    browser.assert_not_called()
                    buttons[0].invoke()
                    if newer:
                        browser.assert_called_once_with(checks.RELEASES + 'v2.0.0')
            with patch.object(checks, 'latest_release', side_effect=OSError('offline')):
                button = RoundedButton(root, text='Sprawdź', command=lambda: None)
                checks.check_updates(root, button)
                self.assertFalse(button.enabled)
                root.after(250, root.quit)
                root.mainloop()
                self.assertTrue(button.enabled)
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                self.assertIn('Nie udało', next(w.cget('text') for w in descendants(dialog) if w.winfo_class() == 'TLabel'))
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()
