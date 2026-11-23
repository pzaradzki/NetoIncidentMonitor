"""Read and write user configuration without loading the interface."""
import json

from neto_incident_monitor.runtime_paths import DATA
from neto_incident_monitor.service_now_urls import normalize_list_url


CONFIG = DATA / "config.json"


def without_legacy_settings(settings):
    from copy import copy

    cleaned = copy(settings)
    cleaned.pop("highlight_unread", None)
    if isinstance(cleaned.get('filters'), list):
        cleaned['filters'] = [
            {key: value for key, value in entry.items() if key != 'first_only'}
            if isinstance(entry, dict) and 'first_only' in entry else entry
            for entry in cleaned['filters']
        ]
    for key in ("visible_columns", "column_widths"):
        value = cleaned.get(key)
        if isinstance(value, list):
            cleaned[key] = [column for column in value if column != "read"]
        elif isinstance(value, dict):
            cleaned[key] = {column: width for column, width in value.items() if column != "read"}
    for key in ("filter_visible_columns", "filter_column_profiles"):
        if isinstance(cleaned.get(key), dict):
            cleaned[key] = {
                url: ([column for column in profile if column != "read"] if isinstance(profile, list)
                      else without_read_column(profile))
                for url, profile in cleaned[key].items()
            }
    return cleaned


def without_read_column(profile):
    if not isinstance(profile, dict):
        return profile
    result = dict(profile)
    for key in ("order", "visible"):
        if isinstance(result.get(key), list):
            result[key] = [column for column in result[key] if column != "read"]
    if isinstance(result.get("schema"), list):
        result["schema"] = [column for column in result["schema"]
                            if not isinstance(column, dict) or column.get("key") != "read"]
    if isinstance(result.get("widths"), dict):
        result["widths"] = {column: width for column, width in result["widths"].items() if column != "read"}
    return result


def read_json(path, default):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import load_config
        return without_legacy_settings(load_config(path, default))
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import save_config
        return save_config(path, without_legacy_settings(value))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_filters(settings, tolerate_invalid=False):
    """Migrate the previous URL-only configuration without touching seen state."""
    entries = settings["filters"] if "filters" in settings else [
        {"name": f"Filtr {index}", "url": url}
        for index, url in enumerate(settings.get("urls", []), 1)
    ]
    from neto_incident_monitor.data_validation import validate_filters
    validate_filters(entries)
    result = []
    for entry in entries:
        try:
            validated = {**entry, "url": normalize_list_url(entry["url"])}
            validated.pop('url_invalid', None)
            result.append(validated)
        except ValueError:
            if not tolerate_invalid:
                raise
            # Keep the original value editable, but never navigate to it.
            result.append({**entry, "enabled": False, "url_invalid": True})
    return result


def initialize_default_filters(settings, path=None):
    """Persist defaults once, only when no previous configuration exists."""
    path = CONFIG if path is None else path
    if path.exists() or 'filters' in settings or 'urls' in settings:
        return settings
    from neto_incident_monitor.default_filters import default_filters
    initialized = {**settings, 'filters': default_filters()}
    save_json(path, initialized)
    return initialized
