from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch
from app import App

class ContextMenuTests(TestCase):
    def test_actions_use_clicked_incident_and_open_marks_read(self):
        app = App.__new__(App)
        app.root = Mock()
        app.mark_read = Mock()
        table = Mock()
        table.identify_row.return_value = 'clicked'
        app.row_numbers = {(table, 'clicked'): 'INC1234567'}
        app.items = {(table, 'clicked'): 'https://example.test/incident'}
        event = SimpleNamespace(widget=table, y=20, x_root=100, y_root=200)
        with patch('app.IncidentMenu') as factory:
            menu = factory.return_value
            app.incident_context_menu(event)
            commands = {call.kwargs['label']: call.kwargs['command'] for call in menu.add_command.call_args_list}
            commands['Kopiuj numer']()
            app.root.clipboard_append.assert_called_with('INC1234567')
            commands['Kopiuj link']()
            app.root.clipboard_append.assert_called_with('https://example.test/incident')
            with patch('app.webbrowser.open', return_value=False):
                commands['Otwórz incydent']()
                app.mark_read.assert_not_called()
            with patch('app.webbrowser.open', return_value=True):
                commands['Otwórz incydent']()
                app.mark_read.assert_called_once_with(['INC1234567'])
            app.mark_read.reset_mock()
            commands['Oznacz jako przeczytany']()
            app.mark_read.assert_called_once_with(['INC1234567'])
            table.selection_set.assert_called_once_with('clicked')
            menu.show.assert_called_once_with(100, 200)

    def test_empty_space_does_not_open_menu(self):
        app = App.__new__(App)
        table = Mock()
        table.identify_row.return_value = ''
        with patch('app.IncidentMenu') as menu:
            app.incident_context_menu(SimpleNamespace(widget=table, y=20))
            menu.assert_not_called()

if __name__ == '__main__':
    main()
