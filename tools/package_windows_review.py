"""Package only the exact runtime files that passed native scan and setup."""
import hashlib
import json
import marshal
import re
import types
from pathlib import Path
import struct
import subprocess
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from package_preview import APP_SOURCES, parse_archive

work = ROOT / 'verification/windows-review'
app = work / 'candidate'
out = work / 'download'
out.mkdir(exist_ok=True)
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((work / 'runtime-manifest.json').read_text())
for name, expected in manifest.items():
    if sha((app / name).read_bytes()) != expected:
        raise SystemExit('Runtime changed after preparation: ' + name)
review = json.loads((work / 'defender.json').read_text(encoding='utf-8-sig'))
exe = app / 'Maple Private Overlay.exe'
if review.get('scanExit') != 0 or not review.get('runtimeTestCompleted') or sha(exe.read_bytes()) != review['sha256'].lower():
    raise SystemExit('Exact EXE did not pass scan/setup')
ocr_review = json.loads((work/'ocr-validation.json').read_text())
if not ocr_review.get('passed') or not review.get('realtimeEnabled'):
    raise SystemExit('OCR verification and realtime Defender are required')
# Compare all embedded app code objects with this checkout, without executing them.
_, entries, _ = parse_archive(exe.read_bytes(), expected_python=313)
entries = {name: data for name, kind, flag, data in entries}
pyz = entries['PYZ.pyz']
toc = dict(marshal.loads(pyz[struct.unpack('!I', pyz[8:12])[0]:]))
def canonical(code):
    return code.replace(co_filename='<source>',co_consts=tuple(canonical(c) if isinstance(c,types.CodeType) else c for c in code.co_consts))
for module, path in APP_SOURCES.items():
    if module == 'maple_exp':
        code = entries['maple_exp']
    else:
        _, offset, size = toc[module]
        code = zlib.decompress(pyz[offset:offset+size])
    expected = compile((ROOT / path).read_bytes(), path, 'exec', dont_inherit=True, optimize=0)
    if canonical(marshal.loads(code)) != canonical(expected):
        raise SystemExit('Embedded/source mismatch: ' + module)
source = out / 'Maple-Private-Overlay-source.zip'
subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(source), 'HEAD'], cwd=ROOT, check=True)
version = re.search(r'^VERSION = "([^"]+)"', (ROOT/'maple_exp.py').read_text(), re.M)[1]
portable = out / f'Maple-Private-Overlay-{version}-portable.zip'
prefix = 'Maple Private Overlay/'
with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in sorted(manifest):
        z.write(app / name, prefix + name)
    z.write(source, prefix + source.name)
    for name in ('README.md', 'UPSTREAM.md', 'CHANGELOG.md'):
        z.write(ROOT / name, prefix + name)
    for path in sorted((ROOT / 'docs').glob('*')):
        if path.is_file(): z.write(path, prefix + 'docs/' + path.name)
    for path in sorted(ROOT.glob('LICENSE*')):
        if path.is_file(): z.write(path, prefix + path.name)
    z.writestr(prefix + 'Check setup.cmd', '@echo off\r\ncd /d "%~dp0"\r\n"Maple Private Overlay.exe" --check-setup\r\npause\r\n')
    z.writestr(prefix + 'READ FIRST.txt', 'Maple Private Overlay 0.1.19 RC2\nExtract the entire ZIP before running. No administrator privileges are needed.\nRun Check setup.cmd, then Maple Private Overlay.exe.\nThis exact EXE passed an enabled Defender scan and native setup on an isolated Windows runner.\nThese checks are not a guarantee against all malicious behavior. The old 0.1.17 detection is unresolved.\nDo not disable antivirus or add exclusions. If detected, stop and retain the alert details.\nNo self-updater, telemetry, wallet/password access features, or automatic uploads.\n')
    z.writestr(prefix + 'WINDOWS-REVIEW.json', json.dumps(review, indent=2))
    z.writestr(prefix + 'RUNTIME-SHA256.json', json.dumps(manifest, indent=2))
    z.write(app / 'setup-check.json', prefix + 'TESTED-SETUP.json')
k, offset, size = toc['PIL._version']
pillow_code = marshal.loads(zlib.decompress(pyz[offset:offset+size]))
if '13.0.0' not in pillow_code.co_consts: raise SystemExit('Packaged Pillow is not patched13.0.0')
advisories=json.loads((work/'advisories.json').read_text())
if advisories['advisory_matches']: raise SystemExit('Dependency advisory gate failed')
native_advisories=json.loads((work/'native-advisories.json').read_text())
if native_advisories['advisory_matches']: raise SystemExit('Native advisory gate failed')
result = dict(review, pythonVersion=sys.version.split()[0], packagedPillow='13.0.0', dependencyAdvisoryMatches=0, buildMethod='Fresh native PyInstaller onedir; UPX disabled', ocrValidation=ocr_review, sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(), embeddedModulesMatched=len(APP_SOURCES), runtimeFilesUnchanged=len(manifest), zipSha256=sha(portable.read_bytes()), sourceZipSha256=sha(source.read_bytes()), portableZipScanned=False)
(out / 'REVIEW.json').write_text(json.dumps(result,indent=2))
(out / 'SHA256SUMS.txt').write_text(f"{result['zipSha256']}  {portable.name}\n{result['sourceZipSha256']}  {source.name}\n{sha(exe.read_bytes())}  Maple Private Overlay.exe\n")
print(json.dumps(result, indent=2))

for name in ('native-build.json','advisories.json','ocr-provenance.json','ocr-validation.json','native-advisories.json'):
    (out/name).write_bytes((work/name).read_bytes())
