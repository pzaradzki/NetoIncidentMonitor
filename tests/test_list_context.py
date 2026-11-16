import unittest


class EncodedConditionsTests(unittest.TestCase):
    def test_end_and_sort_directives_do_not_change_ordered_conditions(self):
        from neto_incident_monitor.list_context import list_conditions
        query = 'active=true^ORstate=1^NQstate=2'
        self.assertEqual(list_conditions(query + '^EQ^ORDERBYDESCnumber'), query)
        self.assertEqual(list_conditions(query + '^ORDERBYnumber^EQ'), query)
        self.assertNotEqual(list_conditions('active=false^ORstate=1^NQstate=2'), query)
        self.assertEqual(list_conditions('short_descriptionLIKEORDERBYnumber'), 'short_descriptionLIKEORDERBYnumber')