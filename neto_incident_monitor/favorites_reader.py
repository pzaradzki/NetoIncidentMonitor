"""Observed Polaris favorites only; no endpoint guessing or business navigation."""
from contextlib import contextmanager
from playwright.sync_api import TimeoutError
from neto_incident_monitor.browser_actions import checkpoint, ready_control, wait_control, read_control
from neto_incident_monitor.read_budget import remaining_ms, BudgetExpired
from neto_incident_monitor.pagination import AuthenticationRequired
from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.favorites import HOME

MENU = 'sn-polaris-menu[aria-label="Więcej menu"]'
SEARCH = 'Wprowadź wyszukiwany termin w celu filtrowania menu Ulubione'


class FavoritesReadError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__('Nie potwierdzono kompletnego menu Ulubione.')


SNAPSHOT = r"""root => {
 const rows=[], groups=[], missing=[];let error=null;
 const seen=new Set();
 for(const [index,host] of [...root.children].entries()) {
   if(host.tagName!=='SN-COLLAPSIBLE-LIST'||host.getAttribute('role')!=='listitem') {error='unsupported';break;}
   const r=host.shadowRoot;
   if(!r){error='loading';break;}
   const anchors=[...r.querySelectorAll('a.item-label')];
   const group=r.querySelector('[role=group]');
   if(r.querySelector('sn-collapsible-list')){error='unsupported';break;}
   let path=[];
   if(group){
     const headings=[...group.querySelectorAll('[role=heading]')];
     const toggles=[...group.querySelectorAll('[role=button][aria-expanded]')];
     if(headings.length!==1||toggles.length!==1||!headings[0].textContent.trim()){error='unsupported';break;}
     const expanded=toggles[0].getAttribute('aria-expanded');
     if(!['true','false'].includes(expanded)){error='unsupported';break;}
     path=[headings[0].textContent.trim()];
     groups.push({index,path,expanded});
     if(!anchors.length){if(expanded==='false')missing.push(index);else error='loading';}
     const items=[...group.querySelectorAll('li')];
     if(items.length!==anchors.length){error='unsupported';break;}
     // Real Polaris reverses these ARIA fields. Accept only a complete range,
     // in either standard or observed orientation; never a virtualized slice.
     if(items.some(i=>i.hasAttribute('aria-setsize')||i.hasAttribute('aria-posinset'))){
       const complete=(total,index)=>items.every((e,i)=>Number(e.getAttribute(total))===items.length&&Number(e.getAttribute(index))===i+1);
       if(!complete('aria-setsize','aria-posinset')&&!complete('aria-posinset','aria-setsize')){error='unsupported';break;}
     }
   }else if(anchors.length!==1){error='unsupported';break;}
   if(r.querySelectorAll('a[href]').length!==anchors.length){error='unsupported';break;}
   for(const a of anchors){
     const id=a.getAttribute('data-id')||a.id,name=a.textContent.trim(),href=a.getAttribute('href');
     if(!id||!name||!href||seen.has(id)){error='incomplete';break;}
     seen.add(id);rows.push({source_id:id,name,href,groups:path});
   }
   if(error)break;
 }
 if(!root.children.length)error='empty_unconfirmed';
 return {rows,groups,missing,error,top_count:root.children.length};
}"""


def check_session(page):
    if authentication_required(page, HOME):
        raise AuthenticationRequired()
    if page.url != HOME:
        raise FavoritesReadError('context')


def click_once(control, page, stop):
    ready_control(control, stop, timeout=5000, check=lambda: check_session(page))
    control.click(timeout=remaining_ms(1000), no_wait_after=True)


@contextmanager
def menu_viewport(page, diagnostics=None):
    """Temporary read-only layout, without fixing the login page viewport."""
    previous = page.viewport_size
    session = page.context.new_cdp_session(page)
    try:
        session.send('Emulation.setDeviceMetricsOverride', {
            'width':751, 'height':884, 'deviceScaleFactor':0, 'mobile':False})
        if diagnostics:
            diagnostics.record('favorites_stage', import_stage='viewport_read')
        yield
    finally:
        try:
            if previous is None:
                session.send('Emulation.clearDeviceMetricsOverride')
            else:
                page.set_viewport_size(previous)
            if diagnostics:
                diagnostics.record('favorites_stage', import_stage='viewport_natural')
        finally:
            try:
                session.detach()
            except Exception:
                if diagnostics:
                    diagnostics.record('browser_cleanup_error', cleanup_errors=1)


def read_favorites(page, stop, diagnostics=None):
    checkpoint(stop)
    check_session(page)
    with menu_viewport(page, diagnostics):
        return _read_favorites(page, stop, diagnostics)


def _read_favorites(page, stop, diagnostics=None):
    menu = page.locator(MENU)
    overflow = page.locator('#nav-overflow')
    search = menu.get_by_role('textbox', name=SEARCH, exact=True)
    # Filtered result lists use hide-scroll, even when only one result group
    # remains. Count alone cannot distinguish a delayed search result.
    root = menu.locator('.sn-polaris-nav-body:not(.hide-scroll)')
    changed_groups = []
    original_search = None
    opened = False
    def record(stage, **facts):
        if diagnostics:
            diagnostics.record('favorites_stage', import_stage=stage, **facts)
    try:
        record('open')
        expanded = read_control(overflow, stop, lambda: overflow.get_attribute('aria-expanded', timeout=300),
                                check=lambda: check_session(page))
        if expanded == 'false':
            opened = True  # Also restore after uncertain delivery, never click again blindly.
            click_once(overflow, page, stop)
        elif expanded != 'true':
            raise FavoritesReadError('unsupported')
        favorites = menu.get_by_role('button', name='Ulubione', exact=True)
        back = menu.get_by_role('button', name='Powrót do menu', exact=True)
        def route():
            for alias, control in (('favorites', search), ('menu', favorites), ('back', back)):
                count = control.count()
                if count > 1:
                    raise FavoritesReadError('unsupported')
                if count == 1:
                    return alias
            raise AssertionError('Favorites route not ready')
        destination = read_control(menu, stop, route, timeout=5000,
                                   assertion=True, check=lambda: check_session(page))
        if destination == 'back':
            click_once(back, page, stop)
        if destination != 'favorites':
            click_once(favorites, page, stop)
        wait_control(search, stop, timeout=5000, check=lambda: check_session(page))
        wait_control(menu.get_by_role('button', name='Edytuj ulubione', exact=True), stop,
                     timeout=5000, check=lambda: check_session(page))
        original_search = read_control(search, stop, lambda: search.input_value(timeout=300),
                                       check=lambda: check_session(page))
        if original_search:
            search.fill('', timeout=remaining_ms(1000))
        previous, stable = None, 0
        expanded_once = set()
        record('snapshot')
        while True:
            checkpoint(stop)
            check_session(page)
            panel_state = read_control(overflow, stop,
                lambda: (overflow.get_attribute('aria-expanded', timeout=300), search.input_value(timeout=300)),
                check=lambda: check_session(page))
            if panel_state[0] != 'true':
                raise FavoritesReadError('context')
            if panel_state[1] != '':
                raise FavoritesReadError('search_changed')
            if root.count() != 1:
                previous, stable = None, 0
            else:
                snapshot = read_control(root, stop, lambda: root.evaluate(SNAPSHOT, timeout=remaining_ms(500)),
                                        check=lambda: check_session(page))
                reason = snapshot['error']
                if reason in ('unsupported', 'incomplete'):
                    raise FavoritesReadError(reason)
                for index in snapshot['missing']:
                    if index in expanded_once:
                        continue
                    toggle = root.locator(':scope > sn-collapsible-list').nth(index).locator('[role="button"][aria-expanded]')
                    expanded_once.add(index)
                    changed_groups.append(toggle)
                    click_once(toggle, page, stop)
                if reason or snapshot['missing']:
                    previous, stable = None, 0
                else:
                    stable = stable + 1 if snapshot == previous else 1
                    previous = snapshot
                    if stable >= 3:
                        record('complete', item_count=len(snapshot['rows']), group_count=len(snapshot['groups']))
                        check_session(page)
                        checkpoint(stop)
                        return snapshot['rows']
            page.wait_for_timeout(remaining_ms(200))
    finally:
        # Cleanup is best effort after cancellation/budget expiry, without replaying actions.
        try:
            if original_search:
                if search.count()==1 and search.input_value(timeout=200)=='':
                    search.fill(original_search, timeout=300)
            for toggle in reversed(changed_groups):
                if toggle.count()==1 and toggle.get_attribute('aria-expanded', timeout=200)=='true':
                    toggle.click(timeout=300, no_wait_after=True)
            if opened and overflow.count()==1 and overflow.get_attribute('aria-expanded', timeout=200)=='true':
                overflow.click(timeout=300, no_wait_after=True)
        except Exception:
            record('cleanup', cleanup_errors=1)
