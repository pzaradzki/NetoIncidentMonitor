"""Verified analytics identity and safe, fixed read-error categories."""
import re
from urllib.parse import urlparse


class DashboardReadError(ValueError):
    def __init__(self, reason, retryable=True):
        self.reason, self.retryable = reason, retryable
        super().__init__('Nie potwierdzono poprawnego odczytu dashboardu (' + reason + ').')


TAB_NAMES = {'sla': ('Dasboard SLA', 'Dashboard SLA'), 'held': ('Wstrzymane L1',),
             'requests': ('Wnioski L1',), 'threatened': ('L1 – Incydenty zagrożone SLA',)}
TAB_IDS = {'sla': 'ba36dad72b6a8b504b98f4c2c891bf73', 'held': 'c228c7d455c81f90211a1d000e482311',
           'requests': '17fcfee03dcc5310e5e0b24c4676861c', 'threatened': '54154e7fadc41fd030fd4a7e9f322595'}
DASHBOARD_ID = '22361ad72b6a8b504b98f4c2c891bfab'


def normalize_title(text):
    return re.sub(r'\s+', ' ', re.sub(r'\s*>\s*', ' >', text)).strip()


def selected_tab(page, section):
    names = re.compile('^(?:' + '|'.join(re.escape(n) for n in TAB_NAMES[section]) + ')$')
    return page.get_by_role('tab', name=names).filter(visible=True)


def verify_target(page, section):
    actual = urlparse(page.url)
    if (actual.scheme != 'https' or actual.hostname != 'adeo.service-now.com' or
            not actual.path.startswith('/now/platform-analytics-workspace/dashboards/') or
            '/sys-id/' + DASHBOARD_ID + '/' not in actual.path + '/'):
        raise DashboardReadError('wrong_dashboard')
    tab = selected_tab(page, section)
    # One DOM observation avoids a count/attribute race during rerendering.
    states = tab.evaluate_all('(elements)=>elements.map(e=>e.getAttribute("aria-selected"))')
    if states != ['true']:
        raise DashboardReadError('wrong_tab')


def date_panel(page):
    # On the real page the hoisted panel, not role=dialog, owns the date fields
    # and action buttons. Its host can have zero geometry while children show.
    start = page.get_by_role('textbox', name='Data rozpoczęcia', exact=True)
    panels = page.locator('now-popover-panel').filter(has=start)
    if panels.count() != 1:
        raise DashboardReadError('ambiguous_period', retryable=False)
    return panels


def begin_refresh_watch(page, titles):
    """Observe only rendered target cards; store no business values or HTML."""
    page.evaluate("""titles => {
        window.__netoDashboardRefresh?.observers.forEach(o=>o.disconnect());
        const state={seen:false,observers:[]};window.__netoDashboardRefresh=state;
        const norm=t=>t.replace(/\\s*>\\s*/g,' >').replace(/\\s+/g,' ').trim();
        const expected=new Set(titles.map(norm));const roots=[];const cards=[];
        const scan=r=>{roots.push(r);for(const e of r.querySelectorAll('*')) {
            if(e.classList.contains('grid-stack-item-content')) cards.push(e);
            if(e.shadowRoot)scan(e.shadowRoot);
        }};scan(document);
        const inside=(node,card)=>{let e=node.nodeType===1?node:node.parentElement;
            while(e){if(e===card)return true;e=e.parentElement||e.getRootNode()?.host;}return false};
        const headings=card=>{const result=[];const walk=r=>{for(const e of r.querySelectorAll('*')){
            if(/^H[1-3]$/.test(e.tagName))result.push(norm(e.textContent));if(e.shadowRoot)walk(e.shadowRoot)}};
            walk(card);return result};
        const targets=cards.filter(c=>c.getClientRects().length && getComputedStyle(c).visibility!=='hidden' &&
            headings(c).some(t=>expected.has(t)));
        for(const root of roots){const observer=new MutationObserver(changes=>{
            if(changes.some(m=>targets.some(c=>inside(m.target,c))))state.seen=true;
        });observer.observe(root,{childList:true,subtree:true,characterData:true,attributes:true,
            attributeFilter:['aria-busy','hidden','class']});state.observers.push(observer)}
    }""", list(titles))


def end_refresh_watch(page):
    try:
        page.evaluate("""() => {window.__netoDashboardRefresh?.observers.forEach(o=>o.disconnect());
            delete window.__netoDashboardRefresh;}""")
    except Exception:
        pass  # A closed/replaced document needs no observer cleanup.
