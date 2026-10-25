"""Drive the integrated UI with synthetic stats; no desktop/game capture or clipboard writes."""
import os,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp(prefix='maple-feature-ui-')
import maple_exp as m

class FeatureUITests(unittest.TestCase):
 def test_pq_share_diagnostics_and_layout(self):
  m.save_config({**m.DEFAULTS,'hotkeys_on':False})
  root=m.tk.Tk();errors=[]
  with patch.object(m.App,'_worker',lambda self:None):app=m.App(root,m.DigitTemplates.load())
  root.report_callback_exception=lambda *args:errors.append(args)
  try:
   self.assertFalse(app.pq_mode);app.toggle_pq();self.assertTrue(app.session.pq);self.assertEqual(app._log_map(),m.PQ_MAP)
   self.assertFalse(app.capture_enabled.is_set())
   t=app.tracker;t._accum=60;t.gained=2000;t.req=95700;t.exp=12000;t.pct=12000/95700*100;app.level=30
   with patch.object(m.PLATFORM,'copy_image',return_value=True) as copy:
    for theme in ['dark','light']:
     app.set_theme(theme)
     for scale in [60,100,200]:
      app.cfg['ui_scale']=scale;app._apply_ui_scale();root.update()
      self.assertTrue(app.view.share_btn.winfo_exists());app.share_card();root.update()
      w=app.card_win;w.scroll.screen_bounds=lambda:(0,0,800,600);w.scroll.fit();root.update()
      self.assertLessEqual(w.winfo_height(),500);self.assertLessEqual(w.winfo_width(),752)
      self.assertTrue((m.DATA_DIR/'share-card.png').exists());w.destroy()
    self.assertEqual(copy.call_count,6)
   m.DIAGNOSTICS.activity('Ready')
   with patch.object(m.PLATFORM,'show_file'),patch.object(m.messagebox,'showinfo'):
    result=app.save_logs()
   with zipfile.ZipFile(result) as z:
    self.assertIn('diagnostic-details.txt',z.namelist());self.assertNotIn('share-card.png',z.namelist())
   app.toggle_pq();self.assertFalse(app.session.pq);self.assertEqual(app.session.idle_gap,15)
   self.assertFalse(app.capture_enabled.is_set());self.assertFalse(errors,errors)
  finally:app.close()
if __name__=='__main__':unittest.main()
