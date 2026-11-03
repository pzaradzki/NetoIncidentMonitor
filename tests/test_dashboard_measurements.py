import json
import unittest
from unittest.mock import Mock

from neto_incident_monitor.login_diagnostics import LoginDiagnostics, diagnostic_read, _logger
from neto_incident_monitor.dashboard import diagnostic_steps, operation, observation, _diagnostics
from neto_incident_monitor.pagination import Cancelled


class MeasurementTests(unittest.TestCase):
    def test_read_context_groups_sections_but_not_periodic_executions(self):
        @diagnostic_read
        def execute():
            for section in ('sla', 'held'):
                log = LoginDiagnostics(source='dashboard', section=section, request_id=3)
                log.record('section_read_attempt', attempt=2)
                with diagnostic_steps(log):
                    operation('read_scores')
                    observation('loading', 0, 2)
                log.record('section_read_complete', arbitrary='PRIVATE_TOKEN')
        with self.assertLogs(_logger, level='INFO') as captured:
            execute()
            execute()
        rows = [json.loads(r.getMessage()) for r in captured.records]
        self.assertEqual(len({r['run_id'] for r in rows}), 1)
        self.assertEqual(len({r['read_id'] for r in rows}), 2)
        for read_id in {r['read_id'] for r in rows}:
            self.assertEqual({r['section'] for r in rows if r['read_id'] == read_id}, {'sla', 'held'})
        ends = [r for r in rows if r['event'] == 'dashboard_stage_end']
        self.assertEqual(len(ends), 4)
        self.assertTrue(all(r['duration_ms'] >= 0 and r['attempt'] == 2 for r in ends))
        self.assertNotIn('PRIVATE_TOKEN', str(captured.output))

    def test_cancel_and_errors_close_stage_without_leaking_exception(self):
        for error, outcome in ((Cancelled(), 'cancelled'), (ValueError('PRIVATE_PASSWORD'), 'error')):
            with self.assertLogs(_logger, level='INFO') as captured:
                with self.assertRaises(type(error)), diagnostic_steps(LoginDiagnostics(section='threatened')):
                    operation('navigate')
                    raise error
            rows = [json.loads(r.getMessage()) for r in captured.records]
            self.assertEqual(rows[-1]['outcome'], outcome)
            self.assertNotIn('PRIVATE_PASSWORD', str(captured.output))
            self.assertIsNone(_diagnostics.get())

    def test_broken_sink_and_detach_do_not_replace_result(self):
        log = Mock()
        log.record.side_effect = OSError('PRIVATE_TOKEN')
        log.attach.return_value.side_effect = OSError('PRIVATE_TOKEN')
        with diagnostic_steps(log, page=Mock()):
            operation('navigate')
            observation('missing', 0, 6)
        log.attach.return_value.assert_called_once()
