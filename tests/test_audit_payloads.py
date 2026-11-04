import json
import re
import unittest
from unittest.mock import patch

from neto_incident_monitor import teams_notifications as teams, google_chat_notifications as chat

NUMBER = 'INC1234567'
LINK = 'https://adeo.service-now.com/incident.do?sys_id=' + 'a'*32 + '&sysparm_view=' + 'a'*64


class AuditPayloadTests(unittest.TestCase):
    def test_teams_expanded_first_chunk_obeys_json_limit_and_preserves_text(self):
        message = ' '.join([NUMBER]*90)
        chunks = list(teams.message_chunks('Synthetic', message, {NUMBER: LINK}))
        self.assertEqual(''.join(chunks), message)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(json.dumps(teams.payload('Synthetic', chunk, {NUMBER: LINK})).encode()), 25000)
            self.assertNotRegex(chunk, r'^(?:NC|C)1234567|INC12345$')

    def test_teams_impossible_header_fails_before_transport(self):
        with patch.object(teams, 'send') as send:
            with self.assertRaises(teams.DeliveryError):
                list(teams.message_chunks('X'*30000, 'message'))
        send.assert_not_called()

    def test_chat_expanded_links_are_complete_without_lost_suffix(self):
        message = ' '.join([NUMBER]*270)
        parts = chat.payloads('Synthetic', message, {NUMBER: LINK})
        visible = ''.join(re.sub(r'<[^>]+\|([^>]+)>', r'\1', p['text'].removeprefix('Synthetic\n')) for p in parts)
        self.assertEqual(visible, message)
        self.assertEqual(sum(p['text'].count(NUMBER) for p in parts), 270)
        for part in parts:
            self.assertLessEqual(len(part['text'].encode()), 28000)
            self.assertLessEqual(len(json.dumps(part, ensure_ascii=False).encode()), 30000)
            self.assertEqual(part['text'].count('<'), part['text'].count('>'))

    def test_unicode_quotes_and_newlines_keep_order_and_every_character(self):
        message = ('Zażółć 😀 " \\ &\n'*4000) + NUMBER
        self.assertEqual(''.join(teams.message_chunks('Title', message)), message)
        parts = chat.payloads('Title', message)
        self.assertEqual(''.join(p['text'].removeprefix('Title\n') for p in parts), chat.plain(message))
        self.assertTrue(all(len(json.dumps(p, ensure_ascii=False).encode()) <= 30000 for p in parts))


if __name__ == '__main__':
    unittest.main()
