"""Windows conda met: plot compact diagnostics from completed Xinjiang case."""
from pathlib import Path
import json,zipfile,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
root=Path(__file__).parent
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'pdf.fonttype':42})
with zipfile.ZipFile(root/'surface_diagnostics.zip') as z:
 meta=json.loads(z.read('diagnostics.json'));shape=meta['chunks'][0]['grid_shape']
 def grid(k):return np.frombuffer(z.read(k+'.f32'),dtype='<f4').reshape(shape).copy()
 lat,lon,hgt,mf,ca,sa=[grid(k) for k in ['XLAT','XLONG','HGT','MAPFAC_M','COSALPHA','SINALPHA']]
 data={}
 for key in ['T2','U10','V10','PSFC','PBLH','HFX','LH','SWDOWN','RAINC','RAINNC']:
  data[key]=np.concatenate([np.frombuffer(z.read(c['fields'][key]['member']),dtype='<f4').reshape(c['fields'][key]['shape']) for c in meta['chunks']])
u=data['U10']*ca-data['V10']*sa;v=data['V10']*ca+data['U10']*sa
speed=np.hypot(u,v);weights=1/mf.astype(float)**2;weights/=weights.sum()
def mean(a):return np.sum(a*weights,axis=(-2,-1))
assert len(data['T2'])==241
with (root/'逐小时区域诊断.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.writer(f);writer.writerow(['UTC','T2_domain_mean_C','wind10_domain_mean_m_s','PBLH_domain_mean_m','SWDOWN_domain_mean_W_m2'])
 for i,t in enumerate([t for c in meta['chunks'] for t in c['times']]):writer.writerow([t,mean(data['T2'])[i]-273.15,mean(speed)[i],mean(data['PBLH'])[i],mean(data['SWDOWN'])[i]])
proj=ccrs.LambertConformal(central_longitude=85,central_latitude=42.5,standard_parallels=(30,60));pc=ccrs.PlateCarree()
fig,axs=plt.subplots(1,2,figsize=(14,6),subplot_kw={'projection':proj})
for ax in axs:
 gl=ax.gridlines(draw_labels=True,x_inline=False,y_inline=False,rotate_labels=False,linestyle=':',alpha=.4);gl.top_labels=False;gl.right_labels=False
 gl.xlabel_style={'size':8};gl.ylabel_style={'size':8}
 ax.set_extent([70,101,32,51],crs=pc)
 ax.contour(lon,lat,hgt,[1500,3000,4500],colors='#64748b',linewidths=.4,transform=pc)
im=axs[0].pcolormesh(lon,lat,data['T2'][24:240].mean(0)-273.15,cmap='RdYlBu_r',shading='auto',transform=pc)
fig.colorbar(im,ax=axs[0],shrink=.8,pad=.04,label='2 m 气温 / °C');axs[0].set_title('(a) 剔除前24h后的平均2m气温')
im=axs[1].pcolormesh(lon,lat,speed[24:240].mean(0),cmap='YlGnBu',shading='auto',transform=pc)
fig.colorbar(im,ax=axs[1],shrink=.8,pad=.04,label=r'10 m 风速 / m s$^{-1}$')
sl=(slice(None,None,5),slice(None,None,5))
q=axs[1].quiver(lon[sl],lat[sl],u[24:240].mean(0)[sl],v[24:240].mean(0)[sl],transform=pc,scale=80,width=.003)
axs[1].quiverkey(q,.84,1.025,5,'5 m/s',coordinates='axes');axs[1].set_title('(b) 平均风速与地理风向')
fig.text(.5,.02,'2024-07-02 00—07-10 23 UTC；新疆及周边模式区域；27 km入门模拟，未经观测精度验证。\n灰线为1500/3000/4500 m等高线；箭头为时间平均地理风矢量。',ha='center',fontsize=9)
fig.subplots_adjust(bottom=.12,wspace=.26)
fig.savefig(root/'十天模拟_气温与风场.png',dpi=350,bbox_inches='tight');fig.savefig(root/'十天模拟_气温与风场.pdf',bbox_inches='tight');plt.close(fig)
fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True)
hours=np.arange(241)
for ax,a,label in zip(axs,[mean(data['T2'])-273.15,mean(speed),mean(data['PBLH'])],['2m气温 / °C','10m风速 / m/s','边界层高度 / m']):
 ax.plot(hours,a,lw=1.3);ax.axvspan(0,24,color='#94a3b8',alpha=.25);ax.set_ylabel(label);ax.grid(alpha=.2)
axs[0].set_title('十天连续积分诊断：全模式区域面积加权平均（不等于新疆行政区统计）')
axs[-1].set(xlabel='距2024-07-01 00 UTC的模拟小时',xlim=(0,240));axs[-1].set_xticks(np.arange(0,241,24))
fig.text(.5,.015,'灰色为前24h调整候选时段；曲线起伏也包含真实天气变化，不能据此单独判断spin-up收敛。',ha='center')
fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(root/'十天模拟_连续时间诊断.png',dpi=300);plt.close(fig)
(root/'output_validation.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print('PLOTS_COMPLETE',meta['n_times'],flush=True)
