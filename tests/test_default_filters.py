import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from neto_incident_monitor.app import initialize_default_filters, load_filters


class DefaultFiltersTests(unittest.TestCase):
    def test_first_run_persists_four_enabled_editable_filters(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd(), ignore_cleanup_errors=True) as directory:
            path = Path(directory) / 'config.json'
            result = initialize_default_filters({}, path)
            filters = load_filters(result)
            self.assertEqual([f['name'] for f in filters],
                             ['L1 - Niepodjęte', 'Moje - Nowe / W trakcie', 'Moje - Wstrzymane', 'Moje - Wnioski'])
            self.assertTrue(all(f['enabled'] for f in filters))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), result)
            new_query = parse_qs(urlsplit(filters[0]['url']).query)['sysparm_query'][0]
            self.assertEqual(new_query, 'state=1^ORstate=2^ORstate=3^company=58e8d49fdbfae300eeb432f6f496194f'
                             '^assigned_toISEMPTY^assignment_group=36e1263edb64b7408033459d3b9619e0')
            query = parse_qs(urlsplit(filters[1]['url']).query)['sysparm_query'][0]
            self.assertEqual(query, 'state=1^ORstate=2^assigned_toDYNAMIC90d1921e5f510100a9ad2572f2b477fe')

    def test_deleted_defaults_never_return(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd(), ignore_cleanup_errors=True) as directory:
            path = Path(directory) / 'config.json'
            initialize_default_filters({}, path)
            path.write_text('{"filters": []}', encoding='utf-8')
            settings = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(load_filters(initialize_default_filters(settings, path)), [])
            # Explicitly empty modern filters take precedence over old URL lists.
            self.assertEqual(load_filters({'filters': [], 'urls': ['https://adeo.service-now.com/incident_list.do']}), [])

    def test_existing_config_and_legacy_urls_unchanged(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd(), ignore_cleanup_errors=True) as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{}', encoding='utf-8')
            self.assertEqual(initialize_default_filters({}, path), {})
            old = {'urls': ['https://adeo.service-now.com/incident_list.do']}
            self.assertIs(initialize_default_filters(old, Path(directory) / 'missing.json'), old)
