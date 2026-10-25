"""Summarize only candidate process trees; never upload raw machine-wide traces."""
import csv,json,re,os
from pathlib import Path
from collections import Counter
base=Path('verification/extended-security').resolve()
report=base/'runtime-observation.json'
if not report.exists():
 print('No runtime observation report; preceding gate failed.');raise SystemExit(1)
r=json.loads(report.read_text(encoding='utf-8-sig'));trace=base/'trace.csv'
if not trace.exists():
 print('No usable trace; no behavioral clearance.');raise SystemExit(1)
def rows():
 with trace.open(encoding='utf-8-sig',errors='replace',newline='') as f:yield from csv.DictReader(f)
roots={int(x['pid']):x['phase'] for x in r['roots']};parents={}
for row in rows():
 if row.get('Operation')=='Process Start':
  m=re.search(r'Parent PID: (\d+)',row.get('Detail',''))
  if m:parents[int(row['PID'])]=int(m[1])
 elif row.get('Operation')=='Process Create':
  m=re.search(r'PID: (\d+)',row.get('Detail',''))
  if m:parents[int(m[1])]=int(row['PID'])
def phase(pid):
 seen=set()
 while pid not in seen:
  if pid in roots:return roots[pid]
  seen.add(pid)
  if pid not in parents:return None
  pid=parents[pid]
 return None
def clean(s):
 for value,label in [(str(base),'<review>'),(os.environ.get('USERPROFILE',''),'<runner-home>'),(os.environ.get('GITHUB_WORKSPACE',''),'<checkout>')]:
  if value:s=re.sub(re.escape(value),lambda m:label,s,flags=re.I)
 return s
counts=Counter();network=[];sensitive=[];persistence=[];untrusted=[];children=set();loads=set();total=0
for row in rows():
 try:pid=int(row['PID'])
 except (KeyError,ValueError):continue
 ph=phase(pid)
 if not ph:continue
 total+=1;op=row.get('Operation','');path=row.get('Path','');result=row.get('Result','')
 counts[ph+' / '+op]+=1
 event={'phase':ph,'process':row.get('Process Name',''),'operation':op,'path':clean(path),'result':result}
 if op.startswith(('TCP ','UDP ')):network.append(event)
 if re.search(r'Google\\Chrome\\User Data|Exodus\\exodus.wallet|Electrum\\wallets|Login Data|Local State',path,re.I):sensitive.append(event)
 if re.search(r'\\CurrentVersion\\Run(?:Once)?(?:\\|$)|\\Start Menu\\Programs\\Startup|\\System32\\Tasks',path,re.I) and op in ('RegSetValue','WriteFile','CreateFile'):persistence.append(event)
 if op=='Load Image':
  loads.add((ph,clean(path)))
  if 'untrusted-working-directory' in path.lower():untrusted.append(event)
 if op=='Process Create':children.add((ph,clean(path)))
summary={'zipSHA256':r['zipSHA256'],'scope':'Bounded packaged setup and 20-second normal startup; synthetic bundled-OCR crop; separate exact-source helper search probe. No live game/full-session coverage. Procmon is not a clipboard API monitor.','eventsInCandidateTrees':total,'operationCounts':dict(counts),'networkEvents':network[:100],'networkEventCount':len(network),'sensitiveFileEvents':sensitive[:100],'sensitiveFileEventCount':len(sensitive),'possiblePersistenceEvents':persistence[:100],'untrustedDirectoryImageLoads':untrusted,'childImages':[{'phase':p,'path':x} for p,x in sorted(children)],'loadedImages':[{'phase':p,'path':x} for p,x in sorted(loads)],'helperCanaryExecuted':r['helperCanaryExecuted'],'rawMachineTracePublished':False}
(base/'behavior-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k not in ('operationCounts','loadedImages')},indent=2))
if total==0:raise SystemExit('Empty trace cannot support conclusions')
