"""Build a minimal static Windows OCR CLI from hash-pinned official sources.

No legacy executable/DLL is reused. This builds but does not execute the CLI;
Defender must clear the full candidate before tools/verify_ocr_runtime.py runs.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'verification/windows-review'
NATIVE = WORK / 'ocr-build'
PREFIX = NATIVE / 'install'
BUNDLE = WORK / 'ocr-runtime'
SOURCES = json.loads((ROOT / 'tools/ocr-sources.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(spec, dest):
    if not dest.exists() or digest(dest) != spec['sha256']:
        with urllib.request.urlopen(spec['url'], timeout=120) as response, dest.open('wb') as output:
            shutil.copyfileobj(response, output)
    if digest(dest) != spec['sha256']:
        raise RuntimeError('Source digest mismatch: ' + spec['name'])


def run(args, label):
    log = WORK / (label + '.txt')
    with log.open('w', encoding='utf-8') as output:
        proc = subprocess.run(args, stdout=output, stderr=subprocess.STDOUT)
    print(label, 'exit', proc.returncode, flush=True)
    if proc.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-100:]))
        raise RuntimeError('Native build failed: ' + label)


def main():
    if sys.platform != 'win32':
        raise SystemExit('Native Windows builder only')
    NATIVE.mkdir(parents=True, exist_ok=True)
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    (BUNDLE / 'tessdata').mkdir(parents=True)
    (BUNDLE / 'licenses').mkdir()
    vswhere = Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    vs_version = subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationVersion'], text=True).strip()
    if not vs_version: raise RuntimeError('MSVC C++ tools unavailable')
    generators = subprocess.check_output(['cmake','--help'], text=True)
    match = re.search(r'Visual Studio '+re.escape(vs_version.split('.')[0])+r' [0-9]{4}', generators)
    if not match: raise RuntimeError('Installed MSVC has no supported CMake generator')
    generator = match.group(0)
    common = ['-G', generator, '-A', 'x64',
              '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_LIBDIR=lib',
              '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
              '-DCMAKE_POLICY_DEFAULT_CMP0091=NEW',
              '-DCMAKE_INSTALL_PREFIX=' + PREFIX.as_posix(),
              '-DCMAKE_PREFIX_PATH=' + PREFIX.as_posix(),
              '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
              '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF']
    zlib = ['-DZLIB_LIBRARY=' + (PREFIX/'lib/libzs.lib').as_posix(),
            '-DZLIB_INCLUDE_DIR=' + (PREFIX/'include').as_posix()]
    options = {
        'zlib': ['-DZLIB_BUILD_SHARED=OFF', '-DZLIB_BUILD_STATIC=ON',
                 '-DZLIB_BUILD_TESTING=OFF', '-DZLIB_INSTALL=ON'],
        'libpng': zlib + ['-DPNG_SHARED=OFF', '-DPNG_STATIC=ON', '-DPNG_TESTS=OFF', '-DPNG_TOOLS=OFF'],
        'leptonica': zlib + ['-DSW_BUILD=OFF', '-DBUILD_PROG=OFF', '-DSTRICT_CONF=ON',
                            '-DENABLE_ZLIB=ON', '-DENABLE_PNG=ON'] +
                     ['-DENABLE_' + codec + '=OFF' for codec in ('GIF','JPEG','TIFF','WEBP','OPENJPEG')],
        'tesseract': ['-DBUILD_TRAINING_TOOLS=OFF', '-DBUILD_TESTS=OFF',
                      '-DDISABLE_CURL=ON', '-DDISABLE_ARCHIVE=ON', '-DDISABLE_TIFF=ON',
                      '-DGRAPHICS_DISABLED=ON', '-DOPENMP_BUILD=OFF',
                      '-DENABLE_NATIVE=OFF', '-DWIN32_MT_BUILD=ON'],
    }
    report = {'sources': SOURCES, 'compiler': 'MSVC x64 / static CRT', 'visualStudioVersion': vs_version, 'generator': generator,
              'cmake': subprocess.check_output(['cmake','--version'], text=True).splitlines()[0],
              'features': 'PNG/zlib only external image codecs; no curl, archive, TLS, training tools or ScrollView',
              'configureOptions': {}, 'files': {}}
    for spec in SOURCES:
        name = spec['name']
        if name == 'eng.traineddata':
            fetch(spec, BUNDLE/'tessdata/eng.traineddata')
            continue
        archive = NATIVE / (name + '.tar.gz')
        fetch(spec, archive)
        source = NATIVE / (name + '-source')
        if source.exists():
            shutil.rmtree(source)
        source.mkdir()
        with tarfile.open(archive) as tar:
            # tarfile's data filter rejects traversal, unsafe links and devices.
            tar.extractall(source, filter='data')
        roots = list(source.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise RuntimeError('Unexpected source archive layout')
        source = roots[0]
        build = NATIVE / (name + '-build')
        if build.exists():
            shutil.rmtree(build)
        flags = common + options[name]
        report['configureOptions'][name] = [x.replace(PREFIX.as_posix(), '<install>') for x in flags]
        run(['cmake','-S',str(source),'-B',str(build),*flags], 'ocr-' + name + '-configure')
        run(['cmake','--build',str(build),'--config','Release','--parallel','4'], 'ocr-' + name + '-compile')
        run(['cmake','--install',str(build),'--config','Release'], 'ocr-' + name + '-install')
        for license_name in ('LICENSE','LICENSE.txt','COPYING','README','leptonica-license.txt'):
            p = source / license_name
            if p.is_file():
                shutil.copyfile(p, BUNDLE/'licenses'/(name+'-'+license_name+'.txt'))
        shutil.copyfile(build/'CMakeCache.txt', WORK/('ocr-'+name+'-cache.txt'))
    shutil.copyfile(PREFIX/'bin/tesseract.exe', BUNDLE/'tesseract.exe')
    configs = PREFIX/'share/tessdata'
    for name in ('configs','tessconfigs'):
        if (configs/name).exists():
            shutil.copytree(configs/name, BUNDLE/'tessdata'/name)
    # English model is byte-identical to RC2, now pinned to its official source.
    (BUNDLE/'licenses/eng-model.txt').write_text('English model: tesseract-ocr/tessdata_fast; Apache-2.0. See official pinned source in OCR-PROVENANCE.json.\n')
    import pefile
    pe = pefile.PE(str(BUNDLE/'tesseract.exe'))
    imports = sorted({item.dll.decode('ascii').lower() for attr in ('DIRECTORY_ENTRY_IMPORT','DIRECTORY_ENTRY_DELAY_IMPORT') for item in getattr(pe,attr,[])})
    system = {'kernel32.dll','user32.dll','gdi32.dll','advapi32.dll','shell32.dll','ole32.dll','oleaut32.dll','ws2_32.dll','ntdll.dll','bcrypt.dll','crypt32.dll','version.dll','shlwapi.dll','secur32.dll','rpcrt4.dll'}
    unexpected = [x for x in imports if x not in system and not x.startswith(('api-ms-win-','ext-ms-win-'))]
    if unexpected:
        raise RuntimeError('Unexpected non-system OCR dependencies: ' + repr(unexpected))
    report['imports'] = imports
    report['files'] = {p.relative_to(BUNDLE).as_posix(): digest(p) for p in sorted(BUNDLE.rglob('*')) if p.is_file()}
    (BUNDLE/'OCR-PROVENANCE.json').write_text(json.dumps(report,indent=2)+'\n')
    (WORK/'ocr-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Minimal native OCR built; not executed. Imports:', imports)


if __name__ == '__main__':
    main()
