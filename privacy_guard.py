"""Offline and capture boundaries. Defense in depth, not an OS security sandbox."""
import sys


class CaptureBlocked(RuntimeError):
    pass


def install_offline_guard():
    """Deny Python networking/browser audit events; native libraries are not sandboxed."""
    denied = {"socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
              "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
              "urllib.Request", "http.client.connect", "webbrowser.open"}
    def guard(event, args):
        if event in denied:
            raise PermissionError("Maple Private Overlay is offline: networking is disabled")
    sys.addaudithook(guard)


def intersect(a, b):
    x, y = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    if right <= x or bottom <= y:
        raise CaptureBlocked("Game area is outside the screen")
    return x, y, right - x, bottom - y


class GameCapture:
    """Restrict each screenshot to a foreground game rectangle; reject focus/move races.

    Screen capture can still include always-on-top windows/notifications over the game.
    A focus check is not per-window compositor isolation.
    """
    def __init__(self, screen, bounds, allowed):
        self.screen, self.bounds, self.allowed = screen, bounds, allowed

    def _check(self):
        if not self.allowed():
            raise CaptureBlocked("Privacy pause: click the game to resume capture")
        rect = self.bounds()
        if not rect or rect[2] <= 0 or rect[3] <= 0:
            raise CaptureBlocked("Privacy pause: game is unavailable")
        return tuple(rect)

    @property
    def monitors(self):
        rect = self._check()
        monitor = self.screen.monitors[0]
        rect = intersect(rect, tuple(monitor[k] for k in ("left", "top", "width", "height")))
        return [dict(zip(("left", "top", "width", "height"), rect))]

    def grab(self, region):
        before = self._check()
        wanted = tuple(region[k] for k in ("left", "top", "width", "height"))
        if wanted != intersect(wanted, before):
            raise CaptureBlocked("Capture outside the game was blocked")
        shot = self.screen.grab(region)
        if self._check() != before:
            raise CaptureBlocked("Game moved during capture; frame discarded")
        return shot
