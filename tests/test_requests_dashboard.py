import json
import queue
import threading
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import HELD_TITLES, REQUEST_TITLES, TITLES
from neto_incident_monitor.login_diagnostics import _logger


class RequestsDashboardTests(unittest.TestCase):
    def test_partial_result_is_bounded_and_not_logged_as_complete(self):
        app = App.__new__(App)
        app.stop, app.events, app.dashboard_requests = threading.Event(), queue.Queue(), queue.Queue()
        app.dashboard_requests.put((1, 2026, 10))
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', return_value=dict.fromkeys(TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES[:-1], 0)), \
                self.assertLogs(_logger, level='INFO') as logs:
            app.read_dashboard_request(Mock())
        records = [json.loads(r.getMessage()) for r in logs.records]
        partial = next(r for r in records if r['event'] == 'section_read_error' and r.get('section') == 'requests')
        self.assertFalse(any(r['event'] == 'section_read_complete' and r['session'] == partial['session'] for r in records))
        self.assertTrue(any(r.get('read_reason') == 'api_incomplete' for r in records))
