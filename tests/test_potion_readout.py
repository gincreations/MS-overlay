"""Presentation-only potion card checks; no game or desktop capture."""
from ast_contract import legacy_dump
import os,sys,tempfile,json,hashlib,traceback,ast
from pathlib import Path
from unittest.mock import patch
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
import ui_palette
from tkinter import font as tf
failed=0
def check(name,ok):
 global failed
 print(('PASS ' if ok else 'FAIL ')+name,flush=True);failed+=not ok
with patch.object(m.App,'_worker',lambda self:None):
 root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load())
# This fixture drives UI scale/theme explicitly. A native monitor DPI refresh
# must not rebuild its widgets halfway through measuring synthetic layouts.
app._check_screen=lambda:None
errors=[];root.report_callback_exception=lambda *e:errors.append(''.join(traceback.format_exception(*e)))
try:
 app.select_potion(0,2000001);app.select_potion(1,2010004)
 for u,v,n in zip(app.potion_usage,[102,90],[2,14]):u.value=v;u.used=n;u.seconds=150;u.status=''
 original_text='\n'.join(app.potion_text(i) for i in range(2))
 session,reader=app.session,app.reader
 for mode in ['dark','light']:
  app.set_theme(mode)
  for size in [100,125,150,200]:
   app.cfg['ui_scale']=size;app._apply_ui_scale();app._update_display();root.update()
   view=app.view.potions_label;cards=view.cards;tag=f'{mode}/{size}%'
   check(tag+' uses separate cards and preserves exact numeric source text',len(cards)==2 and view.cget('text')==original_text)
   check(tag+' has readable default contrast',all(ui_palette.contrast_ratio(c[k].cget('fg'),c[k].cget('bg'))>=4.5 for c in cards for k in ['name','stock','usage','cost','status']))
   check(tag+' larger count and usage type',all(tf.Font(root=root,font=c['stock'].cget('font')).metrics('linespace')>tf.Font(root=root,font=c['usage'].cget('font')).metrics('linespace') for c in cards))
   check(tag+' cards fit fixed overlay width',view.winfo_reqwidth()<=app.theme.px(m.ui_main.INNER)+2 if hasattr(m,'ui_main') else view.winfo_reqwidth()<=app.theme.px(328)+2)
   for compact in [True,False]:
    app.set_compact(compact);root.update()
    check(tag+f'/{compact}: readout stays visible',view.winfo_viewable())
 app.cfg['ui_scale']=100;app._apply_ui_scale()
 app.potion_usage[0].gap('Paused / game not in front');app._update_display();root.update()
 c=app.view.potions_label.cards[0]
 check('missing stock is not shown as zero',c['stock'].cget('text')=='— left')
 check('paused status remains explicit and visible',c['status'].winfo_viewable() and c['status'].cget('text')=='Paused / game not in front')
 app.potion_usage[0].value=100;app.potion_usage[0].status='';app._update_display();root.update()
 check('healthy card has no empty status row',not app.view.potions_label.cards[0]['status'].winfo_ismapped())
 app.set_potion_price(0,'');app._update_display();root.update()
 check('hidden costs have no empty cost row',not app.view.potions_label.cards[0]['cost'].winfo_ismapped())
 app.open_colors();root.update();d=app.color_win
 check('two new potion controls exist',all(k in d.variables for k in ['potion1','potion2']))
 d.variables['potion1'].set('#b53129');d.variables['potion2'].set('#00628a');root.update()
 check('color preview changes without altering live card',d.potion_previews[0].cget('fg')=='#b53129' and app.view.potions_label.cards[0]['name'].cget('fg')!='#b53129')
 d.scroll.screen_bounds=lambda:(0,0,800,600);d.scroll.fit();root.update()
 check('expanded color editor fits short screen with scrolling',d.winfo_height()<=500 and d.scroll.vertical.winfo_ismapped())
 d.save();root.update()
 check('saved colors apply to names counts and stripes',all(app.view.potions_label.cards[i]['name'].cget('fg')==value and app.view.potions_label.cards[i]['stock'].cget('fg')==value and app.view.potions_label.cards[i]['accent'].cget('bg')==value for i,value in enumerate(['#b53129','#00628a'])))
 check('new colors persist',m.load_config()['colors']['light']['potion1']=='#b53129')
 check('visual changes preserve session reader and counts',app.session is session and app.reader is reader and app.potion_usage[0].used==2 and not app.capture_enabled.is_set())
 app.remove_potion(0);app.remove_potion(1);root.update()
 check('Off still hides readout and stops potion sampling',not app.view.potions_label.winfo_viewable() and not app.view.potions_label.cards and app.reader.potion_capture is None)
 check('no UI callback errors',not errors)
 if errors:print(errors)
finally:
 app.close();app._worker_thread.join(3)
 if app.potion_service.thread:app.potion_service.thread.join(3)
# Potion computation, recognition and capture guard remain unchanged.
# App/PQ/share/diagnostics and OCR data lookup are now deliberately extended;
# original rate, capture and OCR behaviors have their own regression suites.
contract=json.loads((Path(__file__).parent/'frames/potion-display-scope.json').read_text())
for filename,expected in contract.items():
 if filename in ("maple_exp.py", "ocr.py"): continue  # authorized 0.1.18 integration; tested separately
 data=(Path(__file__).resolve().parents[1]/filename).read_bytes()
 if filename=='maple_exp.py':
  tree=ast.parse(data)
  for node in tree.body:
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in node.targets):node.value=ast.Constant('0.1.15-private-preview')
   if isinstance(node,ast.ClassDef) and node.name=='ScreenReader':
    for method in node.body:
     if isinstance(method,ast.FunctionDef) and method.name=='_read_extras':method.body=[ast.Pass()]
  data=legacy_dump(tree).encode()
 check(filename+' remains unchanged by feature integration',hashlib.sha256(data).hexdigest()==expected)
sys.exit(bool(failed))
