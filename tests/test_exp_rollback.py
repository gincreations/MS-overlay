"""Prevent the rejected timing adapter/warm-up from returning."""
from ast_contract import legacy_dump
import ast,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
class RollbackTests(unittest.TestCase):
 def test_original_app_delivery_clock_and_display_restored(self):
  tree=ast.parse((Path(__file__).resolve().parents[1]/'maple_exp.py').read_text())
  app=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='App')
  contract=json.loads((Path(__file__).parent/'frames/original-app-rate-contract.json').read_text())
  for name,expected in contract['methods'].items():
   if name in ('_state','_status_for'):  # PQ labels deliberately added; covered by feature UI tests.
    continue
   with self.subTest(name=name):
    method=next(n for n in app.body if isinstance(n,ast.FunctionDef) and n.name==name)
    self.assertEqual(hashlib.sha256(legacy_dump(method).encode()).hexdigest(),expected)
 def test_no_new_adapter_or_freshness_policy(self):
  self.assertFalse(hasattr(m,'FarmingSession'))
  source=(Path(__file__).resolve().parents[1]/'maple_exp.py').read_text()
  self.assertIn('self.session = Session(self.cfg["gap_seconds"])',source)
  self.assertNotIn('captured_reading',source)
 def test_original_ten_second_main_rate(self):
  t=m.ExpTracker();t.gained=200;t._accum=9
  self.assertIsNone(t.rate());t._accum=10
  self.assertEqual(t.rate(),72000)
 def test_original_thirty_second_recent_span(self):
  t=m.ExpTracker();t.samples=m.deque([(0,0),(29,580)])
  self.assertIsNone(t.rolling_rate());t.samples.append((30,600))
  self.assertEqual(t.rolling_rate(),72000)
 def display(self):
  s=m.Session(15);t=s.exp;t.req=95700;t.exp=12000;t.pct=12000/95700*100;t.gained=2000;t._accum=60
  return SimpleNamespace(tracker=t,session=s,level=30,_trend_at=600,_trend=[],meso=s.meso,
   reader=SimpleNamespace(mesos_covered=False),view=Mock(),potion_slots=[],_state=lambda:('paused','Paused'),
   _log_tick=lambda now:None,log_status=Mock(),_log_status_text=lambda now:'',_window_rect=lambda:None)
 def test_original_eta_falls_back_to_session_rate_without_new_warmup(self):
  a=self.display();a.tracker._accum=12;a.tracker.gained=400
  with patch.object(m.time,'monotonic',return_value=12):m.App._update_display(a)
  out=a.view.show.call_args.kwargs
  self.assertEqual(out['rate'],'120,000');self.assertEqual(out['eta'],'Lv 31 in 41 min')
 def test_original_recent_eta_and_stale_display_policy(self):
  a=self.display();a.tracker.samples=m.deque([(0,0),(60,1000)])
  with patch.object(m.time,'monotonic',return_value=600):m.App._update_display(a)
  out=a.view.show.call_args.kwargs
  self.assertEqual(out['rate'],'120,000');self.assertEqual(out['tiles']['Last 5 min'],'60,000')
  self.assertEqual(out['eta'],'Lv 31 in 1 h 23 min')
if __name__=='__main__':unittest.main()
