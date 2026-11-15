import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from neto_incident_monitor.app import navigate, normalize_url, validate_urls
from neto_incident_monitor.monitoring import Health, Schedule
from neto_incident_monitor.single_instance import SingleInstance



class ReliabilityTests(unittest.TestCase):
    def test_classic_navigation_link_preserves_encoded_filter(self):
        from urllib.parse import quote, parse_qs, urlparse
        target = "incident_list.do?sysparm_query=active%3Dtrue%5Eassigned_toISEMPTY%5Estate!%3D6%5ElocationLIKESTORE%20003%20GDA%C5%83SK%5EORlocationLIKESTORE%20073%20GDYNIA%5Eassignment_groupLIKELMPL-L1-Support&sysparm_first_row=1&sysparm_view=default"
        direct = "https://adeo.service-now.com/" + target
        wrapped = "https://adeo.service-now.com/now/nav/ui/classic/params/target/" + quote(target, safe="!")
        self.assertEqual(normalize_url(wrapped), direct)
        self.assertEqual(normalize_url(direct), direct)
        self.assertEqual(validate_urls(wrapped + "\n" + direct), [direct])
        query = parse_qs(urlparse(normalize_url(wrapped)).query)
        self.assertIn("STORE 003 GDAŃSK", query["sysparm_query"][0])
        self.assertEqual(query["sysparm_view"], ["default"])
        from neto_incident_monitor.app import load_filters
        self.assertEqual(load_filters({"filters": [{"name": "Test", "url": wrapped}]}),
                         [{"name": "Test", "url": direct}])
        from unittest.mock import Mock
        page = Mock(url=wrapped)
        navigate(page, wrapped)
        self.assertEqual(page.goto.call_count, 2)
        for call in page.goto.call_args_list:
            self.assertEqual(call.args[0], direct)
        with self.assertRaises(ValueError):
            normalize_url("https://adeo.service-now.com/now/nav/ui/classic/params/target/" + quote("https://other.example/incident_list.do", safe=""))

    def test_schedule_wakes_and_coalesces_requests(self):
        schedule = Schedule()
        stop = threading.Event()
        done = threading.Event()
        thread = threading.Thread(target=lambda: (schedule.wait(60, stop), done.set()))
        thread.start()
        schedule.request()
        self.assertTrue(done.wait(1))
        thread.join()
        schedule.request()
        schedule.request()
        started = time.monotonic()
        self.assertFalse(schedule.wait(60, stop))
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertFalse(schedule.requested)
        stop.set()
        self.assertTrue(schedule.wait(60, stop))

    def test_health_per_filter_recovery_and_authentication(self):
        health = Health()
        self.assertFalse(health.failure("a"))
        self.assertFalse(health.failure("b"))
        self.assertFalse(health.failure("a"))
        self.assertTrue(health.failure("a"))
        self.assertFalse(health.failure("a"))
        health.success("a")
        self.assertFalse(health.failure("a"))
        self.assertTrue(health.authentication())
        self.assertFalse(health.authentication())
        health.resumed()
        self.assertTrue(health.authentication())

    def test_second_process_signals_primary_and_releases_mutex(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            primary = SingleInstance(folder)
            try:
                self.assertTrue(primary.primary)
                script = "from neto_incident_monitor.single_instance import SingleInstance; import sys; x=SingleInstance(sys.argv[1]); assert not x.primary; x.request_show(); x.close()"
                subprocess.run([sys.executable, "-c", script, folder], check=True, timeout=10)
                self.assertTrue(primary.poll())
                self.assertFalse(primary.poll())
            finally:
                primary.close()
            reopened = SingleInstance(folder)
            try:
                self.assertTrue(reopened.primary)
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
