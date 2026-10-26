"""Standalone, ad-hoc signed Apple Silicon app; does not modify the Windows builder."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'verification/macos-review'
NAME='Maple Private Overlay'
VERSION=re.search(r'^VERSION = "([^"]+)"',(ROOT/'maple_exp.py').read_text(),re.M)[1]

def run(args,**kw):return subprocess.run([str(x) for x in args],check=True,**kw)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if sys.platform!='darwin':raise SystemExit('Native macOS only')
    os.environ['MACOSX_DEPLOYMENT_TARGET']='14.0'
    tess=WORK/'ocr-runtime'
    provenance=json.loads((tess/'OCR-PROVENANCE.json').read_text())
    assert all(digest(tess/n)==h for n,h in provenance['files'].items())
    run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
         '--name',NAME,'--target-arch','arm64','--osx-bundle-identifier','local.maple.overlay.private',
         '--codesign-identity','-', '--add-data',str(ROOT/'assets')+':assets',
         '--add-data',str(tess)+':tesseract', '--distpath',WORK/'dist',
         '--workpath',WORK/'pyinstaller-work','--specpath',WORK,ROOT/'maple_exp.py'])
    app=WORK/'dist'/(NAME+'.app')
    info=app/'Contents/Info.plist'
    with info.open('rb') as f:data=plistlib.load(f)
    data.update(CFBundleShortVersionString=VERSION,CFBundleVersion=VERSION,
                LSMinimumSystemVersion='14.0',NSHighResolutionCapable=True,
                NSScreenCaptureUsageDescription='Read visible MapleStory game HUD numbers while the game is in front. No screenshot uploads.')
    with info.open('wb') as f:plistlib.dump(data,f)
    # Sign nested native components before the final bundle seal.
    native=[]
    for p in app.rglob('*'):
        if p.is_symlink() or not p.is_file():continue
        with p.open('rb') as f:magic=f.read(4)
        if magic in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):
            native.append(p)
    for p in sorted(native,key=lambda p:len(p.parts),reverse=True):run(['/usr/bin/codesign','--force','--sign','-',p])
    run(['/usr/bin/codesign','--force','--deep','--sign','-',app])
    run(['/usr/bin/codesign','--verify','--deep','--strict','--verbose=2',app])
    manifest={p.relative_to(app).as_posix():digest(p) for p in sorted(app.rglob('*')) if p.is_file() and not p.is_symlink()}
    (WORK/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',app,WORK/'candidate-debug.zip'])
    print('App assembled and ad-hoc signature verified. Not notarized.')
if __name__=='__main__':main()
