"""Ubuntu: finish isolated 27km Xinjiang run from 41 local GFS analysis files."""
from pathlib import Path
from datetime import datetime,timedelta
import subprocess,re,shutil,json,time,hashlib
b=Path.home()/'WRF_BUILD';case=Path((b/'latest_xinjiang_10d_path.txt').read_text().strip())
w=case/'wps';data=b/'DATA/xinjiang_gfs_20240701';model=b/'WRF'
def run(cmd,cwd,log,marker=None):
 print('RUN',' '.join(map(str,cmd)),flush=True)
 with (cwd/log).open('w') as f:r=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(f'Failed {cmd[0]}, see {cwd/log}')
 if marker:
  files=list(cwd.glob('rsl.error.*')) if 'SUCCESS COMPLETE' in marker else [cwd/log]
  if not any(marker in p.read_text(errors='replace') for p in files):raise RuntimeError('Missing '+marker)
files=sorted(data.glob('gfs_*_1p00_f000.grib2'));assert len(files)==41,len(files)
for i,p in enumerate(files):
 expected=(datetime(2024,7,1)+timedelta(hours=6*i)).strftime('gfs_%Y%m%d_%H_1p00_f000.grib2')
 assert p.name==expected
 name='GRIBFILE.'+chr(65+i//676)+chr(65+(i//26)%26)+chr(65+i%26)
 link=w/name
 if not link.exists():link.symlink_to(p)
run([b/'WPS/ungrib.exe'],w,'ungrib.console.log','Successful completion of ungrib')
run([b/'WPS/metgrid.exe'],w,'metgrid.console.log','Successful completion of metgrid')
mets=sorted(w.glob('met_em.d01.*.nc'));assert len(mets)==41
h=subprocess.check_output(['ncdump','-h',str(mets[0])],text=True)
levels=int(re.search(r'num_metgrid_levels\s*=\s*(\d+)',h)[1])
soil=int(re.search(r'num_st_layers\s*=\s*(\d+)',h)[1])
land=int(re.search(r':NUM_LAND_CAT\s*=\s*(\d+)',h)[1])
runfolder=case/'run';runfolder.mkdir(exist_ok=False)
for p in (model/'run').iterdir():
 if p.name.startswith(('namelist','wrfinput','wrfbdy','wrfout','rsl.')):continue
 if p.exists():(runfolder/p.name).symlink_to(p.resolve(),target_is_directory=p.is_dir())
for exe in ['real.exe','wrf.exe']:
 p=runfolder/exe
 if p.is_symlink():p.unlink()
 p.symlink_to(model/'main'/exe)
for p in mets:(runfolder/p.name).symlink_to(p)
template=(b/'cases/matthew_wps/wrf_run/namelist.input').read_text()
updates={'run_days':10,'run_hours':0,'start_year':2024,'start_month':7,'start_day':1,'start_hour':0,
 'end_year':2024,'end_month':7,'end_day':11,'end_hour':0,'e_we':111,'e_sn':101,'time_step':90,
 'num_metgrid_levels':levels,'num_metgrid_soil_levels':soil,'num_land_cat':land,
 'radt':15,'history_interval':60,'frames_per_outfile':24,'restart_interval':1440}
for key,val in updates.items():
 template,n=re.subn(r'(?m)^(\s*'+key+r'\s*=)[^\n]*',lambda m:m[1]+' '+str(val)+',',template)
 assert n==1,(key,n)
(runfolder/'namelist.input').write_text(template)
metadata={'case_root':str(case),'start_utc':'2024-07-01_00:00:00','end_utc':'2024-07-11_00:00:00',
 'duration_hours':240,'grid_m':27000,'dimensions':[111,101,45],'dt_seconds':90,
 'forcing':'GFS 1-degree f000 analyses, 41 cycles, 6-hourly; NOT a single 240h GFS forecast',
 'model':'original WRF 4.8.0, no wind/PV extension','MPI_ranks':4,
 'spinup_note':'first 24 hours retained and flagged for later assessment, not assumed equilibrated',
 'metgrid_levels':levels,'soil_levels':soil,'num_land_cat':land,
 'wrf_binary_sha256':hashlib.sha256((model/'main/wrf.exe').read_bytes()).hexdigest()}
(case/'experiment.json').write_text(json.dumps(metadata,indent=2))
shutil.copy2(__file__,case/Path(__file__).name)
run(['mpirun','-np','4','./real.exe'],runfolder,'real.console.log','SUCCESS COMPLETE REAL_EM INIT')
print('INITIALIZATION_SUCCESS',case,flush=True)
start=time.time()
run(['mpirun','-np','4','./wrf.exe'],runfolder,'wrf.console.log','SUCCESS COMPLETE WRF')
(case/'SIMULATION_SUCCESS.txt').write_text('SUCCESS COMPLETE WRF\nwall_seconds='+str(time.time()-start))
print('SIMULATION_SUCCESS',case,flush=True)
