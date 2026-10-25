"""Fail the release gate if declared pinned Python dependencies have OSV matches."""
import json
from pathlib import Path
import re
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
packages=[re.match(r'([^#\s=]+)==([^\s]+)',l).groups() for l in (ROOT/'requirements-build.txt').read_text().splitlines() if re.match(r'([^#\s=]+)==([^\s]+)',l)]
req=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps({'queries':[{'package':{'name':n,'ecosystem':'PyPI'},'version':v} for n,v in packages]}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=60) as response: data=json.load(response)
if len(data['results'])!=len(packages): raise SystemExit('Incomplete advisory response')
rows=[{'name':n,'version':v,'advisories':x.get('vulns',[])} for (n,v),x in zip(packages,data['results'])]
report={'provider':'OSV','scope':'Declared pinned Python dependencies, not exhaustive native DLL/OS coverage','packages':rows,'advisory_matches':sum(len(x['advisories']) for x in rows)}
p=ROOT/'verification/windows-review';p.mkdir(parents=True,exist_ok=True);(p/'advisories.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if report['advisory_matches']: raise SystemExit('Dependency security findings block release')
