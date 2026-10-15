import unittest
from datetime import datetime, timezone
from neto_incident_monitor.columns import age_minutes, DATA_FIELDS
from neto_incident_monitor.app import incident_values


class IncidentAgeTests(unittest.TestCase):
    def test_whole_minutes_and_polish_dates(self):
        now = datetime(2026, 10, 15, 10, 30, 59)
        for created in ('2026-10-15 10:00:00', '15.10.2026 10:00:00', '15.10.2026 10:00'):
            self.assertEqual(age_minutes(created, 'INC1234567', now), '30')

    def test_invalid_missing_task_and_future(self):
        now = datetime(2026, 10, 15, 10)
        self.assertEqual(age_minutes('bad', 'INC1', now), '—')
        self.assertEqual(age_minutes('', 'INC1', now), '—')
        self.assertEqual(age_minutes('2026-10-15 09:00', 'SCTASK1', now), '—')
        self.assertEqual(age_minutes('2026-10-15 11:00', 'INC1', now), '0')

    def test_timezone_offset_and_live_recalculation(self):
        self.assertEqual(age_minutes('2026-10-15T10:00:00+02:00', 'INC1', datetime(2026, 10, 15, 8, 45, tzinfo=timezone.utc)), '45')
        self.assertEqual(age_minutes('2026-10-15 10:00', 'INC1', datetime(2026, 10, 15, 10, 31)), '31')

    def test_computed_column_does_not_become_remote_field(self):
        self.assertNotIn('age_minutes', DATA_FIELDS)
        from neto_incident_monitor.columns import FIELDS
        columns = [key for key, _, _ in FIELDS if key not in ('read', 'time')]
        values = incident_values({'number': 'INC1', 'created': 'bad'})
        self.assertEqual(len(values), len(columns))
        self.assertEqual(values[columns.index('age_minutes')], '—')
