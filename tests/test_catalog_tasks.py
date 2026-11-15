import unittest
from urllib.parse import quote

from neto_incident_monitor.app import normalize_url


class CatalogTaskTests(unittest.TestCase):
    def test_navigation_url_preserves_query_encoding(self):
        target = "sc_task_list.do?sysparm_query=request.requested_for.companyDYNAMIC123%5Eopened_by%3D456&sysparm_first_row=1&sysparm_view="
        direct = "https://adeo.service-now.com/" + target
        wrapped = "https://adeo.service-now.com/now/nav/ui/classic/params/target/" + quote(target, safe="")
        self.assertEqual(normalize_url(wrapped), direct)
        self.assertEqual(normalize_url(direct), direct)
