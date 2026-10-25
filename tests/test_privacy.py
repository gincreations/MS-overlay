"""Privacy boundaries, tested with synthetic screens; never captures the real desktop."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["MAPLE_EXP_DATA"] = tempfile.mkdtemp()
from privacy_guard import CaptureBlocked, GameCapture
import maple_exp as m

class Screen:
    monitors = [{"left": -200, "top": 0, "width": 1200, "height": 800}]
    def __init__(self): self.calls = []
    def grab(self, region):
        self.calls.append(region)
        return "pixels"

class PrivacyTests(unittest.TestCase):
    def test_foreground_required_before_read(self):
        screen = Screen()
        cap = GameCapture(screen, lambda: (10,20,300,200), lambda: False)
        with self.assertRaises(CaptureBlocked): cap.grab(dict(left=10,top=20,width=10,height=10))
        self.assertEqual(screen.calls, [])
    def test_capture_is_bounded_to_game(self):
        screen = Screen()
        cap = GameCapture(screen, lambda: (10,20,300,200), lambda: True)
        self.assertEqual(cap.monitors[0], dict(left=10,top=20,width=300,height=200))
        with self.assertRaises(CaptureBlocked): cap.grab(dict(left=0,top=20,width=20,height=20))
        self.assertEqual(screen.calls, [])
        self.assertEqual(cap.grab(dict(left=10,top=20,width=20,height=20)), "pixels")
    def test_focus_switch_discards_frame(self):
        state = iter([True, False]);screen = Screen()
        cap = GameCapture(screen, lambda: (10,20,300,200), lambda: next(state))
        with self.assertRaises(CaptureBlocked): cap.grab(dict(left=10,top=20,width=20,height=20))
        self.assertEqual(len(screen.calls), 1)
    def test_window_move_discards_frame(self):
        bounds = iter([(10,20,300,200),(20,20,300,200)])
        cap = GameCapture(Screen(), lambda: next(bounds), lambda: True)
        with self.assertRaises(CaptureBlocked): cap.grab(dict(left=10,top=20,width=20,height=20))
    def test_negative_monitor_coordinates(self):
        cap = GameCapture(Screen(), lambda: (-100,10,200,100), lambda: True)
        self.assertEqual(cap.monitors[0]["left"], -100)
        self.assertEqual(cap.grab(dict(left=-90,top=10,width=20,height=20)), "pixels")
    def test_network_guard_blocks_dns_tcp_udp(self):
        import socket
        with self.assertRaises(PermissionError): socket.getaddrinfo("example.invalid", 80)
        with socket.socket() as sock:
            with self.assertRaises(PermissionError): sock.connect(("127.0.0.1", 1))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            with self.assertRaises(PermissionError): sock.sendto(b"test", ("127.0.0.1", 1))
    def test_legacy_online_and_desktop_region_settings_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"config.json"
            path.write_text(json.dumps({"check_updates":True,"mode":"region","region":{"left":0,"top":0,"width":100,"height":100}}))
            with patch.object(m,"CONFIG_PATH",path): cfg=m.load_config()
        self.assertEqual(cfg["mode"],"window")
        self.assertNotIn("region",cfg)
        self.assertNotIn("check_updates",cfg)
    def test_app_entrypoint_blocks_read_when_not_foreground(self):
        reader=m.ScreenReader.__new__(m.ScreenReader)
        reader.look_again_requested=False
        reader.hwnd=1
        reader._game_rect=lambda:(10,20,300,200)
        reader.capture_enabled=lambda:True
        screen=Screen()
        with patch.object(m.PLATFORM,"capture_allowed",return_value=False):
            with self.assertRaises(CaptureBlocked): reader.read(screen)
        self.assertEqual(screen.calls,[])
    def test_history_and_backups_removed_settings_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);log=m.AutoLog(15,root/"exp_log.json",root/"exp_log.txt")
            (root/"config.json").write_text("keep settings")
            (root/"unrelated.txt").write_text("keep me")
            (root/"backups").mkdir(exist_ok=True)
            (root/"backups/exp_log-2026-01-01.json").write_text("private note")
            (root/"exp_log.damaged-20260101.json").write_text("private note")
            log.runs=[{"note":"private"}];log.save();log.clear_history()
            self.assertFalse((root/"exp_log.json").exists())
            self.assertFalse(list((root/"backups").glob("exp_log-*.json")))
            self.assertFalse(list(root.glob("exp_log.damaged-*.json")))
            self.assertEqual((root/"config.json").read_text(),"keep settings")
            self.assertEqual((root/"unrelated.txt").read_text(),"keep me")
            self.assertEqual(log.runs,[])
    def test_history_delete_does_not_follow_backup_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);own=root/"own";outside=root/"outside";own.mkdir();outside.mkdir()
            protected=outside/"exp_log-2026-01-01.json";protected.write_text("original history")
            (own/"backups").symlink_to(outside,target_is_directory=True)
            log=m.AutoLog(15,own/"exp_log.json",own/"exp_log.txt");log.clear_history()
            self.assertTrue(protected.exists())
            self.assertFalse((own/"backups").is_symlink())
    def test_windows_predicate_requires_same_visible_foreground_process(self):
        tree=ast.parse((ROOT/"platforms/windows.py").read_text())
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="capture_allowed")
        env={"_IsWindow":lambda h:True,"_IsIconic":lambda h:False,
             "_GetForegroundWindow":lambda:42,"_process_name":lambda h:"maplestory.exe"}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),"foreground-predicate","exec"),env)
        allowed=env["capture_allowed"]
        self.assertTrue(allowed(None,42))
        self.assertFalse(allowed(None,41))
        env["_process_name"]=lambda h:"browser.exe"
        self.assertFalse(allowed(None,42))
        env["_process_name"]=lambda h:"maplestory.exe"
        env["_IsIconic"]=lambda h:True
        self.assertFalse(allowed(None,42))
    def test_exporters_and_network_imports_removed(self):
        self.assertFalse(hasattr(m.App,"report_bug"))
        self.assertFalse(hasattr(m.App,"_save_report_screen"))
        self.assertFalse(hasattr(m,"RegionSelector"))
        forbidden={"urllib","requests","httpx","webbrowser","socket"}
        for file in [ROOT/"maple_exp.py",ROOT/"ocr.py"]:
            tree=ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    self.assertFalse(any(x.name.split(".")[0] in forbidden for x in node.names))
                if isinstance(node,ast.ImportFrom): self.assertNotIn((node.module or "").split(".")[0],forbidden)

if __name__=="__main__": unittest.main()
