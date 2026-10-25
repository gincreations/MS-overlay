"""Live Tk restock-removal presentation with capture worker disabled, synthetic data only."""
import os, sys, tempfile, time, traceback
from pathlib import Path
from unittest.mock import patch
os.environ['MAPLE_EXP_DATA'] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_exp as m
failures = 0

def check(name, ok):
    global failures
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    failures += not ok

with patch.object(m.App, '_worker', lambda self: None):
    root = m.tk.Tk(); app = m.App(root, m.DigitTemplates.load())
errors = []
root.report_callback_exception = lambda *e: errors.append(''.join(traceback.format_exception(*e)))
try:
    app.select_potion(0, 2000000); app.select_potion(1, 2000003)
    now = time.monotonic()
    for i in range(22):
        app.potion_usage[0].observe(200 - i, now - 63 + i * 3)
        app.potion_usage[1].observe(500 - i * 2, now - 63 + i * 3)
    check('paused app has no restock text', 'Restock' not in app.potion_text(0))
    app.capture_enabled.set()  # no worker exists: no live capture possible
    check('HP count and usage retained', '180 left' in app.potion_text(0) and '~20 used' in app.potion_text(0))
    check('MP count and usage retained', '460 left' in app.potion_text(1) and '~40 used' in app.potion_text(1))
    check('detailed view has observation time but no restock requirement', '60s observed' in app.potion_text(0,True) and 'Restock' not in app.potion_text(0,True))
    check('cost remains available', 'Est. cost: 1,000 mesos' in app.potion_text(0))
    for mode in ['dark', 'light']:
        app.set_theme(mode)
        for compact in [False, True]:
            app.set_compact(compact); app._update_display(); root.update()
            text = app.view.potions_label.cget('text')
            check(f'{mode}/{compact} keeps both stock counts without restock', '180 left' in text and '460 left' in text and 'Restock' not in text)
    app.open_potions(); root.update(); app.potion_win.refresh()
    check('Potions panel keeps counts without ETA', '180 left' in app.potion_win.rows[0].cget('text') and 'Restock' not in app.potion_win.rows[0].cget('text'))
    def labels(widget):
        for child in widget.winfo_children():
            if isinstance(child,m.tk.Label):yield str(child.cget('text'))
            yield from labels(child)
    check('Potions help has no restock instructions', all('restock' not in text.lower() for text in labels(app.potion_win)))
    app.potion_usage[0].gap('hidden')
    check('hidden inventory clears stock but retains usage', app.potion_usage[0].value is None and app.potion_usage[0].used==20)
    app.tracker.req=95700;app.tracker.exp=12000;app.tracker.pct=12000/95700*100;app.tracker.gained=2000;app.tracker._accum=60
    with patch.object(app.view,'show',wraps=app.view.show) as show:
        app._update_display()
        check('EXP level-up ETA is retained', ' in ' in show.call_args.kwargs['eta'])
    app.reset()
    check('reset still clears usage', app.potion_usage[0].used==0 and 'Restock' not in app.potion_text(0))
    check('no Tk callback failures', not errors)
    if errors: print(errors)
finally:
    app.close(); app._worker_thread.join(3)
    if app.potion_service.thread: app.potion_service.thread.join(3)
sys.exit(bool(failures))
