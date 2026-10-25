"""Fresh inventory geometry without requiring a recognized mesos amount.

Real inventory-field crops plus synthetic recognition scenes; no live capture.
"""
import os,sys,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maple_exp as m
from potion_recognition import CountFont,Detector,AutoSelection,inventory_region
from potion_tracking import PotionService
from test_auto_potions import inventory,count_image,ASSETS
ROOT=Path(__file__).resolve().parents[1]
PARTS=json.loads((ROOT/'tests/frames/screen_parts.json').read_text())['inventory']

class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.reader=m.ScreenReader(m.DigitTemplates.load())
        self.reader.mesos_digits=m.MesosDigits(path=Path(tempfile.mkdtemp())/'digits.npz')
        self.reader.mesos_box=(100,500,150,12)
        self.reader.gh=9
        self.reader.two_boxes=False
        self.reader.mesos_covered=False
    def reading(self,amount=None,image=None):
        return m.Reading('test',mesos=amount,mesos_image=image)
    def test_current_amount_still_anchors(self):
        self.assertEqual(self.reader._potion_inventory(self.reading(100)),self.reader.mesos_box)
    def test_zero_mesos_still_anchors(self):
        self.assertEqual(self.reader._potion_inventory(self.reading(0)),self.reader.mesos_box)
    def test_cached_location_without_fresh_image_never_anchors(self):
        self.assertIsNone(self.reader._potion_inventory(self.reading()))
    def test_closed_inventory_plain_scene_rejected(self):
        self.assertIsNone(self.reader._potion_inventory(self.reading(image=np.full((36,198,3),120,np.uint8))))
    def test_random_scene_rejected(self):
        self.assertIsNone(self.reader._potion_inventory(self.reading(image=np.random.default_rng(1).integers(0,255,(36,198,3),dtype=np.uint8))))
    def test_storage_or_trade_second_field_rejected(self):
        self.reader.two_boxes=True
        self.assertIsNone(self.reader._potion_inventory(self.reading(100)))
    def test_covered_inventory_rejected(self):
        self.reader.mesos_covered=True
        self.assertIsNone(self.reader._potion_inventory(self.reading(100)))
    def test_missing_geometry_rejected(self):
        self.reader.mesos_box=None
        self.assertIsNone(self.reader._potion_inventory(self.reading(100)))
    def test_wrong_sized_field_rejected(self):
        with patch.object(m,'find_mesos_fields',return_value=[(0,0,60,8)]):
            self.assertIsNone(self.reader._potion_inventory(self.reading(image=np.zeros((36,198,3),np.uint8))))
    def test_multiple_fresh_fields_rejected(self):
        with patch.object(m,'find_mesos_fields',return_value=[(0,0,150,12),(0,20,150,12)]):
            self.assertIsNone(self.reader._potion_inventory(self.reading(image=np.zeros((60,198,3),np.uint8))))
    def test_real_field_at_three_sizes_survives_unrecognized_amount(self):
        for name,info in PARTS.items():
            with self.subTest(name=name):
                full=cv2.imread(str(ROOT/'tests/frames'/name))
                x,y,w,h=info['box'];self.reader.gh=info['gh'];self.reader.mesos_box=(x,y,w,h)
                # Same in-memory crop shape as _read_mesos, clipped to the image.
                image=full[max(0,y-h):min(full.shape[0],y+2*h),max(0,x-2*h):min(full.shape[1],x+w+2*h)]
                self.assertEqual(self.reader._potion_inventory(self.reading(image=image)),(x,y,w,h))
    def test_temporarily_missing_amount_does_not_force_gap(self):
        name,info=next(iter(PARTS.items()));full=cv2.imread(str(ROOT/'tests/frames'/name))
        x,y,w,h=info['box'];self.reader.gh=info['gh'];self.reader.mesos_box=(x,y,w,h)
        image=full[max(0,y-h):y+2*h,max(0,x-2*h):x+w+2*h]
        for amount in [None,12345,None,None,12346]:
            self.assertEqual(self.reader._potion_inventory(self.reading(amount,image)),(x,y,w,h))

class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector=Detector(ASSETS);cls.font=CountFont(ASSETS)
    def test_subnative_known_wrong_200_is_rejected_not_100(self):
        image=inventory(scale=.75)
        samples=self.detector.samples(image,[AutoSelection('Red Potion',2000000)])
        self.assertEqual(len(samples[0][0]),1)
        box,crop=samples[0][0][0]
        self.assertIsNone(self.font.read(crop,box[2]))
    def test_subnative_service_explains_resolution_problem(self):
        svc=PotionService(lambda e:None,ASSETS)
        try:
            result=svc._automatic(inventory(scale=.75),(0,0,165,172),[AutoSelection('Red Potion',2000000)],None,1,0)
            self.assertEqual(result,[(None,'Potion counts too small — enlarge the game UI')])
        finally:svc.close()
    def test_fractional_windows_scales_keep_correct_counts(self):
        selected=[AutoSelection('Red Potion',2000000),AutoSelection('Lemon',2010004)]
        for scale in [1,1.25,1.5,1.75,2,2.25,2.5,3]:
            with self.subTest(scale=scale):
                samples=self.detector.samples(inventory(scale=scale),selected)
                values=[[self.font.read(im,box[2]) for box,im in stacks] for stacks,_ in samples]
                self.assertEqual(values,[[200],[38,100]])

if __name__=='__main__':unittest.main()
