import unittest
from urllib.parse import quote

from neto_incident_monitor.service_now_urls import normalize_list_url, safe_record_url
from neto_incident_monitor.notification_templates import standard
from neto_incident_monitor.teams_notifications import payload
from neto_incident_monitor.google_chat_notifications import payloads

BASE = 'https://adeo.service-now.com'


class RequestListTests(unittest.TestCase):
    def test_lists_and_safe_matching_record_links(self):
        for prefix, table in [('REQ', 'sc_request'), ('RITM', 'sc_req_item')]:
            direct = f'{BASE}/{table}_list.do?sysparm_query=active%3Dtrue'
            self.assertEqual(normalize_list_url(direct), direct)
            wrapped = BASE + '/now/nav/ui/classic/params/target/' + quote(direct[len(BASE)+1:], safe='')
            self.assertEqual(normalize_list_url(wrapped), direct)
            number = prefix + '0012345'
            record = f'{BASE}/{table}.do?sys_id=0123456789abcdef0123456789abcdef'
            self.assertEqual(safe_record_url(record, number, direct), record)
            self.assertEqual(safe_record_url(BASE + '/incident.do?sys_id=0123456789abcdef0123456789abcdef', number), '')
            self.assertEqual(safe_record_url(record.replace('adeo.service-now.com', 'evil.test'), number), '')
            title, text = standard('Filtr', [{'number': number, 'short_description': 'Opis'}])
            self.assertEqual(title, 'Filtr · 1')
            self.assertIn(f'>{number}</a>', payload(title, text, {number: record})['text'])
            self.assertIn(f'|{number}>', payloads(title, text, {number: record})[0]['text'])
