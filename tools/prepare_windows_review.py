"""Build a fresh native runtime; use the minimal hash-pinned native OCR build."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'verification/windows-review'
work.mkdir(parents=True,exist_ok=True)
if sys.version_info[:3]!=(3,13,17): raise SystemExit('Expected pinned Python3.13.17')
ocr_manifest=json.loads((work/'ocr-provenance.json').read_text())
if ocr_manifest['sources'] != json.loads((ROOT/'tools/ocr-sources.json').read_text()): raise SystemExit('OCR source provenance mismatch')
for name, expected in ocr_manifest['files'].items():
 if hashlib.sha256((work/'ocr-runtime'/name).read_bytes()).hexdigest()!=expected: raise SystemExit('OCR build changed before packaging: '+name)
subprocess.run([sys.executable,'-m','pip','check'],check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--noupx','--name','Maple Private Overlay','--icon',str(ROOT/'assets/icon.ico'),'--add-data',str(ROOT/'assets')+os.pathsep+'assets','--distpath',str(work/'dist'),'--workpath',str(work/'build'),'--specpath',str(work),str(ROOT/'maple_exp.py')],cwd=ROOT,check=True)
app=work/'candidate'
if app.exists(): shutil.rmtree(app)
shutil.move(str(work/'dist/Maple Private Overlay'),app)
shutil.copytree(work/'ocr-runtime', app/'tesseract')
manifest={p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(app.rglob('*')) if p.is_file()}
(work/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2))
(work/'candidate-sha256.txt').write_text(manifest['Maple Private Overlay.exe'])
(work/'native-build.json').write_text(json.dumps({'python':sys.version,'method':'Fresh native PyInstaller onedir build; no UPX; no repacked legacy Python runtime','ocr_provenance':json.loads((work/'ocr-provenance.json').read_text()),'packages':json.loads(subprocess.check_output([sys.executable,'-m','pip','list','--format=json'],text=True))},indent=2))
print('Fresh native runtime prepared; EXE has not been executed.')
