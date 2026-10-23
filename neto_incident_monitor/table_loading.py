"""Cancellable, time-bounded Tk table population. Workers never access Tk."""
import queue
import re
import threading
import time
from datetime import datetime

from neto_incident_monitor.columns import age_minutes


def sort_key(value, column):
    value = str(value).strip()
    if column in ('time', 'created', 'updated'):
        for pattern in ('%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M', '%Y-%m-%d'):
            try:
                return (0, datetime.strptime(value, pattern))
            except ValueError:
                pass
    return (1, tuple((0, int(p)) if p.isdigit() else (1, p.casefold()) for p in re.split(r'(\d+)', value)))


class TableLoading:
    def large_tables(self):
        history = getattr(self, 'history', None)
        return (len(getattr(history, 'records', {})) > 150 or
                any(len(s) > 150 for s in getattr(self, 'snapshots', {}).values()))

    def table_visible(self, table):
        return table is (self.current_table if self.tabs.index(self.tabs.select()) == 0 else self.table)

    def cancel_table_load(self, table):
        jobs = getattr(self, '_table_jobs', {})
        job = jobs.pop(table, None)
        if job:
            job['cancel'].set()
            if job.get('timer'):
                self.root.after_cancel(job['timer'])
            if not jobs and hasattr(self, 'table_load_status'):
                self.table_load_status.set('')

    def show_table_tab(self, *_):
        if not hasattr(self, 'current_table'):
            return
        visible = self.current_table if self.tabs.index(self.tabs.select()) == 0 else self.table
        self.table_load_status.set('')
        for table in (self.current_table, self.table):
            if table is not visible:
                self.cancel_table_load(table)
        if getattr(visible, 'load_dirty', False):
            (self.refresh_current if visible is self.current_table else self.refresh_history)()

    def load_table(self, table, history=False):
        table.load_dirty = True
        previous = getattr(self, '_table_jobs', {}).get(table)
        self.cancel_table_load(table)
        if not self.table_visible(table):
            return
        if not hasattr(self, '_table_jobs'):
            self._table_jobs = {}
        url = self.selected_filter_url()
        column, descending = table.sort_column, table.sort_descending
        selected = {self.row_numbers.get((table, item)) for item in table.selection()}
        if previous and previous.get('url') == url:
            selected.update(previous.get('selection', set()))
        scroll = table.yview()[0]
        # Snapshots are replaced by monitoring events rather than modified in place.
        snapshot = self.snapshots.get(self.selected_filter_index(), {})
        result = queue.Queue(maxsize=1)
        cancel = threading.Event()
        job = {'cancel': cancel, 'timer': None, 'url': url, 'selection': selected}
        self._table_jobs[table] = job
        label = 'historii' if history else 'zgłoszeń'
        self.table_load_status.set(f'Przygotowanie {label}…')

        def prepare():
            try:
                records = self.history.snapshot(url)
                if cancel.is_set():
                    return
                if history:
                    source = [(n, r['incident'], r) for n, r in sorted(
                        records.items(), key=lambda pair: pair[1]['detected'], reverse=True)]
                else:
                    source = [(n, incident, records.get(n)) for n, incident in sorted(
                        snapshot.items(), key=lambda pair: int(re.sub(r'\D', '', pair[0]) or 0), reverse=True)]
                rows = []
                for index, (number, incident, record) in enumerate(source):
                    if cancel.is_set():
                        return
                    unread = bool(record and not record['read'])
                    read_label = ('Nieprzeczytany' if unread else 'Przeczytany') if record else '—'
                    detected = time.strftime('%d.%m.%Y %H:%M', time.localtime(record['detected'])) if history else ''
                    values = dict(incident)
                    values.update(incident.get('_values', {}))
                    values.update(number=number, read=read_label, time=detected,
                                  age_minutes=age_minutes(incident.get('created'), number))
                    rows.append((index, number, incident, unread, read_label, detected, values.get(column) or '—'))
                if column:
                    present = [r for r in rows if str(r[-1]).strip() not in ('', '—')]
                    missing = [r for r in rows if str(r[-1]).strip() in ('', '—')]
                    rows = sorted(present, key=lambda r: sort_key(r[-1], column), reverse=descending) + missing
                if not cancel.is_set():
                    result.put((rows, None))
            except Exception as error:
                if not cancel.is_set():
                    result.put((None, error))

        # One preparation worker per application; newer requests supersede queued work.
        if not hasattr(self, '_table_prepare_queue'):
            self._table_prepare_queue = queue.Queue()
            def work():
                while True:
                    task = self._table_prepare_queue.get()
                    if task is None:
                        return
                    event, callback = task
                    if not event.is_set():
                        callback()
            threading.Thread(target=work, daemon=True, name='table-preparation').start()
        self._table_prepare_queue.put((cancel, prepare))
        old = iter(table.get_children())
        state = {'rows': None, 'position': 0, 'cleared': False, 'ids': []}

        def step():
            if cancel.is_set() or self.quitting or self.selected_filter_url() != url or not self.table_visible(table):
                return
            deadline = time.perf_counter() + .006
            if not state['cleared']:
                while time.perf_counter() < deadline:
                    item = next(old, None)
                    if item is None:
                        state['cleared'] = True
                        table.default_order = ()
                        break
                    self.items.pop((table, item), None)
                    self.row_numbers.pop((table, item), None)
                    table.delete(item)
            if state['cleared'] and state['rows'] is None:
                try:
                    rows, error = result.get_nowait()
                    if error:
                        self.table_load_status.set('Nie udało się wczytać tabeli.')
                        self._table_jobs.pop(table, None)
                        return
                    state['rows'] = rows
                    state['ids'] = [None] * len(rows)
                except queue.Empty:
                    pass
            rows = state['rows']
            if rows is not None:
                while state['position'] < len(rows) and time.perf_counter() < deadline:
                    order, number, incident, unread, read_label, detected, _ = rows[state['position']]
                    tags = ('unread',) if unread and self.unread_highlighting_enabled() else (
                        ('alternate',) if state['position'] % 2 else ())
                    item = table.insert('', 'end', values=self.table_values(table, incident, read_label, detected), tags=tags)
                    state['ids'][order] = item
                    self.items[(table, item)] = incident.get('url', '')
                    self.row_numbers[(table, item)] = number
                    if number in selected:
                        table.selection_add(item)
                    state['position'] += 1
                self.table_load_status.set(f'Wczytywanie {label}: {state["position"]} z {len(rows)}')
                if state['position'] == len(rows):
                    table.default_order = tuple(state['ids'])
                    table.load_dirty = False
                    self._table_jobs.pop(table, None)
                    table.yview_moveto(scroll)
                    self.table_load_status.set('')
                    for key, title in table.heading_titles.items():
                        table.heading(key, text=title + ((' ▼' if descending else ' ▲') if key == column else ''))
                    return
            job['timer'] = self.root.after(10, step)
        job['timer'] = self.root.after(0, step)

    def stop_table_loads(self):
        for table in list(getattr(self, '_table_jobs', {})):
            self.cancel_table_load(table)
        if hasattr(self, '_table_prepare_queue'):
            self._table_prepare_queue.put(None)
