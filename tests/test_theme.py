"""Exercise real theme switches, persistence, and preservation of an active run."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

DATA = Path(tempfile.mkdtemp())
os.environ['MAPLE_EXP_DATA'] = str(DATA)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_exp as m
import ui_gfx
import ui_palette

failures = 0

def check(name, ok):
    global failures
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    failures += not ok

m.save_config({**m.DEFAULTS, 'hotkeys_on': False, 'theme': 'invalid'})
check('invalid theme falls back to dark', m.load_config()['theme'] == 'dark')
root = m.tk.Tk()
app = m.App(root, m.DigitTemplates.load())
# This fixture explicitly controls scale; native DPI refresh must not rebuild
# the view underneath palette assertions. Production DPI behavior is unchanged.
app._check_screen = lambda: None
errors = []
root.report_callback_exception = lambda *args: errors.append(str((app.cfg['theme'], app.compact, app.cfg['ui_scale'])) + ''.join(traceback.format_exception(*args)))
try:
    root.update()
    check('dark is the default', root.cget('bg') == '#0b0c10')
    session, reader, worker = app.session, app.reader, app._worker_thread
    app.tracker.gained, app.meso.gained = 12345, 6789
    app.autolog._add('Theme test map', 27, 1, 900, 300, 150, 300, 'Bandit', 'Theme test map')
    app._fill_log()
    app.toggle_log()
    row = app.log_tree.get_children()[0]
    app.log_tree.selection_set(row)
    root.update()
    app.note_text.insert('end', 'keep this note across theme changes')
    root.update()
    app.open_settings()
    root.update()
    app.session.on = True
    # Force a pending child-owned timer: switching must cancel it, not reuse its Tcl command.
    stale = []
    app.view.after(100, lambda: stale.append(True))
    for mode in ('light', 'dark', 'light'):
        app.set_theme(mode)
        root.update()
        expected = '#f3f5f9' if mode == 'light' else '#0b0c10'
        check(f'{mode}: main, settings and log use the selected background',
              root.cget('bg') == app.view.cget('bg') == app.settings_win.cget('bg') == app.log_panel.cget('bg') == expected)
        check(f'{mode}: session and capture worker are preserved',
              app.session is session and app.session.on and app.reader is reader and app._worker_thread is worker and worker.is_alive())
        check(f'{mode}: EXP and mesos totals survive', app.tracker.gained == 12345 and app.meso.gained == 6789)
        check(f'{mode}: choice persists', m.load_config()['theme'] == mode)
        check(f'{mode}: history and unsaved note survive', any('keep this note' in (e.get('note') or '') for e in app.autolog.entries))
        check(f'{mode}: capture remains disabled', not app.capture_enabled.is_set())
        panel = app.theme.gfx.hero_panel(328, 230, 18)
        r,g,b,a = panel.getpixel((300, 200))
        check(f'{mode}: rendered card matches theme', (min(r,g,b) > 180) if mode == 'light' else (max(r,g,b) < 65))
        popup = m.PopupMenu(app.theme, app.view.menu_btn, [('Test item', None, lambda: None)])
        # Measure the constructed palette before unrelated focus-loss timers can
        # intentionally dismiss the menu on a headless/remote Windows desktop.
        root.update_idletasks()
        check(f'{mode}: popup background matches', popup.cget('bg') == expected)
        popup.destroy()
    app.set_compact(True)
    app.set_theme('dark')
    root.update()
    check('pending callbacks of destroyed views are cancelled', not stale)
    check('compact mode survives switching', app.compact and app.view.hero.compact)
    app.cfg['ui_scale'] = 150
    app._apply_ui_scale()
    app.set_theme('light')
    root.update()
    check('size survives switching', app.cfg['ui_scale'] == 150)
    close_stale = []
    app.settings_win.after(50, lambda: close_stale.append(True))
    app.settings_win.destroy()
    app.settings_win = None
    app.set_theme('dark')
    root.update()
    check('switch works with settings closed', app.settings_win is None)
    app.set_theme('light')
    root.update()
    check('closing settings cancels its pending callbacks', not close_stale)
    check('no Tk callback errors', not errors)
    print('CALLBACK ERRORS', errors) if errors else None
finally:
    app.close()
    app._worker_thread.join(timeout=3)
# A new app must restore the saved light palette, not only the selection label.
root = m.tk.Tk()
app = m.App(root, m.DigitTemplates.load())
# This fixture explicitly controls scale; native DPI refresh must not rebuild
# the view underneath palette assertions. Production DPI behavior is unchanged.
app._check_screen = lambda: None
try:
    root.update()
    check('restart restores saved light mode', app.cfg['theme'] == 'light' and root.cget('bg') == '#f3f5f9')
finally:
    app.close()
    app._worker_thread.join(timeout=3)
print('ALL PASSED' if not failures else f'{failures} FAILED')
sys.exit(bool(failures))
