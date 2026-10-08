"""Render a demo of the actual Tk interface without using account data."""
import ctypes
import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab
from neto_incident_monitor.app import App


def main():
    root = tk.Tk()
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent) as temporary:
        try:
            with patch("neto_incident_monitor.app.read_json", return_value={"filters": [
                {"name": "Nowe incydenty", "url": "https://example.com/incident_list.do"},
                {"name": "Gdańsk i Gdynia", "url": "https://example.com/incident_list.do?filter=2"}]}):
                app = App(root, history_path=Path(temporary) / "history.json", enable_tray=False)
            descriptions = ["Brak możliwości płatności kartą — kasa 8", "Reset dostępu do aplikacji", "Problem z drukarką etykiet", "Zmiana ceny w systemie sklepowym", "Błędne przypisanie listy mailingowej", "Zablokowane referencje"]
            incidents = {}
            for index, description in enumerate(descriptions):
                number = f"INC716{1100 + index}"
                incident = {"number": number, "short_description": description,
                            "priority": "2 — wysokie" if index < 2 else "3 — umiarkowane",
                            "location": "STORE 003 GDAŃSK" if index % 2 else "STORE 073 GDYNIA",
                            "created": "2026-10-07 13:04:15", "url": "https://example.com/incident.do"}
                incidents[number] = incident
                app.history.add(incident, "Nowe incydenty", "demo")
            app.history.mark_read(list(incidents)[2:])
            app.new_numbers = set(incidents)
            app.events.put(("snapshot", (1, incidents)))
            app.events.put(("read", (time.time(), "Nowe incydenty")))
            app.events.put(("waiting", (time.monotonic() + 51, False)))
            app.events.put(("status", "Nowe incydenty: 6 zgłoszeń w ostatnim odczycie. Wszystkie listy zostały sprawdzone."))
            app.drain()
            app.start_button.configure(state="disabled")
            app.stop_button.configure(state="normal")
            app.interval_entry.configure(state="disabled")
            app.notify_check.configure(state="disabled")
            root.geometry("1440x850+30+30")
            root.update()
            first_bounds = app.tabs.bbox(0)
            second_bounds = app.tabs.bbox(1)
            app.tabs.select(1)
            root.update()
            assert app.tabs.bbox(0) == first_bounds
            assert app.tabs.bbox(1) == second_bounds
            app.tabs.select(0)
            root.update()
            root.after(500, lambda: None)
            root.update()
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            output = Path(__file__).resolve().parent.parent / "data" / "ui-preview.png"
            ImageGrab.grab(window=hwnd).save(output)
            # Check that primary controls remain within the window at minimum size.
            root.geometry("1120x680+30+30")
            app.set_phase("Oczekiwanie na logowanie")
            root.update()
            for widget in (app.start_button, app.check_button):
                assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width(), widget
            for widget in (app.sidebar_canvas,):
                assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height(), widget
            print(str(output.resolve()))
        finally:
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()


if __name__ == "__main__":
    main()
