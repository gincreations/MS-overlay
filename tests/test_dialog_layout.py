"""Real Tk dialog geometry/navigation; isolated settings, never game/desktop capture."""
import os,sys,tempfile,traceback,time
from pathlib import Path
from types import SimpleNamespace
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
from ui_main import Button
from tkinter import font as tf
failures=0

def check(name,ok):
 global failures
 print(('PASS ' if ok else 'FAIL ')+name,flush=True);failures+=not ok
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load());errors=[]
root.report_callback_exception=lambda *e:errors.append(''.join(traceback.format_exception(*e)))
# This suite controls synthetic work-area bounds and UI scales explicitly.
# A hosted Windows monitor's delayed DPI refresh can rebuild a dialog during
# measurement; native screen tracking is outside this synthetic fixture.
app._check_screen=lambda:None
def pump():
 for _ in range(3):root.update();time.sleep(.03)
try:
 app.hotkeys.supported=True # show Windows hotkey rows without registering OS hooks
 session=app.session;reader=app.reader;worker=app._worker_thread
 app.select_potion(0,2000004);app.select_potion(1,2020010)
 app.set_potion_price(0,'3210');app.potion_usage[0].used=20;app.potion_usage[0].seconds=120
 global_wheel=root.bind_all('<MouseWheel>')
 for mode in ['dark','light']:
  app.set_theme(mode)
  for size in [100,125,150,200]:
   app.cfg['ui_scale']=size;app._apply_ui_scale();pump()
   for kind,opener in [('settings',app.open_settings),('potions',app.open_potions)]:
    opener();w=app.settings_win if kind=='settings' else app.potion_win
    w.scroll.screen_bounds=lambda:(0,0,1024,768)
    w.scroll.fit();pump()
    tag=f'{mode}/{size}%/{kind}'
    check(tag+f' stays within 1024x768 work space ({w.winfo_width()}x{w.winfo_height()} at y={w.winfo_y()})',w.winfo_width()<=976 and w.winfo_height()<=668 and w.winfo_y()+w.winfo_height()<=738)
    check(tag+' uses vertical scroll when content is tall',w.scroll.body.winfo_reqheight()<=w.scroll.canvas.winfo_height() or w.scroll.vertical.winfo_ismapped())
    if kind=='potions':
     check(tag+' labels use the same font family as overlay',all(tf.Font(root=root,font=l.cget('font')).actual('family')==app.theme.font('regular',11).actual('family') for l in w.rows))
     check(tag+' actions use matching custom buttons',all(isinstance(b,Button) for b in w.price_buttons+w.npc_buttons))
     w.close_button.focus_force();pump()
     top=w.close_button.winfo_rooty()-w.scroll.canvas.winfo_rooty()
     check(tag+' keyboard focus reveals bottom Close control',top>=-1 and top+w.close_button.winfo_height()<=w.scroll.canvas.winfo_height()+1)
     w.scroll.canvas.yview_moveto(0)
     w.scroll._wheel(SimpleNamespace(widget=w.rows[0],delta=-120,state=0,num=0));pump()
     check(tag+' wheel scroll works inside panel',w.scroll.canvas.yview()[0]>0 or not w.scroll.vertical.winfo_ismapped())
    w.destroy()
    if kind=='settings':app.settings_win=None
    else:app.potion_win=None
 app.open_settings();pump()
 app._hotkey_ui['choose']('start');app.settings_win.focus_force();pump()
 app.settings_win.event_generate('<Escape>');pump()
 check('Escape cancels hotkey editing without closing Settings',app.settings_win.winfo_exists() and app._hotkey_ui['choosing']['action'] is None)
 app.settings_win.event_generate('<Escape>');pump()
 check('Escape closes Settings when not editing a hotkey',not app.settings_win.winfo_exists())
 app.settings_win=None
 app.open_potions();pump();panel=app.potion_win
 panel.price_vars[0].set('9,999')
 app.cfg['ui_scale']=125;app._apply_ui_scale();pump()
 check('live size change rebuilds panel without losing unfinished price',app.potion_win is not panel and app.potion_win.price_vars[0].get()=='9,999')
 check('live size change keeps applied price and usage intact',app.potion_price(0)==3210 and app.potion_usage[0].used==20)
 app.potion_win.scroll.screen_bounds=lambda:(0,0,480,640);app.potion_win.scroll.fit();pump()
 check('narrow screens provide horizontal scrolling instead of clipping controls',app.potion_win.winfo_width()<=432 and app.potion_win.scroll.horizontal.winfo_ismapped())
 app.potion_win.close_button.focus_force();pump()
 left=app.potion_win.close_button.winfo_rootx()-app.potion_win.scroll.canvas.winfo_rootx()
 check('keyboard focus reveals control horizontally on narrow screens',left>=-1 and left+app.potion_win.close_button.winfo_width()<=app.potion_win.scroll.canvas.winfo_width()+1)
 # Simulate a native window manager moving the transient after initial fit.
 app.potion_win.geometry(f'{app.potion_win.winfo_width()}x{app.potion_win.winfo_height()}+50+300');pump()
 check('late native window reposition is clamped back into the work area',app.potion_win.winfo_y()+app.potion_win.winfo_height()<=610)
 app.potion_win.destroy();app.potion_win=None;pump()
 check('dialog scrolling never adds a global wheel binding',root.bind_all('<MouseWheel>')==global_wheel)
 check('UI changes preserve session reader worker and paused capture',app.session is session and app.reader is reader and app._worker_thread is worker and not app.capture_enabled.is_set())
 check('no callback errors during resize theme change or closing',not errors)
 if errors:print(errors)
finally:
 app.close();app._worker_thread.join(3)
 if app.potion_service.thread:app.potion_service.thread.join(3)
print('ALL PASSED' if not failures else f'{failures} FAILED');sys.exit(bool(failures))
