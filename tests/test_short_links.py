import unittest

from neto_incident_monitor.app import load_filters
from neto_incident_monitor.service_now_urls import normalize_list_url, effective_list_url

BASE = 'https://adeo.service-now.com'
SHORT = BASE + '/now/nav/ui/classic/__tinyId__/' + 'Abc123xyz456' * 3


class ShortLinkTests(unittest.TestCase):
    def test_only_exact_trusted_short_links_are_accepted(self):
        self.assertEqual(normalize_list_url(SHORT), SHORT)
        self.assertNotIn('url_invalid', load_filters({'urls': [SHORT]}, tolerate_invalid=True)[0])
        for bad in [SHORT.replace('adeo.service-now.com', 'evil.test'), SHORT + '/other',
                    SHORT + '?url=https://evil.test', SHORT + '#fragment',
                    SHORT.replace('.com/', '.com:8443/'), SHORT.replace('https://', 'https://:secret@'),
                    SHORT.rsplit('/', 1)[0] + '/short']:
            with self.subTest(url=bad), self.assertRaises(ValueError):
                normalize_list_url(bad)

    def test_only_trusted_saved_targets_are_used_for_shortcuts(self):
        foreign = 'https://evil.test/sc_task_list.do'
        target = BASE + '/sc_task_list.do?sysparm_query=active%3Dtrue'
        self.assertEqual(effective_list_url(SHORT, [{'url': SHORT, 'resolved_list_url': target}]), target)
        self.assertEqual(effective_list_url(SHORT, [{'url': SHORT, 'resolved_list_url': foreign}]), SHORT)
