"""Bounded Windows kernel timings; no live screen capture or binary execution."""
import sys,time,json
from pathlib import Path
import cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tests"))
from test_auto_potions import inventory,Detector,ASSETS,grid_cells
cv2.setNumThreads(1)
d=Detector(ASSETS)
frame=inventory({(0,0):(2000001,100)},scale=3)
x,y,w,h=grid_cells(frame)[0];cell=frame[y:y+h,x:x+w]
template,mask=d.templates(2000001,w)[0]
for enabled in (True,False):
 cv2.ipp.setUseIPP(enabled)
 start=time.perf_counter()
 for _ in range(20): cv2.matchTemplate(cell,template,cv2.TM_SQDIFF_NORMED,mask=mask)
 print(json.dumps({"ipp":enabled,"calls":20,"seconds":time.perf_counter()-start,"cell":cell.shape,"template":template.shape}),flush=True)
