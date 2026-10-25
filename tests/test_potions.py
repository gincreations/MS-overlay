"""Potion estimator and capture boundaries with generated images, never live screens."""
import os,sys,tempfile,time,unittest,threading
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
import numpy as np
import cv2
from potion_tracking import Selection, Usage, PotionService, read_count, clean_name
from privacy_guard import GameCapture, CaptureBlocked


def fixture():
    frame=np.full((180,240,3),190,np.uint8)
    cv2.rectangle(frame,(23,24),(45,54),(220,50,20),-1)
    cv2.circle(frame,(35,39),8,(60,200,240),-1)
    cv2.rectangle(frame,(37,59),(78,78),(20,20,20),-1)
    cv2.putText(frame,'200',(39,74),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
    return frame


def selection():
    return Selection.make('Blue Potion',fixture(),(20,20,64,64),(16,38,44,23))


class UsageTests(unittest.TestCase):
    def run_counts(self,values):
        u=Usage()
        for i,n in enumerate(values):u.observe(n,i*3)
        return u
    def test_decreasing_counts_confirm_without_needing_idle(self):
        u=self.run_counts([200,199,198,197,196,195,194])
        self.assertEqual((u.value,u.used,u.seconds),(195,5,15))
        self.assertEqual(u.per_minute(),20)
    def test_initial_baseline_not_consumption(self):
        u=self.run_counts([200,199]);self.assertEqual(u.used,0)
    def test_single_ocr_dip_does_not_count(self):
        u=self.run_counts([200,200,20,200,200]);self.assertEqual(u.used,0)
    def test_large_confirmed_drop_requires_resync(self):
        u=self.run_counts([200,200,50,50]);self.assertTrue(u.locked);self.assertEqual(u.used,0)
        u.gap('hidden');self.assertIn('Large drop',u.status)
    def test_refill_excluded(self):
        u=self.run_counts([200,199,198,500,499,498]);self.assertEqual(u.used,2)  # unconfirmed pre-refill drop excluded
    def test_hidden_inventory_excludes_hidden_consumption(self):
        u=self.run_counts([200,199,198]);u.gap();u.observe(100,12);u.observe(99,15)
        self.assertEqual(u.used,1);self.assertEqual(u.value,100)
    def test_long_blind_gap_excluded(self):
        u=self.run_counts([200,199,198]);u.observe(80,40);u.observe(79,43)
        self.assertEqual(u.used,1)
    def test_no_rate_before_enough_observation(self):
        self.assertIsNone(self.run_counts([200,199,198]).per_minute())
    def test_invalid_readings_never_assumed_zero(self):
        u=self.run_counts([200,199,198]);u.observe(None,9)
        self.assertEqual(u.used,1);self.assertIsNone(u.value)
    def test_time_reversal_rebaselines(self):
        u=self.run_counts([200,199,198]);u.observe(197,1);self.assertEqual(u.used,1)
    def test_rate_excludes_hidden_duration(self):
        u=self.run_counts([200,199,198,197,196,195,194]);seconds=u.seconds
        u.gap();u.observe(100,400);u.observe(100,403)
        self.assertEqual(u.seconds,seconds)


class ImageTests(unittest.TestCase):
    def test_icon_change_rejected(self):
        s=selection();self.assertTrue(s.matches(fixture()[20:84,20:84]))
        changed=fixture()[20:84,20:84].copy();changed[:36,:]=(10,240,20)
        self.assertFalse(s.matches(changed))
    def test_digits_do_not_affect_icon_identity(self):
        s=selection();changed=fixture()[20:84,20:84].copy();changed[38:61,16:60]=255
        self.assertTrue(s.matches(changed))
    def test_invalid_regions_rejected(self):
        for box in [(-1,0,64,64),(0,0,999,999),(0,0,2,2)]:
            with self.assertRaises(ValueError):Selection.make('pot',fixture(),box,(0,0,10,10))
    def test_blank_icon_cannot_be_armed(self):
        with self.assertRaises(ValueError):Selection.make('pot',np.full((100,100,3),255,np.uint8),(0,0,64,64),(10,40,40,15))
    def test_name_bounded(self):self.assertEqual(clean_name('x'*100+'\n'),'x'*32)
    def test_ocr_must_agree(self):
        reads=iter(['200','20']);t=SimpleNamespace(read_line=lambda *a:next(reads))
        self.assertIsNone(read_count(fixture()[59:79,37:79],t))
    def test_ocr_rejects_blank_and_non_numeric(self):
        for text in ['', ' ', '1 00','99999','123x','-5']:
            self.assertIsNone(read_count(fixture()[59:79,37:79],SimpleNamespace(read_line=lambda *a:text)))
    def test_ocr_accepts_only_agreed_digits(self):
        self.assertEqual(read_count(fixture()[59:79,37:79],SimpleNamespace(read_line=lambda *a:'200\n')),200)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.service=PotionService(self.events.append)
        self.frame=fixture();self.calls=[]
        def grab(region):
            self.calls.append(region)
            x,y=region['left']-100,region['top']-200
            return self.frame[y:y+region['height'],x:x+region['width']]
        self.raw=SimpleNamespace(grab=grab)
        self.screen=GameCapture(self.raw,lambda:(100,200,240,180),lambda:True)
    def tearDown(self):
        self.service.close()
        if self.service.thread:self.service.thread.join(3)
    def results(self):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and not any(e[0]=="potion_counts" for e in self.events):time.sleep(.01)
        return [e for e in self.events if e[0]=="potion_counts"]
    def test_disabled_has_no_capture(self):
        self.service.capture(self.screen,(100,200,240,180),lambda *a:False,None)
        self.assertFalse(self.calls)
    def test_snapshot_requires_game_capture_guard(self):
        self.service.request_snapshot(1)
        denied=GameCapture(self.raw,lambda:(100,200,240,180),lambda:False)
        with self.assertRaises(CaptureBlocked):self.service.capture(denied,(100,200,240,180),lambda *a:False,None)
        self.assertFalse(self.calls)
    def test_snapshot_is_one_shot_and_cancellable(self):
        self.service.request_snapshot(1);self.service.cancel_snapshot()
        self.service.capture(self.screen,(100,200,240,180),lambda *a:False,None)
        self.assertFalse(self.calls)
        self.service.request_snapshot(2);self.service.capture(self.screen,(100,200,240,180),lambda *a:False,None)
        self.service.capture(self.screen,(100,200,240,180),lambda *a:False,None)
        self.assertEqual(len(self.calls),1)
    def test_resize_does_not_read_another_area(self):
        self.service.configure([selection()])
        self.service.capture(self.screen,(100,200,400,300),lambda *a:False,None)
        self.assertFalse(self.calls);self.assertIn('resized',self.results()[0][1][2][0][1])
    def test_overlay_cover_excludes_sample(self):
        self.service.configure([selection()]);self.service.capture(self.screen,(100,200,240,180),lambda *a:True,None)
        self.assertFalse(self.calls);self.assertIsNone(self.results()[0][1][2][0][0])
    def test_only_selected_game_relative_slot_is_captured(self):
        self.service.configure([selection()])
        with patch('potion_tracking.read_count',return_value=200):
            self.service.capture(self.screen,(100,200,240,180),lambda *a:False,SimpleNamespace(cmd='test'))
            result=self.results()
        self.assertEqual(self.calls,[dict(left=120,top=220,width=64,height=64)])
        self.assertEqual(result[0][1][2][0][0],200)
    def test_old_ocr_result_discarded_after_reconfigure(self):
        gate=threading.Event();started=threading.Event()
        def read(*a):started.set();gate.wait(2);return 200
        self.service.configure([selection()])
        with patch('potion_tracking.read_count',side_effect=read):
            self.service.capture(self.screen,(100,200,240,180),lambda *a:False,SimpleNamespace(cmd='test'))
            self.assertTrue(started.wait(1));self.service.configure([]);gate.set();time.sleep(.1)
        self.assertFalse(self.events)

class PriceTests(unittest.TestCase):
    def test_price_input_and_unknown_vs_free(self):
        from potion_tracking import parse_price
        self.assertIsNone(parse_price(' '));self.assertEqual(parse_price('0'),0)
        self.assertEqual(parse_price('1,200'),1200);self.assertEqual(parse_price(' 500 '),500)
    def test_bad_prices_rejected(self):
        from potion_tracking import parse_price
        for value in ['-1','1.5','1e3','1,2','1 200','True','1,000,000,001']:
            with self.assertRaises(ValueError):parse_price(value)
    def test_saved_price_validation(self):
        from potion_tracking import normalize_prices
        self.assertEqual(normalize_prices({'2000000':500,'2000001':True,'2000002':-1,'2000003':1.5,'abc':10}),{'2000000':500})
        self.assertEqual(normalize_prices([]),{})
    def test_cost_math(self):
        from potion_tracking import estimated_cost
        u=Usage();u.used=30;u.seconds=120
        self.assertEqual(estimated_cost(u,50),(1500,45000))
    def test_cost_rate_waits_for_observed_time(self):
        from potion_tracking import estimated_cost
        u=Usage();u.used=2;u.seconds=12
        self.assertEqual(estimated_cost(u,50),(100,None))
        self.assertEqual(estimated_cost(u,None),(None,None))
        u.seconds=15;self.assertEqual(estimated_cost(u,0),(0,0))
    def test_gap_does_not_dilute_cost_rate(self):
        from potion_tracking import estimated_cost
        u=Usage();u.used=30;u.seconds=120;u.gap()
        self.assertEqual(estimated_cost(u,50),(1500,45000))
    def test_repricing_does_not_change_usage(self):
        from potion_tracking import estimated_cost
        u=Usage();u.used=30;u.seconds=120
        self.assertEqual(estimated_cost(u,100),(3000,90000));self.assertEqual((u.used,u.seconds),(30,120))

class NPCPriceTests(unittest.TestCase):
    def test_hidden_config_validation(self):
        from potion_tracking import normalize_hidden_prices
        self.assertEqual(normalize_hidden_prices(['2000000','2000000',True,2000001,'abc',None]),['2000000'])
        self.assertEqual(normalize_hidden_prices({'2000000':True}),[])
    def test_npc_catalog_purchase_values_and_manual_fallbacks(self):
        import json
        from pathlib import Path
        rows=json.loads((Path(__file__).resolve().parents[1]/'assets/consumables/catalog.json').read_text())
        prices={r['id']:r['npc_price'] for r in rows}
        self.assertEqual({i:v for i,v in prices.items() if v is not None},
                         {2000000:50,2000001:150,2000002:350,2000003:220,2000004:3000,
                          2010000:20,2010002:30,2010003:50,2010004:150,2020004:350,
                          2020005:180,2020009:540,2020010:1260,2022000:1120,2022003:1000})
        self.assertEqual({i for i,v in prices.items() if v is None},{2000005,2000006,2001000,2001001,2020013,2020014})
        self.assertTrue(all(r['npc_note'] for r in rows))

if __name__=='__main__':unittest.main()
