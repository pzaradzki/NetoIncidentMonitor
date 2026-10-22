"""Literal, two-level notification templates; no expressions or attribute access."""
import re

TOKEN = re.compile(r'\{([^{}]+)\}')
MESSAGE_ALIASES = {'filtr': 'nazwa filtra', 'liczba': 'liczba elementów', 'lista incydentów': 'lista elementów'}
DEFAULT_MESSAGE = 'Nowe zgłoszenia · {nazwa filtra}\n\nZnaleziono {liczba elementów} zgłoszeń:\n{lista elementów}'
DEFAULT_ITEM = '{number} - {short_description}'
MAX_TEMPLATE = 8000


def standard(name, incidents):
    records = {row['number']: row for row in incidents}
    lines = []
    for number, row in records.items():
        description = row.get('short_description') or row.get('summary') or 'Brak opisu'
        lines.append(f"{number} - {' '.join(description.split())}")
    return f'{name} · {len(records)}', '\n'.join(lines)


def slices(text, width):
    """Split long text without cutting a record identifier in half."""
    start = 0
    for match in re.finditer(r'(?:INC|SCTASK|REQ|RITM)\d{1,20}', text):
        while match.start() >= start + width:
            yield text[start:start + width]
            start += width
        if match.end() > start + width:
            yield text[start:match.start()]
            start = match.start()
    while len(text) - start > width:
        yield text[start:start + width]
        start += width
    yield text[start:]


def validate(message, item, schema, bindings=None):
    if not message.strip() or not item.strip():
        raise ValueError('Oba szablony muszą zawierać tekst.')
    if max(len(message), len(item)) > MAX_TEMPLATE:
        raise ValueError('Szablon może zawierać maksymalnie 8000 znaków.')
    if not any(tag in message for tag in ('{lista incydentów}', '{lista elementów}')):
        raise ValueError('Wstaw zmienną {lista elementów} do szablonu wiadomości.')
    unknown = set(TOKEN.findall(message)) - set(MESSAGE_ALIASES) - set(MESSAGE_ALIASES.values())
    # Stable field keys are used even when labels change or are duplicated.
    available = {c['key'] for c in schema}
    missing = {token for token in TOKEN.findall(item)
               if (bindings or {}).get(token, token) not in available}
    if unknown:
        raise ValueError('Nieznane zmienne wiadomości: ' + ', '.join(sorted(unknown)))
    return sorted(missing)


def render(config, name, incidents):
    records = {row['number']: row for row in incidents}
    items = []
    for row in records.values():
        values = dict(row)
        values.update(row.get('_values', {}))
        values['number'] = row['number']
        bindings = config.get('bindings', {})
        items.append(TOKEN.sub(lambda m: str(values.get(bindings.get(m[1], m[1])) or ''), config.get('item', DEFAULT_ITEM)))
    values = {'filtr': name, 'liczba': str(len(records)), 'lista incydentów': '\n'.join(items)}
    values.update({new: values[old] for old, new in MESSAGE_ALIASES.items()})
    return TOKEN.sub(lambda m: values.get(m[1], ''), config.get('message', DEFAULT_MESSAGE))


def linked_parts(text, links):
    """Link only trusted record numbers, at any position in a template."""
    from neto_incident_monitor.service_now_urls import safe_record_url
    position = 0
    for match in re.finditer(r'(?<!\w)(?:INC|SCTASK|REQ|RITM)\d{1,20}(?!\w)', text):
        url = safe_record_url((links or {}).get(match[0], ''), match[0])
        if url:
            yield text[position:match.start()], None
            yield match[0], url
            position = match.end()
    yield text[position:], None
