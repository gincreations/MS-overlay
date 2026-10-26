"""Opt-in, screen-only potion observations. No files, network or game input.

Counts are estimates from visible inventory stacks or a hotbar total, not proof of consumption.
Selections and icon reference pixels live only in RAM; names may be saved by the UI.
"""
import re
import queue
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

PRESETS = ("HP Potion", "MP Potion", "Red Potion", "Orange Potion", "White Potion",
           "Blue Potion", "Mana Elixir", "Elixir", "Power Elixir", "Unagi", "Ice Cream Pop")
MAX_SLOTS = 2
POLL = 1.0  # Allow each normal ~1.5s foreground capture; no extra capture thread.
MAX_GAP = 12.0


MAX_UNIT_PRICE = 1_000_000_000


def parse_price(text):
    """Blank means unknown; zero explicitly means free. Whole mesos only."""
    text=str(text).strip()
    if not text:
        return None
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)",text):
        raise ValueError("Enter a whole meso price, such as 500 or 1,200. Leave blank to hide costs.")
    value=int(text.replace(",",""))
    if value>MAX_UNIT_PRICE:
        raise ValueError("Price must be between 0 and 1,000,000,000 mesos per item.")
    return value


def normalize_prices(value):
    if not isinstance(value,dict):return {}
    return {k:v for k,v in value.items() if isinstance(k,str) and re.fullmatch(r"[0-9]{7}",k)
            and type(v) is int and 0<=v<=MAX_UNIT_PRICE}


def normalize_hidden_prices(value):
    if not isinstance(value,list):return []
    return sorted({v for v in value if isinstance(v,str) and re.fullmatch(r"[0-9]{7}",v)})


def estimated_cost(usage, price):
    """Revalue confirmed observed consumption at the current reference or custom price."""
    if type(price) is not int or not 0<=price<=MAX_UNIT_PRICE:
        return None,None
    rate=usage.per_minute()
    return usage.used*price, None if rate is None else rate*60*price


def clean_name(value):
    return "".join(c for c in str(value) if c.isprintable()).strip()[:32] or "Potion"


def inside(box, width, height):
    if not isinstance(box, (tuple, list)) or len(box) != 4 or any(type(v) is not int for v in box):
        return False
    x, y, w, h = box
    return x >= 0 and y >= 0 and w >= 5 and h >= 5 and x + w <= width and y + h <= height


def read_count(image, tess):
    """Two preparations must agree. Never infer zero from a blank/hidden stack."""
    if tess is None or image is None or image.size == 0:
        return None
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    grey = cv2.resize(grey, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    border = cv2.copyMakeBorder(grey, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=int(np.median(grey)))
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(binary) < 127:
        binary = 255 - binary
    binary = cv2.copyMakeBorder(binary, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    values = []
    for prepared in (border, binary):
        text = tess.read_line(prepared, "0123456789").strip()
        if not re.fullmatch(r"[0-9]{1,4}", text):
            return None
        value = int(text)
        if value > 9999:
            return None
        values.append(value)
    return values[0] if values[0] == values[1] else None


@dataclass
class Selection:
    name: str
    size: tuple
    box: tuple
    digits: tuple  # relative to box
    reference: np.ndarray
    mask: np.ndarray

    @classmethod
    def make(cls, name, frame, box, digits):
        h, w = frame.shape[:2]
        if not inside(box, w, h) or box[2] > 180 or box[3] > 180:
            raise ValueError("Select one potion slot, not the whole inventory (maximum 180 × 180 pixels).")
        x, y, bw, bh = box
        if not inside(digits, bw, bh):
            raise ValueError("Select the stack digits inside the potion slot.")
        reference = frame[y:y+bh, x:x+bw, :3].copy()
        dx, dy, dw, dh = digits
        mask = np.ones((bh, bw), dtype=bool)
        mask[max(0,dy-2):min(bh,dy+dh+2), max(0,dx-2):min(bw,dx+dw+2)] = False
        # Match the actual coloured icon, not a large plain inventory background.
        spread = np.max(reference, axis=2).astype(float) - np.min(reference, axis=2)
        mask &= (spread > 18) | (cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY) < 75)
        if np.count_nonzero(mask) < 40 or np.std(reference[mask]) < 12:
            raise ValueError("Include the potion icon above/beside its count so it can be recognized.")
        return cls(clean_name(name), (w, h), tuple(box), tuple(digits), reference, mask)

    def matches(self, crop):
        if crop.shape != self.reference.shape:
            return False
        errors = np.abs(crop.astype(np.int16) - self.reference.astype(np.int16)).mean(axis=2)[self.mask]
        return float(np.mean(errors)) <= 15 and float(np.mean(errors > 35)) <= 0.18


class Usage:
    """Confirm readings, exclude blind gaps/refills, and reject implausible losses."""
    def __init__(self):
        self.used, self.seconds = 0, 0.0
        self.value = self.at = self.pending = None
        self.status = "Waiting for two readings"
        self.locked = False

    def gap(self, why="Inventory hidden or slot moved"):
        self.value = self.at = self.pending = None
        if not self.locked:
            self.status = why

    def observe(self, value, now):
        if self.locked:
            return
        if value is None or type(value) is not int or not 0 <= value <= 9999:
            self.gap("Count unreadable — waiting")
            return
        if self.pending is None:
            self.pending = (value, now)
            self.status = "Confirming count"
            return
        candidate, when = self.pending
        dt = now - when
        if not 0 < dt <= MAX_GAP:
            self.gap("Resuming — new baseline")
            self.pending = (value, now)
            return
        # A later equal/slightly lower reading confirms a count. An isolated OCR dip
        # that immediately returns upward cannot be counted as potion use.
        if value > candidate or candidate - value > max(4, dt * 4):
            self.pending = (value, now)
            self.status = "Confirming count change"
            return
        self.pending = (value, now)
        if self.value is None:
            self.value, self.at = candidate, when
            self.status = "Tracking visible stack"
            return
        elapsed = when - self.at
        if not 0 < elapsed <= MAX_GAP:
            self.value, self.at = candidate, when
            self.status = "Resumed — hidden time excluded"
            return
        delta = self.value - candidate
        if delta > max(4, elapsed * 4):
            self.locked = True
            self.status = "Large drop — reselect this stack"
            return
        self.value, self.at = candidate, when
        if delta < 0:
            # Usage during a refill cannot be measured. Do not dilute the rate
            # with its unknown interval.
            self.status = "Refill — new baseline"
        else:
            self.seconds += elapsed
            self.used += delta
            self.status = "Tracking visible stack"

    def per_minute(self):
        return self.used / self.seconds * 60 if self.seconds >= 15 else None


class PotionService:
    """Worker-side sampling only through the caller's foreground-checked GameCapture.

    Main-thread configuration is guarded; generation ids discard stale queued results.
    """
    def __init__(self, emit, assets=None):
        self.emit = emit
        self.assets = assets
        self.detector = None
        self.hotbar_detector = None
        self.identities = {}
        self.lock = threading.Lock()
        self.selections = ()
        self.generation = 0
        self.request = None
        self.next_read = 0
        self.jobs = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.thread = None

    def configure(self, selections):
        with self.lock:
            self.selections = tuple(selections)
            self.generation += 1
            self.next_read = 0
            self.request = None
            if selections and self.thread is None:
                self.thread = threading.Thread(target=self._ocr_worker, daemon=True)
                self.thread.start()
            return self.generation

    def request_snapshot(self, token):
        with self.lock:
            self.request = token

    def cancel_snapshot(self):
        with self.lock:
            self.request = None

    def capture(self, screen, rect, covered, tess, inventory=None):
        now = time.monotonic()
        with self.lock:
            selections, generation = self.selections, self.generation
            request = self.request
            self.request = None
            due = now >= self.next_read
            if due:
                self.next_read = now + POLL
        wx, wy, w, h = rect
        if request is not None:
            try:
                frame = np.array(screen.grab(dict(left=wx, top=wy, width=w, height=h)))[:, :, :3].copy()
                self.emit(("potion_snapshot", (request, frame)))
            except Exception:
                self.emit(("potion_snapshot", (request, None)))
                raise
        if not selections or not due:
            return
        from potion_recognition import AutoSelection, inventory_region
        if all(isinstance(s, AutoSelection) for s in selections):
            # One foreground-checked in-memory game capture feeds both readers.
            # Mask our overlay before recognition; never use it as a hotbar.
            own = getattr(getattr(covered, "__self__", None), "own_rect", None)
            if own is None and covered(wx,wy,w,h):
                self._enqueue((generation,now,("auto",None,None,selections,None),getattr(tess,"cmd",None)))
                self.emit(("potion_gaps",(generation,now,[(i,"Potion area covered — move the overlay") for i in range(len(selections))])))
                return
            game = np.array(screen.grab(dict(left=wx,top=wy,width=w,height=h)))[:,:,:3].copy()
            if own:
                ox,oy,ow,oh=own
                x0,y0=max(0,ox-wx),max(0,oy-wy)
                x1,y1=min(w,ox-wx+ow),min(h,oy-wy+oh)
                if x0<x1 and y0<y1:game[y0:y1,x0:x1]=0
            frame, region = None, None
            if inventory is not None:
                x,y,bw,bh = inventory_region(inventory,w,h)
                if bw>0 and bh>0 and not covered(wx+x,wy+y,bw,bh):
                    region=(x,y,bw,bh)
                    frame=game[y:y+bh,x:x+bw].copy()
            self._enqueue((generation,now,("auto",frame,region,selections,game),getattr(tess,"cmd",None)))
            return
        samples = []
        for selection in selections:
            image, why = None, "Inventory hidden, covered or slot moved"
            if selection.size != (w, h):
                why = "Game resized — reselect stack"
            else:
                x, y, bw, bh = selection.box
                if not covered(wx+x, wy+y, bw, bh):
                    crop = np.array(screen.grab(dict(left=wx+x, top=wy+y, width=bw, height=bh)))[:, :, :3].copy()
                    if selection.matches(crop):
                        dx, dy, dw, dh = selection.digits
                        image = crop[dy:dy+dh, dx:dx+dw].copy()
                        why = "Count unreadable — waiting"
            samples.append((image, why))
        missing = [(i, why) for i, (image, why) in enumerate(samples) if image is None]
        if missing:
            self.emit(("potion_gaps", (generation, now, missing)))
        self._enqueue((generation, now, samples, getattr(tess, "cmd", None)))

    def _enqueue(self, job):
        try:
            self.jobs.put_nowait(job)
        except queue.Full:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                pass
            self.jobs.put_nowait(job)

    def _ocr_worker(self):
        from ocr import Tesseract
        while not self.stop.is_set():
            try:
                generation, now, samples, cmd = self.jobs.get(timeout=0.25)
            except queue.Empty:
                continue
            values = []
            tess = Tesseract(cmd, timeout=2) if cmd else None
            if isinstance(samples,tuple) and samples[0]=="auto":
                _,frame,region,selections,*extra=samples
                hotbar=extra[0] if extra else None
                try:
                    values=self._automatic(frame,region,selections,tess,generation,now,hotbar)
                except Exception:
                    # Fail closed: damaged artwork / unsupported geometry cannot turn
                    # into a guessed count or take down EXP tracking.
                    self.identities.clear()
                    values=[(None,"Potion recognition unavailable — run Check setup") for _ in selections]
                samples=[]
            for image, why in samples:
                if self.stop.is_set():
                    return
                value = None
                if image is not None:
                    try:
                        value = read_count(image, tess)
                    except Exception:
                        why = "OCR unavailable — waiting"
                values.append((value, why))
            with self.lock:
                current = generation == self.generation
            if current and not self.stop.is_set():
                self.emit(("potion_counts", (generation, now, values)))

    def _automatic(self,frame,region,selections,tess,generation,now,hotbar=None):
        from potion_recognition import Detector, CountFont, HotbarDetector
        if frame is None and hotbar is None:
            self.identities.clear()
            return [(None,"Hotbar / inventory unreadable — keep the potion area visible") for _ in selections]
        if self.detector is None:
            self.detector=Detector(self.assets)
            self.count_font=CountFont(self.assets)
        hot_samples=[([],"Hotbar not recognized") for _ in selections]
        if hotbar is not None:
            if self.hotbar_detector is None:self.hotbar_detector=HotbarDetector(self.assets,self.detector)
            hot_samples=self.hotbar_detector.samples(hotbar,selections)
        inventory_samples=None
        output=[]
        def read(stacks, total):
            if not stacks:return None,"Selected item not visible / not recognized"
            if len(stacks)>(8 if total else 6):return None,"Too many visible stacks to read reliably"
            counts=[]
            for box,image in stacks:
                if self.stop.is_set():return None,"Stopped"
                if box[2]<32:return None,"Potion counts too small — enlarge the game UI"
                value=self.count_font.read(image,box[2])
                if value is None:return None,"Count unreadable — waiting"
                counts.append(value)
            if total:
                # Repeated quickslots show the same aggregate; never sum them.
                if len(set(counts))!=1:return None,"Hotbar counts disagree — waiting"
                return counts[0],"Hotbar total"
            value=sum(counts)
            return (value,"") if value<=9999 else (None,"Count exceeds supported range")
        for i,(stacks,why) in enumerate(hot_samples):
            value,problem=read(stacks,True)
            source,area="hotbar",None
            if value is None:
                if inventory_samples is None:
                    inventory_samples=(self.detector.samples(frame,selections) if frame is not None else
                                       [([],"Hotbar / inventory unreadable — keep the potion area visible") for _ in selections])
                stacks,why=inventory_samples[i]
                source,area="inventory",region
                value,problem=read(stacks,False)
                if not stacks:problem=why
            key=selections[i].item_id
            if value is None:
                self.identities.pop(key,None)
                output.append((None,problem));continue
            identity=(generation,(source,area),tuple(box for box,_ in stacks))
            prior=self.identities.get(key)
            same=(prior is not None and prior[0]==identity[0] and prior[1]==identity[1]
                  and len(prior[2])==len(identity[2]) and all(max(abs(a-b) for a,b in zip(old,new))<=max(2,new[2]*.12)
                      for old,new in zip(prior[2],identity[2])))
            if not same:
                self.emit(("potion_gaps",(generation,now,[(i,"Potion source / visible slots changed — new baseline")])))
            self.identities[key]=identity
            output.append((value,problem))
        return output

    def close(self):
        self.stop.set()
        self.configure(())
        try:
            self.jobs.get_nowait()
        except queue.Empty:
            pass
