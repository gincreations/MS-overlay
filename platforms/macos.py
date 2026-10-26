"""macOS: recognizes native MapleStory windows and narrowly identified Wine game windows.
Generic VM desktops, browsers and game-stream windows are deliberately not captured. A window
is known by its window number, and positions are in points: the units mss screenshots and
tkinter use too. Window titles (and screenshots of other programs) need the Screen Recording
permission."""
import ctypes
import fcntl
import os
import platform
import subprocess
from collections import namedtuple
from pathlib import Path

from .base import Hotkeys, Platform

_cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
_appkit = ctypes.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")
_objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
_cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")


class _CGRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]


def _api(fn, restype, *argtypes):
    fn.restype, fn.argtypes = restype, list(argtypes)
    return fn


_vp = ctypes.c_void_p
_CopyWindowInfo = _api(_cg.CGWindowListCopyWindowInfo, _vp, ctypes.c_uint32, ctypes.c_uint32)
_RectFromDict = _api(_cg.CGRectMakeWithDictionaryRepresentation, ctypes.c_bool, _vp, ctypes.POINTER(_CGRect))
_PreflightCapture = _api(_cg.CGPreflightScreenCaptureAccess, ctypes.c_bool)
_RequestCapture = _api(_cg.CGRequestScreenCaptureAccess, ctypes.c_bool)
_ArrayCount = _api(_cf.CFArrayGetCount, ctypes.c_long, _vp)
_ArrayItem = _api(_cf.CFArrayGetValueAtIndex, _vp, _vp, ctypes.c_long)
_DictValue = _api(_cf.CFDictionaryGetValue, _vp, _vp, _vp)
_NumberValue = _api(_cf.CFNumberGetValue, ctypes.c_bool, _vp, ctypes.c_long, _vp)
_StringValue = _api(_cf.CFStringGetCString, ctypes.c_bool, _vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32)
_BoolValue = _api(_cf.CFBooleanGetValue, ctypes.c_bool, _vp)
_CFRelease = _api(_cf.CFRelease, None, _vp)
_KEYS = {k: _vp.in_dll(_cg, "kCGWindow" + k).value
         for k in ("Number", "OwnerPID", "OwnerName", "Name", "Layer", "Bounds", "IsOnscreen")}
_ON_SCREEN, _ONLY_THIS, _NO_DESKTOP = 1, 8, 16          # kCGWindowListOption...
_TOPMOST = 19                                           # the window layer of Always on top (tkinter's -topmost)

MacWindow = namedtuple("MacWindow", "number pid owner title layer rect onscreen")

# Programs whose windows can have "MapleStory" in the title without being the game.
_NOT_GAME = {"safari", "google chrome", "chromium", "firefox", "microsoft edge", "brave browser", "opera",
             "arc", "vivaldi", "orion", "discord", "finder", "preview", "code", "visual studio code",
             "terminal", "iterm2", "ghostty", "warp", "zed", "cursor", "obs", "slack", "telegram", "messages",
             "notes", "quicktime player"}

# The overlay's Windows fonts -> macOS's own (family, weight or None to keep it).
_FONTS = {"Segoe UI": ("Helvetica Neue", None), "Segoe UI Semibold": ("Helvetica Neue", "bold"),
          "Consolas": ("Menlo", None)}


_GetClass = _api(_objc.objc_getClass, _vp, ctypes.c_char_p)
_GetSelector = _api(_objc.sel_registerName, _vp, ctypes.c_char_p)
_SendObject = ctypes.CFUNCTYPE(_vp, _vp, _vp)(("objc_msgSend", _objc))
_SendPID = ctypes.CFUNCTYPE(ctypes.c_int, _vp, _vp)(("objc_msgSend", _objc))
_SendVoid = ctypes.CFUNCTYPE(None, _vp, _vp)(("objc_msgSend", _objc))


def frontmost_pid():
    """NSWorkspace foreground identity; callable from the reader thread, no input hooks."""
    pool = _SendObject(_GetClass(b"NSAutoreleasePool"), _GetSelector(b"new"))
    try:
        workspace = _SendObject(_GetClass(b"NSWorkspace"), _GetSelector(b"sharedWorkspace"))
        app = _SendObject(workspace, _GetSelector(b"frontmostApplication")) if workspace else None
        return _SendPID(app, _GetSelector(b"processIdentifier")) if app else None
    finally:
        if pool:
            _SendVoid(pool, _GetSelector(b"drain"))


def _cf_number(d, key):
    v, n = _DictValue(d, _KEYS[key]), ctypes.c_int64()
    return n.value if v and _NumberValue(v, 4, ctypes.byref(n)) else 0            # kCFNumberSInt64Type


def _cf_text(d, key):
    v, buf = _DictValue(d, _KEYS[key]), ctypes.create_string_buffer(1024)
    ok = v and _StringValue(v, buf, len(buf), 0x08000100)                          # kCFStringEncodingUTF8
    return buf.value.decode("utf-8", "replace") if ok else ""


def window_list(option=_ON_SCREEN | _NO_DESKTOP, number=0):
    """MacWindows, front to back."""
    arr = _CopyWindowInfo(option, number)
    if not arr:
        return []
    try:
        found = []
        for i in range(_ArrayCount(arr)):
            d, r = _ArrayItem(arr, i), _CGRect()
            bounds, onscreen = _DictValue(d, _KEYS["Bounds"]), _DictValue(d, _KEYS["IsOnscreen"])
            found.append(MacWindow(
                _cf_number(d, "Number"), _cf_number(d, "OwnerPID"), _cf_text(d, "OwnerName"),
                _cf_text(d, "Name"), _cf_number(d, "Layer"),
                (r.x, r.y, r.w, r.h) if bounds and _RectFromDict(bounds, ctypes.byref(r)) else None,
                bool(onscreen and _BoolValue(onscreen))))
        return found
    finally:
        _CFRelease(arr)


def is_game(w, own_pid):
    """Could this window be MapleStory's?"""
    # Normal windows up to always-on-top ones: not the Dock, menu bar and the like above them.
    if not 0 <= w.layer <= _TOPMOST or w.pid == own_pid or not w.rect or w.owner.lower() in _NOT_GAME:
        return False
    owner = w.owner.casefold().replace(" ", "")
    title = w.title.casefold().replace(" ", "")
    native = owner in {"maplestory", "maplestory.exe", "maplestoryworlds", "maplestoryworldsplayer"}
    wine = owner in {"wine", "wine64", "wine-preloader", "wine64-preloader", "crossover"}
    return native or (wine and "maplestory" in title)


class MacHotkeys(Hotkeys):
    """No hotkeys on macOS yet: keys pressed in the game can't be seen without the
    Accessibility permission. The buttons work as usual."""

    supported = False

    def set(self, keys, on=True):
        pass

    def pause(self, paused):
        pass


class MacPlatform(Platform):
    name = "macOS"

    def version(self):
        return f"macOS {platform.mac_ver()[0]}"

    def data_root(self):
        return Path.home() / "Library" / "Application Support"

    def tesseract_candidates(self, home_dir, app_dir):
        on_path = [Path(d) / "tesseract" for d in os.environ.get("PATH", "").split(os.pathsep)
                   if d.strip() and os.path.isabs(d.strip())]
        return [home_dir / "tesseract" / "tesseract", app_dir / "tesseract" / "tesseract",
                Path("/opt/homebrew/bin/tesseract"), Path("/usr/local/bin/tesseract"),      # Homebrew
                Path("/opt/local/bin/tesseract"), *on_path]                                 # MacPorts

    def claim_single_instance(self, key, title, old_titles=()):
        # User-private, non-truncating lock: never follow a planted temp-file symlink.
        folder = self.data_root() / "MapleEXPPrivate" / "locks"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(folder / f"{key}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self._lock = os.fdopen(fd, "r+")   # macOS unlocks it at exit
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            subprocess.run(["/usr/bin/osascript", "-e", f'display dialog "{title} is already running."'
                            f' with title "{title}" buttons {{"OK"}} default button 1'], capture_output=True)
            return False

    def ask_permissions(self):
        try:
            _RequestCapture()                        # macOS shows its prompt once, the first time
        except Exception:
            pass

    def missing_permission(self):
        try:
            if _PreflightCapture():
                return None
        except Exception:
            pass
        return ("Can't see other windows. Allow this app (or your Terminal) in System Settings >"
                " Privacy & Security > Screen Recording, then restart it.")

    def capture_allowed(self, number):
        """Fail closed unless the selected game is the foreground app's front window.

        GameCapture rechecks this immediately before and after every bounded crop.
        Screen Recording permission alone never enables arbitrary desktop capture.
        """
        try:
            if not number or not _PreflightCapture():
                return False
            pid = frontmost_pid()
            windows = window_list()
            # Ignore overlay panels, but not other normal windows belonging to the game.
            front = next((w for w in windows if w.pid == pid and w.onscreen
                          and w.layer == 0 and w.rect), None)
            if not front or front.number != number or not is_game(front, os.getpid()):
                return False
            return bool(front.rect[2] >= 100 and front.rect[3] >= 100
                        and frontmost_pid() == pid)
        except Exception:
            return False

    def find_game_window(self):
        found = []
        for w in window_list():
            if is_game(w, os.getpid()):
                rect = self.client_rect(w.number)
                found.append((rect[2] * rect[3] if rect else 0, w.number))
        return max(found)[1] if found else None

    def window_exists(self, number):
        return bool(window_list(_ONLY_THIS, number))

    def client_rect(self, number):
        # Includes the title bar, if the window has one: the overlay looks for the EXP bar,
        # minimap and so on inside the window, so a little more around them does no harm.
        w = next(iter(window_list(_ONLY_THIS, number)), None)
        if not w or not w.onscreen or not w.rect:
            return None
        x, y, width, height = (round(v) for v in w.rect)
        return (x, y, width, height) if width >= 100 and height >= 100 else None

    def own_window_rect(self, root):
        x, y = root.winfo_rootx() + 1, root.winfo_rooty() + 1
        for w in window_list():
            if w.pid == os.getpid() and w.rect:        # in the "topmost" layer if Always on top
                rx, ry, rw, rh = w.rect
                if rx <= x < rx + rw and ry <= y < ry + rh:
                    return tuple(round(v) for v in w.rect)
        return None

    def screen_dpi(self, x, y):
        return 96                                    # a point is about a Windows pixel at 100% scaling

    def create_hotkeys(self, on_press):
        return MacHotkeys(on_press)

    def register_fonts(self, paths):
        # Available to this program only (process scope). If anything about it fails, the overlay
        # just uses the system's own fonts.
        try:
            ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
            _cf.CFURLCreateFromFileSystemRepresentation.restype = _vp
            _cf.CFURLCreateFromFileSystemRepresentation.argtypes = [_vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
            ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
            ct.CTFontManagerRegisterFontsForURL.argtypes = [_vp, ctypes.c_int, _vp]
            ok = True
            for path in paths:
                raw = str(path).encode()
                url = _cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
                ok = bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None)) and ok     # 1: this process only
                _CFRelease(url)
            return ok
        except Exception:
            return False

    def open_folder(self, path):
        subprocess.Popen(["/usr/bin/open", str(path)])

    def show_file(self, path):
        subprocess.Popen(["/usr/bin/open", "-R", str(path)])

    def font(self, family, weight):
        mac_family, mac_weight = _FONTS.get(family, (family, None))
        return mac_family, mac_weight or weight

    def alert(self, title, text):
        # (Tk may be what couldn't start, so AppleScript shows it. Title and text go in as arguments.)
        script = ['on run argv', 'display alert (item 1 of argv) message (item 2 of argv) as critical', 'end run']
        args = ["/usr/bin/osascript"] + [x for line in script for x in ("-e", line)] + [title, text]
        try:
            subprocess.run(args, capture_output=True, timeout=600)
        except Exception:
            super().alert(title, text)

    def copy_image(self, path):
        # AppleScript reads the file as PNG data onto the clipboard. The path goes in as an
        # argument, never into the script's text.
        script = ['on run argv', 'set the clipboard to (read (POSIX file (item 1 of argv)) as «class PNGf»)', 'end run']
        args = ["/usr/bin/osascript"] + [x for line in script for x in ("-e", line)] + [str(path)]
        try:
            return subprocess.run(args, capture_output=True, timeout=10).returncode == 0
        except Exception:
            return False
