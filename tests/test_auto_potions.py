"""Offline recognition tests using bundled native artwork and generated inventories."""
import sys,unittest,time,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from potion_recognition import Detector,CountFont,AutoSelection,grid_cells,inventory_region
from potion_tracking import PotionService
ASSETS=Path(__file__).resolve().parents[1]/'assets/consumables'


def paste(bg,im,x,y):
    h,w=im.shape[:2];alpha=im[:,:,3:4]/255
    bg[y:y+h,x:x+w]=(im[:,:,:3]*alpha+bg[y:y+h,x:x+w]*(1-alpha)).astype(np.uint8)


def count_image(text,scale=1):
    image=np.full((34,36,3),200,np.uint8);x=1
    for c in text:
        g=cv2.imread(str(ASSETS/'digits'/f'{c}.png'),-1);paste(image,g,x,20);x+=g.shape[1]
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
    h,w=image.shape[:2]
    return image[round(h*.53):round(h*.94),:round(w*.93)],w


def inventory(items=None,scale=1,slot_color=(195,200,200)):
    if items is None:items={(0,0):(2000000,200),(1,1):(2010004,38),(2,1):(2010004,100)}
    frame=np.full((230,220,3),245,np.uint8);d=Detector(ASSETS)
    for row in range(6):
        for col in range(5):
            x,y=12+col*36,12+row*34
            frame[y:y+30,x:x+32]=slot_color
            if (col,row) not in items:continue
            item,count=items[(col,row)];icon=d.icons[item];ox,oy=d.catalog[item]['origin']
            paste(frame,icon,x-ox,y+32-oy)
            xx=x+1
            for c in str(count):
                g=cv2.imread(str(ASSETS/'digits'/f'{c}.png'),-1);paste(frame,g,xx,y+20);xx+=g.shape[1]
    return cv2.resize(frame,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)


class RecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=Detector(ASSETS);cls.font=CountFont(ASSETS)
    def test_catalog_covers_requested_food(self):
        self.assertEqual(len(self.d.catalog),21)
        self.assertEqual([self.d.catalog[i]['name'] for i in [2000000,2000003,2010004]],['Red Potion','Blue Potion','Lemon'])
    def test_original_font_digits_and_different_lengths(self):
        for text in ['0','1','8','9','27','38','100','200','999','1234']:
            for scale in [1,1.5,2,3]:
                with self.subTest(text=text,scale=scale):
                    crop,pitch=count_image(text,scale);self.assertEqual(self.font.read(crop,pitch),int(text))
    def test_blank_does_not_mean_zero(self):self.assertIsNone(self.font.read(np.full((15,33,3),200,np.uint8),36))
    def test_nonfont_noise_is_not_a_count(self):
        self.assertIsNone(self.font.read(np.random.default_rng(42).integers(0,255,(15,33,3),dtype=np.uint8),36))
    def test_grid_and_multiple_stacks(self):
        selected=[AutoSelection('Red Potion',2000000),AutoSelection('Lemon',2010004)]
        for scale in [1,1.5,2,3]:
            with self.subTest(scale=scale):
                frame=inventory(scale=scale);self.assertEqual(len(grid_cells(frame)),30)
                found=self.d.samples(frame,selected)
                self.assertEqual([len(v[0]) for v in found],[1,2])
                values=[[self.font.read(im,box[2]) for box,im in v[0]] for v in found]
                self.assertEqual(values,[[200],[38,100]])
    def test_light_classic_world_grid_and_orange_lemon_totals(self):
        # Owner screenshot: brighter beige slots; old V<=220/closing missed grid.
        selected=[AutoSelection('Orange Potion',2000001),AutoSelection('Lemon',2010004)]
        items={(3,0):(2000001,2),(0,1):(2000001,100),(4,0):(2010004,90)}
        for color in [(213,223,225),(220,225,225),(225,225,225)]:
            for scale in [1,1.25,1.5,2,3]:
                with self.subTest(color=color,scale=scale):
                    frame=inventory(items,scale=scale,slot_color=color)
                    self.assertEqual(len(grid_cells(frame)),30)
                    found=self.d.samples(frame,selected)
                    self.assertEqual([len(v[0]) for v in found],[2,1])
                    values=[[self.font.read(im,box[2]) for box,im in v[0]] for v in found]
                    self.assertEqual(values,[[2,100],[90]])
    def test_light_empty_grid_does_not_invent_items(self):
        frame=inventory({},slot_color=(213,223,225))
        self.assertEqual(len(grid_cells(frame)),30)
        for item in self.d.catalog:
            self.assertEqual(self.d.samples(frame,[AutoSelection(self.d.catalog[item]['name'],item)])[0][0],[])
    def test_light_isolated_icons_without_grid_ignored(self):
        frame=np.full((230,220,3),(213,223,225),np.uint8)
        paste(frame,self.d.icons[2000001],20,20)
        paste(frame,self.d.icons[2010004],80,20)
        self.assertEqual(grid_cells(frame),[])

    def test_wrong_item_is_not_selected(self):
        found=self.d.samples(inventory(),[AutoSelection('Blue Potion',2000003)])
        self.assertEqual(found[0][0],[])
    def test_red_blue_and_white_are_distinguished(self):
        for item in [2000000,2000001,2000002,2000003,2000004,2000005]:
            frame=inventory({(0,0):(item,200)})
            got=self.d.samples(frame,[AutoSelection(self.d.catalog[item]['name'],item)])
            self.assertEqual(len(got[0][0]),1,item)
    def test_all_catalog_icons_identifiable_on_clean_inventory(self):
        for item in self.d.catalog:
            with self.subTest(item=item):
                got=self.d.samples(inventory({(0,0):(item,200)}),[AutoSelection(self.d.catalog[item]['name'],item)])
                self.assertEqual(len(got[0][0]),1)
    def test_empty_grid_does_not_invent_white_potions(self):
        self.assertEqual(self.d.samples(inventory({}),[AutoSelection('White Potion',2000002)])[0][0],[])
    def test_missing_inventory_anchor_never_captures(self):
        from types import SimpleNamespace
        events=[];svc=PotionService(events.append,ASSETS)
        try:
            svc.configure([AutoSelection('Red Potion',2000000)])
            screen=SimpleNamespace(grab=lambda r:self.fail('captured without verified inventory'))
            svc.capture(screen,(0,0,800,600),lambda *a:False,None,inventory=None)
            self.assertEqual(events[0][0],'potion_gaps')
        finally:
            svc.close()
            if svc.thread:svc.thread.join(3)
    def test_covered_inventory_never_captures(self):
        from types import SimpleNamespace
        events=[];svc=PotionService(events.append,ASSETS)
        try:
            svc.configure([AutoSelection('Red Potion',2000000)])
            screen=SimpleNamespace(grab=lambda r:self.fail('captured covered inventory'))
            svc.capture(screen,(0,0,800,600),lambda *a:True,None,inventory=(100,500,150,12))
            self.assertEqual(events[0][0],'potion_gaps')
        finally:
            svc.close()
            if svc.thread:svc.thread.join(3)
    def test_hotbar_icon_without_inventory_grid_ignored(self):
        frame=np.full((230,220,3),200,np.uint8);paste(frame,self.d.icons[2000000],20,20)
        self.assertEqual(self.d.samples(frame,[AutoSelection('Red Potion',2000000)])[0][0],[])
    def test_inventory_crop_stays_inside_game(self):
        for anchor in [(1,20,100,12),(500,700,180,20)]:
            x,y,w,h=inventory_region(anchor,800,800)
            self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0);self.assertLessEqual(x+w,800);self.assertLessEqual(y+h,800)
    def test_visible_stacks_combined_and_layout_change_gaps(self):
        events=[];svc=PotionService(events.append,ASSETS)
        try:
            selected=[AutoSelection('Lemon',2010004)]
            a=svc._automatic(inventory(),(0,0,220,230),selected,None,1,3)
            self.assertEqual(a,[(138,'')]);self.assertEqual(len(events),1)
            svc._automatic(inventory(),(0,0,220,230),selected,None,1,6)
            self.assertEqual(len(events),1)
            svc._automatic(inventory({(1,1):(2010004,38)}),(0,0,220,230),selected,None,1,9)
            self.assertEqual(len(events),2)
            svc._automatic(None,None,selected,None,1,12);self.assertEqual(svc.identities,{})
        finally:svc.close()

if __name__=='__main__':unittest.main()
