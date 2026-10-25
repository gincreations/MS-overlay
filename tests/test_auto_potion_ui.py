"""Main-screen item choice, restart persistence and privacy boundaries."""
import os,sys,tempfile,json,traceback
from pathlib import Path
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
failures=0

def check(name,ok):
 global failures
 print(('PASS ' if ok else 'FAIL ')+name,flush=True);failures+=not ok

# Existing 0.1.6 configuration has numeric overrides but no hidden/default mode field.
m.CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
m.CONFIG_PATH.write_text(json.dumps({'potion_prices':{'2000006':4000}}))
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load());errors=[]
root.report_callback_exception=lambda *e:errors.append(''.join(traceback.format_exception(*e)))
try:
 root.update();session=app.session
 check('fresh install has no potion capture hook or recognition thread',app.reader.potion_capture is None and app.potion_service.thread is None)
 check("legacy numeric overrides survive loading new defaults",app.cfg["potion_prices"]["2000006"]==4000 and app.cfg["potion_price_hidden"]==[])
 check('Potions button visible without enabling tracking',app.view.potions_btn.winfo_viewable() and not app.capture_enabled.is_set())
 app.view.cb['potions']();root.update()
 check('opening optional panel does not configure recognition',app.reader.potion_capture is None and not app.potion_service.selections)
 check('main-screen action opens item panel',app.potion_win.winfo_viewable())
 check('21 named items plus Off; no manual drawing control',len(app.potion_win.choices)==22 and 'Lemon' in app.potion_win.choices)
 box=app.potion_win.selectors[0];box.set('Red Potion');box.event_generate('<<ComboboxSelected>>');root.update()
 check('selection enables potion-only capture hook',app.reader.potion_capture is not None)
 check('selecting Red Potion configures recognition directly',app.potion_slots[0].item_id==2000000 and app.potion_picker is None)
 check('selector immediately displays the selected item price',app.potion_win.price_vars[0].get()=='50')
 check('Red Potion automatically uses NPC buy price, not sell value',app.potion_price(0)==50 and 'Using NPC reference' in app.potion_price_source(0))
 check('choice alone never starts capture',not app.capture_enabled.is_set() and app.session is session)
 app.select_potion(1,2010004);root.update()
 check('Lemon and Red Potion appear on main overlay',all(s in app.view.potions_label.cget('text') for s in ['Lemon','Red Potion']))
 app.select_potion(1,2000000)
 check('duplicate item choice cannot double count',app.potion_slots[1].item_id==2010004)
 cfg=json.loads(m.CONFIG_PATH.read_text())
 check('only catalog ids/names persisted, not captured pixels',cfg['potion_items']==[2000000,2010004] and not any(k in cfg for k in ['potion_box','potion_image','potion_slots']))
 app.set_compact(True);root.update();check('Potions shortcut available in compact mode',app.view.potions_btn.winfo_viewable())
 for mode in ['light','dark']:
  app.set_theme(mode);root.update();check(mode+' mode retains selections and shortcut',app.potion_slots[0].item_id==2000000 and app.view.potions_btn.winfo_viewable())
 app.open_potions();root.update();panel=app.potion_win
 app.potion_usage[0].used=30;app.potion_usage[0].seconds=120
 gen=app.potion_generation
 panel.price_vars[0].set('50');panel.save_price(0);root.update()
 check('price shows session cost and observed cost per hour',all(t in app.potion_text(0) for t in ['1,500 mesos','45,000 mesos/hr']))
 check('saving price leaves tracking state unchanged',app.potion_generation==gen and app.potion_usage[0].used==30 and app.session is session)
 panel.price_vars[0].set('-5');panel.save_price(0)
 check('invalid price does not replace saved price',app.potion_price(0)==50 and 'whole meso' in panel.price_message.get())
 panel.price_vars[0].set('1,200');panel.refresh()
 check('periodic refresh preserves unfinished price entry',panel.price_vars[0].get()=='1,200')
 panel.save_price(0);check('comma price is saved as a whole number',app.potion_price(0)==1200)
 app.set_potion_price(1,'0');check('zero explicitly displays free costs','Est. cost: 0 mesos' in app.potion_text(1))
 app.set_potion_price(1,'');check('blank removes costs without disabling tracking',app.potion_price(1) is None and app.potion_slots[1] is not None and 'Est. cost' not in app.potion_text(1))
 app.select_potion(0,2000003);panel.refresh()
 check('switching items does not reuse another item price',panel.price_vars[0].get()=='220' and app.potion_price(0)==220)
 app.select_potion(0,2000000);panel.refresh()
 check('returning to an item restores its own price',panel.price_vars[0].get()=='1,200' and app.potion_price(0)==1200)
 check('custom price label distinguishes default', 'Your paid / average price' in app.potion_price_source(0))
 panel.use_npc(0)
 check('Use NPC removes override and restores price',app.potion_price(0)==50 and '2000000' not in app.cfg['potion_prices'] and panel.price_vars[0].get()=='50')
 app.set_potion_price(0,'')
 check('blank explicitly hides default-priced item',app.potion_price(0) is None and '2000000' in app.cfg['potion_price_hidden'])
 panel.use_npc(0)
 check('Use NPC clears hidden state without starting capture',app.potion_price(0)==50 and '2000000' not in app.cfg['potion_price_hidden'] and not app.capture_enabled.is_set())
 app.select_potion(0,2000005);panel.refresh()
 check('no recorded NPC seller stays unknown with disabled default button',app.potion_price(0) is None and not panel.npc_buttons[0]._enabled and 'No NPC seller recorded' in app.potion_price_source(0))
 app.set_potion_price(0,'2,400');panel.refresh()
 check('manual average works for an item without NPC listing',app.potion_price(0)==2400)
 panel.use_npc(0)
 check('unavailable default cannot erase manual price',app.potion_price(0)==2400 and 'No NPC price' in panel.price_message.get())
 app.select_potion(0,2000004);panel.refresh()
 check('limited-stock Elixir reference clearly shows restriction',app.potion_price(0)==3000 and 'Citizen of Honor' in panel.price_sources[0].cget('text') and 'no refill' in panel.price_sources[0].cget('text'))
 app.select_potion(0,2022003);panel.refresh()
 check('variable shop prices are visible',app.potion_price(0)==1000 and '1,800' in panel.price_sources[0].cget('text'))
 app.select_potion(0,2000000);app.set_potion_price(0,'1200');panel.refresh()
 check('no Tk callback errors',not errors)
finally:
 app.close();app._worker_thread.join(3)
 if app.potion_service.thread:app.potion_service.thread.join(3)
root=m.tk.Tk();app=m.App(root,m.DigitTemplates.load())
try:
 root.update();check('restart restores choices automatically', [s.item_id for s in app.potion_slots]==[2000000,2010004])
 check('restart restores explicit hidden state', '2010004' in app.cfg['potion_price_hidden'])
 check('restart restores per-item prices',app.potion_price(0)==1200 and app.potion_price(1) is None)
 check('restart neither starts capture nor invents previous usage',not app.capture_enabled.is_set() and all(u.used==0 and u.value is None for u in app.potion_usage))
 app.remove_potion(0);app.remove_potion(1);root.update()
 check('Off disconnects potion capture and recognition requests',app.reader.potion_capture is None and not app.potion_service.selections)
 check('Off persists and hides the unused readout',m.load_config()['potion_items']==[None,None] and not app.view.potions_label.winfo_viewable())
finally:
 app.close();app._worker_thread.join(3)
 if app.potion_service.thread:app.potion_service.thread.join(3)
print('ALL PASSED' if not failures else f'{failures} FAILED');sys.exit(bool(failures))
