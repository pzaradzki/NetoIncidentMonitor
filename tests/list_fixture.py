"""Minimal synthetic classic-list DOM based on inspected ServiceNow structure."""
import json

URL = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'


def classic_list(total=205, size=100, start=1, mode='normal', delay=80):
    options = json.dumps(dict(total=total, size=size, first=start, mode=mode, delay=delay))
    return '''<div class="list-container" id="incident_expanded">
      <table class="list_table" id="incident_table" data-list_id="incident" glide_table="incident" query="active=true" sort="incident.number" sort_dir="DESC">
      <thead><tr><th glide_field="incident.number">Numer</th><th glide_field="incident.short_description">Krótki opis</th></tr></thead><tbody></tbody></table>
      <button class="list_nav" aria-label="Pierwsza strona" onclick="move(1)">First</button>
      <input class="list_row_number_input" onkeydown="if(event.key==='Enter')move(Number(this.value))">
      <span id="listv2_fixture_total_rows"></span>
      <button class="list_nav" aria-label="Następna strona" onclick="move('next')">Next</button>
      <div id="empty"></div>
      </div><script>(()=>{const s=''' + options + ''';
      let table=document.querySelector('#incident_table');
      const first=document.querySelector('[aria-label="Pierwsza strona"]');
      const next=document.querySelector('[aria-label="Następna strona"]');
      function render(){const end=Math.min(s.first+s.size-1,s.total);
        for(const [k,v] of Object.entries({first_row:s.first,last_row:end,total_rows:s.total,rows_per_page:s.size}))table.setAttribute(k,v);
        table.querySelector('tbody').innerHTML=Array.from({length:Math.max(0,end-s.first+1)},(_,i)=>{
          const n=s.first+i;return '<tr class="list_row"><td><a href="/incident.do?sys_id=synthetic">INC'+String(n).padStart(7,'0')+'</a></td><td>Synthetic</td></tr>'}).join('');
        document.querySelector('input').value=s.first;first.disabled=s.first===1;
        next.disabled=end>=s.total;document.querySelector('#listv2_fixture_total_rows').textContent=s.total;
        document.querySelector('#empty').textContent=s.total===0?'Brak rekordów do wyświetlenia':'';
        table.setAttribute('aria-busy','false');
      }
      function move(n){if(n==='next')n=s.first+s.size;next.disabled=true;table.setAttribute('aria-busy','true');
        setTimeout(()=>{
          if(n>1 && s.mode==='skip')n+=s.size;
          if(n>1 && s.mode==='overlap')n--;
          if(n>1 && s.mode==='size_change')s.size=s.size===20?100:20;
          if(n>1 && s.mode==='total_change')s.total++;
          if(n>1 && s.mode==='query_change')table.setAttribute('query','changed');
          s.first=n;render();
          if(s.mode==='replace'){const fresh=table.cloneNode(true);table.replaceWith(fresh);table=fresh;}
        },s.delay);
      }window.move=move;render();})();</script>'''
