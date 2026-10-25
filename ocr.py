"""Reading text with Tesseract: the only place the overlay starts it.

Crops are passed via stdin, never stored as image files. One process per crop trades some
CPU for avoiding temporary screenshot files. OMP_NUM_THREADS is limited to one.

The pictures are single-channel (grey) images, which is what the readers make.
"""
import os
import subprocess

import cv2

PAGE_BREAK = "\f"                    # what Tesseract puts between one picture's text and the next


class TesseractError(RuntimeError):
    pass


def _hidden():
    """On Windows, no console window flashing up each time it runs."""
    if not hasattr(subprocess, "STARTUPINFO"):
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": info}


class Tesseract:
    """cmd: the full path of the tesseract program (never looked up on PATH or in this folder)."""

    def __init__(self, cmd, timeout=30):
        self.cmd, self.timeout = cmd, timeout
        self.env = dict(os.environ, OMP_THREAD_LIMIT="1")
        data = os.path.join(os.path.dirname(cmd), "tessdata")
        if os.path.isdir(data):
            self.env["TESSDATA_PREFIX"] = data
        self.runs = 0                                   # how many times Tesseract was started

    def read_lines(self, images, chars=None):
        """Read each crop through stdin: no screenshot or crop files are written to disk."""
        texts = []
        for image in images:
            ok, png = cv2.imencode(".png", image)
            if not ok:
                raise TesseractError("couldn't encode the OCR crop")
            args = [self.cmd, "stdin", "stdout", "--psm", "7"]
            if chars:
                args += ["-c", f"tessedit_char_whitelist={chars}"]
            self.runs += 1
            run = subprocess.run(args, input=png.tobytes(), capture_output=True, env=self.env,
                                 timeout=self.timeout, **_hidden())
            if run.returncode != 0:
                raise TesseractError("Tesseract failed (exit code %s)" % run.returncode)
            texts.append(run.stdout.decode("utf-8", "replace").rstrip("\r\n\f"))
        return texts

    def version(self):
        """Tesseract's version line (asked once), or None if it can't say."""
        if not hasattr(self, "_version"):
            try:
                run = subprocess.run([self.cmd, "--version"], capture_output=True, stdin=subprocess.DEVNULL,
                                     timeout=10, **_hidden())
                text = (run.stdout or run.stderr).decode("utf-8", "replace").strip()
                self._version = text.splitlines()[0] if text else None
            except Exception:
                self._version = None
        return self._version

    def read_line(self, image, chars=None):
        return self.read_lines([image], chars)[0]
