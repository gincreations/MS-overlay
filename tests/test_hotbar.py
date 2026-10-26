"""Hotbar geometry, real UI crop, no double counting and source-transition contracts."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['MAPLE_EXP_DATA']=tempfile.mkdtemp()
from potion_recognition import Detector,HotbarDetector,CountFont,AutoSelection
from potion_tracking import PotionService,Usage
from test_auto_potions import ASSETS,inventory,paste,count_image
ROOT=Path(__file__).resolve().parents[1]
REAL=cv2.imread(str(ROOT/'tests/frames/hotbar-classic.png'))
SELECT=[AutoSelection('Lemon',2010004),AutoSelection('Orange Potion',2000001)]


def hotbar(items=None,scale=1):
    if items is None:items={2:(2010004,167),3:(2000001,76)}
    d=Detector(ASSETS);ref=cv2.imread(str(ASSETS/'hotbar-labels.png'),-1)
    # Empty Ins slot from the same game UI; key labels remain independent of items.
    board=ref[:,:,:3].copy()
    blank=ref[:48,49:98,:3].copy()
    for idx in range(8):
        x,y=(idx%4)*49,(idx//4)*48
        board[y+3:y+45,x+3:x+46]=blank[3:45,3:46]
        if idx in items:
            item,count=items[idx];ox,oy=d.catalog[item]['origin']
            icon=cv2.resize(d.icons[item],None,fx=1.4,fy=1.4,interpolation=cv2.INTER_LINEAR)
            ix,iy=x+round(-ox*1.4),y+round((32-oy)*1.4)
            paste(board,icon,ix,iy)
            if count is not None:
                xx=x+1
                for c in str(count):
                    glyph=cv2.imread(str(ASSETS/'digits'/f'{c}.png'),-1)
                    glyph=cv2.resize(glyph,None,fx=1.4,fy=1.4,interpolation=cv2.INTER_LINEAR)
                    paste(board,glyph,xx,y+28);xx+=round(cv2.imread(str(ASSETS/'digits'/f'{c}.png'),-1).shape[1]*1.4)
        mask=ref[y:y+48,x:x+49,3]>0
        board[y:y+48,x:x+49][mask]=ref[y:y+48,x:x+49,:3][mask]
    # Keep enough margin for geometric alignment; this is only generated game UI.
    canvas=np.full((116,216,3),80,np.uint8);canvas[10:106,10:206]=board
    return cv2.resize(canvas,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)


def rebind(frame, labels, origin=(10,10)):
    """Replace only the key-text band, leaving slot rims and potion pixels intact."""
    frame=frame.copy()
    for idx,text in enumerate(labels):
        x,y=origin[0]+(idx%4)*49,origin[1]+(idx//4)*48
        band=frame[y+3:y+18,x+3:x+46]
        band[:]=232
        cv2.putText(band,text,(1,11),cv2.FONT_HERSHEY_SIMPLEX,.32,(120,120,120),2,cv2.LINE_AA)
        cv2.putText(band,text,(1,11),cv2.FONT_HERSHEY_SIMPLEX,.32,(255,255,255),1,cv2.LINE_AA)
    return frame


class HotbarRecognition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector=Detector(ASSETS);cls.hot=HotbarDetector(ASSETS,cls.detector);cls.font=CountFont(ASSETS)
    def values(self,frame,selected=SELECT):
        return [[self.font.read(im,b[2]) for b,im in stacks] for stacks,_ in self.hot.samples(frame,selected)]
    def test_real_supplied_ui_crop(self):
        self.assertEqual(len(self.hot.cells(REAL)),8)
        self.assertEqual(self.values(REAL),[[167],[76]])
    def test_real_crop_in_full_game_at_different_positions(self):
        for w,h,x,y in [(1920,1200,1690,1085),(1280,720,700,420),(2560,1440,50,80)]:
            with self.subTest(w=w,h=h):
                game=np.full((h,w,3),60,np.uint8);rh,rw=REAL.shape[:2];game[y:y+rh,x:x+rw]=REAL
                self.assertEqual(self.values(game),[[167],[76]])
    def test_real_crop_fractional_and_large_ui(self):
        for scale in [1,1.25,1.5,2]:
            with self.subTest(scale=scale):
                im=cv2.resize(REAL,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
                self.assertEqual(self.values(im),[[167],[76]])
    def test_mac_nominal_raster_counts(self):
        # UI-only crop: no player names, chat, desktop or account information.
        frame=cv2.imread(str(ROOT/'tests/frames/hotbar-mac-nominal.png'))
        selected=[AutoSelection('Orange Potion',2000001),AutoSelection('Blue Potion',2000003)]
        self.assertEqual(len(self.hot.cells(frame)),8)
        self.assertEqual(self.values(frame,selected),[[26],[146]])
    def test_mac_nominal_raster_in_larger_frames(self):
        frame=cv2.imread(str(ROOT/'tests/frames/hotbar-mac-nominal.png'))
        selected=[AutoSelection('Orange Potion',2000001),AutoSelection('Blue Potion',2000003)]
        for x,y in [(0,0),(1300,657),(730,450)]:
            with self.subTest(x=x,y=y):
                scene=np.full((806,1646,3),60,np.uint8)
                h,w=frame.shape[:2];scene[y:y+h,x:x+w]=frame
                self.assertEqual(self.values(scene,selected),[[26],[146]])
    def test_mac_nominal_panel_covered_or_duplicated_rejected(self):
        frame=cv2.imread(str(ROOT/'tests/frames/hotbar-mac-nominal.png'))
        covered=frame.copy();covered[:,70:]=0
        self.assertEqual(self.hot.cells(covered),[])
        scene=np.full((150,400,3),60,np.uint8);h,w=frame.shape[:2]
        for x in (0,220):scene[20:20+h,x:x+w]=frame
        self.assertEqual(self.hot.cells(scene),[])

    def test_generated_counts_and_duplicate_slots(self):
        self.assertEqual(self.values(hotbar({1:(2010004,167),2:(2010004,167),3:(2000001,76)})),[[167,167],[76]])
    def test_changed_potions_zero_and_refill(self):
        for value in [0,1,38,100,200,999,1234]:
            with self.subTest(value=value):
                self.assertEqual(self.values(hotbar({2:(2010004,value)})),[[value],[]])
    def test_all_catalog_icons_on_clean_hotbar(self):
        for item,row in self.detector.catalog.items():
            with self.subTest(item=row['name']):
                self.assertEqual(self.values(hotbar({2:(item,200)}),[AutoSelection(row['name'],item)]),[[200]])
    def test_fresh_counts_are_not_cached_old_stock(self):
        for n in [200,199,198]:
            self.assertEqual(self.values(hotbar({2:(2010004,n)})),[[n],[]])
    def test_subnative_counts_fail_closed(self):
        im=cv2.resize(REAL,None,fx=.6,fy=.6,interpolation=cv2.INTER_LINEAR)
        self.assertTrue(all(value is None for values in self.values(im) for value in values))
    def test_wrong_selected_item_rejected(self):
        self.assertEqual(self.values(REAL,[AutoSelection('Blue Potion',2000003)]),[[]])
    def test_blank_panel_not_a_white_potion(self):
        self.assertEqual(self.values(hotbar({}),[AutoSelection('White Potion',2000002)]),[[]])
    def test_inventory_not_misclassified_as_hotbar(self):
        self.assertEqual(self.hot.cells(inventory()),[])
    def test_random_scene_and_isolated_icon_rejected(self):
        scene=np.random.default_rng(4).integers(0,255,(500,800,3),dtype=np.uint8)
        self.assertEqual(self.hot.cells(scene),[])
        scene=np.full((300,300,3),240,np.uint8);paste(scene,self.detector.icons[2010004],40,40)
        self.assertEqual(self.hot.cells(scene),[])
    def test_destroyed_slot_top_borders_rejected(self):
        frame=hotbar({})
        for row in range(2):frame[10+row*48:10+row*48+18,10:206]=240
        self.assertEqual(self.hot.cells(frame),[])
    def test_cropped_panel_rejected(self):
        self.assertEqual(self.hot.cells(REAL[:70]),[])
    def test_covered_panel_not_reused(self):
        self.assertTrue(self.hot.cells(REAL))
        im=REAL.copy();im[:,100:]=0
        self.assertEqual(self.hot.cells(im),[])

    def test_rebound_key_labels_and_no_labels(self):
        for labels in [('Q','W','E','R','A','S','D','F'),('1','2','3','4','5','6','7','8'),('F1','F2','Ctrl','Alt','Tab','Z','X','C'),('',)*8]:
            with self.subTest(labels=labels):
                self.assertEqual(self.values(rebind(hotbar(),labels)),[[167],[76]])
    def test_real_crop_with_replaced_key_labels(self):
        x,y,_,_=self.hot.cells(REAL)[0]
        self.assertEqual(self.values(rebind(REAL,('Q','W','E','R','A','S','D','F'),(x,y))),[[167],[76]])
    def test_all_catalog_icons_with_rebound_keys(self):
        for item,row in self.detector.catalog.items():
            with self.subTest(item=item):
                frame=rebind(hotbar({2:(item,200)}),('Q','W','E','R','A','S','D','F'))
                self.assertEqual(self.values(frame,[AutoSelection(row['name'],item)]),[[200]])
    def test_all_eight_slots_with_rebound_keys(self):
        for slot in range(8):
            for item,n,selection in [(2010004,167,SELECT[0]),(2000001,76,SELECT[1])]:
                with self.subTest(slot=slot,item=item):
                    frame=rebind(hotbar({slot:(item,n)}),('Q','W','E','R','A','S','D','F'))
                    self.assertEqual(self.values(frame,[selection]),[[n]])
    def test_rebound_labels_scaled_full_game(self):
        frame=rebind(hotbar(),('1','2','3','4','F1','F2','Alt','Tab'))
        for scale in [1,1.25,1.5,2]:
            with self.subTest(scale=scale):
                panel=cv2.resize(frame,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
                game=np.full((1200,1920,3),60,np.uint8);h,w=panel.shape[:2]
                game[1200-h:,1920-w:]=panel
                self.assertEqual(self.values(game),[[167],[76]])
    def test_rebound_empty_slots_not_potions(self):
        frame=rebind(hotbar({}),('Q','W','E','R','A','S','D','F'))
        self.assertTrue(self.hot.cells(frame))
        for item,row in self.detector.catalog.items():
            with self.subTest(item=item):self.assertEqual(self.values(frame,[AutoSelection(row['name'],item)]),[[]])
    def test_runtime_mask_excludes_labels_icons_and_counts(self):
        for row in range(2):
            for col in range(4):
                mask=self.hot.frame[row*48:(row+1)*48,col*49:(col+1)*49,3]
                self.assertFalse(np.any(mask[3:18]))
                self.assertFalse(np.any(mask[27:45]))
                self.assertFalse(np.any(mask[18:27,3:46]))
    def test_unframed_white_button_grid_rejected(self):
        frame=np.full((116,216,3),60,np.uint8)
        for idx in range(8):
            x,y=10+(idx%4)*49,10+(idx//4)*48
            cv2.rectangle(frame,(x+3,y+3),(x+43,y+43),(240,240,240),-1)
        self.assertEqual(self.hot.cells(frame),[])
    def test_two_distinct_hotbars_rejected(self):
        scene=np.full((300,500,3),60,np.uint8)
        for x in [0,260]:scene[50:166,x:x+216]=rebind(hotbar(),('Q','W','E','R','A','S','D','F'))
        self.assertEqual(self.hot.cells(scene),[])


class SourceSelection(unittest.TestCase):
    def setUp(self):
        self.events=[];self.svc=PotionService(self.events.append,ASSETS)
        self.svc.detector=Detector(ASSETS);self.svc.count_font=CountFont(ASSETS)
        self.svc.hotbar_detector=HotbarDetector(ASSETS,self.svc.detector)
        self.selected=[AutoSelection('Lemon',2010004)]
    def tearDown(self):self.svc.close()
    def stack(self,value,x=0):
        crop,p=count_image(str(value));return ((x,0,p,34),crop)
    def read(self,hot,inv,now=0):
        with patch.object(self.svc.hotbar_detector,'samples',return_value=[(hot,'missing')]),patch.object(self.svc.detector,'samples',return_value=[(inv,'missing')]):
            return self.svc._automatic(np.zeros((2,2,3),np.uint8),(0,0,200,200),self.selected,None,1,now,np.zeros((2,2,3),np.uint8))[0]
    def test_both_visible_hotbar_wins_not_sum(self):
        self.assertEqual(self.read([self.stack(167)],[self.stack(100),self.stack(67,40)]),(167,'Hotbar total'))
    def test_hotbar_zero_wins_over_nonzero_inventory(self):
        self.assertEqual(self.read([self.stack(0)],[self.stack(100)]),(0,'Hotbar total'))
    def test_duplicate_hotbar_slots_are_not_summed(self):
        self.assertEqual(self.read([self.stack(167),self.stack(167,40)],[self.stack(100)]),(167,'Hotbar total'))
    def test_disagreeing_hotbar_duplicates_fall_back(self):
        self.assertEqual(self.read([self.stack(167),self.stack(166,40)],[self.stack(100)]),(100,''))
    def test_no_hotbar_sums_inventory_stacks(self):
        self.assertEqual(self.read([],[self.stack(100),self.stack(67,40)]),(167,''))
    def test_unreadable_hotbar_is_not_zero_and_falls_back(self):
        bad=((0,0,36,34),np.full((15,33,3),200,np.uint8))
        self.assertEqual(self.read([bad],[self.stack(100)]),(100,''))
    def test_neither_source_is_unavailable(self):self.assertIsNone(self.read([],[])[0])
    def test_source_change_rebaselines_and_preserves_totals(self):
        usage=Usage();used_events=0
        for now,source,value in [(0,'hot',200),(1.5,'hot',200),(3,'hot',199),(4.5,'hot',199),(6,'inv',70),(7.5,'inv',70),(9,'inv',69),(10.5,'inv',69),(12,'hot',195),(13.5,'hot',195)]:
            got,why=self.read([self.stack(value)] if source=='hot' else [],[self.stack(value)],now)
            if len(self.events)>used_events:usage.gap();used_events=len(self.events)
            usage.observe(got,now)
        self.assertEqual(usage.used,2)
        self.assertEqual(usage.value,195)
        self.assertEqual(len(self.events),3)
    def test_visible_inventory_does_not_reset_hotbar_baseline(self):
        self.read([self.stack(167)],[],0);events=len(self.events)
        self.read([self.stack(166)],[self.stack(100),self.stack(66,40)],1.5)
        self.assertEqual(len(self.events),events)
    def test_duplicate_slot_removed_rebaselines_not_fake_usage(self):
        self.read([self.stack(167),self.stack(167,40)],[],0)
        self.read([self.stack(167)],[],1.5)
        self.assertEqual(len(self.events),2)
    def test_source_priority_independent_for_each_item(self):
        frame=inventory({(0,0):(2010004,100),(1,0):(2000003,50)})
        selected=[AutoSelection('Lemon',2010004),AutoSelection('Blue Potion',2000003)]
        result=self.svc._automatic(frame,(0,0,220,230),selected,None,1,0,REAL)
        self.assertEqual(result,[(167,'Hotbar total'),(50,'')])
    def test_no_selections_does_not_capture(self):
        self.svc.capture(SimpleNamespace(grab=lambda r:self.fail('unnecessary capture')),(0,0,800,600),lambda *a:False,None)
    def test_foreground_capture_block_propagates(self):
        from privacy_guard import CaptureBlocked
        self.svc.selections=tuple(self.selected)
        def blocked(r):raise CaptureBlocked('not foreground')
        with self.assertRaises(CaptureBlocked):self.svc.capture(SimpleNamespace(grab=blocked),(0,0,800,600),lambda *a:False,None)
    def test_overlay_pixels_masked_before_worker(self):
        class Reader:
            own_rect=(10,20,100,50)
            def covered(self,*a):return True
        self.svc.selections=tuple(self.selected)
        screen=SimpleNamespace(grab=lambda r:np.full((r['height'],r['width'],4),200,np.uint8))
        with patch.object(self.svc,'_enqueue') as job:
            self.svc.capture(screen,(0,0,800,600),Reader().covered,None)
        game=job.call_args[0][0][2][4]
        self.assertTrue(np.all(game[20:70,10:110]==0));self.assertTrue(np.all(game[100:200,200:300]==200))

if __name__=='__main__':unittest.main()
