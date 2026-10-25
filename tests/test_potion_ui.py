"""UI/lifecycle integration using a generated inventory image, never desktop capture."""
import os,sys,tempfile,time,json,traceback
from pathlib import Path
from types import SimpleNamespace
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import maple_exp as m
from test_potions import fixture, selection
from potion_ui import PotionPicker
failures=0

def check(name,ok):
 global failures
 print(('PASS ' if ok else 'FAIL ')+name,flush=True);failures+=not ok

root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load());errors=[]
root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
try:
 root.update();check('potion row hidden when not configured',not app.view.potions_label.winfo_viewable())
 session,worker=app.session,app._worker_thread
 app.open_potions();root.update()
 check('panel opens without enabling capture',app.potion_win.winfo_viewable() and not app.capture_enabled.is_set())
 check('panel fits screen',app.potion_win.winfo_reqheight()<root.winfo_screenheight())
 app.potion_win.destroy();closed=[];saved=[]
 picker=PotionPicker(root,fixture(),'Blue Potion',saved.append,lambda:closed.append(True));root.update()
 def drag(box):
  x,y,w,h=box;scale=picker.scale
  picker.press(SimpleNamespace(x=x*scale,y=y*scale))
  picker.release(SimpleNamespace(x=(x+w)*scale,y=(y+h)*scale))
 drag((20,20,64,64));root.update();check('first drag selects slot and zooms it',picker.box==(20,20,64,64) and picker.digits is None)
 drag((16,38,44,23));root.update()
 check('second drag selects count and enables save',picker.digits==(16,38,44,23) and not picker.save_button.instate(['disabled']))
 picker.save();root.update()
 check('save returns memory-only selection and releases snapshot',len(saved)==1 and picker.frame is None and closed==[True])
 app._save_potion(0,saved[0]);root.update()
 check('selected potion appears on overlay',app.view.potions_label.winfo_viewable() and 'Blue Potion' in app.view.potions_label.cget('text'))
 cfg=json.loads(m.CONFIG_PATH.read_text())
 check('only names persisted, no screenshot/region/reference data',cfg['potion_names'][0]=='Blue Potion' and not any(k in cfg for k in ['potion_slots','potion_reference','potion_image','potion_box']))
 check('selection does not start capture or reset EXP',not app.capture_enabled.is_set() and app.session is session and app._worker_thread is worker)
 app.capture_enabled.set();now=time.monotonic();gen=app.potion_generation
 app._potion_counts(gen,now,[(200,'')]);app._potion_counts(gen,now+3,[(199,'')]);app._potion_counts(gen,now+6,[(198,'')])
 check('matching generation produces estimated use',app.potion_usage[0].used==1)
 app.capture_enabled.clear();before=app.potion_usage[0].used
 app._potion_counts(gen,now+9,[(197,'')]);check('paused capture ignores queued counts',app.potion_usage[0].used==before)
 app.capture_enabled.set();app._potion_counts(gen-1,now+9,[(197,'')]);check('stale generation ignored',app.potion_usage[0].used==before)
 app.potion_after=now+10;app._potion_counts(gen,now+9,[(197,'')]);check('pre-pause OCR timestamp ignored',app.potion_usage[0].used==before)
 app.potion_after=0;app._potion_gaps(gen,now+12,[(0,'Inventory hidden')])
 app._potion_counts(gen,now+11,[(190,'')]);check('hidden-frame boundary rejects older in-flight OCR',app.potion_usage[0].value is None and app.potion_usage[0].used==before)
 app.capture_enabled.clear();app.set_compact(True);root.update();check('potion row remains available in compact mode',app.view.potions_label.winfo_viewable())
 for mode in ['light','dark']:
  app.set_theme(mode);root.update();check(mode+' mode preserves potion selection and total',app.potion_slots[0] is saved[0] and app.potion_usage[0].used==1)
 app.potion_usage[0].locked=True;app.reset_potion(0)
 check('resync clears baseline/lock but preserves total',app.potion_usage[0].value is None and not app.potion_usage[0].locked and app.potion_usage[0].used==1)
 app.reset();check('global reset clears potion totals and leaves EXP reset working',app.potion_usage[0].used==0 and not app.capture_enabled.is_set())
 app.remove_potion(0);root.update();check('removing last stack hides potion row',not app.view.potions_label.winfo_viewable())
 app.potion_requested=0;app.potion_token=44;app._potion_snapshot(43,fixture())
 check('cancelled snapshot never opens picker',app.potion_picker is None)
 check('no callbacks raised',not errors)
 if errors:print(errors)
finally:
 app.close();worker.join(3)
 if app.potion_service.thread:app.potion_service.thread.join(5)
check('potion OCR worker stops on close',not app.potion_service.thread or not app.potion_service.thread.is_alive())
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load())
try:
 root.update();check('restart remembers name but requires fresh selection',app.cfg['potion_names'][0]=='Blue Potion' and app.potion_slots==[None,None])
finally:
 app.close();app._worker_thread.join(3)
print('ALL PASSED' if not failures else f'{failures} FAILED');sys.exit(bool(failures))
