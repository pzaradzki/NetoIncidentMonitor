from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch
from neto_incident_monitor.app import App

class ContextMenuTests(TestCase):
    def test_notification_uses_record_from_clicked_tab_without_marking_read(self):
        app = App.__new__(App)
        app.root = Mock()
        app.filters = [{'url': 'filter', 'enabled': False}]
        app.selected_filter_url = Mock(return_value='filter')
        app.selected_filter_index = Mock(return_value=1)
        app.notify = Mock(); app.notify.get.return_value = True
        app.teams_enabled = Mock(); app.teams_enabled.get.return_value = False
        app.current_table = Mock()
        app.snapshots = {1: {'SCTASK1234567': {'short_description': 'Current task', 'requested_for': 'Anna'}}}
        app.history = Mock()
        app.history.snapshot.return_value = {'INC1234567': {'incident': {'short_description': 'Historical incident'}}}
        app.notify_filter = Mock()
        app.test_record_notification(app.current_table, 'SCTASK1234567', 'https://example.test/sc_task.do')
        self.assertEqual(app.notify_filter.call_args.args[1][0]['short_description'], 'Current task')
        self.assertTrue(app.notify_filter.call_args.kwargs['manual'])
        app.test_record_notification(Mock(), 'INC1234567', 'https://example.test/incident.do')
        self.assertEqual(app.notify_filter.call_args.args[1][0]['short_description'], 'Historical incident')
        app.history.mark_read.assert_not_called()

    def test_actions_use_clicked_incident_and_open_marks_read(self):
        app = App.__new__(App)
        app.root = Mock()
        app.mark_read = Mock()
        app.test_record_notification = Mock()
        table = Mock()
        table.identify_row.return_value = 'clicked'
        app.row_numbers = {(table, 'clicked'): 'INC1234567'}
        app.items = {(table, 'clicked'): 'https://example.test/incident'}
        event = SimpleNamespace(widget=table, y=20, x_root=100, y_root=200)
        with patch('neto_incident_monitor.app.IncidentMenu') as factory:
            menu = factory.return_value
            app.incident_context_menu(event)
            commands = {call.kwargs['label']: call.kwargs['command'] for call in menu.add_command.call_args_list}
            commands['Kopiuj numer']()
            app.root.clipboard_append.assert_called_with('INC1234567')
            commands['Kopiuj link']()
            app.root.clipboard_append.assert_called_with('https://example.test/incident')
            with patch('neto_incident_monitor.app.webbrowser.open', return_value=False):
                commands['Otwórz incydent']()
                app.mark_read.assert_not_called()
            with patch('neto_incident_monitor.app.webbrowser.open', return_value=True):
                commands['Otwórz incydent']()
                app.mark_read.assert_called_once_with(['INC1234567'])
            app.mark_read.reset_mock()
            commands['Oznacz jako przeczytany']()
            app.mark_read.assert_called_once_with(['INC1234567'])
            commands['Test powiadomienia']()
            app.test_record_notification.assert_called_once_with(table, 'INC1234567', 'https://example.test/incident')
            table.selection_set.assert_called_once_with('clicked')
            menu.show.assert_called_once_with(100, 200)

    def test_empty_space_does_not_open_menu(self):
        app = App.__new__(App)
        table = Mock()
        table.identify_row.return_value = ''
        with patch('neto_incident_monitor.app.IncidentMenu') as menu:
            app.incident_context_menu(SimpleNamespace(widget=table, y=20))
            menu.assert_not_called()

if __name__ == '__main__':
    main()
