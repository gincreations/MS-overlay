"""After Defender clearance, exercise the exact bundled OCR through the app API."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ocr
work = ROOT/'verification/windows-review'
app = work/'candidate'
review = json.loads((work/'defender.json').read_text(encoding='utf-8-sig'))
if review.get('scanExit') != 0 or not review.get('realtimeEnabled'):
    raise SystemExit('OCR execution requires enabled Defender clearance')
manifest = json.loads((work/'runtime-manifest.json').read_text())
for name, digest in manifest.items():
    if hashlib.sha256((app/name).read_bytes()).hexdigest() != digest:
        raise SystemExit('Scanned runtime modified before OCR validation')
exe = app/'tesseract/tesseract.exe'
result = subprocess.run([str(exe),'--version'],capture_output=True,text=True,check=True,timeout=15)
version = result.stdout + result.stderr
for required in ('tesseract 5.5.3','leptonica-1.87.0','libpng 1.6.59','zlib 1.3.2.1-motley'):
    if required not in version:
        raise SystemExit('Unexpected OCR version: missing '+required+' in '+version)
for forbidden in ('libcurl','libarchive','libtiff','libjpeg','libwebp','OpenSSL'):
    if forbidden.lower() in version.lower():
        raise SystemExit('Unwanted OCR feature retained: '+forbidden)
font = ImageFont.truetype(str(Path(os.environ['WINDIR'])/'Fonts/arial.ttf'),42)
reader = ocr.Tesseract(str(exe))
cases = [('1234567890','0123456789'),('5,410,845','0123456789,'),('Maple Classic',None)]
observed = []
for expected, chars in cases:
    image = Image.new('L',(600,90),255)
    ImageDraw.Draw(image).text((20,15),expected,font=font,fill=0)
    start=time.monotonic()
    actual=reader.read_line(np.array(image),chars)
    if actual.strip() != expected:
        raise SystemExit('OCR regression: expected '+repr(expected)+' got '+repr(actual))
    observed.append({'expected':expected,'actual':actual,'seconds':round(time.monotonic()-start,3)})
report={'versionOutput':version,'cliSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
        'tests':observed,'stdinPNGThroughApplicationAPI':True,'passed':True,
        'scope':'Synthetic grayscale PNG crops; not a full gameplay accuracy/performance trial'}
(work/'ocr-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
