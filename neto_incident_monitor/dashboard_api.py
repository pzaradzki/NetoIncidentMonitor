"""Adapters from the dashboard sections to the ServiceNow Aggregate API."""
from neto_incident_monitor.analytics_api import read_counts, stats, summarize_month
from neto_incident_monitor.analytics_config import held_queries, monthly_query, request_queries


def read_month(page, stop, diagnostics, config, year, month):
    query = monthly_query(config, year, month)
    return summarize_month(stats(page, stop, diagnostics, 'sla', 'task_sla', query,
                                 group='task.priority,has_breached'))


def read_held(page, stop, diagnostics, config, completed):
    return read_counts(page, stop, diagnostics, 'held', 'incident_metric', held_queries(config), completed)


def read_requests(page, stop, diagnostics, config, completed):
    return read_counts(page, stop, diagnostics, 'requests', 'sc_task', request_queries(config), completed)
