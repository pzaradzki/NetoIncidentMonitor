import json
import queue
import threading
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError
from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import operation
from neto_incident_monitor.login_diagnostics import _logger


class DashboardControlTests(unittest.TestCase):
    def test_error_diagnostics_identify_operation_without_dom_or_exception_text(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app.dashboard_requests = queue.Queue()
        app.dashboard_requests.put((1, 2026, 10))
        def fail(*args):
            operation('api_request')
            raise TimeoutError('PRIVATE_LOGIN PRIVATE_TOKEN')
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=fail), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value={}), \
                self.assertLogs(_logger, level='INFO') as captured:
            app.read_dashboard_request(Mock())
        records = [json.loads(record.getMessage()) for record in captured.records]
        failure = next(record for record in records if record['event'] == 'section_read_error')
        self.assertEqual(failure['operation'], 'api_request')
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))
