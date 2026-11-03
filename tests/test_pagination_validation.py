import json
import threading
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.app import collect, empty_list, authentication_page, navigate
from neto_incident_monitor.pagination import read_all, Cancelled, AuthenticationRequired, LargeListRejected
from neto_incident_monitor.list_context import ListStateError
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from tests.list_fixture import URL, classic_list


class PaginationValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.loads = []

    def serve(self, factory):
        def route(request):
            self.loads.append(True)
            request.fulfill(body=factory(len(self.loads)), content_type='text/html; charset=utf-8')
        self.page.route('**/*', route)

    def read(self, **kwargs):
        kwargs.setdefault('diagnostics', Mock())
        return read_all(self.page, URL, threading.Event(), collect, empty_list,
                        authentication_page, navigate, **kwargs)

    def test_complete_read_with_twenty_or_one_hundred_rows_and_short_last_page(self):
        for size, total in ((20, 45), (100, 205)):
            with self.subTest(size=size):
                self.page.unroute_all()
                self.serve(lambda _: classic_list(total=total, size=size))
                values, pages = self.read()
                self.assertEqual(len(values), total)
                self.assertEqual(pages, 3)
                self.assertEqual(set(values), {f'INC{i:07}' for i in range(1, total + 1)})

    def test_restored_first_page_is_confirmed_by_range_not_url(self):
        self.serve(lambda _: classic_list(total=45, size=20, start=41))
        values, pages = self.read()
        self.assertEqual((len(values), pages), (45, 3))
        self.assertEqual(len(self.loads), 1)

    def test_skip_overlap_size_total_and_query_changes_never_return_partial_result(self):
        for mode in ('skip', 'overlap', 'size_change', 'total_change', 'query_change'):
            with self.subTest(mode=mode), patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 1.8):
                self.page.unroute_all()
                self.loads.clear()
                self.serve(lambda _, mode=mode: classic_list(total=45, size=20, mode=mode))
                with self.assertRaises(ListStateError) as error:
                    self.read()
                self.assertIn(error.exception.reason, ('range_mismatch', 'list_changed'))
                self.assertEqual(len(self.loads), 2)

    def test_retry_restarts_from_first_row_and_discards_previous_attempt(self):
        self.serve(lambda attempt: classic_list(total=45, size=20, mode='overlap' if attempt == 1 else 'normal'))
        with patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 1.8):
            values, pages = self.read()
        self.assertEqual((len(values), pages), (45, 3))
        self.assertEqual(set(values), {f'INC{i:07}' for i in range(1, 46)})
        self.assertEqual(len(self.loads), 2)

    def test_disabled_next_does_not_override_total(self):
        self.serve(lambda _: classic_list(total=528, size=20).replace('next.disabled=end>=s.total', 'next.disabled=true'))
        with patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 1.8):
            with self.assertRaises(ListStateError) as error:
                self.read()
        self.assertEqual(error.exception.reason, 'premature_end')
        self.assertEqual(len(self.loads), 2)

    def test_partial_dom_is_not_accepted_even_with_stable_record_numbers(self):
        html = classic_list(total=45, size=20).replace('s.first+i', 's.first')
        self.serve(lambda _: html)
        with patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 1.8):
            with self.assertRaises(ListStateError) as error:
                self.read()
        self.assertEqual(error.exception.reason, 'row_count_mismatch')

    def test_empty_message_without_target_table_is_not_a_result(self):
        self.serve(lambda _: '<p>No records to display</p>')
        with patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 0.8):
            with self.assertRaises(ListStateError):
                self.read()

    def test_wrong_initial_query_rejects_even_complete_rows(self):
        self.serve(lambda _: classic_list(total=2).replace('query="active=true"', 'query="active=false"'))
        with self.assertRaises(ListStateError) as error:
            self.read()
        self.assertEqual(error.exception.reason, 'query_mismatch')
        self.assertEqual(len(self.loads), 2)

    def test_primary_table_without_range_cannot_pass_as_anonymous_legacy_list(self):
        self.serve(lambda _: '<table id="incident_table" data-list_id="incident" query="active=true">'
                             '<tr><th>Numer</th></tr><tr><td><a href="/incident.do">INC0000001</a></td></tr>'
                             '</table><button aria-label="Inna strona">Dalej</button>')
        with patch('neto_incident_monitor.pagination.PAGE_WAIT_SECONDS', 0.8):
            with self.assertRaises(ListStateError) as error:
                self.read()
        self.assertEqual(error.exception.reason, 'metadata_missing')

    def test_schema_change_retries_whole_list_with_fresh_discovery(self):
        from neto_incident_monitor.columns import ColumnDiscovery

        def response(attempt):
            html = classic_list(total=3, size=2)
            if attempt == 1:
                return html.replace('s.first=n;render()', 's.first=n;table.querySelector("th").textContent="Changed";render()')
            return html.replace('>Numer<', '>New number<')

        discovery = ColumnDiscovery()

        def stage(name, index):
            nonlocal discovery
            if name == 'retry':
                discovery = ColumnDiscovery()

        self.serve(response)
        records, pages = read_all(
            self.page, URL, threading.Event(), lambda page: collect(page, discovery),
            empty_list, authentication_page, navigate, on_stage=stage)
        self.assertEqual((len(records), pages, len(self.loads)), (3, 2, 2))
        self.assertEqual(discovery.schema[0]['label'], 'New number')

    def test_redirect_to_other_explicit_view_is_rejected(self):
        requested = URL + '&sysparm_view=expected'

        self.serve(lambda _: classic_list(total=2))
        with self.assertRaises(ListStateError) as error:
            read_all(self.page, requested, threading.Event(), collect, empty_list, authentication_page,
                     lambda page, url: navigate(page, url.replace("sysparm_view=expected", "sysparm_view=other")))
        self.assertEqual(error.exception.reason, 'view_mismatch')

    def test_genuine_empty_list_is_accepted(self):
        self.serve(lambda _: classic_list(total=0, size=100))
        self.assertEqual(self.read(), ({}, 1))

    def test_late_pager_is_waited_for_without_reloading(self):
        self.serve(lambda _: classic_list(total=45, size=20).replace(
            'window.move=move;render();',
            "window.move=move;next.remove();setTimeout(()=>document.querySelector('#incident_expanded').appendChild(next),700);render();"))
        values, pages = self.read()
        self.assertEqual((len(values), pages), (45, 3))
        self.assertEqual(len(self.loads), 1)

    def test_late_metadata_is_waited_for_without_reloading(self):
        self.serve(lambda _: classic_list(total=45, size=20).replace(
            'window.move=move;render();',
            "window.move=move;render();table.removeAttribute('total_rows');setTimeout(()=>table.setAttribute('total_rows',45),700);"))
        self.assertEqual(len(self.read()[0]), 45)
        self.assertEqual(len(self.loads), 1)

    def test_replaced_table_is_rebound_without_mixing_pages(self):
        self.serve(lambda _: classic_list(total=45, size=20, mode='replace'))
        self.assertEqual(len(self.read()[0]), 45)
        self.assertEqual(len(self.loads), 1)

    def test_stop_between_pages_does_not_click_next_or_retry(self):
        self.serve(lambda _: classic_list(total=45, size=20))
        stop = threading.Event()
        with self.assertRaises(Cancelled):
            read_all(self.page, URL, stop, collect, empty_list, authentication_page, navigate,
                     progress=lambda *_: stop.set(), diagnostics=Mock())
        self.assertEqual(self.page.locator('#incident_table').get_attribute('first_row'), '1')
        self.assertEqual(len(self.loads), 1)

    def test_large_list_rejection_is_not_retried(self):
        self.serve(lambda _: classic_list(total=1500, size=100))
        approve = Mock(return_value=False)
        with self.assertRaises(LargeListRejected):
            self.read(approve_large=approve)
        approve.assert_called_once_with(1500)
        self.assertEqual(len(self.loads), 1)

    def test_cancel_and_expired_session_are_not_retried(self):
        for exception in (Cancelled, AuthenticationRequired):
            stop = threading.Event()
            page = Mock()
            auth = Mock(return_value=exception is AuthenticationRequired)
            if exception is Cancelled:
                stop.set()
            with self.subTest(exception=exception), self.assertRaises(exception):
                read_all(page, URL, stop, collect, empty_list, auth, Mock(), diagnostics=Mock())
            page.goto.assert_not_called()

    def test_retry_logs_include_context_but_never_credentials_or_content(self):
        self.serve(lambda _: classic_list(total=4, size=2).replace('Synthetic', 'PRIVATE_PASSWORD').replace('query="synthetic"', 'query="PRIVATE_TOKEN"'))
        calls = []
        def navigation(page, url):
            calls.append(True)
            if len(calls) == 1:
                raise TimeoutError('PRIVATE_USER PRIVATE_PASSWORD SAMLRequest=PRIVATE_TOKEN')
            navigate(page, url)
        with self.assertLogs(_logger, level='INFO') as captured:
            diagnostics = LoginDiagnostics(source='pagination', filter_index=7)
            result = read_all(self.page, URL, threading.Event(), collect, empty_list,
                              authentication_page, navigation, diagnostics=diagnostics)
        self.assertEqual(len(result[0]), 4)
        output = '\n'.join(captured.output)
        self.assertNotIn('PRIVATE_', output)
        self.assertNotIn('SAMLRequest', output)
        self.assertNotIn('INC000', output)
        records = [json.loads(r.getMessage()) for r in captured.records]
        self.assertTrue(any(r['event'] == 'pagination_retry' and r['attempt'] == 1 for r in records))
        self.assertTrue(any(r['event'] == 'pagination_page' and r['page_size'] == 2 and r['total_rows'] == 4 for r in records))
        self.assertEqual({r['session'] for r in records}, {diagnostics.session})
        self.assertEqual(records[-1]['event'], 'pagination_complete')

    def test_diagnostic_sink_failure_does_not_break_a_valid_read(self):
        self.serve(lambda _: classic_list(total=2, size=100))
        diagnostics = Mock()
        diagnostics.record.side_effect = OSError('PRIVATE_TOKEN')
        self.assertEqual(len(self.read(diagnostics=diagnostics)[0]), 2)
