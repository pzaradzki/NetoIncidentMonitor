import unittest
from unittest.mock import Mock
from app import App
from notifications import batch_text


class NotificationTests(unittest.TestCase):
    def test_batch_deduplicates_and_limits_message(self):
        incidents = [{"number": f"INC00000{i:02}"} for i in range(12)]
        title, message = batch_text(incidents + incidents)
        self.assertEqual(title, "Nowe incydenty: 12")
        self.assertIn("oraz 6 kolejnych", message)
        self.assertLessEqual(len(message), 240)
        self.assertIsNone(batch_text([]))

    def test_single_incident_includes_description(self):
        self.assertEqual(batch_text([{"number": "INC0000001", "short_description": "Problem z kasą"}]),
                         ("Nowy incydent: INC0000001", "Problem z kasą"))

    def test_one_alert_and_sound_for_multiple_incidents(self):
        from unittest.mock import patch
        app = Mock()
        app.history.snapshot.return_value = {number: {"read": False} for number in ("INC0000001", "INC0000002")}
        incidents = [{"number": "INC0000001"}, {"number": "INC0000002"}, {"number": "INC0000001"}]
        with patch("plyer.notification.notify") as notify:
            App.notify_batch(app, incidents)
            notify.assert_called_once()
            app.root.bell.assert_called_once()
            self.assertEqual(notify.call_args.kwargs["title"], "Nowe incydenty: 2")
            app.history.snapshot.return_value = {}
            App.notify_batch(app, incidents)
            notify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
