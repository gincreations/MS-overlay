"""Bounded local diagnostics. Export is explicit and never includes user history or images."""
import faulthandler
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import zipfile


class Diagnostics:
    FILES = ("overlay.log", "overlay.old.log", "errors.log", "errors.old.log", "crash.log", "crash.old.log")
    LIMIT = 500_000

    def __init__(self, directory, version):
        self.directory, self.version = Path(directory), version
        self._file = None
        self._lock = threading.RLock()
        self._old_hooks = None

    @staticmethod
    def redact(text):
        for secret in sorted({str(Path.home()), os.environ.get("USER", ""), os.environ.get("USERNAME", "")}, key=len, reverse=True):
            if len(secret) > 2:
                text = text.replace(secret, "<user>")
        text = re.sub(r"(?i)[a-z]:[\\/]Users[\\/][^\\/\s\"']+", "<home>", text)
        text = re.sub(r"/(?:Users|home)/[^/\s\"']+", "<home>", text)
        return text

    def _safe(self, name):
        path = self.directory / name
        if path.is_symlink():
            raise ValueError("Diagnostic symlinks are not supported")
        return path

    def activity(self, text):
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                p = self._safe("overlay.log")
                if p.exists() and p.stat().st_size > self.LIMIT:
                    old = self._safe("overlay.old.log")
                    os.replace(p, old)
                line = self.redact(" ".join(str(text).split()))[:500]
                with p.open("a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
        except (OSError, ValueError):
            pass

    def error(self, context, exc=None):
        # No exception message or locals: those can contain sensitive arbitrary data.
        self.activity(f"Error: {context}; {type(exc).__name__ if exc is not None else 'unknown'}")

    def start(self):
        if self._old_hooks is not None:
            return False
        previous = False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            marker = self._safe("running.flag")
            previous = marker.exists()
            p = self._safe("crash.log")
            if p.exists() and p.stat().st_size > self.LIMIT:
                os.replace(p, self._safe("crash.old.log"))
            self._file = p.open("a", encoding="utf-8")
            self._file.write(f"\n--- v{self.version} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._file.flush()
            faulthandler.enable(file=self._file, all_threads=True)
            marker.write_text(time.strftime('%Y-%m-%d %H:%M:%S'), encoding="utf-8")
        except (OSError, ValueError, RuntimeError) as exc:
            self.error("enabling crash diagnostics", exc)
        self._old_hooks = (sys.excepthook, threading.excepthook)
        sys.excepthook = lambda kind, exc, tb: self.error("uncaught main-thread exception", exc)
        threading.excepthook = lambda args: self.error("uncaught worker exception", args.exc_value)
        self.activity(f"v{self.version} started" + ("; previous run ended unexpectedly" if previous else ""))
        return previous

    def end(self):
        self.activity("closed normally")
        try:
            self._safe("running.flag").unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
        if self._file:
            faulthandler.disable()
            self._file.close()
            self._file = None
        if self._old_hooks:
            sys.excepthook, threading.excepthook = self._old_hooks
            self._old_hooks = None

    def export(self, facts):
        with self._lock:
            if self._file:
                self._file.flush()
            folder = self._safe("logs")
            folder.mkdir(parents=True, exist_ok=True)
            name = f"overlay-logs-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{time.time_ns() % 1000000}.zip"
            path = folder / name
            # Exclusive creation: don't overwrite/follow an existing file or link.
            with path.open("xb") as output, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for name in self.FILES:
                    p = self._safe(name)
                    if p.is_file():
                        with p.open("rb") as f:
                            f.seek(max(0, p.stat().st_size - self.LIMIT))
                            text = f.read(self.LIMIT).decode("utf-8", errors="replace")
                        archive.writestr(name, self.redact(text))
                allowed = {k: facts[k] for k in ("version", "worker_alive", "capture_enabled", "pq_mode", "ocr_available", "polls", "read_errors", "potions_selected") if k in facts}
                archive.writestr("diagnostic-details.txt", self.redact(json.dumps(allowed, indent=2)))
            return path
