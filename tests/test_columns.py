import unittest
from xml.sax.saxutils import quoteattr

from neto_incident_monitor.filter_layouts import parse_layout


class ColumnTests(unittest.TestCase):
    def test_layout_preserves_distinct_description_and_stable_field_keys(self):
        mapping = {'configuration_item': 'cmdb_ci', 'assignment_group': 'assignment_group',
                   'description': 'description', 'number': 'number', 'short_description': 'short_description',
                   'updated': 'sys_updated_on', 'state': 'state', 'caller': 'caller_id',
                   'assigned_to': 'assigned_to', 'parent_incident': 'parent_incident',
                   'opened_by': 'request.opened_by', 'sn:request_state': 'request_state',
                   'sn:request_item.state': 'request_item.state', 'sn:u_custom': 'u_custom'}
        choices = ''.join(f'<choice value={quoteattr(field)} label={quoteattr(field)}/>'
                          for field in mapping.values())
        xml = ('<xml sysparm_processor="AJAXXMLHttpAggregator"><xml status="200" '
               'sysparm_processor="UIPage" sysparm_name="getList" sysparm_processor_index="0">'
               f'<choice_list_set user_list="true"><selected>{choices}</selected></choice_list_set></xml></xml>')
        columns, personalized = parse_layout(xml)
        self.assertTrue(personalized)
        self.assertEqual([(column['key'], column['field']) for column in columns], list(mapping.items()))
