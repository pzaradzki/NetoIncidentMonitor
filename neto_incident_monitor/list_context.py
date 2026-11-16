"""Compare encoded filter conditions saved by older application versions."""
import re


def _ordered_conditions(query):
    if query is None:
        return None
    parts = query.split("^")
    while parts and (parts[-1] == "EQ" or
                     re.fullmatch(r"ORDERBY(?:DESC)?[a-zA-Z_][\w.]*", parts[-1])):
        parts.pop()
    return parts


# Only a complete comparison value can use the observed date alias.
_DATE_ALIAS = re.compile(r'((?:OR|NQ)?(?:GOTO)?sys_updated_on(?:<=|>=|!=|=|<|>))'
                         r'javascript:gs\.daysAgoStart\(7\)')


def list_conditions(query):
    """Preserve ordered logic, accepting only the observed seven-day date alias."""
    parts = _ordered_conditions(query)
    if parts is None:
        return None
    return '^'.join((match[1] + 'javascript:gs.beginningOfLast7Days()')
                    if (match := _DATE_ALIAS.fullmatch(part)) else part for part in parts)


def compare_list_conditions(requested, observed):
    if observed is None or list_conditions(requested) != list_conditions(observed):
        return 'mismatch'
    return 'exact' if _ordered_conditions(requested) == _ordered_conditions(observed) else 'known_alias'
