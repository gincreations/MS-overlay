"""Reuse a preserved native build only with matching source and exact file inventory.
This does not clear it for execution: the normal Defender/OCR gates still follow.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

REPO = os.environ.get('GITHUB_REPOSITORY', 'gincreations/MS-overlay')
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification/windows-review'

def api(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/{endpoint}']))

def main():
    run_id = os.environ['REUSE_OCR_RUN_ID']
    if not re.fullmatch(r'[0-9]+', run_id):
        raise RuntimeError('Invalid source run')
    run = api(f'actions/runs/{run_id}')
    if run['repository']['full_name'] != REPO or run['path'] != '.github/workflows/windows-review.yml':
        raise RuntimeError('Unexpected build provenance')
    jobs = api(f'actions/runs/{run_id}/jobs?per_page=100')['jobs']
    if not any(step['name'] == 'Build minimal pinned native OCR (no execution)' and step['conclusion'] == 'success'
               for job in jobs for step in job['steps']):
        raise RuntimeError('Source run did not successfully compile native OCR')
    for name in ('tools/build_ocr_runtime.py', 'tools/ocr-sources.json'):
        old = base64.b64decode(api(f'contents/{name}?ref={run["head_sha"]}')['content'])
        if old.replace(b'\r\n', b'\n') != (ROOT / name).read_bytes().replace(b'\r\n', b'\n'):
            raise RuntimeError(f'Build source changed: {name}')
    stage = OUT / 'reused-ocr'
    stage.mkdir(parents=True, exist_ok=False)
    subprocess.run(['gh', 'run', 'download', run_id, '--repo', REPO, '--name',
                    'native-ocr-build-not-release-cleared', '--dir', str(stage)], check=True)
    provenance = json.loads((stage / 'ocr-provenance.json').read_text())
    manifest = json.loads((ROOT / 'tools/ocr-sources.json').read_text())
    if provenance['sources'] != manifest:
        raise RuntimeError('Source manifest mismatch')
    runtime = stage / 'ocr-runtime'
    if json.loads((runtime / 'OCR-PROVENANCE.json').read_text()) != provenance:
        raise RuntimeError('Bundled provenance mismatch')
    actual = {p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}
    if actual != set(provenance['files']) | {'OCR-PROVENANCE.json'}:
        raise RuntimeError('Unexpected native file inventory')
    for name, expected in provenance['files'].items():
        path = runtime / name
        if path.is_symlink() or not path.resolve().is_relative_to(runtime.resolve()):
            raise RuntimeError('Unsafe native path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Native file hash mismatch: {name}')
    shutil.copytree(runtime, OUT / 'ocr-runtime')
    shutil.copy2(stage / 'ocr-provenance.json', OUT / 'ocr-provenance.json')
    (OUT / 'ocr-reuse.json').write_text(json.dumps({
        'sourceRun': run_id, 'sourceCommit': run['head_sha'],
        'buildSourcesMatched': True, 'inventoryAndHashesMatched': True,
        'executionCleared': False}, indent=2))
    print('Native OCR provenance and complete inventory verified; scan still required.')

if __name__ == '__main__':
    main()
