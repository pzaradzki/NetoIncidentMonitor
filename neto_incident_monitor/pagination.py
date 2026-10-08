"""Read complete classic ServiceNow lists; never return a partial traversal."""
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


class AuthenticationRequired(Exception):
    pass


class Cancelled(Exception):
    pass


def first_page(url):
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key != "sysparm_first_row"]
    query.append(("sysparm_first_row", "1"))
    return urlunparse(parsed._replace(query=urlencode(query)))


def navigation_button(page, direction):
    for frame in page.frames:
        if not urlparse(frame.url).path.endswith("/incident_list.do"):
            continue
        english, polish = ("First page", "Pierwsza strona") if direction == "first" else ("Next page", "Następna strona")
        selector = ", ".join(
            f'{tag}[{attribute}{operator}"{value}" i]'
            for tag in ("button", "a")
            for attribute, operator, value in (
                ("data-type", "=", f"list_nav_{direction}"),
                ("title", "*=", english), ("aria-label", "*=", english),
                ("title", "*=", polish), ("aria-label", "*=", polish),
                ("onclick", "*=", f"{direction}Page")))
        buttons = frame.locator(selector)
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if not button.is_visible():
                continue
            disabled = button.evaluate("""el => !!(el.disabled || el.getAttribute('aria-disabled') === 'true'
                || el.closest('[disabled], [aria-disabled=true], .disabled'))""")
            return button, disabled
    return None, False


def next_button(page):
    return navigation_button(page, "next")


def row_input(page):
    for frame in page.frames:
        if not urlparse(frame.url).path.endswith("/incident_list.do"):
            continue
        inputs = frame.locator('input.list2_page, input[data-type="list_nav_input"], input[name="sysparm_first_row"]')
        for index in range(inputs.count()):
            control = inputs.nth(index)
            if control.is_visible():
                value = control.input_value().strip()
                if value.isdigit():
                    return control, int(value)
    return None, None


def read_all(page, url, stop, collect, empty_list, authentication_page, navigate, progress=None):
    navigate(page, first_page(url))
    result = {}
    previous = None
    signatures = set()
    reset_requested = False
    restored_signature = None
    for page_index in range(1, 1001):
        rows = None
        stable = None
        repeats = 0
        for _ in range(60):
            if stop.is_set():
                raise Cancelled()
            page.wait_for_timeout(250)
            if authentication_page(page, url):
                raise AuthenticationRequired()
            try:
                candidate = collect(page)
                empty = empty_list(page, url) if not candidate else False
                if page_index == 1:
                    # ServiceNow can restore the last row from its session,
                    # even when the URL explicitly requests first_row=1.
                    first, first_disabled = navigation_button(page, "first")
                    cursor, row = row_input(page)
                    if ((first is not None and not first_disabled) or (row is not None and row > 1)) and not (empty and (row is None or row <= 1)):
                        if not reset_requested:
                            restored_signature = tuple(sorted(collect(page)))
                            if first is not None and not first_disabled:
                                first.click(timeout=10000)
                            elif cursor is not None:
                                cursor.fill("1")
                                cursor.press("Enter")
                            reset_requested = True
                            if progress:
                                progress(0, 0)
                        # Do not accept the restored last page while the
                        # first-page navigation is still loading.
                        repeats = 0
                        stable = None
                        continue
            except Exception as exc:
                if any(fragment in str(exc) for fragment in ("Execution context was destroyed", "Frame was detached")):
                    continue
                raise
            signature = tuple(sorted(candidate))
            if reset_requested and page_index == 1 and signature == restored_signature and not empty:
                continue
            if not candidate and not empty:
                continue
            if previous is not None and signature == previous:
                continue
            repeats = repeats + 1 if stable == signature else 1
            stable = signature
            if repeats >= 3:
                rows = candidate
                break
        if rows is None:
            if page_index == 1 and reset_requested:
                raise RuntimeError("Nie udało się wrócić do pierwszej strony. Nie zapisano częściowego wyniku.")
            raise RuntimeError("Nie udało się odczytać kolejnej strony listy. Nie zapisano częściowego wyniku.")
        if not rows:
            if page_index == 1:
                if progress:
                    progress(1, 0)
                return {}, 1
            raise RuntimeError("Lista zmieniła się podczas paginacji: kolejna strona jest pusta. Spróbuję ponownie w następnym cyklu.")
        signature = tuple(sorted(rows))
        if signature in signatures:
            raise RuntimeError("Paginacja powróciła do wcześniej odczytanej strony. Odczyt przerwany.")
        signatures.add(signature)
        result.update(rows)
        if progress:
            progress(page_index, len(result))
        button, disabled = next_button(page)
        if disabled:
            return result, page_index
        if button is None:
            # A missing pager is safe only when the list has no pagination at all.
            for frame in page.frames:
                if urlparse(frame.url).path.endswith("/incident_list.do") and frame.locator(
                    '[data-type^="list_nav"], input.list2_page, .list2_paging').count():
                    raise RuntimeError("Nie rozpoznano przycisku następnej strony. Nie zapisano częściowego wyniku.")
            return result, page_index
        previous = signature
        button.click(timeout=10000)
    raise RuntimeError("Przekroczono limit 1000 stron. Nie zapisano częściowego wyniku.")
