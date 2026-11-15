"""Synthetic classic table with only the metadata needed to define a filter."""

URL = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'


def classic_list(total=205, size=100, size_menu=False):
    menu = '''<button id="incident_control_button" aria-label="Czynności"
        onclick="localStorage.menuOpens=1">Czynności</button>''' if size_menu else ''
    return f'''<div class="list-container">{menu}
      <table class="list_table" id="incident_table" data-list_id="incident" glide_table="incident"
          query="active=true" total_rows="{total}" rows_per_page="{size}">
        <thead><tr><th glide_field="incident.number">Numer</th>
          <th glide_field="incident.short_description">Krótki opis</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>'''
