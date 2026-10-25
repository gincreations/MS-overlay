"""Run each suite in isolation, preserving logs and bounded stack-dump diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[name]="1"
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/windows-review'
OUT.mkdir(parents=True,exist_ok=True)
bootstrap="import faulthandler,runpy,sys,cv2;from pathlib import Path;cv2.setNumThreads(1);cv2.ipp.setUseIPP(False);path=sys.argv[1];sys.path.insert(0,str(Path(path).parent));sys.argv=[path,'-v'];faulthandler.dump_traceback_later(90,file=sys.stderr);runpy.run_path(path,run_name='__main__')"
report=OUT/'test-suites.json'
results=json.loads(report.read_text()) if report.exists() and sys.argv[1:] else []
paths=sorted((ROOT/'tests').glob('test_*.py'))
if sys.argv[1:]:
 requested=set(sys.argv[1:])
 if not requested <= {p.stem for p in paths}: raise SystemExit('Unknown regression suite')
 paths=[p for p in paths if p.stem in requested]
for path in paths:
 start=time.monotonic()
 os.environ['MAPLE_EXP_DATA']=str(OUT/'test-data'/path.stem)
 print('START',path.name,flush=True)
 with (OUT/(path.stem+'.txt')).open('w',encoding='utf-8') as log:
  try:
   r=subprocess.run([sys.executable,'-u','-c',bootstrap,str(path)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
   code=r.returncode
  except subprocess.TimeoutExpired:
   code=124;log.write('\nSUITE TIMEOUT (600 seconds)\n')
 row={'suite':path.stem,'exit':code,'seconds':round(time.monotonic()-start,2)}
 results.append(row);(OUT/'test-suites.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(row),flush=True)
 if code:
  print((OUT/(path.stem+'.txt')).read_text()[-18000:])
  raise SystemExit('Regression gate failed; see preserved suite log')
