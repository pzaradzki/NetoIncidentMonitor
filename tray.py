"""Windows tray integration. All actions reach Tk through its event queue."""
import logging


class Tray:
    def __init__(self, events):
        import pystray
        self.events = events
        self.count = 0
        self.phase = "Gotowy"
        menu = pystray.Menu(
            pystray.MenuItem("Pokaż aplikację", lambda icon, item: events.put(("show", None)), default=True),
            pystray.MenuItem("Oznacz wszystkie jako przeczytane", lambda icon, item: events.put(("mark_all", None))),
            pystray.MenuItem("Zatrzymaj monitoring", lambda icon, item: events.put(("stop_monitor", None))),
            pystray.MenuItem("Zakończ aplikację", lambda icon, item: events.put(("quit", None))),
            pystray.MenuItem("Sprawdź teraz", lambda icon, item: events.put(("check_now", None))),
        )
        self.icon = pystray.Icon("servicenow_monitor", self.image(0), "Neto Incident Monitor", menu)

    @staticmethod
    def image(count):
        from PIL import Image, ImageDraw
        from runtime_paths import ROOT
        with Image.open(ROOT / "assets" / "netology-icon.png") as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        if count:
            draw.ellipse((30, 0, 63, 33), fill="#b42318")
            label = str(count) if count < 100 else "99+"
            draw.text((47, 16), label, fill="white", anchor="mm", font_size=15)
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

    def update(self, count, phase):
        if count != self.count:
            self.icon.icon = self.image(count)
        self.count, self.phase = count, phase
        self.icon.title = f"ServiceNow — nieprzeczytane: {count} — {phase}"[:127]

    def stop(self):
        self.icon.visible = False
        self.icon.stop()
