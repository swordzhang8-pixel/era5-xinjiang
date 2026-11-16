from pathlib import Path
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
import urllib.request,time,hashlib,json,shutil
out=Path(__file__).resolve().parent
data=out/'GFS';data.mkdir(parents=True,exist_ok=True)

def get(t):
 name=f'gfs_{t:%Y%m%d_%H}_1p00_f000.grib2';p=data/name
 url=f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{t:%Y%m%d}/{t:%H}/atmos/gfs.t{t:%H}z.pgrb2.1p00.f000'
 if p.exists() and p.stat().st_size>1000000:
  return {'name':name,'url':url,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 for attempt in range(4):
  try:
   part=p.with_suffix('.part');h=hashlib.sha256();size=0
   with urllib.request.urlopen(url,timeout=90) as r,part.open('wb') as f:
    expected=int(r.headers['Content-Length'])
    while True:
     chunk=r.read(1024*1024)
     if not chunk:break
     f.write(chunk);h.update(chunk);size+=len(chunk)
   assert size==expected
   with part.open('rb') as f:
    assert f.read(4)==b'GRIB';f.seek(-4,2);assert f.read()==b'7777'
   part.replace(p);print('Downloaded',name,size,flush=True)
   return {'name':name,'url':url,'bytes':size,'sha256':h.hexdigest()}
  except Exception as e:
   if attempt==3:raise
   print('Retry',name,type(e).__name__,flush=True);time.sleep(2+attempt*3)
dates=[datetime(2024,7,1)+timedelta(hours=6*i) for i in range(41)]
with ThreadPoolExecutor(max_workers=4) as pool:results=[f.result() for f in as_completed([pool.submit(get,t) for t in dates])]
results.sort(key=lambda r:r['name'])
(out/'download_manifest.json').write_text(json.dumps(results,indent=2))
print('DOWNLOAD_COMPLETE',len(results),sum(r['bytes'] for r in results),flush=True)

