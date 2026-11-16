"""Adapters from the dashboard sections to the ServiceNow Aggregate API."""
from neto_incident_monitor.analytics_api import read_counts, stats, summarize_month
from neto_incident_monitor.analytics_config import (
    held_queries, lost_incidents_query, monthly_query, request_queries, stale_l1_query,
)
from neto_incident_monitor.dashboard import LOST_TITLE, MONTHLY_TITLES, STALE_L1_TITLE, UNASSIGNED_TITLE


def read_month(page, stop, diagnostics, config, year, month, completed=None):
    if completed is None:
        completed = {}
    if MONTHLY_TITLES[0] not in completed:
        query = monthly_query(config, year, month)
        completed.update(summarize_month(stats(page, stop, diagnostics, 'sla', 'task_sla', query,
                                               group='task.priority,has_breached')))
    read_counts(page, stop, diagnostics, 'sla', 'task_sla',
                {UNASSIGNED_TITLE: monthly_query(config, year, month, unassigned=True)}, completed, start=2)
    return read_counts(page, stop, diagnostics, 'sla', 'incident',
                       {LOST_TITLE: lost_incidents_query(config)}, completed, start=3)


def read_held(page, stop, diagnostics, config, completed):
    read_counts(page, stop, diagnostics, 'held', 'incident_metric', held_queries(config), completed)
    return read_counts(page, stop, diagnostics, 'held', 'incident',
                       {STALE_L1_TITLE: stale_l1_query(config)}, completed, start=3)


def read_requests(page, stop, diagnostics, config, completed):
    return read_counts(page, stop, diagnostics, 'requests', 'sc_task', request_queries(config), completed)
