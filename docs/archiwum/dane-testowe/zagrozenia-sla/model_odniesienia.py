"""Executable design model only; no product imports, UI, disk state or network."""
import copy
import json
from pathlib import Path


def initial():
    return {'current': {}, 'history': {}}


def complete_rows(step, catalog):
    if step.get('outcome', 'complete') != 'complete':
        return None
    total = step['total']
    if type(total) is not int or total < 0:
        return None
    rows, seen, expected = [], set(), 1
    pages = step['pages']
    if total == 0:
        return [] if pages == [] and step.get('empty_confirmed') is True else None
    for page in pages:
        names = page['rows']
        if (not names or page['first'] != expected
                or page['last'] != expected + len(names) - 1
                or page['total'] != total):
            return None
        for name in names:
            row = catalog[name]
            if row['sla'] in seen:
                return None
            seen.add(row['sla'])
            rows.append(row)
        expected = page['last'] + 1
    return rows if expected == total + 1 else None


def advance(state, step, catalog):
    # Restart preserves membership/history through a serialization boundary.
    if step.get('operation') == 'restart':
        return json.loads(json.dumps(state)), [], 'restored'
    rows = complete_rows(step, catalog)
    if rows is None:
        return copy.deepcopy(state), [], 'rejected'
    if step.get('synthetic_simulation'):
        return copy.deepcopy(state), [], 'simulation_only'
    candidate = copy.deepcopy(state)
    groups = {}
    for row in rows:
        groups.setdefault(row['incident'], []).append(row)
    current, arrivals = {}, []
    for incident, contracts in sorted(groups.items()):
        # Unknown deadline cannot safely compete with known deadlines.
        representative = (min(contracts, key=lambda r: (r['deadline'], r['sla']))
                          if all(type(r.get('deadline')) is int for r in contracts)
                          else None)
        view = {'representative': representative['sla'] if representative else None,
                'remaining': representative['remaining'] if representative else None,
                'percentage': representative['percentage'] if representative else None,
                'categories': sorted({r['category'] for r in contracts})}
        current[incident] = view
        fresh = incident not in state['current']
        if fresh:
            arrivals.append(incident)
        history = candidate['history'].setdefault(incident, {
            'first': step['at'], 'appearances': 0})
        history.update(last=step['at'], view=copy.deepcopy(view))
        history['appearances'] += int(fresh)
    candidate['current'] = current
    # Inject a failed commit before publishing state or notification intents.
    if step.get('commit') == 'fail':
        return copy.deepcopy(state), [], 'commit_failed'
    return candidate, arrivals, 'accepted'


def summary(state, arrivals, result):
    return {'current': sorted(state['current']),
            'history': {key: {field: value[field] for field in ('first', 'last', 'appearances')}
                        for key, value in sorted(state['history'].items())},
            'views': state['current'], 'arrivals': arrivals, 'result': result}


def run(path=None):
    source = Path(path) if path else Path(__file__).with_name('scenariusze.json')
    spec = json.loads(source.read_text(encoding='utf-8'))
    count = 0
    for scenario in spec['scenarios']:
        state = initial()
        for index, step in enumerate(scenario['steps'], 1):
            state, arrivals, result = advance(state, step, spec['catalog'])
            actual = summary(state, arrivals, result)
            for key, expected in step['expect'].items():
                if actual[key] != expected:
                    raise AssertionError(f"{scenario['id']} step {index}: {key} mismatch")
            count += 1
    print(json.dumps({'scope': 'synthetic_design_model_only',
                      'scenarios': len(spec['scenarios']), 'steps_passed': count,
                      'product_verified': False}))


if __name__ == '__main__':
    run()
