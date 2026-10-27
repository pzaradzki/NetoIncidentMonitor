"""Editable first-run filters; never merged into an existing configuration."""
from urllib.parse import urlencode


def default_filters():
    current_user = 'assigned_toDYNAMIC90d1921e5f510100a9ad2572f2b477fe'
    entries = (
        ('L1 - Niepodjęte', 'incident', 'state=1^ORstate=2^ORstate=3^company=58e8d49fdbfae300eeb432f6f496194f'
         '^assigned_toISEMPTY^assignment_group=36e1263edb64b7408033459d3b9619e0'),
        ('Moje - Nowe / W trakcie', 'incident', 'state=1^ORstate=2^' + current_user),
        ('Moje - Wstrzymane', 'incident', 'state=3^' + current_user),
        ('Moje - Wnioski', 'sc_task', 'active=true^request.requested_for.companyDYNAMIC'
         '3b2e7e19db69bb008033459d3b9619b8^' + current_user),
    )
    return [{'name': name, 'url': f'https://adeo.service-now.com/{table}_list.do?'
             + urlencode({'sysparm_query': query}), 'enabled': True}
            for name, table, query in entries]
