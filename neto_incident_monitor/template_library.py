"""Shared named templates with stable IDs and migration of per-channel drafts."""
import copy
import uuid


def migrate(library, filters):
    library = copy.deepcopy(library) if isinstance(library, dict) else {}
    filters = copy.deepcopy(filters)
    for entry in filters:
        for channel, config in entry.get('notification_templates', {}).items():
            if 'template_id' in config or not config.get('message'):
                continue
            identity = next((key for key, value in library.items()
                             if value.get('message') == config['message'] and value.get('item') == config.get('item')), None)
            if identity is None:
                identity = uuid.uuid4().hex
                base = f"{entry['name']} — {'Teams' if channel == 'teams_webhook' else 'Google Chat'}"
                name = base
                suffix = 2
                while any(v['name'].casefold() == name.casefold() for v in library.values()):
                    name = f'{base} ({suffix})'
                    suffix += 1
                library[identity] = {'name': name, 'message': config['message'], 'item': config.get('item', '{number}'),
                                     'bindings': dict(config.get('bindings', {}))}
            entry['notification_templates'][channel] = {'template_id': identity if config.get('enabled') else ''}
    return library, filters


def resolve(config, library):
    if 'template_id' in config:
        value = library.get(config['template_id'])
        return {**value, 'enabled': True} if value else {}
    return config


def put(library, name, message, item, identity=None, bindings=None):
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError('Podaj nazwę szablonu (1–100 znaków).')
    if name.casefold() == 'standardowy' or any(
            key != identity and value['name'].casefold() == name.casefold() for key, value in library.items()):
        raise ValueError('Ta nazwa jest już używana. Wybierz inną nazwę.')
    identity = identity or uuid.uuid4().hex
    library[identity] = {'name': name, 'message': message, 'item': item, 'bindings': dict(bindings or {})}
    return identity


def clear_missing(filters, library):
    for entry in filters:
        for config in entry.get('notification_templates', {}).values():
            if config.get('template_id') and config['template_id'] not in library:
                config['template_id'] = ''
