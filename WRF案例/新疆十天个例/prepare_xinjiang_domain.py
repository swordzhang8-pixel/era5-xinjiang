"""Ubuntu: create isolated Xinjiang WPS domain using the saved namelist template."""
from pathlib import Path
from datetime import datetime
import subprocess,re,shutil
b=Path.home()/'WRF_BUILD'
c=b/'cases'/('xinjiang_10d_20240701_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
w=c/'wps';w.mkdir(parents=True,exist_ok=False)
s=(Path(__file__).parent/'namelist.wps').read_text(encoding='utf-8-sig')
geog=b/'DATA/wps_practice/WPS_GEOG_LOW_RES'
assert geog.is_dir(),geog
s,n=re.subn(r"geog_data_path\s*=\s*'[^']*'",lambda m:"geog_data_path='"+str(geog)+"'",s)
assert n==1
(w/'namelist.wps').write_text(s)
for name in ['geogrid','metgrid']:(w/name).symlink_to(b/'WPS'/name,target_is_directory=True)
(w/'Vtable').symlink_to(b/'WPS/ungrib/Variable_Tables/Vtable.GFS')
with (w/'geogrid.console.log').open('w') as f:
 subprocess.run([str(b/'WPS/geogrid.exe')],cwd=w,stdout=f,stderr=subprocess.STDOUT,check=True)
assert 'Successful completion of geogrid' in (w/'geogrid.console.log').read_text()
(b/'latest_xinjiang_10d_path.txt').write_text(str(c))
print('GEOGRID_SUCCESS',c)
