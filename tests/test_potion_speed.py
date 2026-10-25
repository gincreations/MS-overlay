"""Fresh-frame responsiveness without weakening count/consumption confirmation."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from potion_recognition import Detector,CountFont,AutoSelection
from potion_tracking import PotionService,Usage
from test_auto_potions import inventory,count_image,ASSETS

class SpeedTests(unittest.TestCase):
    def test_identical_fresh_pixels_skip_rematching_but_changed_icon_does_not(self):
        d=Detector(ASSETS)
        red=inventory({(0,0):(2000000,200)})[12:46,12:48].copy()
        orange=inventory({(0,0):(2000001,200)})[12:46,12:48].copy()
        with patch.object(d,'_identify',wraps=d._identify) as match:
            self.assertEqual(d.identify(red),2000000)
            self.assertEqual(d.identify(red.copy()),2000000)
            self.assertEqual(match.call_count,1)
            self.assertEqual(d.identify(orange),2000001)
            self.assertEqual(match.call_count,2)
            self.assertIsNone(d.identify(np.full_like(red,225)))
    def test_new_digits_in_same_slot_are_read_and_blank_is_not_old_stock(self):
        f=CountFont(ASSETS);a,p=count_image('200');b,_=count_image('199')
        with patch.object(f,'_read',wraps=f._read) as read:
            self.assertEqual(f.read(a,p),200)
            self.assertEqual(f.read(a.copy(),p),200)
            self.assertEqual(read.call_count,1)
            self.assertEqual(f.read(b,p),199)
            self.assertEqual(read.call_count,2)
            self.assertIsNone(f.read(np.full_like(a,225),p))
    def test_subnative_scale_stays_rejected_after_cached_valid_read(self):
        f=CountFont(ASSETS);a,p=count_image('200')
        self.assertEqual(f.read(a,p),200)
        self.assertIsNone(f.read(a,27))
    def test_identity_cache_is_bounded(self):
        d=Detector(ASSETS)
        with patch.object(d,'_identify',return_value=None) as read:
            for i in range(140):d.identify(np.full((34,36,3),i,np.uint8))
            self.assertLessEqual(len(d.identity_cache),128)
            d.identify(np.zeros((34,36,3),np.uint8))
            self.assertEqual(read.call_count,141) # evicted pixels are rechecked
    def test_count_cache_is_bounded(self):
        f=CountFont(ASSETS)
        with patch.object(f,'_read',return_value=None) as read:
            for i in range(140):f.read(np.full((15,33,3),i,np.uint8),36)
            self.assertLessEqual(len(f.count_cache),128)
            f.read(np.zeros((15,33,3),np.uint8),36)
            self.assertEqual(read.call_count,141)
    def test_each_normal_capture_is_sampled_without_extra_capture_thread(self):
        calls=[];jobs=[];svc=PotionService(lambda e:None,ASSETS)
        svc.selections=(AutoSelection('Orange Potion',2000001),)
        screen=SimpleNamespace(grab=lambda r:(calls.append(r) or np.zeros((r['height'],r['width'],4),np.uint8)))
        try:
            with patch.object(svc,'_enqueue',side_effect=jobs.append):
                for now in [0,0.5,1.5,3.0]:
                    with patch('potion_tracking.time.monotonic',return_value=now):
                        svc.capture(screen,(0,0,400,300),lambda *a:False,None,inventory=(40,250,130,12))
            self.assertEqual([j[1] for j in jobs],[0,1.5,3.0])
            self.assertEqual(len(calls),3)
            self.assertIsNone(svc.thread)
        finally:svc.close()
    def test_changed_stack_confirmed_on_next_normal_sample(self):
        svc=PotionService(lambda e:None,ASSETS);u=Usage()
        try:
            for now,count in [(0,100),(1.5,100),(3,99),(4.5,99)]:
                frame=inventory({(0,0):(2000001,count)},slot_color=(213,223,225))
                result=svc._automatic(frame,(0,0,220,230),[AutoSelection('Orange Potion',2000001)],None,1,now)
                self.assertEqual(result,[(count,'')]);u.observe(result[0][0],now)
                if now==3:self.assertEqual((u.value,u.used),(100,0))
            self.assertEqual((u.value,u.used),(99,1))
        finally:svc.close()
    def test_faster_samples_still_reject_a_single_bad_dip(self):
        u=Usage()
        for now,count in [(0,100),(1.5,100),(3,95),(4.5,100),(6,100)]:u.observe(count,now)
        self.assertEqual(u.used,0);self.assertEqual(u.value,100)
    def test_faster_sampling_uses_elapsed_seconds_for_usage_rate(self):
        u=Usage()
        for i in range(41):u.observe(200-i,i*1.5)
        self.assertEqual((u.used,u.seconds,u.per_minute()),(39,58.5,40))
        u.observe(159,61.5)
        self.assertEqual((u.value,u.used,u.seconds,u.per_minute()),(160,40,60,40))
    def test_missing_inventory_still_clears_stock_after_cache_warmup(self):
        svc=PotionService(lambda e:None,ASSETS);selected=[AutoSelection('Orange Potion',2000001)]
        try:
            frame=inventory({(0,0):(2000001,100)})
            self.assertEqual(svc._automatic(frame,(0,0,220,230),selected,None,1,0),[(100,'')])
            self.assertIsNone(svc._automatic(None,None,selected,None,1,1.5)[0][0])
            self.assertEqual(svc.identities,{})
        finally:svc.close()

if __name__=='__main__':unittest.main()
