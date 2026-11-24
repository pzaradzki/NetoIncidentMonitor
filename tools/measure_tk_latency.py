"""Measure real Tk views with disposable runtime files and synthetic records."""
import argparse
import json
import math
from pathlib import Path
import platform
from statistics import median
import subprocess
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


INTERVAL_MS = 16
URL = 'https://adeo.service-now.com/incident_list.do'
COLUMN = 'sn:u_benchmark'


def summary(values):
    ordered = sorted(values)
    return dict(samples=len(ordered), median_ms=round(median(ordered), 2),
                p95_ms=round(ordered[math.ceil(len(ordered) * .95) - 1], 2),
                max_ms=round(ordered[-1], 2))


def drive(root, done, *, limit=18):
    deadline = time.perf_counter() + limit
    while not done():
        if time.perf_counter() >= deadline:
            raise TimeoutError('Synthetic Tk scenario did not complete.')
        root.update()
        time.sleep(.001)


class Pulse:
    def __init__(self, root):
        self.root = root
        self.delays = []
        self.overhead = []
        self.schedule()

    def schedule(self):
        self.due = time.perf_counter() + INTERVAL_MS / 1000
        self.timer = self.root.after(INTERVAL_MS, self.tick)

    def tick(self):
        now = time.perf_counter()
        self.delays.append(max(0, (now - self.due) * 1000))
        self.schedule()
        self.overhead.append((time.perf_counter() - now) * 1000)

    def stop(self):
        self.root.after_cancel(self.timer)


def observe(app, action, ready, settled=None, *, start_after=40):
    root = app.root
    pulse = Pulse(root)
    launched = False
    started = None
    elapsed = None

    def begin():
        nonlocal started, launched
        started = time.perf_counter()
        action()
        launched = True

    def visible():
        nonlocal elapsed
        if launched and ready():
            elapsed = (time.perf_counter() - started) * 1000
            return True
        return False

    try:
        root.after(start_after, begin)
        drive(root, visible)
        if settled:
            drive(root, settled)
        total = (time.perf_counter() - started) * 1000
        drive(root, lambda end=time.perf_counter() + .12: time.perf_counter() >= end)
    finally:
        pulse.stop()
    return dict(visible_ms=round(elapsed, 2), total_ms=round(total, 2), lag=summary(pulse.delays),
                sample_overhead=summary(pulse.overhead))


def setup_app(folder):
    import tkinter as tk
    from neto_incident_monitor import runtime_paths

    runtime_paths.DATA = folder
    runtime_paths.LOG_DIR = folder
    (folder / 'config.json').write_text(json.dumps({'filters': [{'url': URL, 'name': 'Pomiar'}]}), encoding='utf-8')
    from neto_incident_monitor.app import App

    root = tk.Tk()
    root.geometry('1300x850')
    root.title('Neto Incident Monitor - pomiar Tk')
    app = App(root, enable_tray=False, apply_startup=False)
    root.title('Neto Incident Monitor - pomiar Tk')
    app.session.ready_once = True
    app.handle_session_event('session_ready', None)
    app.accept_column_schema(URL, [{'key': 'number', 'label': 'Numer'},
                                  {'key': COLUMN, 'label': 'Opis'}])
    root.update()
    return app


def cache_cases(app, path, repeat):
    from neto_incident_monitor import dashboard_cache as cache
    from neto_incident_monitor.dashboard import HELD_TITLES, REQUEST_TITLES, TITLES

    view = app.dashboard_view
    app.show_dashboard_view()
    sections = (('sla', TITLES), ('held', HELD_TITLES), ('requests', REQUEST_TITLES))
    replace = cache.os.replace
    output = []
    for mode in ('normal', 'slow', 'transient', 'denied'):
        for shape in ('section', 'full', 'series'):
            for run in range(repeat):
                attempts = {}
                writes = 0
                remaining = 3 if shape == 'series' else 1

                def replace_fixture(source, target):
                    nonlocal writes
                    if Path(target) == path:
                        writes += 1
                        attempts[source] = attempts.get(source, 0) + 1
                        if mode == 'slow':
                            time.sleep(.06)
                        if mode == 'denied' or (mode == 'transient' and attempts[source] <= 2):
                            raise PermissionError('synthetic')
                    replace(source, target)

                def enqueue():
                    nonlocal remaining
                    request = view.request_refresh()
                    assert request
                    for alias, titles in (sections[:1] if shape == 'section' else sections):
                        meta = {'section': alias, 'values': dict.fromkeys(titles, remaining + run),
                                'read_at': '2026-11-01T10:00:00+01:00', 'diagnostics': SimpleNamespace(
                                    record=lambda *_args, **_facts: None)}
                        app.events.put(('dashboard_result', (*request, {}, None, '', meta)))
                    if shape != 'section':
                        app.events.put(('dashboard_result', (*request, {}, None, '')))
                    app.events.put(('dashboard_updating', (*request, 'finished')))
                    remaining -= 1

                def ready():
                    if view.active_request is not None:
                        return False
                    if remaining:
                        enqueue()
                        return False
                    return True

                def settled():
                    writer = getattr(view, 'cache_writer', None)
                    return (writer is None or writer.idle) and app.events.empty()

                with patch.object(cache.os, 'replace', replace_fixture):
                    result = observe(app, enqueue, ready, settled)
                assert writes > 0
                output.append(dict(mode=mode, shape=shape, repeat=run, replace_calls=writes, **result))
    return output


def column_cases(app, repeat):
    from tkinter import ttk
    from tkinter.font import Font

    app.show_incident_view()
    output = []
    for name, table, index, count in (
            ('small', app.current_table, 0, 100), ('current', app.current_table, 0, 1000),
            ('history', app.table, 1, 10000), ('loading', app.current_table, 0, 1000)):
        app.tabs.select(index)
        app.root.update()
        # Keep the target within the viewport at both Windows scaling settings.
        columns = tuple(table['displaycolumns'])
        table['displaycolumns'] = (COLUMN, *(key for key in columns if key != COLUMN))
        values = [f'Syntetyczny opis {i % 41} ' * (2 if i % 17 else 8) for i in range(count)]
        for run in range(repeat):
            app.cancel_table_load(table)
            table.delete(*table.get_children())
            save_times = []
            save = app.save_column_profiles

            def timed_save(profiles):
                started = time.perf_counter()
                try:
                    return save(profiles)
                finally:
                    save_times.append((time.perf_counter() - started) * 1000)

            if name == 'loading':
                key = app.selected_filter_index()
                assert key is not None
                app.snapshots[key] = {f'INC{i:08d}': {'number': f'INC{i:08d}', '_values': {COLUMN: value}}
                                      for i, value in enumerate(values)}
            else:
                for i, value in enumerate(values):
                    table.insert('', 'end', values=app.table_values(
                        table, {'number': f'INC{i:08d}', '_values': {COLUMN: value}}, ''))
                app.root.update()
            table.column(COLUMN, width=80)
            table.xview_moveto(0)
            app.root.update_idletasks()
            x = next((x for x in range(table.winfo_width())
                      if table.identify_region(x, 10) == 'separator' and app.column_at(table, x) == COLUMN), None)
            assert x is not None, (name, table.winfo_width())
            event = SimpleNamespace(widget=table, x=x, y=10)
            rows = 0

            def fit():
                nonlocal rows
                rows = len(table.get_children())
                app.open_incident(event)

            with patch.object(app, 'save_column_profiles', timed_save):
                if name == 'loading':
                    insert = table.insert

                    def insert_and_fit(*args, **kwargs):
                        item = insert(*args, **kwargs)
                        if rows == 0:
                            fit()
                        return item

                    with patch.object(table, 'insert', insert_and_fit):
                        result = observe(app, app.refresh_current,
                                         lambda: rows > 0 and not getattr(app, '_column_fit_jobs', {}))
                else:
                    result = observe(app, fit, lambda: not getattr(app, '_column_fit_jobs', {}))
            if name == 'loading':
                drive(app.root, lambda: table not in app._table_jobs)
            assert save_times or name == 'loading', name
            stamp = time.perf_counter()
            children = table.get_children()
            children_ms = (time.perf_counter() - stamp) * 1000
            stamp = time.perf_counter()
            texts = [table.set(item, COLUMN) for item in children]
            get_values_ms = (time.perf_counter() - stamp) * 1000
            font = Font(table, font=ttk.Style(table).lookup('Treeview', 'font') or 'TkDefaultFont')
            stamp = time.perf_counter()
            for text in texts:
                font.measure(text)
            measure_ms = (time.perf_counter() - stamp) * 1000
            output.append(dict(case=name, repeat=run, rows_at_action=rows, profiled_rows=len(children),
                               children_ms=round(children_ms, 2), get_values_ms=round(get_values_ms, 2),
                               measure_ms=round(measure_ms, 2), save_ms=[round(t, 2) for t in save_times], **result))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=3, choices=range(1, 11), metavar='1-10')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='neto-tk-latency-') as work:
        folder = Path(work)
        app = setup_app(folder)
        try:
            pulse = Pulse(app.root)
            drive(app.root, lambda end=time.perf_counter() + .5: time.perf_counter() >= end)
            pulse.stop()
            result = dict(
                commit=subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], text=True).strip(),
                python=platform.python_version(), tk=str(app.root.tk.call('info', 'patchlevel')),
                dpi=round(app.root.winfo_fpixels('1i')), interval_ms=INTERVAL_MS, repeat=args.repeat,
                idle_lag=summary(pulse.delays), idle_sample_overhead=summary(pulse.overhead),
                columns=column_cases(app, args.repeat),
                cache=cache_cases(app, folder / 'dashboard-cache.json', args.repeat))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        finally:
            from neto_incident_monitor.login_diagnostics import close_diagnostics
            app.root.after(0, app.quit_app)
            app.root.mainloop()
            close_diagnostics()


if __name__ == '__main__':
    main()
