"""Verify the assembled Mac app without capturing the runner desktop or real gameplay."""
import hashlib
import json
import marshal
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from package_preview import APP_SOURCES
from PyInstaller.archive.readers import CArchiveReader
WORK=ROOT/'verification/macos-review'
NAME='Maple Private Overlay'
APP=WORK/'dist'/(NAME+'.app')
EXE=APP/'Contents/MacOS'/NAME
VERSION=re.search(r'^VERSION = "([^"]+)"',(ROOT/'maple_exp.py').read_text(),re.M)[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def output(args):return subprocess.check_output([str(x) for x in args],text=True,stderr=subprocess.STDOUT)
def normalize(code):
    if isinstance(code,types.CodeType):
        return code.replace(co_filename='<source>',co_consts=tuple(normalize(x) for x in code.co_consts))
    if isinstance(code,tuple):return tuple(normalize(x) for x in code)
    if isinstance(code,frozenset):return frozenset(normalize(x) for x in code)
    return code

def main():
    assert sys.platform=='darwin'
    manifest=json.loads((WORK/'runtime-manifest.json').read_text())
    assert all(digest(APP/p)==h for p,h in manifest.items())
    signature=output(['/usr/bin/codesign','--verify','--deep','--strict','--verbose=2',APP])
    native=[]
    for p in APP.rglob('*'):
        if p.is_symlink():
            assert p.resolve().is_relative_to(APP.resolve()), 'Escaping bundle symlink'
            continue
        if not p.is_file():continue
        with p.open('rb') as f:magic=f.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):continue
        arch=output(['/usr/bin/lipo','-archs',p]).strip()
        assert arch=='arm64',(p.name,arch)
        linked=[x.strip().split(' (')[0] for x in output(['/usr/bin/otool','-L',p]).splitlines()[1:]]
        for dep in linked:
            assert dep.startswith(('/usr/lib/','/System/Library/','@loader_path/','@executable_path/','@rpath/')),dep
        loads=output(['/usr/bin/otool','-l',p])
        versions=re.findall(r'\bminos (\d+\.\d+(?:\.\d+)?)',loads)
        assert all(tuple(map(int,v.split('.'))) <= (14,0,0) for v in versions),(p.name,versions)
        native.append({'path':p.relative_to(APP).as_posix(),'arch':arch,'imports':linked,'minimumOS':versions})
    archive=CArchiveReader(str(EXE))
    pyz=archive.open_embedded_archive('PYZ.pyz')
    verified=[]
    for name,path in APP_SOURCES.items():
        actual=marshal.loads(archive.extract(name)) if name=='maple_exp' else pyz.extract(name)
        expected=compile((ROOT/path).read_bytes(),path,'exec',dont_inherit=True,optimize=0)
        assert normalize(actual)==normalize(expected),'Embedded source mismatch: '+name
        verified.append({'module':name,'sha256':digest(ROOT/path)})
    tess=next(p for p in APP.rglob('tesseract') if p.is_file() and not p.is_symlink())
    version=output([tess,'--version'])
    for expected in ('tesseract 5.5.3','leptonica-1.87.0','libpng 1.6.59','zlib 1.3.2.1-motley'):assert expected in version,(expected,version)
    for unwanted in ('libcurl','libarchive','libtiff','libjpeg','libwebp','OpenSSL'):assert unwanted.lower() not in version.lower()
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    import ocr
    font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',42)
    assert (tess.parent/'tessdata/eng.traineddata').is_file(), 'OCR executable cannot reach bundled language model'
    reader=ocr.Tesseract(str(tess),timeout=20)
    samples=[]
    for text,chars in [('1234567890','0123456789'),('5,410,845','0123456789,'),('Maple Classic',None)]:
        image=Image.new('L',(600,90),255);ImageDraw.Draw(image).text((20,15),text,font=font,fill=0)
        try:
            value=reader.read_line(np.array(image),chars)
        except ocr.TesseractError:
            import cv2
            ok,png=cv2.imencode('.png',np.array(image));assert ok
            failure=subprocess.run([str(tess),'stdin','stdout','--psm','7'],input=png.tobytes(),capture_output=True,env=reader.env,timeout=20)
            (WORK/'ocr-failure.txt').write_text(failure.stderr.decode('utf-8','replace'))
            print(failure.stderr.decode('utf-8','replace'),flush=True)
            raise
        assert value.strip()==text,(text,value)
        samples.append({'expected':text,'actual':value})
    subprocess.run([str(EXE),'--check-setup'],cwd=WORK,check=True,timeout=180)
    setup=json.loads((WORK/'setup-check.json').read_text());assert setup['passed']
    assert all(digest(APP/p)==h for p,h in manifest.items()),'App changed during tests'
    release=WORK/'release';release.mkdir(exist_ok=True)
    stage=WORK/'package'/'MS Overlay Mac';stage.mkdir(parents=True,exist_ok=True)
    shutil.copytree(APP,stage/APP.name,symlinks=True,dirs_exist_ok=True)
    for name in ('LICENSE','MACOS.md'):
        if (ROOT/name).exists():shutil.copy2(ROOT/name,stage/name)
    script=stage/'Check setup.command'
    script.write_text('#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nexec "./Maple Private Overlay.app/Contents/MacOS/Maple Private Overlay" --check-setup\n')
    script.chmod(0o755)
    archive_path=release/f'MS-Overlay-{VERSION}-mac-arm64.zip'
    subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(stage),str(archive_path)],check=True)
    # Check the distributable extraction, not merely the build directory.
    unpack=WORK/'roundtrip'
    subprocess.run(['/usr/bin/ditto','-x','-k',str(archive_path),str(unpack)],check=True)
    restored=unpack/stage.name/APP.name
    output(['/usr/bin/codesign','--verify','--deep','--strict',restored])
    assert all(digest(restored/p)==h for p,h in manifest.items())
    source=release/f'MS-Overlay-{VERSION}-mac-source.zip'
    subprocess.run(['git','archive','--format=zip','--output='+str(source),'HEAD'],cwd=ROOT,check=True)
    report={'version':VERSION,'platform':'Apple Silicon macOS 14+',
            'commit':output(['git','rev-parse','HEAD']).strip(),'signature':'ad-hoc, not Developer ID/notarized',
            'signatureVerification':signature,'nativeFiles':native,'embeddedSource':verified,
            'ocrVersion':version,'ocrSamples':samples,'setup':setup,'runtimeFileCount':len(manifest),
            'zipRoundtripVerified':True,'scope':'Synthetic regression and no-capture packaged startup; real game and user Screen Recording permission still require Mac tester validation.'}
    (WORK/'mac-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copy2(WORK/'mac-verification.json',release/'mac-verification.json')
    shutil.copy2(WORK/'runtime-manifest.json',release/'runtime-manifest.json')
    sums=''.join(digest(p)+'  '+p.name+'\n' for p in sorted(release.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt')
    (release/'SHA256SUMS.txt').write_text(sums)
    print(json.dumps({'passed':True,'modules':len(verified),'nativeFiles':len(native),'runtimeFiles':len(manifest),'zip':archive_path.name}))
if __name__=='__main__':main()
