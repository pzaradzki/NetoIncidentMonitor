"""Shared browser resources; called only by the exclusive Playwright owner."""
from neto_incident_monitor.browser_policy import BrowserRuntime


def open_context(playwright, profile, diagnostics, *, visible=False, offer_password_save=False):
    from neto_incident_monitor.browser_icon import browser_launch_options
    from neto_incident_monitor.authentication import install_input_guard
    diagnostics.record('browser_launch_attempt')
    context = playwright.chromium.launch_persistent_context(
        str(profile), headless=False, no_viewport=True,
        **browser_launch_options(visible=visible, offer_password_save=offer_password_save))
    try:
        install_input_guard(context)
        diagnostics.record('browser_launched')
        return context
    except BaseException:
        close_session(context, None, diagnostics)
        raise


def create_runtime(page, options, diagnostics, events, set_state, window_changed):
    from neto_incident_monitor.browser_window import BrowserWindow
    def window_factory():
        return BrowserWindow(page.context.browser,
            visibility_changed=lambda: events.put(('browser_visibility', None)))
    return BrowserRuntime(page, options, window_factory, set_state, diagnostics, window_changed)


def close_session(context, runtime, diagnostics):
    errors = 0
    for resource in (runtime, context):
        if resource is not None:
            try:
                resource.close()
            except Exception:
                errors += 1
    if errors:
        try:
            diagnostics.record('browser_cleanup_error', cleanup_errors=errors)
        except Exception:
            pass
