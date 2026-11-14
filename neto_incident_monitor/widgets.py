"""Small keyboard-accessible controls matching the application palette."""
import tkinter as tk
from time import monotonic
from PIL import Image, ImageDraw, ImageOps, ImageTk
from neto_incident_monitor.theme import SURFACE, TEXT, ACCENT


def checkbox_images(master, background):
    """Shared checkbox geometry; None keeps table/selection backgrounds visible."""
    images = []
    for checked in (False, True):
        picture = Image.new('RGBA' if background is None else 'RGB', (96, 96),
                            (0, 0, 0, 0) if background is None else background)
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((8, 12, 76, 80), radius=16,
            fill=ACCENT if checked else SURFACE,
            outline=ACCENT if checked else '#737c8b', width=4)
        if checked:
            draw.line([(24, 44), (36, 56), (60, 32)], fill=TEXT, width=8)
        images.append(ImageTk.PhotoImage(picture.resize((24, 24), Image.Resampling.LANCZOS), master=master))
    return images


def draw_gear(draw, x, y, color, size=16):
    """Shared gear outline, rendered at 4x resolution for smooth edges."""
    import math
    scale = size / 16
    outline = []
    for i in range(32):
        angle = i * math.pi / 16
        radius = 7.5 if i % 4 in (1, 2) else 5.5
        outline.append((round((x + (8 + math.cos(angle) * radius) * scale) * 4),
                        round((y + (8 + math.sin(angle) * radius) * scale) * 4)))
    stroke = round(6 * scale)
    draw.line(outline + [outline[0]], fill=color, width=stroke, joint="curve")
    draw.ellipse((round((x + 5 * scale) * 4), round((y + 5 * scale) * 4),
                  round((x + 11 * scale) * 4), round((y + 11 * scale) * 4)),
                 outline=color, width=stroke)


class StatusPill(tk.Canvas):
    """Compact status badge with smooth rounded edges."""
    def __init__(self, parent, compact=False, fit=False):
        from neto_incident_monitor.theme import BG
        self.pill_height = 22 if compact else 28
        self.pill_font = ('Segoe UI', 8 if compact else 9, 'bold')
        self.pill_padding = 18 if compact else 24
        super().__init__(parent, height=self.pill_height, bg=BG, bd=0, highlightthickness=0)
        self.fit = fit
        self.status_text = ''
        self.tone = None
        if fit:
            parent.bind('<Configure>', lambda event: self.set_status(self.status_text, self.tone), add='+')
            self.status_tooltip = StatusTooltip(self)

    def set_status(self, text, tone=None):
        from tkinter.font import Font
        self.status_text, self.tone = text, tone
        if self.fit and self.status_tooltip.text != text:
            self.status_tooltip.hide()
            self.status_tooltip.text = text
        colors = {
            "Zaktualizowany": ("#244b37", "#8ee2ac"),
            "Dane aktualne": ("#244b37", "#8ee2ac"),
            "Błąd odczytu": ("#472c33", "#ff929e"),
            "W trakcie aktualizacji": ("#27364a", "#9ac4f4"),
            "Ponawianie odczytu": ("#433923", "#efc778"),
            "Dane nieaktualne": ("#433923", "#efc778"),
            "Aktualizacja częściowa": ("#433923", "#efc778"),
            "Oczekuje": ("#343942", "#c8cdd6"),
            "Monitoring aktywny": ("#243d33", "#85d6aa"),
            "Oczekiwanie na logowanie": ("#433923", "#efc778"),
            "Sprawdzanie list": ("#27364a", "#9ac4f4"),
            "Uruchamianie przeglądarki": ("#27364a", "#9ac4f4"),
            "Błąd odczytu": ("#472c33", "#ff929e"),
            "Błąd uruchomienia": ("#472c33", "#ff929e"),
        }
        tones = {'working': ('#27364a', '#9ac4f4'), 'waiting': ('#433923', '#efc778'),
                 'success': ('#244b37', '#8ee2ac'), 'error': ('#472c33', '#ff929e')}
        background, foreground = tones.get(tone, colors.get(text, ("#343942", "#c8cdd6")))
        font = Font(self, font=self.pill_font)
        width = font.measure(text) + self.pill_padding
        if self.fit:
            width = min(width, max(1, self.master.winfo_width()))
            available = max(0, width - self.pill_padding)
            if font.measure(text) > available:
                while text and font.measure(text + '…') > available:
                    text = text[:-1]
                text = text + '…' if text else ''
        self.display_text = text
        height = self.pill_height
        self.configure(width=width)
        picture = Image.new("RGB", (width * 4, height * 4), self.cget("bg"))
        ImageDraw.Draw(picture).rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1),
                                                  radius=height * 2, fill=background)
        self.picture = ImageTk.PhotoImage(picture.resize((width, height), Image.Resampling.LANCZOS), master=self)
        self.delete("all")
        self.create_image(0, 0, image=self.picture, anchor="nw")
        self.create_text(width / 2, height / 2, text=text, fill=foreground, font=self.pill_font)


class PriorityDots:
    """Small cell overlays, following scrolling and column rearrangements."""
    COLORS = {"1": "#ff3b57", "2": "#ff901f", "3": "#ffe13b", "4": "#35e893", "5": "#8ab4ff"}

    def __init__(self, table):
        self.table = table
        self.root = table.winfo_toplevel()
        self.dots = []
        self.images = {}
        self.timer = None
        table.bind("<Destroy>", self.close, add="+")
        self.refresh()

    def close(self, event):
        if event.widget is self.table and self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def refresh(self):
        table = self.table
        used = 0
        if table.winfo_ismapped() and "priority" in table["displaycolumns"]:
            rows = dict.fromkeys(table.identify_row(y) for y in range(0, table.winfo_height(), 8))
            selected = set(table.selection())
            for item in rows:
                if not item:
                    continue
                value = table.set(item, "priority").strip()
                color = self.COLORS.get(value[:1])
                bounds = table.bbox(item, "priority")
                if not color or not bounds:
                    continue
                x, y, width, height = bounds
                x += 4
                if x < 0 or x + 14 > table.winfo_width():
                    continue
                if used == len(self.dots):
                    dot = tk.Canvas(table, width=14, height=14, highlightthickness=0, borderwidth=0)
                    # Forward clicks to the row so the decoration does not block selection.
                    for sequence in ("<Button-1>", "<Double-1>", "<Button-3>"):
                        dot.bind(sequence, lambda event, seq=sequence: table.event_generate(
                            seq, x=event.x_root-table.winfo_rootx(), y=event.y_root-table.winfo_rooty()))
                    self.dots.append(dot)
                dot = self.dots[used]
                tags = table.item(item, "tags")
                background = "#2b2f37" if "alternate" in tags else SURFACE
                if item in selected:
                    from tkinter import ttk
                    background = ttk.Style(table).lookup("Treeview", "background", ("selected",)) or background
                dot.configure(background=background)
                dot.delete("all")
                key = (color, background)
                if key not in self.images:
                    scale = 8
                    picture = Image.new("RGB", (14 * scale, 14 * scale), background)
                    draw = ImageDraw.Draw(picture)
                    draw.ellipse((1 * scale, 1 * scale, 13 * scale, 13 * scale), fill=color)
                    self.images[key] = ImageTk.PhotoImage(
                        picture.resize((14, 14), Image.Resampling.LANCZOS), master=table)
                dot.create_image(0, 0, anchor="nw", image=self.images[key])
                dot.place(x=x, y=y+(height-14)//2)
                used += 1
        for dot in self.dots[used:]:
            dot.place_forget()
        self.timer = self.root.after(100, self.refresh)


class IncidentMenu(tk.Toplevel):
    """Borderless popup with keyboard navigation and outside-click dismissal."""
    def __init__(self, parent):
        super().__init__(parent, background="#373c46")
        self.withdraw()
        self.overrideredirect(True)
        self.rows = []
        self.selected = -1
        self.body = tk.Frame(self, background=SURFACE, pady=4)
        self.body.pack(padx=1, pady=1)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Down>", lambda event: self.select((self.selected + 1) % len(self.rows)))
        self.bind("<Up>", lambda event: self.select((self.selected - 1) % len(self.rows)))
        self.bind("<Return>", lambda event: self.invoke(self.selected))
        self.bind("<ButtonPress-1>", self.outside_click)
        self.bind("<ButtonPress-3>", self.redirect_right_click)
        self.bind("<FocusOut>", lambda event: self.after_idle(self.check_focus))

    def add_command(self, label, command):
        index = len(self.rows)
        row = tk.Label(self.body, text=label, background=SURFACE, foreground=TEXT,
                       font=("Segoe UI", 10), anchor="w", padx=14, pady=8, cursor="hand2")
        row.pack(fill="x", padx=4)
        self.rows.append((row, command))
        row.bind("<Enter>", lambda event: self.select(index))
        row.bind("<ButtonRelease-1>", lambda event: self.invoke(index))

    def add_separator(self):
        tk.Frame(self.body, background="#373c46", height=1).pack(fill="x", padx=12, pady=4)

    def select(self, index):
        self.selected = index
        for i, (row, _) in enumerate(self.rows):
            row.configure(background=ACCENT if i == index else SURFACE)
        return "break"

    def invoke(self, index):
        if 0 <= index < len(self.rows):
            command = self.rows[index][1]
            self.destroy()
            command()
        return "break"

    def outside_click(self, event):
        if not (self.winfo_rootx() <= event.x_root < self.winfo_rootx() + self.winfo_width()
                and self.winfo_rooty() <= event.y_root < self.winfo_rooty() + self.winfo_height()):
            self.destroy()
            return "break"

    def check_focus(self):
        if self.winfo_exists() and str(self.tk.call('focus')) != str(self):
            self.destroy()

    def redirect_right_click(self, event):
        x, y = event.x_root, event.y_root
        owner = self.master
        self.destroy()
        target = owner.winfo_containing(x, y)
        if target is not None and target.winfo_toplevel() == owner.winfo_toplevel():
            target.event_generate("<ButtonPress-3>", x=x - target.winfo_rootx(),
                                  y=y - target.winfo_rooty(), rootx=x, rooty=y)
        return "break"

    def show(self, x, y):
        import sys

        self.update_idletasks()
        if sys.platform == "win32":
            from neto_incident_monitor.window_style import move_popup
            self.deiconify()
            self.update_idletasks()
            move_popup(self, x, y)
        else:
            self.geometry(f"+{x}+{y}")
            self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_force()


class Toggle(tk.Canvas):
    def __init__(self, parent, variable):
        super().__init__(parent, width=48, height=28, bg=SURFACE, bd=0,
                         highlightthickness=1, highlightbackground=SURFACE,
                         highlightcolor="#606875", takefocus=True, cursor="hand2")
        self.variable = variable
        self.enabled = True
        self.images = {}
        self.trace = variable.trace_add("write", lambda *_: self.redraw())
        self.bind("<Button-1>", self.toggle)
        self.bind("<space>", self.toggle)
        self.bind("<Return>", self.toggle)
        self.redraw()

    def toggle(self, event=None):
        if self.enabled:
            self.variable.set(not self.variable.get())
            self.focus_set()
        return "break"

    def redraw(self):
        self.delete("all")
        on = self.variable.get()
        color = (ACCENT if on else "#4b515c") if self.enabled else ("#85444c" if on else "#343840")
        background = self.cget("background")
        key = (bool(on), self.enabled, background)
        if key not in self.images:
            # Draw at 8x resolution, then downsample to smooth curved edges.
            scale = 8
            image = Image.new("RGB", (48 * scale, 28 * scale), background)
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((2 * scale, 2 * scale, 46 * scale, 26 * scale),
                                   radius=12 * scale, fill=color)
            center = 34 if on else 14
            draw.ellipse(((center - 9) * scale, 5 * scale, (center + 9) * scale, 23 * scale), fill=TEXT)
            image = image.resize((48, 28), Image.Resampling.LANCZOS)
            self.images[key] = ImageTk.PhotoImage(image, master=self)
        self.create_image(0, 0, anchor="nw", image=self.images[key])

    def configure(self, cnf=None, **kwargs):
        state = kwargs.get("state") or (cnf.get("state") if isinstance(cnf, dict) else None)
        result = super().configure(cnf, **kwargs)
        if state is not None:
            self.enabled = state != "disabled"
            self.redraw()
        if "background" in kwargs or "bg" in kwargs:
            super().configure(highlightbackground=self.cget("background"))
            self.redraw()
        return result

    def destroy(self):
        self.variable.trace_remove("write", self.trace)
        super().destroy()

class RoundedButton(tk.Canvas):
    """A button with the same command/state interface as the sidebar buttons."""
    def __init__(self, parent, text, command, primary=False, background=SURFACE, icon=None, compact=False):
        from tkinter.font import Font
        self.text_width = Font(parent, font=("Segoe UI", 9)).measure(text)
        self.icon = icon
        self.button_height = 26 if compact else 36
        self.min_width = 36 if icon and not text else (45 if compact else 90)
        width = max(self.min_width, self.text_width + (18 if compact else 24) + (22 if icon and text else 0))
        super().__init__(parent, width=width, height=self.button_height, bg=background, bd=0,
                         highlightthickness=0, takefocus=True, cursor="hand2")
        self.text, self.command, self.primary = text, command, primary
        self.enabled, self.hover = True, False
        self.bind("<Configure>", self.redraw)
        self.bind("<Enter>", lambda _: self.set_hover(True))
        self.bind("<Leave>", lambda _: self.set_hover(False))
        self.bind("<Button-1>", self.invoke)
        self.bind("<space>", self.invoke)
        self.bind("<Return>", self.invoke)
        self.bind("<FocusIn>", self.redraw)
        self.bind("<FocusOut>", self.redraw)

    def set_hover(self, hover):
        self.hover = hover
        self.redraw()

    def invoke(self, event=None):
        if self.enabled:
            self.focus_set()
            self.command()
        return "break"

    def redraw(self, event=None):
        self.delete("all")
        width, height = max(self.min_width, self.winfo_width()), self.button_height
        color = (ACCENT if self.primary else "#373c46")
        if self.hover and self.enabled:
            color = "#f04b59" if self.primary else "#484f5c"
        if not self.enabled:
            color = "#30343c"
        picture = Image.new("RGB", (width * 4, height * 4), self.cget("background"))
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius=8 * 4,
                               fill=color, outline='#606875' if str(self.tk.call('focus')) == str(self) else color, width=4)
        foreground = TEXT if self.enabled else "#747b88"
        if self.icon:
            self.draw_icon(draw, (width - self.text_width - 22) / 2 if self.text else (width - 16) / 2, (height - 16) / 2, foreground)
        self.picture = ImageTk.PhotoImage(picture.resize((width, height), Image.Resampling.LANCZOS), master=self)
        self.create_image(0, 0, image=self.picture, anchor="nw")
        self.create_text(width / 2 + (11 if self.icon else 0), height / 2, text=self.text,
                         fill=foreground, font=("Segoe UI", 9))

    def draw_icon(self, draw, x, y, color):
        def points(coords):
            return [(round((x + a) * 4), round((y + b) * 4)) for a, b in coords]
        def line(coords):
            draw.line(points(coords), fill=color, width=6, joint="curve")
        def box(a, b, c, d):
            return (round((x+a)*4), round((y+b)*4), round((x+c)*4), round((y+d)*4))
        if self.icon == "play":
            draw.polygon(points([(4, 2), (14, 8), (4, 14)]), fill=color)
        elif self.icon == "stop":
            draw.rounded_rectangle(box(3, 3, 13, 13), radius=4, fill=color)
        elif self.icon == "refresh":
            draw.arc(box(2, 2, 14, 14), start=35, end=320, fill=color, width=6)
            line([(10, 1), (14, 3), (13, 7)])
        elif self.icon == "check":
            line([(2, 8), (6, 12), (13, 4)])
        elif self.icon == "trash":
            line([(2, 4), (14, 4)])
            line([(6, 4), (6, 2), (10, 2), (10, 4)])
            line([(4, 5), (5, 14), (11, 14), (12, 5)])
            line([(7, 7), (7, 11)])
            line([(9, 7), (9, 11)])
        elif self.icon == "edit":
            draw.polygon(points([(3, 10), (10, 3), (13, 6), (6, 13), (2, 14)]),
                         outline=color, width=6)
            line([(8, 5), (11, 8)])
        elif self.icon == "columns":
            draw.rounded_rectangle(box(1, 2, 15, 14), radius=4, outline=color, width=6)
            line([(6, 2), (6, 14)])
            line([(10, 2), (10, 14)])
        elif self.icon == "gear":
            draw_gear(draw, x, y, color)

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        result = super().configure(cnf, **kwargs)
        if state is not None:
            self.enabled = state != "disabled"
            self.configure(cursor="hand2" if self.enabled else "arrow")
            self.redraw()
        return result


UPDATING_BADGE_WIDTH = 77


def draw_updating_badge(canvas, draw, left, center_y):
    right = left + UPDATING_BADGE_WIDTH
    draw.rounded_rectangle((left * 4, (center_y - 11) * 4, right * 4, (center_y + 11) * 4),
                           radius=44, fill='#244b37')
    canvas.create_text((left + right) / 2, center_y, text='Aktualizuje',
                       fill='#8ee2ac', font=('Segoe UI', 8))


class ThreatenedIncidentsButton(RoundedButton):
    """Sidebar warning with a cancellable, smooth pulse on the Tk thread."""
    def __init__(self, parent):
        self.alert = False
        self.healthy = False
        self.selected = False
        self.updating = False
        self.pulse_timer = None
        self.pulse_started = 0
        super().__init__(parent, text='Incydenty zagrożone', command=lambda: None, icon='warning')
        self.button_height = 46
        self.configure(height=self.button_height)
        self.bind('<Destroy>', self._stop_pulse, add='+')

    def _stop_pulse(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self.pulse_timer is not None:
            self.after_cancel(self.pulse_timer)
            self.pulse_timer = None

    def set_alert(self, active, confirmed=True):
        from time import monotonic
        active = bool(active)
        healthy = not active and bool(confirmed)
        if self.alert == active and self.healthy == healthy:
            return
        self._stop_pulse()
        self.alert = active
        self.healthy = healthy
        self.pulse_started = monotonic()
        self._pulse() if active else self.redraw()

    def _pulse(self):
        self.pulse_timer = None
        if self.alert:
            self.redraw()
            self.pulse_timer = self.after(50, self._pulse)

    def set_updating(self, updating):
        if self.updating != updating:
            self.updating = updating
            self.redraw()

    def redraw(self, event=None):
        from math import cos, pi
        from time import monotonic
        width, height = max(self.min_width, self.winfo_width()), self.button_height
        color = '#484f5c' if self.hover else '#373c46'
        if self.healthy:
            color = '#2c493b' if self.hover else '#253a32'
        if self.alert:
            blend = (1 - cos((monotonic() - self.pulse_started) * 2 * pi / 1.8)) / 2
            dark, bright = (67, 42, 50), (227, 57, 76)
            color = tuple(round(a + (b - a) * blend) for a, b in zip(dark, bright))
        self.delete('all')
        label = self.create_text(width / 2, height / 2, text=self.text,
                                 fill='#b0d8bf' if self.healthy else TEXT, font=('Segoe UI', 10, 'bold'))
        bounds = self.bbox(label)
        self.move(label, width / 2 - (bounds[0] + bounds[2]) / 2, 0)
        bounds = self.bbox(label)
        # Use the actual text item bounds: equal gaps, centered as one group.
        icon_positions = (bounds[0] - 26, bounds[2] + 10)
        label_y = badge_y = height / 2
        if self.updating:
            extra_width = 8 + UPDATING_BADGE_WIDTH
            side_space = 34 if self.alert else 8
            if bounds[2] - bounds[0] + extra_width + 2 * side_space <= width:
                self.move(label, -extra_width / 2, 0)
                badge_left = bounds[2] - extra_width / 2 + 8
                icon_positions = (icon_positions[0] - extra_width / 2, icon_positions[1] + extra_width / 2)
            else:
                label_y, badge_y = 12, height - 12
                self.move(label, 0, label_y - height / 2)
                badge_left = (width - UPDATING_BADGE_WIDTH) / 2
        picture = Image.new('RGB', (width * 4, height * 4), self.cget('background'))
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius=32,
                               fill=color, outline=ACCENT if self.selected else '#95505c' if self.alert else
                               '#476b57' if self.healthy else color, width=8 if self.selected else 4)
        if self.alert:
            y = label_y - 8
            for x in icon_positions:
                draw.polygon([(x * 4, (y + 15) * 4), ((x + 8) * 4, y * 4),
                              ((x + 16) * 4, (y + 15) * 4)], fill='#ffe0a3')
                draw.line(((x + 8) * 4, (y + 5) * 4, (x + 8) * 4, (y + 9) * 4), fill='#61232e', width=6)
                draw.ellipse(((x + 7.2) * 4, (y + 11) * 4, (x + 8.8) * 4, (y + 12.6) * 4), fill='#61232e')
        if self.updating:
            draw_updating_badge(self, draw, badge_left, badge_y)
        self.picture = ImageTk.PhotoImage(picture.resize((width, height), Image.Resampling.LANCZOS), master=self)
        background = self.create_image(0, 0, image=self.picture, anchor='nw')
        self.tag_lower(background)


class AnimatedMetricTile(tk.Frame):
    """Display a metric with an animated hover highlight."""

    def __init__(self, parent, accent, **options):
        super().__init__(parent, bg=SURFACE, highlightthickness=1,
                         highlightbackground='#3c424d', takefocus=False, cursor='arrow', **options)
        self.accent = accent
        self.hovered = False
        self.timer = None
        self.current_color = self.color_from = self.color_to = SURFACE
        self.labels = []

    def bind_content(self, *widgets):
        self.labels = widgets
        for widget in (self, *widgets):
            widget.configure(bg=self.current_color, cursor='arrow')
            widget.bind('<Enter>', self.enter)
            widget.bind('<Leave>', self.leave)
        self.bind('<Destroy>', self.close, add='+')

    def enter(self, event):
        self.set_hovered(True)

    def leave(self, event):
        # Moving from the tile to a child label is still inside the same tile.
        if not (self.winfo_rootx() <= event.x_root < self.winfo_rootx() + self.winfo_width()
                and self.winfo_rooty() <= event.y_root < self.winfo_rooty() + self.winfo_height()):
            self.set_hovered(False)

    def set_hovered(self, hovered):
        if self.hovered == hovered:
            return
        self.hovered = hovered
        self.configure(highlightbackground=self.accent if hovered else '#3c424d')
        self.color_from, self.color_to = self.current_color, '#303947' if hovered else SURFACE
        self.started = monotonic()
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        self.animate()

    def animate(self):
        self.timer = None
        fraction = min(1, (monotonic() - self.started) / 0.14)
        start = self.winfo_rgb(self.color_from)
        end = self.winfo_rgb(self.color_to)
        color = '#' + ''.join(f'{round((a + (b - a) * fraction) / 257):02x}' for a, b in zip(start, end))
        self.current_color = color
        for widget in (self, *self.labels):
            widget.configure(bg=color)
        if fraction < 1:
            self.timer = self.after(16, self.animate)

    def close(self, event):
        if event.widget is self and self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None


class DashboardButton(RoundedButton):
    """Sidebar dashboard navigation with a monitoring-style activity badge."""
    def __init__(self, parent):
        self.updating = False
        self.selected = False
        super().__init__(parent, text="DASHBOARD", command=lambda: None)
        from tkinter.font import Font
        self.label_font = Font(self, font=("Segoe UI", 10, "bold"))
        self.label_width = self.label_font.measure(self.text)
        self.button_height = 60
        self.configure(height=self.button_height)

    def redraw(self, event=None):
        self.delete("all")
        width, height = max(self.min_width, self.winfo_width()), self.button_height
        picture = Image.new("RGB", (width * 4, height * 4), self.cget("background"))
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius=32,
                               fill=("#34485F" if self.hover else "#2D3948") if self.selected else
                                    ("#333C48" if self.hover else "#292E36"),
                               outline="#8DB7E8" if self.selected else
                                       ("#606875" if str(self.tk.call('focus')) == str(self) else "#414B58"), width=4)
        draw.rounded_rectangle((12 * 4, 14 * 4, 44 * 4, 46 * 4), radius=28, fill="#2D3D50")
        for left, top, right, bottom in ((21, 23, 27, 29), (30, 23, 36, 26),
                                         (21, 32, 27, 37), (30, 29, 36, 37)):
            draw.rounded_rectangle((left * 4, top * 4, right * 4, bottom * 4),
                                   radius=3, outline="#8DB7E8", width=5)
        draw.line(((width - 20) * 4, 26 * 4, (width - 16) * 4, 30 * 4,
                   (width - 20) * 4, 34 * 4), fill="#A9BDDA", width=6, joint="curve")
        label_x = width / 2
        badge_y = height / 2
        if self.updating:
            gap = 8
            group_width = self.label_width + gap + UPDATING_BADGE_WIDTH
            left = max(48, (width - group_width) / 2)
            label_x = left + self.label_width / 2
            badge_left = left + self.label_width + gap
            draw_updating_badge(self, draw, badge_left, badge_y)
        self.picture = ImageTk.PhotoImage(picture.resize((width, height), Image.Resampling.LANCZOS), master=self)
        background = self.create_image(0, 0, image=self.picture, anchor="nw")
        self.tag_lower(background)
        self.create_text(label_x, badge_y, text=self.text, fill=TEXT, font=self.label_font)


class FilterList(tk.Canvas):
    """Card list exposing the small Treeview interface used by the app."""
    ROW = 48
    ICON_SIZE = 20
    ICON_SLOT = 24

    def __init__(self, parent):
        super().__init__(parent, width=200, height=4 * self.ROW, bg=SURFACE,
                         bd=0, highlightthickness=0, takefocus=True, cursor="hand2")
        self.rows, self.selected, self.pictures = {}, None, []
        self.card_images = {}
        self.labels = {}
        self.image_layout = None
        self.show_selection = True
        self.enabled_rows = {}
        self.notification_channels = ()
        self.notification_rows = {}
        self.notification_images = {}
        self.updating_item = None
        self.on_toggle = None
        self.on_select = None
        self.on_activate = None
        self.on_reorder = None
        self.drag = None
        self.bind("<Configure>", self.redraw)
        self.bind("<Button-1>", self.select_at)
        self.bind("<B1-Motion>", self.drag_motion)
        self.bind("<ButtonRelease-1>", self.drag_end)
        self.bind("<Escape>", self.drag_cancel)
        self.bind("<Up>", lambda _: self.move(-1))
        self.bind("<Down>", lambda _: self.move(1))
        self.bind("<MouseWheel>", lambda event: self.yview_scroll(-int(event.delta / 120), "units"))
        self.configure(yscrollincrement=self.ROW)
        self.control_tooltip = FilterControlTooltip(self)

    def get_children(self):
        return tuple(self.rows)

    def replace_rows(self, rows):
        """Replace a complete snapshot without an intermediate empty scroll region."""
        self.rows = dict(rows)
        self.labels.clear()
        if self.selected not in self.rows:
            self.selected = None
        self.redraw()

    def delete(self, *items):
        for item in items:
            self.rows.pop(item, None)
        if self.selected not in self.rows:
            self.selected = None
        self.redraw()

    def insert(self, parent, position, iid, values):
        self.rows[iid] = values[0]
        self.redraw()

    def selection(self):
        return (self.selected,) if self.selected in self.rows else ()

    def selection_set(self, item):
        self.selected = item
        self.redraw()
        if self.on_select:
            self.on_select()

    def select_at(self, event):
        self.drag_cancel()
        index = int(self.canvasy(event.y) // self.ROW)
        items = self.get_children()
        if 0 <= index < len(items):
            if event.x >= self.winfo_width() - 42 and self.on_toggle is not None:
                self.on_toggle(items[index])
                return "break"
            self.selection_set(items[index])
            if self.on_activate:
                self.on_activate()
            self.focus_set()
            self.drag = {"item": items[index], "y": event.y, "active": False, "slot": index}

    def drag_motion(self, event):
        if not self.drag:
            return
        if not self.drag["active"] and abs(event.y - self.drag["y"]) < 6:
            return
        self.drag["active"] = True
        self.configure(cursor="fleur")
        if len(self.rows) * self.ROW <= self.winfo_height():
            self.yview_moveto(0)
        elif event.y < 16:
            self.yview_scroll(-1, "units")
        elif event.y > self.winfo_height() - 16:
            self.yview_scroll(1, "units")
        self.drag["slot"] = max(0, min(len(self.rows), int((self.canvasy(event.y) + self.ROW / 2) // self.ROW)))
        self.draw_drop_marker()
        return "break"

    def draw_drop_marker(self):
        super().delete("drop_marker")
        if self.drag and self.drag["active"]:
            y = self.drag["slot"] * self.ROW
            y = max(self.canvasy(0) + 3, min(self.canvasy(self.winfo_height()) - 3, y))
            width = self.winfo_width()
            self.create_line(7, y, width - 7, y, fill=ACCENT, width=3, tags="drop_marker")
            for x in (7, width - 7):
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=ACCENT, outline=ACCENT, tags="drop_marker")

    def drag_cancel(self, event=None):
        self.drag = None
        super().delete("drop_marker")
        self.configure(cursor="hand2")

    def drag_end(self, event):
        drag = self.drag
        self.drag_cancel()
        if drag and drag["active"] and self.on_reorder and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.on_reorder(drag["item"], drag["slot"])
        return "break"

    def move(self, direction):
        items = self.get_children()
        if not items:
            return "break"
        index = items.index(self.selected) if self.selected in items else 0
        index = max(0, min(len(items) - 1, index + direction))
        self.selection_set(items[index])
        if self.on_activate:
            self.on_activate()
        top = self.canvasy(0)
        bottom = top + self.winfo_height()
        if index * self.ROW < top:
            self.yview_moveto(index / len(items))
        elif (index + 1) * self.ROW > bottom:
            self.yview_moveto(((index + 1) * self.ROW - self.winfo_height()) / (len(items) * self.ROW))
        return "break"

    def configure(self, cnf=None, **kwargs):
        if "height" in kwargs:
            kwargs["height"] *= self.ROW
        return super().configure(cnf, **kwargs)

    def redraw(self, event=None):
        self.delete_canvas()
        width = max(100, self.winfo_width())
        icon_width = len(self.notification_channels) * self.ICON_SLOT
        layout = (width, icon_width)
        if layout != self.image_layout:
            self.card_images.clear()
            self.labels.clear()
            self.image_layout = layout
        badge_inline = width - icon_width >= 220
        if badge_inline:
            badge = (width - 127 - icon_width, 11, width - 50 - icon_width, 33)
        else:
            badge = (27, 24, 104, 40)
        first_icon = width - 48 - icon_width + self.ICON_SLOT / 2
        from tkinter.font import Font
        font = Font(self, font=("Segoe UI", 9))
        for index, (iid, name) in enumerate(self.rows.items()):
            chosen = self.show_selection and iid == self.selected
            enabled = self.enabled_rows.get(iid, True)
            updating = iid == self.updating_item
            key = (chosen, bool(enabled), updating)
            photo = self.card_images.get(key)
            if photo is None:
                photo = self.card_image(width, chosen, enabled, badge if updating else None)
                self.card_images[key] = photo
            self.pictures.append(photo)
            y = index * self.ROW
            self.create_image(0, y, image=photo, anchor="nw")
            label_key = (name, updating)
            if label_key not in self.labels:
                label = name
                label_limit = width - icon_width - (162 if updating and badge_inline else 72)
                while label and font.measure(label) > label_limit:
                    label = label[:-1]
                if label != name:
                    label = label[:-1] + "…"
                self.labels[label_key] = label
            name_y = 13 if updating and not badge_inline else 22
            self.create_text(27, y + name_y, text=self.labels[label_key], anchor="w", fill=TEXT, font=("Segoe UI", 9))
            if updating:
                self.create_text((badge[0] + badge[2]) / 2, y + (badge[1] + badge[3]) / 2, text="Aktualizuje",
                                 fill="#8ee2ac", font=("Segoe UI", 8))
            states = self.notification_rows.get(iid, ())
            for slot, (channel, active) in enumerate(zip(self.notification_channels, states)):
                self.create_image(first_icon + slot * self.ICON_SLOT, y + name_y,
                                  image=self.notification_icon(channel, active), tags="notification_icon")
        self.configure(scrollregion=(0, 0, width, max(self.winfo_height(), len(self.rows) * self.ROW)))
        self.draw_drop_marker()

    def notification_icon(self, channel, active):
        if channel not in self.notification_images:
            from neto_incident_monitor.runtime_paths import ROOT
            filename = f"icons8-{channel.replace('_', '-')}-48.png"
            with Image.open(ROOT / "icons" / filename) as source:
                color = source.convert("RGBA").resize((self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS)
            gray = ImageOps.colorize(ImageOps.grayscale(color), "#696969", "#b6b6b6")
            gray.putalpha(color.getchannel("A"))
            self.notification_images[channel] = (ImageTk.PhotoImage(gray, master=self),
                                                 ImageTk.PhotoImage(color, master=self))
        return self.notification_images[channel][active]

    def card_image(self, width, chosen, enabled, badge):
        picture = Image.new("RGB", (width * 4, self.ROW * 4), SURFACE)
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 2 * 4, width * 4 - 1, 42 * 4), radius=8 * 4,
                               fill="#432e36" if chosen else "#30353e",
                               outline=ACCENT if chosen else "#444b56", width=4)
        if badge is not None:
            draw.rounded_rectangle(tuple(value * 4 for value in badge), radius=11 * 4, fill="#244b37")
        left = width - 38
        draw.rounded_rectangle((left*4, 13*4, (left+30)*4, 31*4), radius=9*4,
                               fill=ACCENT if enabled else "#555c68")
        center = left + (21 if enabled else 9)
        draw.ellipse(((center-6)*4, 16*4, (center+6)*4, 28*4), fill=TEXT)
        radius = 3 if chosen else 1.5
        draw.ellipse(((14 - radius) * 4, (22 - radius) * 4,
                      (14 + radius) * 4, (22 + radius) * 4),
                     fill=ACCENT if chosen else "#919aa8")
        return ImageTk.PhotoImage(picture.resize((width, self.ROW), Image.Resampling.LANCZOS), master=self)

    def delete_canvas(self):
        super().delete("all")
        self.pictures.clear()


def confirm_dialog(parent, title, message, *, confirm_text="Tak, wyczyść", cancel_text="Anuluj"):
    """Application-styled modal confirmation, with cancellation as the default."""
    from neto_incident_monitor.theme import BG, MUTED, TEXT
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    from neto_incident_monitor.window_style import apply_window_style
    dialog.after_idle(lambda: apply_window_style(dialog))
    dialog.configure(background=BG)
    dialog.transient(parent)
    dialog.resizable(False, False)
    content = tk.Frame(dialog, background=BG, padx=24, pady=24)
    content.pack(fill="both", expand=True)
    tk.Label(content, text=title, background=BG, foreground=TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 14))
    tk.Label(content, text=message, background=BG, foreground=MUTED,
             font=("Segoe UI", 10), wraplength=430, justify="left").pack(anchor="w")
    actions = tk.Frame(content, background=BG)
    actions.pack(fill="x", pady=(22, 0))
    result = False

    def finish(value=False):
        nonlocal result
        result = value
        dialog.destroy()

    RoundedButton(actions, text=confirm_text, command=lambda: finish(True),
                  primary=True, background=BG).pack(side="right")
    cancel = RoundedButton(actions, text=cancel_text, command=finish, background=BG)
    cancel.pack(side="right", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", finish)
    dialog.bind("<Escape>", lambda _: finish())
    dialog.update_idletasks()
    if parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - dialog.winfo_reqheight()) // 2
    else:
        x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 2
    dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
    dialog.grab_set()
    cancel.focus_set()
    parent.wait_window(dialog)
    return result


class TabTooltip:
    def __init__(self, notebook, index, text):
        self.widget, self.index, self.text = notebook, index, text
        self.root = notebook.winfo_toplevel()
        self.timer = self.tip = None
        notebook.bind("<Motion>", self.motion, add="+")
        notebook.bind("<Leave>", self.hide, add="+")
        notebook.bind("<ButtonPress>", self.hide, add="+")
        notebook.bind("<Destroy>", self.hide, add="+")

    def motion(self, event):
        try:
            hovered = self.widget.index(f"@{event.x},{event.y}") == self.index
        except tk.TclError:
            hovered = False
        if not hovered:
            self.hide()
        elif self.timer is None and self.tip is None:
            self.position = (event.x_root + 12, event.y_root + 24)
            self.timer = self.root.after(450, self.show)

    def show(self):
        self.timer = None
        from neto_incident_monitor.theme import BG
        self.tip = tk.Toplevel(self.widget, background="#484e59")
        self.tip.overrideredirect(True)
        tk.Label(self.tip, text=self.text, background=BG, foreground=TEXT,
                 font=("Segoe UI", 9), padx=10, pady=7, wraplength=320,
                 justify="left").pack(padx=1, pady=1)
        self.tip.update_idletasks()
        x, y = self.position
        x = max(0, min(x, self.tip.winfo_screenwidth() - self.tip.winfo_reqwidth() - 8))
        y = max(0, min(y, self.tip.winfo_screenheight() - self.tip.winfo_reqheight() - 8))
        self.tip.geometry(f"+{x}+{y}")

    def hide(self, event=None):
        if event is not None and event.type == tk.EventType.Destroy and event.widget is not self.widget:
            return
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.tip is not None:
            tip, self.tip = self.tip, None
            tip.destroy()


class StatusTooltip(TabTooltip):
    """Full activity remains readable when the header pill is shortened."""
    def __init__(self, widget):
        super().__init__(widget, None, '')

    def motion(self, event):
        if self.widget.status_text == self.widget.display_text:
            self.hide()
        elif self.timer is None and self.tip is None:
            self.position = (event.x_root + 12, event.y_root + 24)
            self.timer = self.root.after(450, self.show)


class FilterControlTooltip(TabTooltip):
    """Tooltips for monitoring switches inside filter cards."""
    def __init__(self, widget):
        super().__init__(widget, None, "")
        self.target = None
        widget.bind("<MouseWheel>", self.hide, add="+")

    def motion(self, event):
        widget = self.widget
        index = int(widget.canvasy(event.y) // widget.ROW)
        items = widget.get_children()
        target = None
        if not widget.drag and 0 <= index < len(items):
            item = items[index]
            width = widget.winfo_width()
            if event.x >= width - 42:
                enabled = widget.enabled_rows.get(item, True)
                target = (item, "toggle", enabled)
                text = "Wyłącz monitoring filtra" if enabled else "Włącz monitoring filtra"
        if target is None:
            self.hide()
            self.target = None
        elif target != self.target or (self.timer is None and self.tip is None):
            self.hide()
            self.target, self.text = target, text
            self.position = (event.x_root + 12, event.y_root + 24)
            self.timer = self.root.after(450, self.show)


class ColumnWarning(tk.Canvas):
    """Small warning badge with a delayed, application-themed tooltip."""
    def __init__(self, parent, label):
        from neto_incident_monitor.theme import BG
        super().__init__(parent, width=20, height=22, bg=BG, bd=0,
                         highlightthickness=0, cursor="question_arrow")
        self.label, self.timer, self.tip = label, None, None
        self.create_oval(2, 3, 18, 19, fill=ACCENT, outline=ACCENT)
        self.create_text(10, 11, text="!", fill=TEXT, font=("Segoe UI", 9, "bold"))
        self.bind("<Enter>", self.schedule)
        self.bind("<Leave>", self.hide)
        self.bind("<Button-1>", self.hide)
        self.bind("<Destroy>", self.hide)

    def schedule(self, event=None):
        self.hide()
        self.timer = self.after(350, self.show)

    def show(self):
        from neto_incident_monitor.theme import BG
        self.timer = None
        if not self.winfo_exists():
            return
        self.tip = tk.Toplevel(self)
        self.tip.overrideredirect(True)
        self.tip.configure(background="#484e59")
        tk.Label(self.tip, text=f'Nie wykryto kolumny „{self.label}” w ServiceNow.',
                 background=BG, foreground=TEXT, font=("Segoe UI", 9),
                 padx=10, pady=7, wraplength=300, justify="left").pack(padx=1, pady=1)
        self.tip.update_idletasks()
        x = min(self.winfo_rootx() + 12, self.winfo_screenwidth() - self.tip.winfo_reqwidth() - 8)
        y = min(self.winfo_rooty() + 24, self.winfo_screenheight() - self.tip.winfo_reqheight() - 8)
        self.tip.geometry(f"+{max(0,x)}+{max(0,y)}")

    def hide(self, event=None):
        if event is not None and event.type == tk.EventType.Destroy and event.widget is not self:
            return
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.tip is not None:
            tip, self.tip = self.tip, None
            tip.destroy()
