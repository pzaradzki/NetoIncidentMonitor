import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from neto_incident_monitor.app import collect
from neto_incident_monitor.columns import ColumnDiscovery
from neto_incident_monitor.list_context import ListStateError


class FilterRecordTypeTests(unittest.TestCase):
    def test_wrong_record_type_cannot_be_collected_as_an_incident(self):
        frame = Mock(url='https://adeo.service-now.com/incident_list.do')
        frame.locator.return_value.evaluate_all.return_value = [
            {'label': 'RITM0000123', 'href': '', 'fields': {'short_description': ''}},
        ]
        with self.assertRaisesRegex(ListStateError, 'record_type_mismatch'):
            collect(SimpleNamespace(frames=[frame]))


class ColumnConsistencyTests(unittest.TestCase):
    def test_reordering_is_allowed_but_changed_labels_fail(self):
        columns = ColumnDiscovery()
        schema = [{'key': 'number', 'label': 'Numer'}, {'key': 'state', 'label': 'Stan'}]
        columns.discover(schema)
        columns.discover(list(reversed(schema)))
        with self.assertRaisesRegex(ListStateError, 'schema_changed'):
            columns.discover([schema[0], {'key': 'state', 'label': 'State'}])


if __name__ == '__main__':
    unittest.main()
