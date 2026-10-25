"""Inventory relocation using real crops; no desktop capture or rate-policy changes."""
import os,sys,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import cv2,numpy as np
import maple_exp as m
PARTS=json.loads((ROOT/'tests/frames/screen_parts.json').read_text())['inventory']
class Screen:
 def __init__(self,image):
  self.image=image;self.monitors=[dict(left=0,top=0,width=image.shape[1],height=image.shape[0])]
 def grab(self,r):
  a=self.image[r['top']:r['top']+r['height'],r['left']:r['left']+r['width']]
  return np.dstack([a,np.full(a.shape[:2],255,np.uint8)])
class MoveTests(unittest.TestCase):
 def setup_scene(self,name):
  self.info=PARTS[name];self.inv=cv2.imread(str(ROOT/'tests/frames'/name));self.h,self.w=self.inv.shape[:2]
  self.H,self.W=self.h*2+20,self.w*3+20
  self.r=m.ScreenReader(m.DigitTemplates.load());self.r.gh=self.info['gh']
  self.r.mesos_digits=m.MesosDigits(Path(tempfile.mkdtemp())/'digits.npz')
  self.clock=100.;return self.scene(0,0)
 def scene(self,x,y,alpha=1):
  a=np.full((self.H,self.W,3),25,np.uint8)
  a[y:y+self.h,x:x+self.w]=(alpha*self.inv+(1-alpha)*25).astype(np.uint8);return a
 def look(self,im):
  with patch.object(m.time,'monotonic',return_value=self.clock):
   out=self.r._read_extras(Screen(im),(0,0,self.W,self.H),m.Reading('test'))
  self.clock+=m.POLL_SECONDS;return out
 def test_solid_inventory_moves_to_all_corners_and_center_at_three_sizes(self):
  for name in PARTS:
   with self.subTest(name=name):
    self.look(self.setup_scene(name))
    for x,y in [(self.W-self.w,0),(0,self.H-self.h),(self.W-self.w,self.H-self.h),(self.w,self.h//2),(0,0)]:
     scene=self.scene(x,y);got=None
     for _ in range(6):
      out=self.look(scene)
      if out.mesos==self.info['mesos']:
       bx,by,bw,bh=self.info['box']
       if self.r.mesos_box==(x+bx,y+by,bw,bh):got=out;break
     self.assertIsNotNone(got,(name,x,y,self.r.mesos_box))
 def test_transparent_relocation_recovers_within_five_frames(self):
  self.look(self.setup_scene('inventory_gh28.png'))
  scene=self.scene(self.W-self.w-10,self.H-self.h-10,.6)
  found=[]
  for i in range(1,6):
   out=self.look(scene)
   if out.mesos is not None:found.append((i,out.mesos))
  self.assertTrue(found);self.assertEqual(found[0][1],self.info['mesos'])
 def test_two_failed_old_crops_trigger_fresh_search(self):
  self.look(self.setup_scene('inventory_gh11.png'));self.r.next_scan=1000;self.r.next_outline=1000
  blank=np.full((self.H,self.W,3),25,np.uint8)
  self.look(blank);self.assertEqual(self.r.next_scan,1000)
  self.look(blank);self.assertEqual(self.r.next_scan,0);self.assertEqual(self.r.next_outline,0)
 def test_relocation_clears_old_crop_confirmation(self):
  self.look(self.setup_scene('inventory_gh11.png'));self.r.mesos_count=9;self.r.mesos_pending=(123456789,2)
  self.r.mesos_checked=123456789;self.r.next_mesos_check=1000;self.r.next_scan=0
  with patch.object(self.r,'_read_mesos',return_value=(None,None,())):
   self.look(self.scene(self.w,0))
  self.assertEqual(self.r.mesos_pending,(None,0));self.assertIsNone(self.r.mesos_count)
  self.assertIsNone(self.r.mesos_checked);self.assertEqual(self.r.next_mesos_check,0)
 def test_missing_inventory_keeps_outline_backoff(self):
  self.look(self.setup_scene('inventory_gh11.png'));blank=np.full((self.H,self.W,3),25,np.uint8)
  calls=[]
  with patch.object(self.r,'_find_seethrough_box',side_effect=lambda *a:calls.append(self.clock)):
   for _ in range(20):self.look(blank)
  self.assertLessEqual(len(calls),4);self.assertGreaterEqual(len(calls),2)
 def test_second_mesos_field_still_blocks_after_move(self):
  self.look(self.setup_scene('inventory_gh11.png'));self.r.next_scan=0
  scene=self.scene(self.w,0);scene[self.h:self.h*2,0:self.w]=self.inv
  out=self.look(scene)
  self.assertTrue(self.r.two_boxes);self.assertIsNone(self.r.mesos_box);self.assertIsNone(out.mesos)
 def test_overlay_covering_old_location_triggers_relocation_search(self):
  self.look(self.setup_scene('inventory_gh11.png'));bx,by,bw,bh=self.r.mesos_box
  self.r.own_rect=(bx,by,bw,bh);self.r.next_scan=1000;self.r.next_outline=1000
  self.look(self.scene(self.w,0));self.assertEqual(self.r.next_scan,0)
  out=self.look(self.scene(self.w,0));self.assertEqual(out.mesos,self.info['mesos'])
if __name__=='__main__':unittest.main()
