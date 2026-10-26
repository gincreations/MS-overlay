"""Build a minimal static arm64 macOS 14 OCR CLI from the shared pinned source manifest.
No Homebrew OCR runtime or legacy executable is redistributed.
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
WORK = ROOT / 'verification/macos-review'
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
    if sys.platform != 'darwin':
        raise SystemExit('Native macOS builder only')
    import platform
    if platform.machine() != 'arm64':
        raise SystemExit('Apple Silicon runner required')
    NATIVE.mkdir(parents=True, exist_ok=True)
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    (BUNDLE / 'tessdata').mkdir(parents=True)
    (BUNDLE / 'licenses').mkdir()
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = '14.0'
    os.environ['PKG_CONFIG_LIBDIR'] = str(PREFIX / 'lib/pkgconfig')
    common = ['-G', 'Unix Makefiles', '-DCMAKE_BUILD_TYPE=Release',
              '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0',
              '-DCMAKE_INSTALL_LIBDIR=lib', '-DCMAKE_INSTALL_PREFIX=' + str(PREFIX),
              '-DCMAKE_PREFIX_PATH=' + str(PREFIX), '-DBUILD_SHARED_LIBS=OFF',
              '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local',
              '-DCMAKE_FIND_FRAMEWORK=NEVER',
              '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
              '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF']
    zlib = ['-DZLIB_LIBRARY=' + str(PREFIX/'lib/libz.a'),
            '-DZLIB_INCLUDE_DIR=' + str(PREFIX/'include')]
    options = {
        'zlib': ['-DZLIB_BUILD_SHARED=OFF', '-DZLIB_BUILD_STATIC=ON',
                 '-DZLIB_BUILD_TESTING=OFF', '-DZLIB_INSTALL=ON'],
        'libpng': zlib + ['-DPNG_SHARED=OFF', '-DPNG_FRAMEWORK=OFF', '-DPNG_STATIC=ON', '-DPNG_TESTS=OFF', '-DPNG_TOOLS=OFF'],
        'leptonica': zlib + ['-DPNG_PNG_INCLUDE_DIR:PATH=' + str(PREFIX/'include'),
                            '-DPNG_LIBRARY_RELEASE:FILEPATH=' + str(PREFIX/'lib/libpng16.a'),
                            '-DSW_BUILD=OFF', '-DBUILD_PROG=OFF', '-DSTRICT_CONF=ON',
                            '-DENABLE_ZLIB=ON', '-DENABLE_PNG=ON'] +
                     ['-DENABLE_' + codec + '=OFF' for codec in ('GIF','JPEG','TIFF','WEBP','OPENJPEG')],
        'tesseract': ['-DBUILD_TRAINING_TOOLS=OFF', '-DBUILD_TESTS=OFF',
                      '-DDISABLE_CURL=ON', '-DDISABLE_ARCHIVE=ON', '-DDISABLE_TIFF=ON',
                      '-DGRAPHICS_DISABLED=ON', '-DOPENMP_BUILD=OFF',
                      '-DENABLE_NATIVE=OFF'],
    }
    report = {'sources': SOURCES, 'compiler': 'Apple clang arm64 / static OCR libraries',
              'deploymentTarget': '14.0',
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
        if name == 'leptonica':
            cache = (build/'CMakeCache.txt').read_text()
            assert 'PNG_PNG_INCLUDE_DIR:PATH=' + str(PREFIX/'include') in cache
            assert 'PNG_LIBRARY_RELEASE:FILEPATH=' + str(PREFIX/'lib/libpng16.a') in cache
        run(['cmake','--build',str(build),'--config','Release','--parallel','4'], 'ocr-' + name + '-compile')
        run(['cmake','--install',str(build),'--config','Release'], 'ocr-' + name + '-install')
        for license_name in ('LICENSE','LICENSE.txt','COPYING','README','leptonica-license.txt'):
            p = source / license_name
            if p.is_file():
                shutil.copyfile(p, BUNDLE/'licenses'/(name+'-'+license_name+'.txt'))
        shutil.copyfile(build/'CMakeCache.txt', WORK/('ocr-'+name+'-cache.txt'))
    shutil.copy2(PREFIX/'bin/tesseract', BUNDLE/'tesseract')
    configs = PREFIX/'share/tessdata'
    for name in ('configs','tessconfigs'):
        if (configs/name).exists():
            shutil.copytree(configs/name, BUNDLE/'tessdata'/name)
    # English model is byte-identical to RC2, now pinned to its official source.
    (BUNDLE/'licenses/eng-model.txt').write_text('English model: tesseract-ocr/tessdata_fast; Apache-2.0. See official pinned source in OCR-PROVENANCE.json.\n')
    cli = BUNDLE/'tesseract'
    subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(cli)],check=True)
    imports = [line.strip().split(' (')[0] for line in subprocess.check_output(
        ['/usr/bin/otool','-L',str(cli)],text=True).splitlines()[1:]]
    if any(not name.startswith(('/usr/lib/','/System/Library/')) for name in imports):
        raise RuntimeError('OCR depends on a non-system dynamic library: ' + repr(imports))
    report['imports'] = imports
    report['files'] = {p.relative_to(BUNDLE).as_posix(): digest(p) for p in sorted(BUNDLE.rglob('*')) if p.is_file()}
    (BUNDLE/'OCR-PROVENANCE.json').write_text(json.dumps(report,indent=2)+'\n')
    (WORK/'ocr-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Minimal Mac OCR built; not executed. Imports:', imports)


if __name__ == '__main__':
    main()
