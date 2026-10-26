"""Native API contract plus synthetic foreground/permission/bounds failure cases.
No screen capture or permission prompts. Run on macOS only.
"""
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == 'darwin':
    from platforms import macos as m
    from privacy_guard import GameCapture, CaptureBlocked

@unittest.skipUnless(sys.platform == 'darwin', 'macOS backend')
class MacCaptureTests(unittest.TestCase):
    def setUp(self):
        self.platform=m.MacPlatform()
        self.game=m.MacWindow(101,987654,'MapleStory Worlds','MapleStory',0,(-500,20,900,700),True)
        self.patches=[patch.object(m,'_PreflightCapture',return_value=True),
                      patch.object(m,'frontmost_pid',return_value=self.game.pid),
                      patch.object(m,'window_list',return_value=[self.game])]
        self.permission,self.pid,self.windows=[p.start() for p in self.patches]
        for p in self.patches:self.addCleanup(p.stop)
    def test_native_game(self):self.assertTrue(self.platform.capture_allowed(101))
    def test_missing_permission(self):
        self.permission.return_value=False
        self.assertFalse(self.platform.capture_allowed(101))
        self.assertIn('Screen Recording',self.platform.missing_permission())
    def test_permission_exception(self):
        self.permission.side_effect=RuntimeError()
        self.assertFalse(self.platform.capture_allowed(101))
        self.assertIsNotNone(self.platform.missing_permission())
    def test_browser_foreground(self):
        self.pid.return_value=77
        self.assertFalse(self.platform.capture_allowed(101))
    def test_spoofed_browser_title(self):
        self.windows.return_value=[self.game._replace(owner='Google Chrome')]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_generic_vm_desktop(self):
        self.windows.return_value=[self.game._replace(owner='prl_vm_app')]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_minimized(self):
        self.windows.return_value=[self.game._replace(onscreen=False)]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_own_window(self):
        self.windows.return_value=[self.game._replace(pid=os.getpid())]
        self.pid.return_value=os.getpid()
        self.assertFalse(self.platform.capture_allowed(101))
    def test_foreground_changes_mid_check(self):
        self.pid.side_effect=[self.game.pid,77]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_other_game_window_in_front(self):
        self.windows.return_value=[self.game._replace(number=102,title='Settings'),self.game]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_other_app_panel_does_not_change_focus(self):
        self.windows.return_value=[self.game._replace(number=102,pid=os.getpid(),layer=19),self.game]
        self.assertTrue(self.platform.capture_allowed(101))
    def test_wrong_id(self):self.assertFalse(self.platform.capture_allowed(200))
    def test_absent_id(self):self.assertFalse(self.platform.capture_allowed(None))
    def test_tiny_window(self):
        self.windows.return_value=[self.game._replace(rect=(0,0,10,10))]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_wine_requires_game_title(self):
        self.windows.return_value=[self.game._replace(owner='wine64-preloader')]
        self.assertTrue(self.platform.capture_allowed(101))
        self.windows.return_value=[self.game._replace(owner='wine64-preloader',title='Desktop')]
        self.assertFalse(self.platform.capture_allowed(101))
    def test_api_error(self):
        self.windows.side_effect=RuntimeError()
        self.assertFalse(self.platform.capture_allowed(101))
    def test_screen_coordinates_negative_origin(self):
        class Fake:
            monitors=[dict(left=-1000,top=0,width=3000,height=1200)]
            def grab(self,region):return b'pixels'
        capture=GameCapture(Fake(),lambda:self.platform.client_rect(101),lambda:self.platform.capture_allowed(101))
        self.assertEqual(capture.grab(dict(left=-490,top=30,width=100,height=100)),b'pixels')
        with self.assertRaises(CaptureBlocked):capture.grab(dict(left=-510,top=30,width=100,height=100))
    def test_focus_loss_discards_pixels(self):
        pid=self.pid
        class Fake:
            monitors=[dict(left=-1000,top=0,width=3000,height=1200)]
            def grab(self,region):pid.return_value=77;return b'private pixels'
        capture=GameCapture(Fake(),lambda:self.platform.client_rect(101),lambda:self.platform.capture_allowed(101))
        with self.assertRaises(CaptureBlocked):capture.grab(dict(left=-490,top=30,width=100,height=100))
    def test_mss_uses_nominal_points(self):
        import mss.darwin as d
        self.assertTrue(d.IMAGE_OPTIONS & d.kCGWindowImageNominalResolution)

    def test_lock_does_not_follow_symlink(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder, patch.object(self.platform,'data_root',return_value=Path(folder)):
            locks=Path(folder)/'MapleEXPPrivate/locks';locks.mkdir(parents=True)
            protected=Path(folder)/'protected';protected.write_text('keep')
            (locks/'example.lock').symlink_to(protected)
            with self.assertRaises(OSError):self.platform.claim_single_instance('example','Overlay')
            self.assertEqual(protected.read_text(),'keep')

    def test_lock_is_private_and_nontruncating(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder, patch.object(self.platform,'data_root',return_value=Path(folder)):
            self.assertTrue(self.platform.claim_single_instance('example','Overlay'))
            self.platform._lock.close()
            path=Path(folder)/'MapleEXPPrivate/locks/example.lock'
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            path.write_text('keep')
            self.assertTrue(self.platform.claim_single_instance('example','Overlay'))
            self.platform._lock.close()
            self.assertEqual(path.read_text(),'keep')

if __name__=='__main__':unittest.main()
