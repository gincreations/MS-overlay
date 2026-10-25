"""Offline, selected-item recognition within a freshly read inventory.

Only bundled reference artwork is loaded. No screen pixels are written to disk.
An inventory money-field anchor and a repeated slot grid are both required: a
matching icon on the hotbar, ground or minimap is not sufficient.
"""
import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np


@dataclass(frozen=True)
class AutoSelection:
    name: str
    item_id: int


def catalog(folder):
    rows = json.loads((Path(folder) / 'catalog.json').read_text(encoding='utf-8'))
    return {int(r['id']): r for r in rows}


def inventory_region(anchor, width, height):
    x, y, w, h = anchor
    scale = h / 12
    left, top = max(0, int(x-30*scale)), max(0, int(y-250*scale))
    right, bottom = min(width, int(x+w+30*scale)), min(height, y)
    return left, top, right-left, bottom-top


def grid_cells(frame):
    """Find a repeated inventory grid, not isolated icon-shaped scene patches."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Classic World slots can be light beige (V=225), not just gray. Keep
    # the bright separators excluded and do not close over narrow slot borders:
    # closing merges icon/background contours and destroys the repeated grid.
    mask = cv2.inRange(hsv, np.array([0,0,175]), np.array([180,55,230]))
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 100]
    boxes = [b for b in boxes if 16 <= b[2] <= 140 and .80 < b[2]/b[3] < 1.25]
    if not 9 <= len(boxes) <= 180:
        return []
    pitches = []
    for axis in (0,1):
        distances = [b[axis]-a[axis] for a in boxes for b in boxes
                     if .9*max(a[2+axis],b[2+axis]) < b[axis]-a[axis] < 1.5*max(a[2+axis],b[2+axis])
                     and abs(b[1-axis]-a[1-axis]) < .18*max(a[3-axis],b[3-axis])]
        if len(distances) < 5:
            return []
        # Most-supported spacing, then median within its tolerance.
        seed = max(distances, key=lambda d: sum(abs(v-d)<d*.10 for v in distances))
        pitches.append(float(np.median([v for v in distances if abs(v-seed)<seed*.10])))
    px, py = pitches
    if not .85 < px/py < 1.25:
        return []
    # Find the grid phase with the largest aligned set; icon-filled cell contours
    # may begin a few pixels inside the actual slot, so use the lower quantile.
    origins=[]
    for axis, pitch in enumerate(pitches):
        seed=max(boxes,key=lambda a:sum(abs((b[axis]-a[axis]+pitch/2)%pitch-pitch/2)<pitch*.16 for b in boxes))[axis]
        residual=[b[axis]-round((b[axis]-seed)/pitch)*pitch for b in boxes
                  if abs((b[axis]-seed+pitch/2)%pitch-pitch/2)<pitch*.16]
        origins.append(float(np.quantile(residual,.20)))
    ox,oy=origins
    aligned=[b for b in boxes if abs((b[0]-ox+px/2)%px-px/2)<px*.18 and abs((b[1]-oy+py/2)%py-py/2)<py*.18]
    cols={round((b[0]-ox)/px) for b in aligned};rows={round((b[1]-oy)/py) for b in aligned}
    if not 3<=len(cols)<=10 or not 3<=len(rows)<=12 or len(aligned)<len(cols)*len(rows)*.45:
        return []
    if max(cols)-min(cols)+1 != len(cols) or max(rows)-min(rows)+1 != len(rows):
        return []
    h,w=frame.shape[:2]
    return [(round(ox+c*px),round(oy+r*py),round(px),round(py)) for r in sorted(rows) for c in sorted(cols)
            if 0<=round(ox+c*px) and 0<=round(oy+r*py) and ox+(c+1)*px<=w+2 and oy+(r+1)*py<=h+2]


class Detector:
    def __init__(self, folder):
        self.catalog=catalog(folder)
        self.icons={i:cv2.imread(str(Path(folder)/r['file']),cv2.IMREAD_UNCHANGED) for i,r in self.catalog.items()}
        if any(v is None or v.ndim!=3 or v.shape[2]!=4 for v in self.icons.values()):
            raise ValueError('Bundled potion artwork is missing or damaged')
        self.cache={}
        self.identity_cache=OrderedDict()

    def templates(self, item, pitch):
        key=(item,pitch)
        if key not in self.cache:
            icon=self.icons[item];origin=self.catalog[item]['origin'];out=[]
            for scale in sorted(set([pitch/36]+list(np.linspace(pitch/36*.75,pitch/36*1.08,8)))):
                t=cv2.resize(icon,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
                mask=(t[:,:,3]>240).astype(np.uint8)*255
                mask[max(1,round((20-(32-origin[1]))*scale)):]=0
                if np.count_nonzero(mask)>=25:out.append((t[:,:,:3].copy(),mask))
            if len(self.cache)>128:self.cache.clear()
            self.cache[key]=out
        return self.cache[key]

    def identify(self, cell):
        # Reuse only an exact fresh pixel match, never an old slot position.
        # Counts/icon changes invalidate the key; no pixels leave memory.
        key=(cell.shape,cell.dtype.str,cell.tobytes())
        if key in self.identity_cache:
            self.identity_cache.move_to_end(key)
            return self.identity_cache[key]
        result=self._identify(cell)
        self.identity_cache[key]=result
        if len(self.identity_cache)>128:self.identity_cache.popitem(last=False)
        return result

    def _identify(self, cell):
        # Compare all supported identities, not just the selected colour. Similar
        # bottles must win against their neighbours or remain unclassified.
        scores=[];h,w=cell.shape[:2]
        if np.std(cv2.cvtColor(cell[:round(h*.60),:round(w*.89)],cv2.COLOR_BGR2GRAY))<15:
            return None
        for item in self.catalog:
            best=1.0
            for template,mask in self.templates(item,w):
                th,tw=template.shape[:2]
                if th>h or tw>w:continue
                result=cv2.matchTemplate(cell,template,cv2.TM_SQDIFF_NORMED,mask=mask)
                _,_,loc,_=cv2.minMaxLoc(result)
                value=float(result[loc[1],loc[0]])
                if not np.isfinite(value) or value>=min(best,.12):continue
                patch=cell[loc[1]:loc[1]+th,loc[0]:loc[0]+tw]
                corr=float(cv2.matchTemplate(patch,template,cv2.TM_CCOEFF_NORMED,mask=mask)[0,0])
                if np.isfinite(value) and np.isfinite(corr) and corr>=.70:best=min(best,value)
            scores.append((best,item))
        scores.sort()
        if scores[0][0]>.12 or scores[1][0]-scores[0][0]<.012:
            return None
        return scores[0][1]

    def samples(self, frame, selected):
        cells=grid_cells(frame)
        found={s.item_id:[] for s in selected}
        for x,y,w,h in cells:
            cell=frame[y:y+h,x:x+w]
            item=self.identify(cell)
            if item in found:
                # Count occupies the bottom-left of a classic inventory slot;
                # keep the whole digit band, independent of the icon's size.
                # Keep the complete lower outline at fractional UI scales;
                # trimming at 94% can clip the final rows of a valid digit.
                count=cell[round(h*.53):, :round(w*.93)].copy()
                found[item].append(((x,y,w,h),count))
        return [(found[s.item_id], 'Inventory grid not recognized' if not cells else 'Selected item not visible / not recognized') for s in selected]


class CountFont:
    """Read the game's outlined item-number font, with explicit ambiguity rejection.

    Unlike generic OCR this uses all ten local reference glyphs. A weak/partial
    match is not a count; the Usage estimator still requires consecutive readings.
    """
    def __init__(self, folder):
        self.glyphs=[cv2.imread(str(Path(folder)/'digits'/f'{i}.png'),cv2.IMREAD_UNCHANGED) for i in range(10)]
        if any(g is None for g in self.glyphs):raise ValueError('Missing count-font references')
        self.cache={}
        self.count_cache=OrderedDict()

    def read(self, image, pitch):
        if pitch < 32:
            return None
        key=(pitch,image.shape,image.dtype.str,image.tobytes())
        if key in self.count_cache:
            self.count_cache.move_to_end(key)
            return self.count_cache[key]
        result=self._read(image,pitch)
        self.count_cache[key]=result
        if len(self.count_cache)>128:self.count_cache.popitem(last=False)
        return result

    def _read(self, image, pitch):
        # At sub-native resolution distinct outlined glyphs can collapse into
        # another digit (e.g. 200 -> 100 at 75%). Do not publish that false count.
        if pitch < 32:
            return None
        h,w=image.shape[:2]
        if len(self.cache)>1024:self.cache.clear()
        all_maps=[]
        for digit,glyph in enumerate(self.glyphs):
            choices=[]
            for scale in sorted(set([pitch/36]+list(np.linspace(pitch/36*.88,pitch/36*1.08,7)))):
                for phase in ((0,0),(1,0),(0,1),(1,1)):
                    key=(digit,round(scale,3),phase)
                    if key not in self.cache:
                        padded=cv2.copyMakeBorder(glyph,phase[1],0,phase[0],0,cv2.BORDER_CONSTANT,value=(0,0,0,0))
                        t=cv2.resize(padded,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
                        t=t[int(phase[1]*scale):,int(phase[0]*scale):]
                        mask=(t[:,:,3]>240).astype(np.uint8)*255
                        self.cache[key]=(t[:,:,:3].copy(),mask,round(glyph.shape[1]*scale))
                    t,mask,advance=self.cache[key];th,tw=t.shape[:2]
                    if th>h or tw>w:continue
                    scores=cv2.matchTemplate(image,t,cv2.TM_SQDIFF_NORMED,mask=mask)
                    choices.append((scores,tw,th,t,mask,advance))
            all_maps.append(choices)
        # The count begins at the slot's left edge. Follow a single baseline and
        # contiguous proportional-width glyphs, never hunt elsewhere in the icon.
        x=0; baseline=None;out=[]
        for position in range(5):
            ranked=[]
            for digit,choices in enumerate(all_maps):
                best=(9,None)
                for scores,tw,th,t,mask,advance in choices:
                    lo=max(0,x-1);hi=min(scores.shape[1],x+max(3,round(pitch*.07))+1)
                    if hi<=lo:continue
                    ylo=0 if baseline is None else max(0,baseline-1)
                    yhi=scores.shape[0] if baseline is None else min(scores.shape[0],baseline+2)
                    if yhi<=ylo:continue
                    block=scores[ylo:yhi,lo:hi]
                    _,_,loc,_=cv2.minMaxLoc(block);xx,yy=loc;value=float(block[yy,xx])
                    patch=image[yy+ylo:yy+ylo+th,xx+lo:xx+lo+tw]
                    corr=float(cv2.matchTemplate(patch,t,cv2.TM_CCOEFF_NORMED,mask=mask)[0,0])
                    if np.isfinite(value) and np.isfinite(corr) and corr>=.70 and value<best[0]:
                        best=(value,(xx+lo,yy+ylo,advance,th))
                ranked.append((best[0],digit,best[1]))
            ranked.sort()
            score,digit,where=ranked[0]
            if score>.45:
                return int(''.join(out)) if out else None
            if score>.24 or ranked[1][0]-score<.035 or position==4:
                return None
            xx,yy,tw,th=where
            if baseline is None:baseline=yy
            out.append(str(digit));x=xx+tw
            if x>=w-2:
                return int(''.join(out))
        return None
