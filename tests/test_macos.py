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
    def test_native_classic_and_worlds_name_variants(self):
        for owner in ('MapleStory Classic', 'MapleStory-Classic.app',
                      'MapleStory Classic Client', 'MapleStory Worlds - Player',
                      'MapleStory_Worlds_Client', 'MapleStory.exe'):
            with self.subTest(owner=owner):
                self.windows.return_value=[self.game._replace(owner=owner)]
                self.assertEqual(self.platform.find_game_window(),101)
                self.assertTrue(self.platform.capture_allowed(101))

    def test_native_classic_world_reported_process(self):
        # Reported native process name, distinct from the MapleStory window title.
        self.windows.return_value=[self.game._replace(owner='Maplestory Classic World',title='MapleStory')]
        with patch.object(m,'native_game_process',return_value=False):
            self.assertEqual(self.platform.find_game_window(),101)
            self.assertTrue(self.platform.capture_allowed(101))

    def test_classic_world_focus_layer_transition(self):
        # Sanitized shape of the owner's diagnostic: same game/window moves
        # from normal layer 0 to layer 26 when focused. Titles may be absent.
        game=self.game._replace(owner='MapleStory Classic World',title='',rect=(0,0,1366,796))
        for layer, focused in ((0,False),(26,True),(0,False),(26,True)):
            with self.subTest(layer=layer,focused=focused):
                self.windows.return_value=[game._replace(layer=layer)]
                self.pid.return_value=game.pid if focused else 77
                with patch.object(m,'native_game_process',return_value=False):
                    self.assertEqual(self.platform.find_game_window(),game.number)
                    self.assertEqual(self.platform.capture_allowed(game.number),focused)

    def test_raised_game_is_selected_ahead_of_same_process_normal_window(self):
        game=self.game._replace(layer=26,owner='MapleStory Classic World',title='')
        normal=game._replace(number=202,layer=0,rect=(0,0,2000,1200))
        self.windows.return_value=[game,normal]
        self.assertEqual(self.platform.find_game_window(),game.number)
        self.assertTrue(self.platform.capture_allowed(game.number))
        self.assertFalse(self.platform.capture_allowed(normal.number))

    def test_raised_layer_keeps_identity_permission_and_visibility_guards(self):
        game=self.game._replace(layer=26,owner='MapleStory Classic World',title='')
        for owner in ('Google Chrome','MapleStory Launcher','wineloader','AutoFill (MapleStory Classic World)'):
            with self.subTest(owner=owner),patch.object(m,'native_game_process',return_value=False):
                self.windows.return_value=[game._replace(owner=owner)]
                self.assertIsNone(self.platform.find_game_window())
                self.assertFalse(self.platform.capture_allowed(game.number))
        self.windows.return_value=[game]
        self.permission.return_value=False
        self.assertFalse(self.platform.capture_allowed(game.number))
        self.permission.return_value=True
        self.windows.return_value=[game._replace(onscreen=False)]
        self.assertIsNone(self.platform.find_game_window())
        self.assertFalse(self.platform.capture_allowed(game.number))
        for layer in (-1,20,25,27,1000):
            with self.subTest(layer=layer):
                self.windows.return_value=[game._replace(layer=layer)]
                self.assertIsNone(self.platform.find_game_window())
                self.assertFalse(self.platform.capture_allowed(game.number))

    def test_raised_game_focus_loss_discards_pixels(self):
        self.windows.return_value=[self.game._replace(layer=26)]
        pid=self.pid
        class Fake:
            def grab(self,region):
                pid.return_value=77
                return b'pixels must not reach OCR'
        capture=GameCapture(Fake(),lambda:self.game.rect,lambda:self.platform.capture_allowed(self.game.number))
        with self.assertRaises(CaptureBlocked):
            capture.grab(dict(left=-490,top=30,width=100,height=100))

    def test_native_executable_fallback(self):
        self.windows.return_value=[self.game._replace(owner='Localized game label')]
        with patch.object(m,'native_game_process',return_value=True):
            self.assertTrue(self.platform.capture_allowed(101))
        with patch.object(m,'native_game_process',return_value=False):
            self.assertFalse(self.platform.capture_allowed(101))

    def test_titles_alone_do_not_enable_capture(self):
        for owner in ('Unity', 'Nexon Launcher', 'prl_vm_app', 'Moonlight', 'MapleStory Classic Browser'):
            with self.subTest(owner=owner), patch.object(m,'native_game_process',return_value=False):
                self.windows.return_value=[self.game._replace(owner=owner)]
                self.assertIsNone(self.platform.find_game_window())
                self.assertFalse(self.platform.capture_allowed(101))

    def test_foreground_game_wins_over_larger_background_client(self):
        bigger=self.game._replace(number=202,pid=345678,rect=(0,0,2000,1200))
        self.windows.return_value=[bigger,self.game]
        self.assertEqual(self.platform.find_game_window(),101)
        self.pid.return_value=bigger.pid
        self.assertEqual(self.platform.find_game_window(),202)

    def test_foreground_game_window_wins_within_same_process(self):
        bigger=self.game._replace(number=202,rect=(0,0,2000,1200))
        self.windows.return_value=[self.game,bigger]
        self.assertEqual(self.platform.find_game_window(),101)

    def test_hidden_and_tiny_windows_not_selected(self):
        for game in (self.game._replace(onscreen=False),self.game._replace(rect=(0,0,10,10))):
            self.windows.return_value=[game]
            self.assertIsNone(self.platform.find_game_window())

    def test_reader_reacquires_new_game_id_at_same_size(self):
        import maple_exp as app
        reader=app.ScreenReader(None)
        with patch.object(app, 'PLATFORM', self.platform):
            self.assertEqual(reader._game_rect(), self.game.rect)
            reader.box=(1,2,3,4)
            reader.map_box=(5,6,7,8)
            self.windows.return_value=[self.game._replace(number=202)]
            self.assertEqual(reader._game_rect(), self.game.rect)
            self.assertEqual(reader.hwnd,202)
            self.assertIsNone(reader.box)
            self.assertIsNone(reader.map_box)

    def test_reader_keeps_calibration_for_unchanged_window(self):
        import maple_exp as app
        reader=app.ScreenReader(None)
        with patch.object(app, 'PLATFORM', self.platform):
            reader._game_rect()
            reader.box=(1,2,3,4)
            reader._game_rect()
            self.assertEqual(reader.box,(1,2,3,4))

    def test_own_python_process_is_not_native_game(self):
        self.assertFalse(m.native_game_process(os.getpid()))

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

@unittest.skipUnless(sys.platform == 'darwin', 'macOS backend')
class MacDesktopTests(unittest.TestCase):
    def test_collection_policy_is_managed_not_transient_or_all_spaces(self):
        flags = m.desktop_collection_behavior(1 | 2 | 8 | 16 | 64 | 128 | 512 | 1024)
        self.assertEqual(flags & (1 | 2 | 8 | 16 | 64 | 128 | 512), 0)
        self.assertEqual(flags & (4 | 32 | 256), 4 | 32 | 256)
        self.assertTrue(flags & 1024)
        self.assertEqual(m.desktop_collection_behavior(flags), flags)

    def test_real_tk_window_is_managed_with_topmost_on_and_off(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.title('Maple desktop regression window')
        platform = m.MacPlatform()
        for topmost in (True, False, True):
            root.attributes('-topmost', topmost)
            root.update()
            platform.style_window(root, '#000000', '#ffffff')
            root.update()
            window = m.native_window(root)
            self.assertTrue(window)
            flags = m._SendUnsigned(window, m._GetSelector(b'collectionBehavior'))
            self.assertEqual(flags & (4 | 32 | 256), 4 | 32 | 256)
            self.assertEqual(flags & (1 | 2 | 8 | 16 | 64 | 128 | 512), 0)
            self.assertEqual(bool(root.attributes('-topmost')), topmost)
        root.withdraw(); root.update(); root.deiconify()
        root.after(250, root.quit); root.mainloop()
        window = m.native_window(root)
        flags = m._SendUnsigned(window, m._GetSelector(b'collectionBehavior'))
        self.assertTrue(flags & 4)

    def test_duplicate_native_titles_are_not_guessed(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        child = tk.Toplevel(root)
        root.title('Duplicate regression title'); child.title(root.title())
        root.update()
        self.assertIsNone(m.native_window(root))

if __name__=='__main__':unittest.main()
