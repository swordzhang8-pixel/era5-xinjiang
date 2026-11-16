"""Ubuntu: verify completed WRF output and export compact surface diagnostics.
Uses installed netCDF C library via ctypes; no Python package installation.
Original full NetCDF files remain in the simulation directory.
"""
from pathlib import Path
import ctypes as C,ctypes.util,math,json,zipfile,re
from datetime import datetime,timedelta
base=Path.home()/'WRF_BUILD';case=Path((base/'latest_xinjiang_10d_path.txt').read_text().strip())
assert (case/'SIMULATION_SUCCESS.txt').exists(),'Simulation has not finished'
lib=C.CDLL(ctypes.util.find_library('netcdf'))
def read(nc,name,text=False):
 var=C.c_int();assert lib.nc_inq_varid(nc,name.encode(),C.byref(var))==0,name
 nd=C.c_int();assert lib.nc_inq_varndims(nc,var,C.byref(nd))==0
 ids=(C.c_int*nd.value)();assert lib.nc_inq_vardimid(nc,var,ids)==0
 dims=[]
 for di in ids:
  n=C.c_size_t();assert lib.nc_inq_dimlen(nc,di,C.byref(n))==0;dims.append(n.value)
 typ=C.c_char if text else C.c_float
 arr=(typ*math.prod(dims))()
 fn=lib.nc_get_var_text if text else lib.nc_get_var_float
 assert fn(nc,var,arr)==0,name
 return arr,dims
fields=['T2','TSK','U10','V10','PSFC','PBLH','HFX','LH','SWDOWN','RAINC','RAINNC']
times=[];stats={k:dict(min=math.inf,max=-math.inf) for k in fields};chunks=[]
pack=case/'surface_diagnostics.zip'
with zipfile.ZipFile(pack,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for file_index,p in enumerate(sorted((case/'run').glob('wrfout_d01_*'))):
  nc=C.c_int();assert lib.nc_open(str(p).encode(),0,C.byref(nc))==0
  try:
   a,dims=read(nc,'Times',True)
   filetimes=[bytes(a[t*dims[1]:(t+1)*dims[1]]).decode('ascii').rstrip('\0') for t in range(dims[0])]
   times.extend(filetimes);entry={'source':p.name,'times':filetimes,'fields':{}}
   for k in fields:
    a,shape=read(nc,k)
    assert all(math.isfinite(v) for v in a),(p.name,k,'nonfinite')
    lo,hi=min(a),max(a);stats[k]['min']=min(stats[k]['min'],lo);stats[k]['max']=max(stats[k]['max'],hi)
    if k in ['T2','TSK']:assert lo>160 and hi<400,(p.name,k,lo,hi)
    if k=='PSFC':assert lo>10000 and hi<120000,(p.name,k,lo,hi)
    member=f'chunk{file_index:02d}_{k}.f32'
    z.writestr(member,bytes(a));entry['fields'][k]={'member':member,'shape':shape,'dtype':'<f4'}
   if file_index==0:
    for k in ['XLAT','XLONG','HGT','MAPFAC_M','COSALPHA','SINALPHA']:
     a,shape=read(nc,k);count=shape[-1]*shape[-2]
     z.writestr(k+'.f32',bytes(a)[:count*4]);entry['grid_shape']=shape[-2:]
   chunks.append(entry)
  finally:lib.nc_close(nc)
 expected=[(datetime(2024,7,1)+timedelta(hours=i)).strftime('%Y-%m-%d_%H:%M:%S') for i in range(241)]
 assert times==expected,('Time axis mismatch',len(times),times[:1],times[-1:])
 warnings=[]
 for logfile in (case/'run').glob('rsl.error.*'):
  warnings.extend(float(x) for x in re.findall(r'TBOUND exceeds table limit: reset\s+([\d.]+)',logfile.read_text(errors='replace')))
 summary={'case_root':str(case),'n_times':len(times),'first':times[0],'last':times[-1],
          'hourly_time_axis_complete':True,'finite_fields_and_ranges':stats,'chunks':chunks,
          'RRTM_TBOUND_warning_count_all_ranks':len(warnings),
          'RRTM_TBOUND_max_logged_K':max(warnings) if warnings else None,
          'RRTM_warning_explanation':'Built-in RRTM code clips radiation boundary temperature >340 K to 339.99 K; no scientific validation claimed.',
          'note':'Basic completion/format/range checks only; not observational accuracy or spin-up convergence.'}
 z.writestr('diagnostics.json',json.dumps(summary,indent=2))
 for p in [case/'experiment.json',case/'run/namelist.input',case/'wps/namelist.wps',case/'run/rsl.error.0000',case/'SIMULATION_SUCCESS.txt']:
  z.write(p,p.name)
(case/'output_validation.json').write_text(json.dumps(summary,indent=2))
print('OUTPUT_VERIFIED',len(times),times[-1],pack.stat().st_size,flush=True)
