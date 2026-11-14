"""Prepare local dashboard-api.json from the reviewed workbook, without Excel."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neto_incident_monitor.analytics_config import held_queries, monthly_query, request_queries, reference
from neto_incident_monitor.dashboard import HELD_TITLES, REQUEST_TITLES, TITLES
from neto_incident_monitor.runtime_paths import DATA

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RISK_WINDOWS = (('hour', 1), ('hour', 2), ('hour', 4), ('hour', 24), ('hour', 48), ('minute', 5))


def read_rows(path):
    with ZipFile(path) as book:
        shared = []
        if 'xl/sharedStrings.xml' in book.namelist():
            tree = ElementTree.fromstring(book.read('xl/sharedStrings.xml'))
            shared = [''.join(node.itertext()) for node in tree.findall('m:si', NS)]
        for name in book.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                continue
            cells = {}
            tree = ElementTree.fromstring(book.read(name))
            for cell in tree.findall('.//m:c', NS):
                address = cell.attrib['r']
                if not re.fullmatch(r'[BE](?:9|[12][0-9]|3[0-2])', address):
                    continue
                if cell.find('m:f', NS) is not None:
                    raise ValueError('Formula in a definition cell')
                value = cell.findtext('m:v', default='', namespaces=NS)
                if cell.get('t') == 's':
                    value = shared[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(part.text or '' for part in cell.findall('.//m:t', NS))
                cells[address] = value
            if cells.get('B9') == TITLES[0]:
                return {cells[f'B{i}']: cells[f'E{i}'].strip() for i in range(9, 33)}
    raise ValueError('Missing dashboard sheet')


def value_of(query, prefix):
    return next(term[len(prefix):] for term in query.split('^') if term.startswith(prefix))


def conditions(query):
    return Counter(','.join(sorted(term.split(','))) if ',' in term and
                   re.match(r'^(task\.)?(location|assigned_to)IN|^inc_assigned_toIN', term) else term
                   for term in query.split('^'))


def compile_config(rows):
    monthly = rows[TITLES[0]]
    held = rows[HELD_TITLES[0]]
    simple = rows[REQUEST_TITLES[0]]
    smart = rows[REQUEST_TITLES[-1]]
    risk = {name: query for name, query in rows.items()
            if name not in (*TITLES, *HELD_TITLES, *REQUEST_TITLES)}
    if len(risk) != 6 or len(rows) != 24:
        raise ValueError('Invalid number of widget definitions')
    config = {
        'version': 1,
        'locations': value_of(monthly, 'task.locationIN').split(','),
        'assignees': value_of(monthly, 'task.assigned_toIN').split(','),
        'monthly_group': value_of(monthly, 'task.assignment_group='),
        'held_metric': value_of(held, 'mi_definition='),
        'l1_group_name': value_of(simple, 'assignment_group.name='),
        'smartphone_variable': value_of(smart, 'variables.').split('RELATIVELT', 1)[0],
        'smartphone_description': value_of(smart, 'short_descriptionLIKE'),
        'threatened_group': value_of(next(iter(risk.values())), 'task.assignment_group='),
    }
    start = re.search(r"task\.opened_atBETWEENjavascript:gs\.dateGenerate\('(\d{4})-(\d{2})-01'", monthly)
    if start is None:
        raise ValueError('Missing monthly period')
    query = monthly_query(config, *map(int, start.groups()))
    expected = {TITLES[0]: query, **held_queries(config), **request_queries(config)}
    for priority in range(1, 6):
        expected[f'Zgłoszenia P{priority}'] = f'{query}^task.priority={priority}'
        expected[f'Przekroczone P{priority}'] = f'{query}^task.priority={priority}^has_breached=true'
    group = reference(config, 'threatened_group')
    common = (f'task.sys_class_name=incident^task.assignment_group={group}^task.active=true^'
              'task.stateNOT IN3,6,7,8^active=true^stage=in_progress^task.ref_incident.parent_incidentISEMPTY')
    for priority, (unit, window) in enumerate(RISK_WINDOWS, 1):
        label = f'P{priority} – ' if priority <= 5 else 'Podjęcie – '
        title = next(name for name in risk if name.startswith(label))
        kind = f'resolution^task.priority={priority}' if priority <= 5 else 'response'
        expected[title] = f'{common}^sla.target={kind}^planned_end_timeRELATIVELT@{unit}@ahead@{window}'
    if any(conditions(rows[title]) != conditions(query) for title, query in expected.items()):
        raise ValueError('Workbook conditions differ from supported definitions')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--output', type=Path, default=DATA / 'dashboard-api.json')
    args = parser.parse_args()
    pending = None
    try:
        config = compile_config(read_rows(args.workbook))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=args.output.parent, mode='w', encoding='utf-8', delete=False) as stream:
            pending = Path(stream.name)
            json.dump(config, stream, ensure_ascii=False, indent=2)
        pending.replace(args.output)
    except Exception:
        parser.exit(1, 'Nie udało się przygotować konfiguracji dashboardu. Sprawdź układ i warunki arkusza.\n')
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    print(f"Sprawdzono 24 definicje, {len(config['assignees'])} osób i {len(config['locations'])} lokalizacje.")


if __name__ == '__main__':
    main()
