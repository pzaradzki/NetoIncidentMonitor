import threading
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.read_budget import Budget, budget_scope
from neto_incident_monitor.pagination import Cancelled


def fixture(extra=''):
    return '''<button id="nav-overflow" aria-expanded="false">Więcej menu</button>
    <sn-polaris-menu aria-label="Więcej menu"></sn-polaris-menu>
    <sn-polaris-menu aria-label="Odpięte menu Ulubione"></sn-polaris-menu>
    <script>
    const menu=document.querySelector('sn-polaris-menu').attachShadow({mode:'open'});
    menu.innerHTML='<button id="favorites" hidden>Ulubione</button>';
    document.querySelector('#nav-overflow').onclick=()=>{
      let b=document.querySelector('#nav-overflow');b.setAttribute('aria-expanded',String(b.getAttribute('aria-expanded')!=='true'));
      menu.querySelector('#favorites').hidden=b.getAttribute('aria-expanded')!=='true';};
    function item(root,id,name,href){let h=document.createElement('sn-collapsible-list');h.setAttribute('role','listitem');
      let r=h.attachShadow({mode:'open'});r.innerHTML='<a class="item-label" id="'+id+'" data-id="'+id+'" href="'+href+'" aria-label="WRONG POSITION">'+name+'</a>';
      root.append(h);return h;}
    function mount(){menu.innerHTML='<button>Edytuj ulubione</button><input aria-label="Wprowadź wyszukiwany termin w celu filtrowania menu Ulubione"><div class="sn-polaris-nav-body" role="list"></div>';
      let root=menu.querySelector('[role=list]');item(root,'a','Filtr A','incident_list.do?sysparm_query=active%3Dtrue');
      let h=document.createElement('sn-collapsible-list');h.setAttribute('role','listitem');let r=h.attachShadow({mode:'open'});
      r.innerHTML='<div role="group"><div role="button" aria-expanded="false"><span role="heading">Grupa A</span></div><ul><li><a id="b" data-id="b" class="item-label" href="/sc_task_list.do?sysparm_query=active%3Dtrue">Filtr A</a></li></ul></div>';
      root.append(h);r.querySelector('[role=button]').onclick=()=>r.querySelector('[role=button]').setAttribute('aria-expanded','true');
      window.fixtureRoot=root;window.fixtureMenu=menu;
      ''' + extra + '''
    }
    menu.querySelector('#favorites').onclick=mount;
    </script>'''


class FavoritesReaderTests(unittest.TestCase):
    def setUp(self):
        self.pw = sync_playwright().start()
        self.addCleanup(self.pw.stop)
        self.browser = self.pw.chromium.launch(headless=True)
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.stop = threading.Event()

    def load(self, extra=''):
        self.page.route('**/*', lambda r: r.fulfill(body=fixture(extra), content_type='text/html; charset=utf-8'))
        self.page.goto('https://adeo.service-now.com/now/sow/home')

    def read(self):
        from neto_incident_monitor.favorites_reader import read_favorites
        with patch('neto_incident_monitor.favorites_reader.check_session'), budget_scope(Budget(3)):
            return read_favorites(self.page, self.stop)

    def test_bulk_snapshot_keeps_names_targets_order_groups_and_collapsed_children(self):
        self.load()
        rows = self.read()
        self.assertEqual([r['name'] for r in rows], ['Filtr A', 'Filtr A'])
        self.assertEqual(rows[1]['groups'], ['Grupa A'])
        self.assertEqual(rows[0]['href'], 'incident_list.do?sysparm_query=active%3Dtrue')
        from neto_incident_monitor.favorites import classify
        self.assertEqual(classify(rows,[])[0]['kind'], 'INC')
        self.assertEqual(self.page.locator('#nav-overflow').get_attribute('aria-expanded'), 'false')

    def test_late_content_restarts_stability(self):
        self.load("setTimeout(()=>item(root,'c','Filtr C','/sc_request_list.do'),250);")
        self.assertEqual(len(self.read()), 3)

    def test_unknown_child_cannot_silently_disappear(self):
        from neto_incident_monitor.favorites_reader import FavoritesReadError
        self.load("root.append(document.createElement('div'));")
        with self.assertRaises(FavoritesReadError):
            self.read()

    def test_unconfirmed_empty_is_not_success(self):
        from neto_incident_monitor.favorites_reader import FavoritesReadError
        self.load("root.replaceChildren();")
        with self.assertRaises((FavoritesReadError, TimeoutError)):
            self.read()

    def test_stop_does_not_click_menu(self):
        self.load()
        self.stop.set()
        with self.assertRaises(Cancelled):
            self.read()
        self.assertEqual(self.page.locator('#nav-overflow').get_attribute('aria-expanded'), 'false')

    def test_missing_name_is_incomplete(self):
        from neto_incident_monitor.favorites_reader import FavoritesReadError
        self.load("root.children[0].shadowRoot.querySelector('a').textContent='';")
        with self.assertRaises(FavoritesReadError):
            self.read()

    def test_delayed_search_reset_cannot_accept_old_subset(self):
        self.load("""const input=menu.querySelector('input');input.value='Syntetyczne';root.classList.add('hide-scroll');
            input.oninput=()=>setTimeout(()=>{root.classList.remove('hide-scroll');item(root,'c','Filtr C','/sc_request_list.do');},650);""")
        self.assertEqual(len(self.read()),3)

    def test_virtual_group_slice_is_rejected(self):
        from neto_incident_monitor.favorites_reader import FavoritesReadError
        self.load("""const li=root.children[1].shadowRoot.querySelector('li');
            li.setAttribute('aria-posinset','10');li.setAttribute('aria-setsize','1');""")
        with self.assertRaises(FavoritesReadError):
            self.read()

    def test_closed_menu_cannot_return_retained_dom_as_success(self):
        from neto_incident_monitor.favorites_reader import FavoritesReadError
        self.load("setTimeout(()=>document.querySelector('#nav-overflow').setAttribute('aria-expanded','false'),250);")
        with self.assertRaises(FavoritesReadError):
            self.read()
