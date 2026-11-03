"""Synthetic analytics workspace based on the observed public DOM structure."""
import json
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES

RISK_TITLES = tuple(f'P{p} – < {t} / po terminie' for p, t in enumerate(('1 h','2 h','4 h','1 dzień','2 dni'),1)) + ('Podjęcie – < 5 min / po terminie',)


def workspace(delay=80):
    data = {'sla': TITLES, 'held': HELD_TITLES, 'requests': REQUEST_TITLES, 'threatened': RISK_TITLES}
    return '''<button id="refresh">Odśwież bieżącą kartę</button><div id="tabs"></div><main></main>
    <script>const titles=''' + json.dumps(data) + ''';
    const ids={sla:'ba36dad72b6a8b504b98f4c2c891bf73',held:'c228c7d455c81f90211a1d000e482311',requests:'17fcfee03dcc5310e5e0b24c4676861c',threatened:'54154e7fadc41fd030fd4a7e9f322595'};
    const names={sla:'Dasboard SLA',held:'Wstrzymane L1',requests:'Wnioski L1',threatened:'L1 – Incydenty zagrożone SLA'};
    let section=Object.keys(ids).find(k=>location.pathname.includes(ids[k]))||'sla';
    let first='2026-10-01',last='2026-10-31';window.applied=0;
    function refresh(){for(const card of document.querySelectorAll('.score-card')){
        card.querySelector('now-score-basic').innerHTML='<span>Trwa ładowanie danych wizualizacji</span>';
        setTimeout(()=>{if(card.isConnected)card.querySelector('now-score-basic').innerHTML='<span class="now-score-value">'+card.dataset.value+'</span>'},''' + str(delay) + ''');}}
    function show(key){section=key;for(const b of document.querySelectorAll('[role=tab]'))b.setAttribute('aria-selected',String(b.dataset.key===key));
      const main=document.querySelector('main');main.innerHTML='';
      if(key==='sla'){const p=document.createElement('button');p.id='period';periodLabel(p);p.onclick=dates;main.appendChild(p);}
      const cats=key==='sla'?['Status zgłoszenia','Lokalizacja','Przypisany do']:key==='threatened'?[]:['Agent L1'];
      for(const name of cats){const c=document.createElement('sn-component-filter');c.innerHTML='<h3>'+name+'</h3><label><input type="checkbox" checked>Wybierz wszystko</label><button>Zastosuj</button>';
        c.querySelector('button').onclick=()=>{window.applied++;refresh()};main.appendChild(c);}
      titles[key].forEach((title,i)=>{const c=document.createElement('div');c.className='grid-stack-item-content score-card';c.dataset.value=i;
        const h=document.createElement('h2');h.textContent=title;c.appendChild(h);c.innerHTML+='<now-score-basic><span class="now-score-value">'+i+'</span></now-score-basic>';main.appendChild(c);});
      main.insertAdjacentHTML('beforeend','<div class="grid-stack-item-content"><h2>Unrelated chart</h2><span>Trwa ładowanie danych wizualizacji</span></div>');
    }
    function periodLabel(p){p.setAttribute('aria-label','Filtr Okres otwarcia z typem daterange. Wybrane wartości to: '+first+' - '+last);p.textContent=first+' - '+last;}
    function dates(){const panel=document.createElement('now-popover-panel');panel.innerHTML='<input aria-label="Data rozpoczęcia" value="'+first+'"><input aria-label="Data zakończenia" value="'+last+'"><button>Zastosuj</button><button>Anuluj</button>';
      panel.querySelectorAll('button')[0].onclick=()=>{first=panel.querySelectorAll('input')[0].value;last=panel.querySelectorAll('input')[1].value;periodLabel(document.querySelector('#period'));panel.remove();refresh()};
      panel.querySelectorAll('button')[1].onclick=()=>panel.remove();document.body.appendChild(panel);}
    for(const key of Object.keys(names)){const b=document.createElement('button');b.setAttribute('role','tab');b.dataset.key=key;b.textContent=names[key];b.onclick=()=>show(key);document.querySelector('#tabs').appendChild(b);}
    document.querySelector('#refresh').onclick=refresh;show(section);
    </script>'''
