"""Privacy-relevant OCR contract tests: PNG stdin, no temporary screenshots."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import ocr

class OCRTests(unittest.TestCase):
    def test_stdin_multiple_crops(self):
        calls = []
        def run(args, **kw):
            calls.append((args, kw))
            return SimpleNamespace(returncode=0, stdout=(b"12\n" if len(calls)==1 else b"34\n"), stderr=b"")
        with patch.object(ocr.subprocess, "run", run):
            got = ocr.Tesseract("trusted/tesseract.exe").read_lines([np.zeros((20,30), np.uint8)]*2, "0123456789")
        self.assertEqual(got, ["12", "34"])
        for args, kw in calls:
            self.assertEqual(args[1:3], ["stdin", "stdout"])
            self.assertTrue(kw["input"].startswith(b"\x89PNG"))
            self.assertNotIn("cwd", kw)
            self.assertFalse(kw.get("shell", False))
            self.assertEqual(kw["env"]["OMP_THREAD_LIMIT"], "1")
    def test_failure_does_not_expose_stderr(self):
        with patch.object(ocr.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=b"PRIVATE IMAGE CONTENT")):
            with self.assertRaises(ocr.TesseractError) as cm:
                ocr.Tesseract("trusted/tesseract.exe").read_lines([np.zeros((2,2), np.uint8)])
        self.assertNotIn("PRIVATE", str(cm.exception))
    def test_empty_images_no_subprocess(self):
        with patch.object(ocr.subprocess, "run") as run:
            self.assertEqual(ocr.Tesseract("unused").read_lines([]), [])
            run.assert_not_called()

if __name__ == "__main__": unittest.main()
