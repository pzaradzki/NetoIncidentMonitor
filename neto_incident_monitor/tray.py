"""Windows tray integration. All actions reach Tk through its event queue."""
import logging


class Tray:
    def __init__(self, events, browser_visible=None, login_waiting=None):
        import pystray
        self.events = events
        self.phase = "Gotowy"
        browser_visible = browser_visible or (lambda: False)
        browser_action = (pystray.MenuItem('Pokaż okno logowania',
            lambda icon, item: events.put(('show_browser', None)), visible=lambda item: login_waiting())
            if login_waiting is not None else
            pystray.MenuItem(lambda item: "Ukryj przeglądarkę" if browser_visible() else "Pokaż przeglądarkę",
                lambda icon, item: events.put(("hide_browser" if browser_visible() else "show_browser", None))))
        menu = pystray.Menu(
            pystray.MenuItem("Pokaż aplikację", lambda icon, item: events.put(("show", None)), default=True),
            browser_action,
            pystray.MenuItem("Zatrzymaj monitoring", lambda icon, item: events.put(("stop_monitor", None))),
            pystray.MenuItem("Zakończ aplikację", lambda icon, item: events.put(("quit", None))),
            pystray.MenuItem("Sprawdź teraz", lambda icon, item: events.put(("check_now", None))),
        )
        self.icon = pystray.Icon("servicenow_monitor", self.image(), "Neto Incident Monitor", menu)

    @staticmethod
    def image():
        from PIL import Image
        from neto_incident_monitor.runtime_paths import ROOT
        with Image.open(ROOT / "assets" / "netology-icon.png") as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        return image

    def start(self):
        def setup(icon):
            try:
                icon.visible = True
                self.events.put(("tray_ready", None))
            except Exception:
                logging.exception("Nie udało się wyświetlić ikony zasobnika")
                self.events.put(("tray_failed", None))
        self.icon.run_detached(setup)

    def update(self, phase):
        self.phase = phase
        self.icon.title = f"ServiceNow — {phase}"[:127]

    def stop(self):
        self.icon.visible = False
        self.icon.stop()
