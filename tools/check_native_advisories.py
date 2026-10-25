"""Fail closed on OSV commit matches for the source-built native OCR components."""
import json
from pathlib import Path
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
sources = [s for s in json.loads((ROOT/'tools/ocr-sources.json').read_text()) if s['name'] != 'eng.traineddata']
request = urllib.request.Request('https://api.osv.dev/v1/querybatch', data=json.dumps({'queries':[{'commit':s['commit']} for s in sources]}).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=60) as response:
    results = json.load(response)['results']
if len(results) != len(sources):
    raise SystemExit('Incomplete native advisory response')
report={'provider':'OSV','scope':'Four pinned native source commits. Coverage is not exhaustive; no matches is not a safety guarantee.',
        'components':[dict(name=s['name'],version=s['version'],commit=s['commit'],advisories=r.get('vulns',[])) for s,r in zip(sources,results)],
        'advisory_matches':sum(len(r.get('vulns',[])) for r in results)}
work=ROOT/'verification/windows-review';work.mkdir(parents=True,exist_ok=True)
(work/'native-advisories.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if report['advisory_matches']:
    raise SystemExit('Native source advisories block publication')
