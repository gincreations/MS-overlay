"""The overlay's main window, built from smooth custom widgets (see ui_gfx.py).

MainView takes the numbers through show(...) and only touches what changed, so while nothing changes
it draws nothing. It knows nothing about screens, logs or the game: the App gives it callbacks."""
from ui_palette import color as ui_color, register
import ui_palette
import tkinter as tk
from tkinter import font as tkfont, ttk

from PIL import Image, ImageDraw

from ui_gfx import (GOLD_BOTTOM, GOLD_TOP, INK, TEXT, TEXT_DIM, TEXT_FAINT, UP, DOWN, Gfx, rgb)

W = 360                                   # the window's width, in logical pixels
SIDE = 16
INNER = W - 2 * SIDE

# state -> (dot colour, glows)
STATES = {"waiting": ("#6c7280", False), "ready": ("#ffcf4a", False), "tracking": ("#5fe39a", True),
          "paused": ("#ffb27a", False), "alert": ("#ff7a5c", True)}


MIN_TEXT_PX = 8                          # the smallest text, at any Size, so it stays readable


def cancel_widget_callbacks(widget):
    """Cancel timers owned by widgets about to be destroyed, not the app's worker timers.

    Tk deletes widget commands on destroy, but keeps their scheduled after events.
    A stale event can otherwise target a deleted (or reused) callback after a rebuild.
    """
    commands = {}
    def collect(w):
        commands.update({name: w for name in (w._tclCommands or ())})
        for child in w.winfo_children():
            collect(child)
    collect(widget)
    for timer in widget.tk.call("after", "info"):
        script, _ = widget.tk.call("after", "info", timer)
        parts = widget.tk.splitlist(script)
        if parts and parts[0] in commands:
            commands[parts[0]].after_cancel(timer)


class Window(tk.Toplevel):
    """A popup whose delayed callbacks cannot survive closing or rebuilding it."""

    def destroy(self):
        cancel_widget_callbacks(self)
        super().destroy()


class DialogScroll(tk.Frame):
    """Screen-bounded popup body with local scrolling and keyboard focus reveal."""
    def __init__(self, window, bg=None):
        bg=INK if bg is None else bg
        super().__init__(window,bg=bg)
        self.window=window
        self._fit_job=None
        self._fitting=False
        self.canvas=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0,takefocus=0,
                              yscrollincrement=1,xscrollincrement=1)
        self.body=tk.Frame(self.canvas,bg=bg)
        self.item=self.canvas.create_window(0,0,window=self.body,anchor="nw")
        style=ttk.Style(window)
        style.configure("Dialog.Horizontal.TScrollbar",troughcolor=bg,background=ui_color('#2c313e'),
                        bordercolor=bg,lightcolor=ui_color('#2c313e'),darkcolor=ui_color('#2c313e'))
        self.vertical=ttk.Scrollbar(self,orient="vertical",command=self.canvas.yview,style="Dark.Vertical.TScrollbar")
        self.horizontal=ttk.Scrollbar(self,orient="horizontal",command=self.canvas.xview,style="Dialog.Horizontal.TScrollbar")
        self.canvas.configure(yscrollcommand=self.vertical.set,xscrollcommand=self.horizontal.set)
        self.canvas.grid(row=0,column=0,sticky="nsew")
        self.rowconfigure(0,weight=1);self.columnconfigure(0,weight=1)
        self.pack(fill="both",expand=True)
        self.body.bind("<Configure>",self.schedule_fit)
        # Native window managers may reposition a transient after its first
        # layout/map. Recheck that final geometry, not just the body request.
        window.bind("<Configure>",self._window_changed,add="+")
        window.bind("<MouseWheel>",self._wheel,add="+")
        window.bind("<Button-4>",self._wheel,add="+")
        window.bind("<Button-5>",self._wheel,add="+")
        window.bind("<FocusIn>",self._focus,add="+")
        self.schedule_fit()

    def _window_changed(self, event):
        if event.widget == self.window:
            self.schedule_fit()

    def screen_bounds(self):
        # Respect the popup's Windows monitor/work area (including negative origins).
        import sys
        if sys.platform=="win32":
            import ctypes
            from ctypes import wintypes
            class MonitorInfo(ctypes.Structure):
                _fields_=[("cbSize",wintypes.DWORD),("monitor",wintypes.RECT),
                          ("work",wintypes.RECT),("flags",wintypes.DWORD)]
            user32=ctypes.windll.user32
            nearest=user32.MonitorFromPoint
            nearest.argtypes=[wintypes.POINT,wintypes.DWORD];nearest.restype=wintypes.HANDLE
            getinfo=user32.GetMonitorInfoW
            getinfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)];getinfo.restype=wintypes.BOOL
            monitor=nearest(wintypes.POINT(self.window.winfo_x()+20,self.window.winfo_y()+20),2)
            info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
            if monitor and getinfo(monitor,ctypes.byref(info)):
                r=info.work
                return r.left,r.top,r.right-r.left,r.bottom-r.top
        return (0,0,self.winfo_screenwidth(),self.winfo_screenheight())

    def schedule_fit(self, event=None):
        if self._fit_job is None and not self._fitting:
            self._fit_job=self.after_idle(self.fit)

    def fit(self):
        if self._fitting:return
        self._fit_job=None
        self._fitting=True
        try:self._fit_now()
        finally:self._fitting=False

    def _fit_now(self):
        self.update_idletasks()
        x0,y0,sw,sh=self.screen_bounds()
        maxw,maxh=max(160,sw-48),max(160,sh-100)
        bw,bh=self.body.winfo_reqwidth(),self.body.winfo_reqheight()
        vw,vh=min(bw,maxw),min(bh,maxh)
        # Account for one scrollbar forcing the other at a screen edge.
        for _ in range(3):
            needv=bh>vh;needh=bw>vw
            vw=min(bw,maxw-(self.vertical.winfo_reqwidth() if needv else 0))
            vh=min(bh,maxh-(self.horizontal.winfo_reqheight() if needh else 0))
        if needv:self.vertical.grid(row=0,column=1,sticky="ns")
        else:self.vertical.grid_remove()
        if needh:self.horizontal.grid(row=1,column=0,sticky="ew")
        else:self.horizontal.grid_remove()
        self.canvas.configure(width=vw,height=vh,scrollregion=(0,0,bw,bh))
        self.canvas.itemconfigure(self.item,width=bw,height=bh)
        ww=vw+(self.vertical.winfo_reqwidth() if needv else 0)
        wh=vh+(self.horizontal.winfo_reqheight() if needh else 0)
        self.window.update_idletasks()
        x=max(x0+12,min(self.window.winfo_x(),x0+sw-ww-24))
        y=max(y0+30,min(self.window.winfo_y(),y0+sh-wh-60))
        geometry=f"{ww}x{wh}+{x}+{y}"  # +negative is an absolute monitor coordinate, not a right-edge offset
        if self.window.geometry()!=geometry:self.window.geometry(geometry)

    def _wheel(self, event):
        if isinstance(event.widget,ttk.Combobox):return
        if getattr(event,"num",None) in (4,5):step=-3 if event.num==4 else 3
        else:
            delta=getattr(event,"delta",0)
            if not delta:return
            step=-int(delta/120) if abs(delta)>=120 else (-1 if delta>0 else 1)
        view=self.canvas.xview_scroll if event.state & 1 else self.canvas.yview_scroll
        # Pixel-aligned focus reveal; keep wheel movement at its prior 24px step.
        view(step*24,"units")
        return "break"

    def _focus(self,event):
        widget=event.widget
        if widget in (self.window,self,self.canvas):return
        # The focus event belongs to this toplevel, never another app/dialog.
        try:
            if widget.winfo_toplevel()!=self.window:return
            for axis in ('x','y'):
                start=getattr(widget,'winfo_root'+axis)()-getattr(self.body,'winfo_root'+axis)()
                size=widget.winfo_width() if axis=='x' else widget.winfo_height()
                total=self.body.winfo_width() if axis=='x' else self.body.winfo_height()
                extent=self.canvas.winfo_width() if axis=='x' else self.canvas.winfo_height()
                view=self.canvas.xview if axis=='x' else self.canvas.yview
                move=self.canvas.xview_moveto if axis=='x' else self.canvas.yview_moveto
                offset=view()[0]*total
                if start<offset:move(max(0,start-8)/max(1,total))
                elif start+size>offset+extent:move(max(0,start+size-extent+8)/max(1,total))
        except tk.TclError:pass


class Theme:
    """One size of everything: the graphics engine and the text fonts, for this screen and Size setting."""

    def __init__(self, root, scale, fonts_dir, own_fonts, fallback, colors=None):
        self.root, self.gfx = root, Gfx(scale, fonts_dir)
        self.colors = ui_palette.normalize_overrides(colors)
        self.fam = ({"regular": "Manrope", "semibold": "Manrope SemiBold", "bold": "Manrope Bold",
                     "extra": "Manrope ExtraBold"} if own_fonts else
                    {k: fallback(f, "normal")[0] for k, f in (("regular", "Segoe UI"), ("semibold", "Segoe UI Semibold"),
                                                              ("bold", "Segoe UI Semibold"), ("extra", "Segoe UI Semibold"))})
        self._tk = {}

    def value_color(self, key, default):
        return self.colors.get(key, default)

    def px(self, n):
        return self.gfx.px(n)

    def font(self, weight, size):
        key = (weight, size)
        if key not in self._tk:
            self._tk[key] = tkfont.Font(root=self.root, family=self.fam[weight], size=-max(MIN_TEXT_PX, self.px(size)))
        return self._tk[key]


class Tip:
    """A small label that appears after a short hover, so icon-only buttons say what they do."""

    def __init__(self, widget, theme, text):
        self.w, self.theme, self.text, self.win, self.job = widget, theme, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress-1>", self._hide, add="+")

    def _enter(self, _):
        self._hide()
        self.job = self.w.after(450, self._show)

    def _show(self):
        self.win = tk.Toplevel(self.w)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        tk.Label(self.win, text=self.text, bg=ui_color('#242833'), fg=TEXT, font=self.theme.font("semibold", 11), padx=10, pady=5,
                 highlightthickness=1, highlightbackground=ui_color('#343a48')).pack()
        self.win.geometry(f"+{self.w.winfo_rootx()}+{self.w.winfo_rooty() + self.w.winfo_height() + 6}")

    def _hide(self, _=None):
        if self.job:
            self.w.after_cancel(self.job)
            self.job = None
        if self.win:
            self.win.destroy()
            self.win = None


# kind -> (top, bottom) for normal / hover / pressed, and the text colour
LOOKS = {
    "primary": {"normal": ("#ffd75e", "#ffb81f"), "hover": ("#ffe48c", "#ffc43b"), "press": ("#f2b620", "#e5a100"),
                "fg": "#1b1403", "fg_hover": "#1b1403", "border": 0.28},
    "secondary": {"normal": ("#272c38", "#1f232d"), "hover": ("#303644", "#262b36"), "press": ("#1c2029", "#181b23"),
                  "fg": TEXT, "fg_hover": TEXT, "border": 0.12},
    "ghost": {"normal": None, "hover": ("#212530", "#1a1d26"), "press": ("#171a21", "#14161c"),
              "fg": TEXT_DIM, "fg_hover": TEXT, "border": 0.0},
}


class Button(tk.Canvas):
    """A rounded button: text and/or an icon. Hover and press change it; Tab reaches it, and Space or
    Enter press it. Primary buttons carry a soft gold glow."""

    def __init__(self, parent, theme, text="", icon=None, command=None, kind="secondary", width=None, height=40,
                 radius=12, weight="semibold", size=13, tip=None, bg=None, align="center"):
        bg = INK if bg is None else bg
        self.t, self.text, self.icon, self.command, self.kind, self.align = theme, text, icon, command, kind, align
        self.weight, self.size, self.radius, self.bw, self.bh = weight, size, radius, width, height
        self._hover = self._down = self._focus = False
        self._enabled = True
        self._glow = 8 if kind == "primary" else 0
        g = theme.gfx
        if width is None:
            width = 28 + (22 if icon and text else 0) + (g.text_width(text, weight, size) / g.s if text else 0)   # (text_width is in screen pixels)
            if icon and not text:
                width = height
        self.bw = width
        super().__init__(parent, width=g.px(width) + 2 * g.px(self._glow), height=g.px(height) + 2 * g.px(self._glow),
                         bg=bg, highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self._bg = self.create_image(0, 0, anchor="nw")
        self._ico = self.create_image(0, 0, anchor="nw") if icon else None
        self._txt = self.create_text(0, 0, text=text, font=theme.font(weight, size), anchor="center") if text else None
        self._photo = self._iphoto = None
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: (self.focus_set(), self._set(down=True)))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda e: self._set(focus=True))
        self.bind("<FocusOut>", lambda e: self._set(focus=False))
        self.bind("<space>", lambda e: self._fire())
        self.bind("<Return>", lambda e: self._fire())
        if tip:
            Tip(self, theme, tip)
        self._render()

    def _render(self):
        g, look = self.t.gfx, LOOKS[self.kind]
        pad, w, h = g.px(self._glow), g.px(self.bw), g.px(self.bh)
        state = "press" if self._down else "hover" if self._hover else "normal"
        colors = look[state] if self._enabled else (ui_color('#1d2029'), ui_color('#1a1c24'))
        # ghost buttons only show a body when hovered; a primary one shows a glow
        if colors is None:
            body = None
        else:
            body = g.panel(w, h, self.radius, colors[0], colors[1], look["border"])
        photo_parts = []
        if self.kind == "primary" and self._enabled:
            photo_parts.append(g.glow(w, h, self.radius, ui_color('#ffb71f'), 7 if not self._hover else 9,
                                      0.30 if not self._hover else 0.45, pad))
        img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        for p in photo_parts:
            img.alpha_composite(p)
        if body is not None:
            img.alpha_composite(body, (pad, pad))
        if self._focus:
            ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(ring).rounded_rectangle((pad - 1, pad - 1, pad + w, pad + h), self.radius * g.s + 1,
                                                   outline=rgb(ui_color('#ffd25a')) + (255,), width=max(1, g.px(1.6)))
            img.alpha_composite(ring)
        self._photo = g.photo(img)
        self.itemconfigure(self._bg, image=self._photo)
        fg = (look["fg_hover"] if self._hover else look["fg"]) if self._enabled else TEXT_FAINT
        cx, cy = pad + w / 2, pad + h / 2
        isz = g.px(18)
        total = (isz if self.icon else 0) + (g.px(8) if self.icon and self.text else 0)
        tw = self.t.font(self.weight, self.size).measure(self.text) if self.text else 0
        left = cx - (total + tw) / 2 if self.align == "center" else pad + g.px(14)
        if self.icon:
            self._iphoto = g.photo(g.icon(self.icon, isz, fg))
            self.itemconfigure(self._ico, image=self._iphoto)
            self.coords(self._ico, left, cy - isz / 2)
            left += isz + (g.px(8) if self.text else 0)
        if self.text:
            self.itemconfigure(self._txt, text=self.text, fill=fg, anchor="w")
            self.coords(self._txt, left, cy + 1)

    def _set(self, hover=None, down=None, focus=None):
        if hover is not None:
            self._hover = hover
        if down is not None:
            self._down = down
        if focus is not None:
            self._focus = focus
        self._render()

    def _release(self, e):
        was = self._down
        self._set(down=False)
        if was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self._fire()

    def _fire(self):
        if self._enabled and self.command:
            self.command()

    def resize(self, width):
        self.bw = width
        g = self.t.gfx
        self.configure(width=g.px(width) + 2 * g.px(self._glow))
        self._render()

    def set(self, text=None, icon=None, kind=None, enabled=None):
        if text is not None:
            self.text = text
            if self._txt is None:
                self._txt = self.create_text(0, 0, text=text, font=self.t.font(self.weight, self.size), anchor="w")
        if icon is not None:
            self.icon = icon
        if kind is not None:
            self.kind = kind
        if enabled is not None:
            self._enabled = enabled
        self._render()


class Pill(tk.Canvas):
    """The status pill: a coloured dot and a short word for where things stand."""

    H = 30

    def __init__(self, parent, theme, bg=None):
        bg = INK if bg is None else bg
        self.t = theme
        g = theme.gfx
        super().__init__(parent, width=g.px(190), height=g.px(self.H), bg=bg, highlightthickness=0, bd=0)
        self._img = self.create_image(0, 0, anchor="nw")
        self._dot = self.create_image(0, 0, anchor="nw")
        self._txt = self.create_text(0, 0, anchor="w", fill=TEXT, font=theme.font("semibold", 12))
        self._last, self._photos = None, []
        self.set("waiting", "Looking for the game")

    def set(self, state, text):
        if (state, text) == self._last:
            return
        self._last = (state, text)
        g = self.t.gfx
        color, glows = STATES[state]
        tw = self.t.font("semibold", 12).measure(text)
        w, h = tw + g.px(40), g.px(self.H)
        self.configure(width=w)
        body = g.panel(w, h, self.H / 2, ui_color('#1c1f28'), ui_color('#161920'), 0.10)
        d = g.px(8)
        dot = Image.new("RGBA", (d * 3, d * 3), (0, 0, 0, 0))
        if glows:
            dot.alpha_composite(g.glow(d, d, d / g.s / 2, color, 3, 0.55, d))
        ImageDraw.Draw(dot).ellipse((d, d, 2 * d - 1, 2 * d - 1), fill=rgb(color) + (255,))
        self._photos = [g.photo(body), g.photo(dot)]
        self.itemconfigure(self._img, image=self._photos[0])
        self.itemconfigure(self._dot, image=self._photos[1])
        self.coords(self._dot, g.px(14) - d, h / 2 - d * 1.5)
        self.itemconfigure(self._txt, text=text)
        self.coords(self._txt, g.px(14) + d + g.px(8), h / 2 + 1)


class Hero(tk.Canvas):
    """The big card: EXP per hour, how it's trending, and how far you are into the level."""

    def __init__(self, parent, theme, bg=None):
        bg = INK if bg is None else bg
        self.t, self.compact = theme, False
        g = theme.gfx
        super().__init__(parent, width=g.px(INNER), height=g.px(self._height()), bg=bg, highlightthickness=0, bd=0)
        self._bgi = self.create_image(0, 0, anchor="nw")
        self._cap = self.create_text(0, 0, anchor="nw", text="EXP PER HOUR", fill=TEXT_DIM, font=theme.font("semibold", 10))
        self._chip = self.create_image(0, 0, anchor="ne")
        self._chip_t = self.create_text(0, 0, anchor="center", text="", font=theme.font("bold", 11))
        self._digits, self._gphotos = [], {}
        self._spark = self.create_image(0, 0, anchor="nw")
        self._barimg = self.create_image(0, 0, anchor="nw")
        self._eta = self.create_text(0, 0, anchor="nw", text="", fill=theme.value_color('eta', ui_color('#e9c15a')), font=theme.font("bold", 13))
        self._pct = self.create_text(0, 0, anchor="ne", text="", fill=TEXT_DIM, font=theme.font("semibold", 12))
        # compact mode has no tiles, so mesos/hr sits under the number (value, then its unit)
        self._mval = self.create_text(0, 0, anchor="nw", text="", fill=theme.value_color("meso", TEXT), font=theme.font("bold", 12), state="hidden")
        self._munit = self.create_text(0, 0, anchor="nw", text="mesos / hr", fill=TEXT_DIM, font=theme.font("semibold", 10), state="hidden")
        self._photos, self._chip_text = {}, None
        self._m = dict(rate=None, delta=None, spark=(), pct=None, eta="", chip=None, mesos="")
        self._layout()
        self.redraw(everything=True)

    def _show_number(self, text, live):
        """EXP/hr as a row of ready-made digits: changing the number only moves pictures that already exist."""
        g = self.t.gfx
        style = ("extra", 52, GOLD_TOP, GOLD_BOTTOM, ui_color('#ffb71f')) if live else ("extra", 52, ui_color('#4a505d'), ui_color('#393e49'), None)
        custom = self.t.colors.get("exp")
        if live and custom:
            style = ("extra", 52, custom, custom, custom)
        x = g.px(18)
        for i, ch in enumerate(text):
            img, adv, asc, pad = g.glyph(ch, *style)
            key = (ch, live, style)
            if key not in self._gphotos:
                self._gphotos[key] = g.photo(img)
            if i >= len(self._digits):
                self._digits.append(self.create_image(0, 0, anchor="nw"))
            item = self._digits[i]
            self.itemconfigure(item, image=self._gphotos[key], state="normal")
            self.coords(item, x - pad, g.px(30) - pad // 2)
            x += adv
        for item in self._digits[len(text):]:
            self.itemconfigure(item, state="hidden")

    def _height(self):
        return 158 if self.compact else 196

    def _layout(self):
        g = self.t.gfx
        self.configure(height=g.px(self._height()))
        self.coords(self._cap, g.px(18), g.px(16))
        self.coords(self._chip, g.px(INNER - 14), g.px(11))
        self.coords(self._chip_t, g.px(INNER - 14) - g.px(34), g.px(24))
        self._bar_y = 119 if self.compact else 148
        self.coords(self._mval, g.px(19), g.px(96))
        self.coords(self._barimg, g.px(18), g.px(self._bar_y) - g.px(6))
        self.coords(self._eta, g.px(18), g.px(self._bar_y + 16))
        self.coords(self._pct, g.px(INNER - 18), g.px(self._bar_y + 16))
        self.coords(self._spark, g.px(8), g.px(96))

    def set_compact(self, on):
        if on != self.compact:
            self.compact = on
            self._layout()
            self.redraw(everything=True)

    def show(self, **kw):
        changed = {k for k, v in kw.items() if self._m.get(k) != v}
        if changed:
            self._m.update(kw)
            self.redraw(changed)

    def redraw(self, changed=(), everything=False):
        g, m = self.t.gfx, self._m
        every = everything
        if every:
            self._photos["bg"] = g.photo(g.hero_panel(g.px(INNER), g.px(self._height()), 18, self.t.colors.get("exp")))
            self.itemconfigure(self._bgi, image=self._photos["bg"])
        if every or "rate" in changed:
            self._show_number(m["rate"] if m["rate"] else "—", bool(m["rate"]))
        if (every or "spark" in changed) and not self.compact:
            self._photos["spark"] = g.photo(g.spark(m["spark"], g.px(INNER - 16), g.px(40), self.t.colors.get("exp")))
            self.itemconfigure(self._spark, image=self._photos["spark"], state="normal")
        elif every and self.compact:
            self.itemconfigure(self._spark, state="hidden")
        if every or "mesos" in changed:
            show = self.compact and bool(m["mesos"])
            self.itemconfigure(self._mval, text=m["mesos"], state="normal" if show else "hidden")
            self.itemconfigure(self._munit, state="normal" if show else "hidden")
            if show:
                bbox = self.bbox(self._mval)
                self.coords(self._munit, bbox[2] + g.px(6), g.px(96) + g.px(2))
        if every or "pct" in changed:
            frac = round((m["pct"] or 0) / 100 * 500) / 500          # (in steps you can't see, so the picture is reused)
            self._photos["bar"] = g.photo(g.bar(g.px(INNER - 36), g.px(8), frac, pad=g.px(6) // 1, fill_color=self.t.colors.get("progress")))
            self.itemconfigure(self._barimg, image=self._photos["bar"])
            self.itemconfigure(self._pct, text=f"{m['pct']:.1f}%" if m["pct"] is not None else "")
        if every or "eta" in changed:
            self.itemconfigure(self._eta, text=m["eta"])
        if every or "delta" in changed or "rate" in changed:
            d = m["delta"]
            if d is None or not m["rate"]:
                self.itemconfigure(self._chip, state="hidden")
                self.itemconfigure(self._chip_t, state="hidden")
                self._chip_text = None
            else:
                up = d >= 0.005
                down = d <= -0.005
                text = (f"▲ {d * 100:.0f}%" if up else f"▼ {abs(d) * 100:.0f}%" if down else "● steady") + "  vs 5 min"
                if text == self._chip_text and not every:
                    return
                col = UP if up else DOWN if down else TEXT_DIM
                w = self.t.font("bold", 11).measure(text) + g.px(22)
                body = g.panel(w, g.px(26), 13, ui_color('#1b2a24') if up else ui_color('#2b1c1b') if down else ui_color('#222631'),
                               ui_color('#15221c') if up else ui_color('#231615') if down else ui_color('#1c1f28'), 0.10)
                self._photos["chip"] = g.photo(body)
                self.itemconfigure(self._chip, image=self._photos["chip"], state="normal")
                self.itemconfigure(self._chip_t, text=text, fill=col, state="normal")
                self.coords(self._chip, g.px(INNER - 14), g.px(11))
                self.coords(self._chip_t, g.px(INNER - 14) - w / 2, g.px(24))


class Tile(tk.Canvas):
    """A small panel with one number."""

    def __init__(self, parent, theme, label, width, bg=None):
        bg = INK if bg is None else bg
        self.t, self.label_text, self.bw = theme, label, width
        g = theme.gfx
        super().__init__(parent, width=g.px(width), height=g.px(62), bg=bg, highlightthickness=0, bd=0)
        self._photo = g.photo(g.panel(g.px(width), g.px(62), 13, ui_color('#191c25'), ui_color('#13151b'), 0.09))
        self.create_image(0, 0, anchor="nw", image=self._photo)
        self.create_text(g.px(13), g.px(12), anchor="nw", text=label.upper(), fill=TEXT_DIM, font=theme.font("semibold", 9))
        self._v = self.create_text(g.px(13), g.px(29), anchor="nw", text="—", fill=theme.value_color("meso", TEXT) if label == "Mesos / hr" else TEXT, font=theme.font("bold", 17))

    def set(self, value):
        if self.itemcget(self._v, "text") != value:
            room = self.t.px(self.bw) - 2 * self.t.px(13)
            for size in (17, 15, 13, 11):                      # a long number gets a smaller size, not cut off
                font = self.t.font("bold", size)
                if font.measure(value) <= room:
                    break
            self.itemconfigure(self._v, text=value, font=font)


class Details(tk.Canvas):
    """The rest of the numbers, one line each, for when you want them."""

    ROW = 28

    def __init__(self, parent, theme, labels, bg=None):
        bg = INK if bg is None else bg
        self.t, self.labels = theme, labels
        g = theme.gfx
        h = 14 + self.ROW * len(labels)
        super().__init__(parent, width=g.px(INNER), height=g.px(h), bg=bg, highlightthickness=0, bd=0)
        self._photo = g.photo(g.panel(g.px(INNER), g.px(h), 14, ui_color('#191c25'), ui_color('#13151b'), 0.09))
        self.create_image(0, 0, anchor="nw", image=self._photo)
        self._vals = {}
        for i, name in enumerate(labels):
            y = g.px(7 + i * self.ROW + self.ROW / 2)
            self.create_text(g.px(16), y, anchor="w", text=name, fill=TEXT_DIM, font=theme.font("regular", 12))
            self._vals[name] = self.create_text(g.px(INNER - 16), y, anchor="e", text="—", fill=theme.value_color("meso", TEXT) if name.startswith("Mesos") else TEXT, font=theme.font("bold", 12.5))
            if i:
                self.create_line(g.px(14), g.px(7 + i * self.ROW), g.px(INNER - 14), g.px(7 + i * self.ROW), fill=ui_color('#232733'))

    def set(self, name, value):
        if self.itemcget(self._vals[name], "text") != value:
            self.itemconfigure(self._vals[name], text=value)


class Toggle(tk.Canvas):
    """A switch with a label, tied to a BooleanVar-like get/set."""

    def __init__(self, parent, theme, text, value=True, command=None, bg=None, alt=None):
        bg = INK if bg is None else bg
        self.t, self.on, self.command, self.text = theme, value, command, text
        g = theme.gfx
        tw = max(theme.font("semibold", 12).measure(x) for x in (text, alt or text))
        super().__init__(parent, width=g.px(46) + tw + g.px(6), height=g.px(30), bg=bg, highlightthickness=0, bd=0,
                         takefocus=1, cursor="hand2")
        self._img = self.create_image(0, g.px(3), anchor="nw")
        self._lbl = self.create_text(g.px(46), g.px(15), anchor="w", text=text, fill=TEXT_DIM, font=theme.font("semibold", 12))
        self._photo = None
        for ev in ("<Button-1>", "<space>"):
            self.bind(ev, lambda e: self.toggle())
        self.bind("<FocusIn>", lambda e: self.itemconfigure(self._lbl, fill=TEXT))
        self.bind("<FocusOut>", lambda e: self._paint())
        self._paint()

    def _paint(self):
        g = self.t.gfx
        w, h = g.px(36), g.px(22)
        img = g.panel(w, h, 11, *((ui_color('#ffd25a'), ui_color('#ffb71f')) if self.on else (ui_color('#2a2f3b'), ui_color('#232731'))), 0.10 if self.on else 0.06)
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        base.alpha_composite(img)
        r = h - g.px(6)
        x = w - g.px(3) - r if self.on else g.px(3)
        knob = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
        ImageDraw.Draw(knob).ellipse((x * 3, g.px(3) * 3, (x + r) * 3 - 1, (g.px(3) + r) * 3 - 1),
                                     fill=rgb(ui_color('#1b1403') if self.on else ui_color('#e8e6e0')) + (255,))
        base.alpha_composite(knob.resize((w, h), Image.LANCZOS))
        self._photo = g.photo(base)
        self.itemconfigure(self._img, image=self._photo)
        self.itemconfigure(self._lbl, fill=TEXT if self.on else TEXT_DIM)

    def toggle(self):
        self.set(not self.on)
        if self.command:
            self.command(self.on)

    def set(self, value, label=None):
        if label is not None:
            self.itemconfigure(self._lbl, text=label)
        if value != self.on:
            self.on = value
        self._paint()


class Message(tk.Label):
    """The line of guidance at the bottom."""

    def __init__(self, parent, theme, bg=None):
        bg = INK if bg is None else bg
        super().__init__(parent, text="", bg=bg, fg=TEXT_FAINT, font=theme.font("regular", 11), justify="left", anchor="w")

    def set(self, text, wrap):
        if self.cget("text") != text or str(self.cget("wraplength")) != str(wrap):
            self.configure(text=text, wraplength=wrap)


class PotionReadout(tk.Frame):
    """Presentation only: format the existing potion strings, never calculate values."""
    def __init__(self, parent, theme, bg):
        super().__init__(parent, bg=bg)
        self.theme, self._text, self.cards = theme, "", []
        self.columnconfigure(0, weight=1)

    def cget(self, key):
        # Preserve the existing readout inspection interface.
        return self._text if key == "text" else super().cget(key)

    def set_text(self, text):
        if text == self._text:
            return
        self._text = text
        groups = []
        for line in text.splitlines():
            if ": " in line and " left · " in line:
                name, _, values = line.partition(": ")
                stock, _, usage = values.partition(" · ")
                groups.append(dict(name=name, stock=stock, usage=usage, cost=[], status=[]))
            elif groups:
                groups[-1]["cost" if line.startswith("Est. cost:") else "status"].append(line)
            elif line:
                groups.append(dict(name="Potions", stock="", usage="", cost=[], status=[line]))
        th = self.theme; px = th.px
        panel, border = ui_color("#14161c"), ui_color("#343a48")
        while len(self.cards) > len(groups):
            self.cards.pop()["frame"].destroy()
        for index, data in enumerate(groups):
            if index >= len(self.cards):
                frame = tk.Frame(self, bg=panel, highlightthickness=1, highlightbackground=border)
                frame.grid(row=index, column=0, sticky="we", pady=(0, px(6)))
                frame.columnconfigure(1, weight=1)
                accent = tk.Frame(frame, width=px(4), bg=TEXT)
                accent.grid(row=0, column=0, rowspan=4, sticky="ns", padx=(0, px(9)))
                head = tk.Frame(frame, bg=panel)
                head.grid(row=0, column=1, sticky="we", padx=(0, px(9)), pady=(px(7), 0))
                head.columnconfigure(0, weight=1)
                name = tk.Label(head, bg=panel, fg=TEXT, font=th.font("bold", 13),
                                anchor="w", justify="left", wraplength=px(190))
                name.grid(row=0, column=0, sticky="w")
                stock = tk.Label(head, bg=panel, fg=TEXT, font=th.font("bold", 16), anchor="e")
                stock.grid(row=0, column=1, sticky="e", padx=(px(6), 0))
                usage = tk.Label(frame, bg=panel, fg=TEXT, font=th.font("regular", 12),
                                 anchor="w", justify="left", wraplength=px(INNER-28))
                usage.grid(row=1, column=1, sticky="we", padx=(0, px(9)), pady=(px(2), 0))
                cost = tk.Label(frame, bg=panel, fg=ui_color("#ffd966"), font=th.font("semibold", 12),
                                anchor="w", justify="left", wraplength=px(INNER-28))
                cost.grid(row=2, column=1, sticky="we", padx=(0, px(9)), pady=(px(2), 0))
                status = tk.Label(frame, bg=panel, fg=ui_color("#ffb27a"), font=th.font("semibold", 12),
                                  anchor="w", justify="left", wraplength=px(INNER-28))
                status.grid(row=3, column=1, sticky="we", padx=(0, px(9)), pady=(px(3), px(7)))
                self.cards.append(dict(frame=frame, accent=accent, name=name, stock=stock,
                                       usage=usage, cost=cost, status=status))
            widgets = self.cards[index]
            defaults = ui_palette.color_defaults()
            key = "potion1" if index == 0 else "potion2"
            color = th.value_color(key, defaults[key])
            widgets["accent"].configure(bg=color)
            for key in ("name", "stock", "usage"):
                widgets[key].configure(text=data[key])
            widgets["name"].configure(fg=color, wraplength=max(px(40), px(INNER-34) - th.font("bold", 16).measure(data["stock"])))
            widgets["stock"].configure(fg=color)
            for key in ("cost", "status"):
                value = "\n".join(data[key])
                widgets[key].configure(text=value)
                (widgets[key].grid if value else widgets[key].grid_remove)()
            # Keep bottom breathing room even without a status line.
            widgets["usage"].grid_configure(pady=(px(2), px(7) if not data["cost"] and not data["status"] else 0))
            if data["cost"]:
                widgets["cost"].grid_configure(pady=(px(2), px(7) if not data["status"] else 0))


class MainView(tk.Frame):
    """Everything in the main window, top to bottom."""

    def __init__(self, parent, theme, cb, details=False, bg=None):
        bg = INK if bg is None else bg
        super().__init__(parent, bg=bg)
        self.t, self.cb, g = theme, cb, theme.gfx
        self.columnconfigure(0, weight=1, minsize=g.px(W))
        pad = lambda a=0, b=0: (g.px(a), g.px(b))
        self.compact = False

        head = tk.Frame(self, bg=bg)
        head.grid(row=0, column=0, sticky="we", padx=g.px(SIDE), pady=pad(14, 10))
        head.columnconfigure(0, weight=1)
        self.pill = Pill(head, theme, bg)
        self.pill.grid(row=0, column=0, sticky="w")
        icons = tk.Frame(head, bg=bg)
        icons.grid(row=0, column=1, sticky="e")
        self.potions_btn = Button(icons, theme, text="Potions", kind="ghost", width=64, height=34, radius=10, command=cb.get("potions"), tip="Choose potions or food to track", bg=bg)
        self.settings_btn = Button(icons, theme, icon="gear", kind="ghost", width=34, height=34, radius=10, command=cb["settings"], tip="Settings", bg=bg)
        self.compact_btn = Button(icons, theme, icon="shrink", kind="ghost", width=34, height=34, radius=10, command=cb["compact"], tip="Compact mode", bg=bg)
        self.log_btn = Button(icons, theme, icon="list", kind="ghost", width=34, height=34, radius=10, command=cb["log"], tip="Open the log", bg=bg)
        for b in (self.potions_btn, self.log_btn, self.compact_btn, self.settings_btn):
            b.pack(side="left", padx=(2, 0))

        self.hero = Hero(self, theme, bg)
        self.hero.grid(row=1, column=0, padx=g.px(SIDE), pady=pad(0, 10))
        self.hero.bind("<Double-Button-1>", lambda e: cb["compact"]())

        self.tiles_row = tk.Frame(self, bg=bg)
        self.tiles_row.grid(row=2, column=0, padx=g.px(SIDE), pady=pad(0, 6), sticky="we")
        tw = (INNER - 16) // 3
        self.tiles = {}
        for i, name in enumerate(("Last 5 min", "Mesos / hr", "Elapsed")):
            t = Tile(self.tiles_row, theme, name, tw, bg)
            t.grid(row=0, column=i, padx=(0 if i == 0 else g.px(8), 0))
            self.tiles[name] = t

        self.more_btn = Button(self, theme, text="Details", icon="down", kind="ghost", width=INNER, height=30, radius=10,
                               size=12, weight="semibold", command=self._toggle_details, bg=bg)
        self.more_btn.grid(row=3, column=0, padx=g.px(SIDE), pady=pad(0, 4))
        self.details_open = details
        self.details = Details(self, theme, ("% / hr", "% last 5 min", "% last 15 min", "% last 30 min",
                                             "% last hour", "Gained", "Current", "Mesos", "Mesos / 5 min"), bg)
        self.details.grid(row=4, column=0, padx=g.px(SIDE), pady=pad(0, 8))
        if not details:
            self.details.grid_remove()
        self.more_btn.set(icon="up" if details else "down")

        self.potions_label = PotionReadout(self, theme, bg)
        self.potions_label.grid(row=5, column=0, sticky="we", padx=g.px(SIDE), pady=pad(0, 6))
        self.potions_label.grid_remove()

        controls = tk.Frame(self, bg=bg)
        controls.grid(row=6, column=0, padx=g.px(SIDE - 8), pady=pad(0, 2), sticky="we")
        controls.columnconfigure(0, weight=1)
        self.start_btn = Button(controls, theme, text="Start", icon="play", kind="primary", width=INNER - 8 - 52 - 52, height=46,
                                radius=14, size=14, weight="bold", command=cb["start"], bg=bg)
        self.start_btn.grid(row=0, column=0, sticky="w")
        self.reset_btn = Button(controls, theme, icon="reset", kind="secondary", width=46, height=46, radius=14, command=cb["reset"], tip="Reset", bg=bg)
        self.reset_btn.grid(row=0, column=1, padx=(g.px(-2), 0))
        self.menu_btn = Button(controls, theme, icon="more", kind="secondary", width=46, height=46, radius=14, command=self._menu, tip="More", bg=bg)
        self.menu_btn.grid(row=0, column=2, padx=(g.px(4), 0))

        foot = tk.Frame(self, bg=bg)
        foot.grid(row=7, column=0, padx=g.px(SIDE), pady=pad(6, 0), sticky="we")
        foot.columnconfigure(0, weight=1)
        self.logging = Toggle(foot, theme, "Log this run", True, cb["logging"], bg, alt="Not logging")
        self.logging.grid(row=0, column=0, sticky="w")
        self.share_btn = Button(foot, theme, text="Share", icon="share", kind="ghost", height=30, radius=10, size=12,
                                command=cb.get("share", lambda: None), tip="A local picture of this session to share", bg=bg)
        self.share_btn.grid(row=0, column=1, sticky="e")
        self.message = Message(self, theme, bg)
        self.message.grid(row=8, column=0, padx=g.px(SIDE + 2), pady=pad(2, 14), sticky="we")
        self.foot_widgets = [self.tiles_row, self.more_btn, self.details, self.reset_btn, self.menu_btn, foot]

    # ---- showing things
    def show(self, **m):
        """rate, delta, spark, pct, eta (hero); tiles, details (dicts); state, state_text, message."""
        hero = {k: m[k] for k in ("rate", "delta", "spark", "pct", "eta", "mesos") if k in m}
        if "spark" in hero:
            hero["spark"] = tuple(hero["spark"])
        if hero:
            self.hero.show(**hero)
        for name, value in (m.get("tiles") or {}).items():
            self.tiles[name].set(value)
        for name, value in (m.get("details") or {}).items():
            self.details.set(name, value)
        if "state" in m:
            self.pill.set(m["state"], m.get("state_text", ""))
        if "message" in m:
            self.message.set(m["message"], self.t.px(INNER - 6))

    def show_potions(self, text):
        self.potions_label.set_text(text)
        (self.potions_label.grid if text else self.potions_label.grid_remove)()

    def _toggle_details(self):
        self.details_open = not self.details_open
        (self.details.grid if self.details_open else self.details.grid_remove)()
        self.more_btn.set(icon="up" if self.details_open else "down")
        if self.cb.get("details"):
            self.cb["details"](self.details_open)

    def set_compact(self, on):
        self.compact = on
        self.hero.set_compact(on)
        for w in self.foot_widgets:
            if on:
                w.grid_remove()
            elif w is not self.details or self.details_open:
                w.grid()
        self.start_btn.resize(INNER - 8 if on else INNER - 8 - 52 - 52)
        self.compact_btn.set(icon="grow" if on else "shrink")
        (self.log_btn.pack_forget() if on else self.log_btn.pack(side="left", padx=(2, 0), before=self.compact_btn))

    def _menu(self):
        self.cb["menu"](self.menu_btn)


class PopupMenu(Window):
    """The 'more' menu: a short list of actions in a rounded panel, closed by choosing one, clicking away or Esc."""

    def __init__(self, theme, anchor, items):
        super().__init__(anchor)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=INK)
        g = theme.gfx
        w, row = 210, 38
        h = 12 + row * len(items)
        body = tk.Canvas(self, width=g.px(w), height=g.px(h), bg=INK, highlightthickness=0, bd=0)
        body.pack()
        self._photo = g.photo(g.panel(g.px(w), g.px(h), 14, ui_color('#20242e'), ui_color('#181b23'), 0.16))
        body.create_image(0, 0, anchor="nw", image=self._photo)
        for i, (text, icon, command) in enumerate(items):
            b = Button(body, theme, text=text, icon=icon, kind="ghost", width=w - 12, height=row - 4, radius=10, size=12,
                       align="left", command=lambda c=command: (self.destroy(), c()), bg=ui_color('#1c1f28'))
            body.create_window(g.px(6), g.px(6 + i * row), anchor="nw", window=b)
        self.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() - self.winfo_reqwidth()
        y = anchor.winfo_rooty() - self.winfo_reqheight() - 6
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", lambda e: self.after(120, self._maybe_close))

    def _maybe_close(self):
        try:
            if self.winfo_exists() and not str(self.focus_get()).startswith(str(self)):
                self.destroy()
        except Exception:
            pass


class Slider(tk.Canvas):
    """A slider tied to an IntVar: drag it, click the track, or use the arrow keys."""

    def __init__(self, parent, theme, variable, lo, hi, width=330, bg=None):
        bg = INK if bg is None else bg
        self.t, self.var, self.lo, self.hi, self.bw = theme, variable, lo, hi, width
        g = theme.gfx
        super().__init__(parent, width=g.px(width), height=g.px(30), bg=bg, highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self._img = self.create_image(0, 0, anchor="nw")
        self._photo, self._focus = None, False
        self.bind("<Button-1>", lambda e: (self.focus_set(), self._drag(e)))
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Left>", lambda e: self._nudge(-1))
        self.bind("<Right>", lambda e: self._nudge(1))
        self.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.bind("<FocusOut>", lambda e: self._set_focus(False))
        variable.trace_add("write", lambda *_: self._paint())
        self._paint()

    def _set_focus(self, on):
        self._focus = on
        self._paint()

    def _value(self):
        try:
            return min(self.hi, max(self.lo, int(float(self.var.get()))))
        except (ValueError, tk.TclError):
            return self.lo

    def _paint(self):
        g = self.t.gfx
        frac = (self._value() - self.lo) / (self.hi - self.lo)
        self._photo = g.photo(g.slider(g.px(self.bw), g.px(30), frac, self._focus))
        self.itemconfigure(self._img, image=self._photo)

    def _drag(self, e):
        r = self.t.gfx.px(10) * 1.7
        frac = (e.x - r) / max(1, self.winfo_width() - 2 * r)
        self.var.set(self.lo + round(min(1, max(0, frac)) * (self.hi - self.lo)))

    def _nudge(self, by):
        self.var.set(min(self.hi, max(self.lo, self._value() + by)))

class ColorDialog(Window):
    """A local color editor: preview changes, then save or cancel without touching tracking."""

    def __init__(self, parent, theme, mode, on_save, on_close):
        super().__init__(parent)
        self.t, self.mode, self.on_save, self.on_close = theme, mode, on_save, on_close
        self._closed, self._loading = False, False
        self.title("Customize colors — " + mode.title())
        self.configure(bg=INK)
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        px = theme.px
        self.scroll = DialogScroll(self, INK)
        body = tk.Frame(self.scroll.body, bg=INK)
        body.pack(padx=px(18), pady=px(14))
        tk.Label(body, text="Your overlay colors", bg=INK, fg=TEXT, font=theme.font("bold", 15)).pack(anchor="w")
        tk.Label(body, text=f"Saved for {mode} mode. Blank = theme default.", bg=INK, fg=TEXT_DIM,
                 font=theme.font("regular", 11)).pack(anchor="w", pady=(px(3), px(10)))
        presets = tk.Frame(body, bg=INK)
        presets.pack(fill="x", pady=(0, px(10)))
        for name in ui_palette.COLOR_PRESETS[mode]:
            Button(presets, theme, text=name, width=100, height=30, size=11,
                   command=lambda name=name: self.use_preset(name)).pack(side="left", padx=(0, px(6)))
        self.variables, self.swatches = {}, {}
        form = tk.Frame(body, bg=INK)
        form.pack(fill="x")
        for i, (key, label) in enumerate(ui_palette.COLOR_FIELDS):
            tk.Label(form, text=label, bg=INK, fg=TEXT, font=theme.font("semibold", 12)).grid(
                row=i, column=0, sticky="w", padx=(0, px(12)), pady=px(5))
            var = self.variables[key] = tk.StringVar(value=theme.colors.get(key, ""))
            entry = tk.Entry(form, textvariable=var, width=10, bg=ui_color('#232732'), fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=theme.font("regular", 12))
            entry.grid(row=i, column=1, sticky="e", padx=(0, px(8)))
            swatch = self.swatches[key] = tk.Button(form, text="", width=3, relief="flat", cursor="hand2",
                                                   command=lambda key=key: self.pick(key))
            swatch.grid(row=i, column=2, padx=(0, px(6)))
            Button(form, theme, text="Pick", width=48, height=28, size=10,
                   command=lambda key=key: self.pick(key)).grid(row=i, column=3)
            var.trace_add("write", self._update_preview)
        self.feedback = tk.Label(body, text="", bg=INK, fg=TEXT_DIM, font=theme.font("regular", 10),
                                 wraplength=px(INNER), justify="left", anchor="w")
        self.feedback.pack(fill="x", pady=(px(5), px(8)))
        self.preview = Hero(body, theme)
        self.preview.pack()
        self.preview.show(rate="123,456", eta="Level in 42 min", pct=62.5,
                          spark=(20, 27, 25, 35, 40, 38, 48), mesos="12,345")
        self.meso_preview = tk.Label(body, text="12,345 mesos / hr", bg=INK, fg=TEXT,
                                     font=theme.font("bold", 12))
        self.meso_preview.pack(anchor="w", pady=(px(5), px(10)))
        self.potion_previews = []
        for index in range(2):
            label = tk.Label(body, text=f"Potion card {index+1}  ·  120 left", bg=INK,
                             fg=TEXT, font=theme.font("bold", 12))
            label.pack(anchor="w", pady=(0, px(4)))
            self.potion_previews.append(label)
        footer = tk.Frame(body, bg=INK)
        footer.pack(fill="x")
        Button(footer, theme, text="Theme defaults", width=116, height=32, size=10,
               command=lambda: self.use_preset(None)).pack(side="left")
        self.save_button = Button(footer, theme, text="Save colors", kind="primary", width=100, height=32,
                                  size=10, command=self.save)
        self.save_button.pack(side="right")
        Button(footer, theme, text="Cancel", width=70, height=32, size=10, command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.save())
        self._update_preview()
        self.update_idletasks()
        x = max(0, min(parent.winfo_rootx() + 30, self.winfo_screenwidth() - self.winfo_reqwidth()))
        y = max(0, min(parent.winfo_rooty() + 30, self.winfo_screenheight() - self.winfo_reqheight() - 50))
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _values(self):
        values = {k: v.get().strip() for k, v in self.variables.items()}
        invalid = [label for key, label in ui_palette.COLOR_FIELDS
                   if values[key] and not ui_palette.normalize_overrides({key: values[key]})]
        return ui_palette.normalize_overrides(values), invalid

    def _update_preview(self, *_):
        if self._loading:
            return
        colors, invalid = self._values()
        self.save_button.set(enabled=not invalid)
        if invalid:
            self.feedback.configure(text="Use #RRGGBB or leave blank: " + ", ".join(invalid), fg=ui_color('#ff8a7a'))
            return
        defaults = ui_palette.color_defaults()
        for key, button in self.swatches.items():
            value = colors.get(key, defaults[key])
            button.configure(bg=value, activebackground=value)
        self.t.colors = colors
        self.preview.itemconfigure(self.preview._eta, fill=colors.get("eta", defaults["eta"]))
        self.preview.itemconfigure(self.preview._mval, fill=colors.get("meso", defaults["meso"]))
        self.preview.redraw(everything=True)
        self.meso_preview.configure(fg=colors.get("meso", defaults["meso"]))
        for index, label in enumerate(self.potion_previews):
            key = f"potion{index+1}"
            label.configure(fg=colors.get(key, defaults[key]))
        background = ui_color('#13151b')
        low = [label for key, label in ui_palette.COLOR_FIELDS
               if key in colors and ui_palette.contrast_ratio(colors[key], background) < 3]
        self.feedback.configure(text=("Low contrast: " + ", ".join(low) + ". You can still save." if low else
                                      "Preview only — press Save colors to apply."), fg=TEXT_DIM)

    def _choose_native(self, initial, title):
        # Tk's native chooser is already bundled; no extra modules, websites or dependencies.
        return str(self.tk.call("tk_chooseColor", "-initialcolor", initial, "-parent", str(self), "-title", title))

    def pick(self, key):
        colors, _ = self._values()
        initial = colors.get(key, ui_palette.color_defaults()[key])
        selected = self._choose_native(initial, dict(ui_palette.COLOR_FIELDS)[key])
        if selected:
            self.variables[key].set(selected)

    def use_preset(self, name):
        values = ui_palette.COLOR_PRESETS[self.mode].get(name, {})
        self._loading = True
        try:
            for key, variable in self.variables.items():
                variable.set(values.get(key, ""))
        finally:
            self._loading = False
        self._update_preview()

    def save(self):
        colors, invalid = self._values()
        if invalid:
            self._update_preview()
            return
        self.on_save(colors)
        self.destroy()

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        try:
            super().destroy()
        finally:
            self.on_close()


register(globals())
