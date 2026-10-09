"""Small keyboard-accessible controls matching the application palette."""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from neto_incident_monitor.theme import SURFACE, TEXT, ACCENT


class StatusPill(tk.Canvas):
    """Compact status badge with smooth rounded edges."""
    def __init__(self, parent):
        from neto_incident_monitor.theme import BG
        super().__init__(parent, height=28, bg=BG, bd=0, highlightthickness=0)

    def set_status(self, text):
        from tkinter.font import Font
        colors = {
            "Monitoring aktywny": ("#243d33", "#85d6aa"),
            "Oczekiwanie na logowanie": ("#433923", "#efc778"),
            "Sprawdzanie list": ("#27364a", "#9ac4f4"),
            "Uruchamianie przeglądarki": ("#27364a", "#9ac4f4"),
            "Błąd odczytu": ("#472c33", "#ff929e"),
            "Błąd uruchomienia": ("#472c33", "#ff929e"),
        }
        background, foreground = colors.get(text, ("#343942", "#c8cdd6"))
        font = Font(self, font=("Segoe UI", 9, "bold"))
        width = font.measure(text) + 24
        self.configure(width=width)
        picture = Image.new("RGB", (width * 4, 28 * 4), self.cget("bg"))
        ImageDraw.Draw(picture).rounded_rectangle((0, 0, width * 4 - 1, 28 * 4 - 1),
                                                  radius=14 * 4, fill=background)
        self.picture = ImageTk.PhotoImage(picture.resize((width, 28), Image.Resampling.LANCZOS), master=self)
        self.delete("all")
        self.create_image(0, 0, image=self.picture, anchor="nw")
        self.create_text(width / 2, 14, text=text, fill=foreground, font=("Segoe UI", 9, "bold"))


class PriorityDots:
    """Small cell overlays, following scrolling and column rearrangements."""
    COLORS = {"1": "#ef4858", "2": "#f59b45", "3": "#e6c44b", "4": "#69bf91", "5": "#919aa8"}

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
                background = "#382c33" if "unread" in tags else "#2b2f37" if "alternate" in tags else SURFACE
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
                    draw.ellipse((3 * scale, 3 * scale, 11 * scale, 11 * scale), fill=color)
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
        if self.winfo_exists() and self.focus_get() is not self:
            self.destroy()

    def show(self, x, y):
        self.update_idletasks()
        x = max(0, min(x, self.winfo_screenwidth() - self.winfo_reqwidth()))
        y = max(0, min(y, self.winfo_screenheight() - self.winfo_reqheight()))
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_force()


class Toggle(tk.Canvas):
    def __init__(self, parent, variable):
        super().__init__(parent, width=48, height=28, bg=SURFACE, bd=0,
                         highlightthickness=1, highlightbackground=SURFACE,
                         highlightcolor=ACCENT, takefocus=True, cursor="hand2")
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
        key = (bool(on), self.enabled)
        if key not in self.images:
            # Draw at 8x resolution, then downsample to smooth curved edges.
            scale = 8
            image = Image.new("RGB", (48 * scale, 28 * scale), SURFACE)
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
        return result

    def destroy(self):
        self.variable.trace_remove("write", self.trace)
        super().destroy()

class RoundedButton(tk.Canvas):
    """A button with the same command/state interface as the sidebar buttons."""
    def __init__(self, parent, text, command, primary=False, background=SURFACE, icon=None):
        from tkinter.font import Font
        self.text_width = Font(parent, font=("Segoe UI", 9)).measure(text)
        self.icon = icon
        width = max(90, self.text_width + 24 + (22 if icon else 0))
        super().__init__(parent, width=width, height=36, bg=background, bd=0,
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
        width, height = max(90, self.winfo_width()), 36
        color = (ACCENT if self.primary else "#373c46")
        if self.hover and self.enabled:
            color = "#f04b59" if self.primary else "#484f5c"
        if not self.enabled:
            color = "#30343c"
        picture = Image.new("RGB", (width * 4, height * 4), self.cget("background"))
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius=8 * 4,
                               fill=color, outline=ACCENT if self.focus_get() == self else color, width=4)
        foreground = TEXT if self.enabled else "#747b88"
        if self.icon:
            self.draw_icon(draw, (width - self.text_width - 22) / 2, 10, foreground)
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
        elif self.icon in ("check", "checks"):
            if self.icon == "checks":
                line([(0, 8), (3, 11), (8, 5)])
                line([(8, 8), (11, 11), (16, 5)])
            else:
                line([(2, 8), (6, 12), (13, 4)])
        elif self.icon == "trash":
            line([(2, 4), (14, 4)])
            line([(6, 4), (6, 2), (10, 2), (10, 4)])
            line([(4, 5), (5, 14), (11, 14), (12, 5)])
            line([(7, 7), (7, 11)])
            line([(9, 7), (9, 11)])
        elif self.icon == "columns":
            draw.rounded_rectangle(box(1, 2, 15, 14), radius=4, outline=color, width=6)
            line([(6, 2), (6, 14)])
            line([(10, 2), (10, 14)])
        elif self.icon == "gear":
            import math
            outline = []
            for i in range(32):
                angle = i * math.pi / 16
                radius = 7.5 if i % 4 in (1, 2) else 5.5
                outline.append((8 + math.cos(angle)*radius, 8 + math.sin(angle)*radius))
            line(outline + [outline[0]])
            draw.ellipse(box(5, 5, 11, 11), outline=color, width=6)

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        result = super().configure(cnf, **kwargs)
        if state is not None:
            self.enabled = state != "disabled"
            self.configure(cursor="hand2" if self.enabled else "arrow")
            self.redraw()
        return result


class FilterList(tk.Canvas):
    """Card list exposing the small Treeview interface used by the app."""
    ROW = 48

    def __init__(self, parent):
        super().__init__(parent, width=200, height=4 * self.ROW, bg=SURFACE,
                         bd=0, highlightthickness=0, takefocus=True, cursor="hand2")
        self.rows, self.selected, self.pictures = {}, None, []
        self.enabled_rows = {}
        self.on_toggle = None
        self.on_select = None
        self.on_settings = None
        self.bind("<Configure>", self.redraw)
        self.bind("<Button-1>", self.select_at)
        self.bind("<Up>", lambda _: self.move(-1))
        self.bind("<Down>", lambda _: self.move(1))
        self.bind("<MouseWheel>", lambda event: self.yview_scroll(-int(event.delta / 120), "units"))
        self.configure(yscrollincrement=self.ROW)

    def get_children(self):
        return tuple(self.rows)

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
        index = int(self.canvasy(event.y) // self.ROW)
        items = self.get_children()
        if 0 <= index < len(items):
            if self.winfo_width() - 70 <= event.x < self.winfo_width() - 42 and self.on_settings:
                self.on_settings(items[index])
                return "break"
            if event.x >= self.winfo_width() - 42 and self.on_toggle is not None:
                self.on_toggle(items[index])
                return "break"
            self.selection_set(items[index])
            self.focus_set()

    def move(self, direction):
        items = self.get_children()
        if not items:
            return "break"
        index = items.index(self.selected) if self.selected in items else 0
        index = max(0, min(len(items) - 1, index + direction))
        self.selection_set(items[index])
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
        for index, (iid, name) in enumerate(self.rows.items()):
            chosen = iid == self.selected
            picture = Image.new("RGB", (width * 4, self.ROW * 4), SURFACE)
            draw = ImageDraw.Draw(picture)
            draw.rounded_rectangle((0, 2 * 4, width * 4 - 1, 42 * 4), radius=8 * 4,
                                   fill="#432e36" if chosen else "#30353e",
                                   outline=ACCENT if chosen else "#444b56", width=4)
            enabled = self.enabled_rows.get(iid, True)
            left = width - 38
            draw.rounded_rectangle((left*4, 13*4, (left+30)*4, 31*4), radius=9*4,
                                   fill=ACCENT if enabled else "#555c68")
            center = left + (21 if enabled else 9)
            draw.ellipse(((center-6)*4, 16*4, (center+6)*4, 28*4), fill=TEXT)
            photo = ImageTk.PhotoImage(picture.resize((width, self.ROW), Image.Resampling.LANCZOS), master=self)
            self.pictures.append(photo)
            y = index * self.ROW
            self.create_image(0, y, image=photo, anchor="nw")
            self.create_text(14, y + 22, text="●" if chosen else "•", fill=ACCENT if chosen else "#919aa8", font=("Segoe UI", 10))
            # Ellipsis keeps each card a single row without changing its saved name.
            from tkinter.font import Font
            font = Font(self, font=("Segoe UI", 9))
            label = name
            while label and font.measure(label) > width - 100:
                label = label[:-1]
            if label != name:
                label = label[:-1] + "…"
            self.create_text(27, y + 22, text=label, anchor="w", fill=TEXT, font=("Segoe UI", 9))
            self.create_text(width - 56, y + 22, text="⚙", fill=TEXT if chosen else "#a8b0bd", font=("Segoe UI Symbol", 13))
        self.configure(scrollregion=(0, 0, width, len(self.rows) * self.ROW))

    def delete_canvas(self):
        super().delete("all")
        self.pictures.clear()


def confirm_dialog(parent, title, message):
    """Application-styled modal confirmation, with cancellation as the default."""
    from tkinter import ttk
    from neto_incident_monitor.theme import BG, MUTED
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    from neto_incident_monitor.window_style import apply_window_style
    dialog.after_idle(lambda: apply_window_style(dialog))
    dialog.configure(background=BG)
    dialog.transient(parent)
    dialog.resizable(False, False)
    content = ttk.Frame(dialog, padding=24)
    content.pack(fill="both", expand=True)
    ttk.Label(content, text=title, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 14))
    ttk.Label(content, text=message, wraplength=430, justify="left", foreground=MUTED).pack(anchor="w")
    actions = ttk.Frame(content)
    actions.pack(fill="x", pady=(22, 0))
    result = False

    def finish(value=False):
        nonlocal result
        result = value
        dialog.destroy()

    RoundedButton(actions, text="Tak, wyczyść", command=lambda: finish(True),
                  primary=True, background=BG).pack(side="right")
    cancel = RoundedButton(actions, text="Anuluj", command=finish, background=BG)
    cancel.pack(side="right", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", finish)
    dialog.bind("<Escape>", lambda _: finish())
    dialog.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - dialog.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - dialog.winfo_reqheight()) // 2
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
