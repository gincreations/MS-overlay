"""Real UI tests for custom colors, persistence, cancellation and active-session continuity."""
import os,sys,tempfile,traceback,json
from pathlib import Path
DATA=Path(tempfile.mkdtemp())
os.environ['MAPLE_EXP_DATA']=str(DATA)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
import ui_palette
from PIL import ImageTk
failures=0

def check(name,ok):
 global failures
 print(('PASS ' if ok else 'FAIL ')+name,flush=True);failures+=not ok

m.save_config({**m.DEFAULTS,'hotkeys_on':False,'colors':{'dark':{'exp':'#FF00AA','meso':'red','eta':123,'unknown':'#111111'},'light':[]}})
cfg=m.load_config()
check('invalid colors and unknown keys are discarded',cfg['colors']=={'dark':{'exp':'#ff00aa'},'light':{}})
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load());errors=[]
root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
try:
 root.update()
 session,reader,worker=app.session,app.reader,app._worker_thread
 app.session.on=True;app.tracker.gained=54321;app.meso.gained=987
 # Keep the synthetic farming rate present if the periodic display refresh
 # runs while inspecting rendered glyphs; an empty tracker would erase them.
 app.tracker.rate=lambda:123456.0
 app.tracker.rolling_rate=lambda:123456.0
 app.open_settings();app.open_colors();root.update();d=app.color_win
 check('editor opens without starting capture',d.winfo_viewable() and not app.capture_enabled.is_set())
 check('editor fits vertically at normal size',d.winfo_reqheight()<root.winfo_screenheight())
 original=json.loads(m.CONFIG_PATH.read_text())['colors']
 d.variables['exp'].set('#');root.update()
 check('incomplete hex disables saving',not d.save_button._enabled)
 d.save();check('invalid save leaves editor open',d.winfo_exists())
 d.variables['exp'].set('#12abef');d.variables['meso'].set('#88e4b4');d.variables['eta'].set('#ff9ecb');d.variables['progress'].set('#ab45cd');root.update()
 check('preview uses exact entered EXP color',d.preview.t.colors['exp']=='#12abef')
 check('preview does not change saved settings',json.loads(m.CONFIG_PATH.read_text())['colors']==original)
 check('preview does not change live overlay',app.theme.colors['exp']=='#ff00aa')
 d._choose_native=lambda initial,title:''
 d.pick('exp');check('cancelled color picker preserves draft',d.variables['exp'].get()=='#12abef')
 d._choose_native=lambda initial,title:'#33ccaa'
 d.pick('exp');check('color picker selection updates draft',d.variables['exp'].get()=='#33ccaa')
 d.variables['exp'].set('#12abef');d.save();root.update()
 check('save closes editor',not d.winfo_exists())
 colors={'exp':'#12abef','meso':'#88e4b4','eta':'#ff9ecb','progress':'#ab45cd'}
 check('all four colors persist',m.load_config()['colors']['dark']==colors)
 app.view.show(rate='123,456',mesos='12,345',eta='Level in 42 min',pct=62.5)
 root.update();h=app.view.hero
 glyph=ImageTk.getimage(next(v for k,v in h._gphotos.items() if k[1]))
 target=(0x12,0xab,0xef)
 check('rendered EXP glyph contains chosen RGB pixels',any(tuple(pixel[:3])==target and pixel[3]>200 for pixel in glyph.getdata()))
 check('mesos tile uses chosen color',app.view.tiles['Mesos / hr'].itemcget(app.view.tiles['Mesos / hr']._v,'fill')==colors['meso'])
 check('time-to-level uses chosen color',h.itemcget(h._eta,'fill')==colors['eta'])
 bar=app.theme.gfx.bar(200,8,0.6,fill_color=colors['progress'])
 check('progress bar renders chosen RGB',bar.getpixel((50,10))[:3]==(0xab,0x45,0xcd))
 app.set_compact(True);root.update()
 check('compact mesos uses chosen color',app.view.hero.itemcget(app.view.hero._mval,'fill')==colors['meso'])
 check('session and reader objects survive save',app.session is session and app.reader is reader and app._worker_thread is worker)
 check('active run and totals survive save',app.session.on and app.tracker.gained==54321 and app.meso.gained==987)
 check('saving colors does not enable capture',not app.capture_enabled.is_set())
 app.set_theme('light');root.update()
 check('dark colors do not overwrite light defaults',app.theme.colors=={})
 app.open_colors();d=app.color_win;d.use_preset('Ocean');root.update()
 check('light preset is readable on light cards',ui_palette.contrast_ratio(d.t.colors['exp'],'#edf1f7')>=3)
 d.save();root.update();light=dict(app.theme.colors)
 app.set_theme('dark');root.update()
 check('returning to dark restores its custom colors',app.theme.colors==colors)
 app.open_colors();d=app.color_win;d.use_preset('Rose');d.destroy();root.update()
 check('cancel leaves saved/live colors unchanged',app.theme.colors==colors and m.load_config()['colors']['dark']==colors)
 app.open_colors();d=app.color_win;d.use_preset(None);d.save();root.update()
 check('theme defaults clears current override',app.theme.colors=={} and m.load_config()['colors']['dark']=={})
 check('reset keeps other theme colors',m.load_config()['colors']['light']==light)
 app.open_colors();d=app.color_win;d.variables['exp'].set('#13151b');root.update()
 check('low contrast is explained but allowed','Low contrast' in d.feedback.cget('text') and d.save_button._enabled)
 d.destroy();app.cfg['ui_scale']=200;app._apply_ui_scale();app.open_colors();root.update()
 check('editor remains on screen at 200% overlay size',app.color_win.winfo_reqheight()<root.winfo_screenheight())
 app.color_win.destroy();app.set_theme('light');root.update()
 check('no Tk callback errors',not errors)
 if errors:print(errors)
finally:
 app.close();app._worker_thread.join(timeout=3)
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load())
try:
 root.update();check('restart restores saved theme and custom colors',app.cfg['theme']=='light' and app.theme.colors==light)
finally:
 app.close();app._worker_thread.join(timeout=3)
print('ALL PASSED' if not failures else f'{failures} FAILED');sys.exit(bool(failures))
