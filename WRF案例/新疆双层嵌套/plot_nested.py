from pathlib import Path
import json, zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from scipy.interpolate import griddata
root=Path(__file__).parent
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'pdf.fonttype':42})
data=[]
for dom in ['d01','d02']:
 with zipfile.ZipFile(root/f'surface_{dom}.zip') as z:
  m=json.loads(z.read('diagnostics.json')); shape=m['chunks'][0]['grid_shape']
  d={k:np.frombuffer(z.read(k+'.f32'),'<f4').reshape(shape).copy() for k in ['XLAT','XLONG','HGT','COSALPHA','SINALPHA']}
  for k in ['T2','U10','V10','RAINC','RAINNC']:
   d[k]=np.concatenate([np.frombuffer(z.read(c['fields'][k]['member']),'<f4').reshape(c['fields'][k]['shape']) for c in m['chunks']])
  d['u']=d['U10']*d['COSALPHA']-d['V10']*d['SINALPHA'];d['v']=d['V10']*d['COSALPHA']+d['U10']*d['SINALPHA']
  d['temp']=d['T2'][24:240].mean(0)-273.15;d['wind']=np.hypot(d['u'],d['v'])[24:240].mean(0)
  d['rain']=d['RAINC'][-1]+d['RAINNC'][-1]-d['RAINC'][24]-d['RAINNC'][24]
  data.append(d)
  (root/f'validation_{dom}.json').write_text(json.dumps(m,indent=2),encoding='utf8')
pc=ccrs.PlateCarree(); proj=ccrs.LambertConformal(central_longitude=85,central_latitude=42.5,standard_parallels=(30,60))
def setup(ax,extent):
 ax.set_extent(extent,pc)
 gl=ax.gridlines(draw_labels=True,x_inline=False,y_inline=False,linestyle=':',alpha=.35);gl.top_labels=False;gl.right_labels=False
 gl.xlabel_style={'size':8};gl.ylabel_style={'size':8}
def save(fig,name):
 fig.savefig(root/(name+'.png'),dpi=350,bbox_inches='tight');fig.savefig(root/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(14,6),subplot_kw={'projection':proj})
for ax,d,title in zip(axs,data,['D01：27 km 新疆及周边','D02：9 km 哈密附近']):
 extent=[float(d['XLONG'].min()),float(d['XLONG'].max()),float(d['XLAT'].min()),float(d['XLAT'].max())];setup(ax,extent)
 im=ax.pcolormesh(d['XLONG'],d['XLAT'],d['HGT'],cmap='terrain',vmin=0,vmax=6000,transform=pc,shading='auto');ax.set_title(title)
d=data[1]; x=d['XLONG'];y=d['XLAT']
axs[0].plot(np.r_[x[0,:],x[1:,-1],x[-1,-2::-1],x[-2::-1,0]],np.r_[y[0,:],y[1:,-1],y[-1,-2::-1],y[-2::-1,0]],color='red',lw=1.5,transform=pc)
fig.colorbar(im,ax=list(axs),label='地形高度 / m',shrink=.7);save(fig,'01_嵌套区域与地形')
extent=[89.5,97.5,40,45.5]
for key,title,unit,cmap,name in [('temp','平均2 m气温','°C','RdYlBu_r','02_气温分辨率对照'),('wind','平均10 m风速','m/s','YlGnBu','03_风速风向对照'),('rain','累计降水','mm','YlGnBu','04_累计降水对照')]:
 fig,axs=plt.subplots(1,3,figsize=(17,5.5),subplot_kw={'projection':proj})
 d1,d2=data; coords=(d1['XLONG'].ravel(),d1['XLAT'].ravel()); interp=griddata(coords,d1[key].ravel(),(d2['XLONG'],d2['XLAT']),method='linear');delta=d2[key]-interp
 lo=min(np.nanmin(d2[key]),np.nanmin(interp));hi=max(np.nanmax(d2[key]),np.nanmax(interp));lim=max(float(np.nanpercentile(abs(delta),99)),.01)
 for i,(ax,d,a) in enumerate(zip(axs,[d1,d2,d2],[d1[key],d2[key],delta])):
  setup(ax,extent);im=ax.pcolormesh(d['XLONG'],d['XLAT'],a,shading='auto',transform=pc,cmap=cmap if i<2 else 'RdBu_r',vmin=lo if i<2 else -lim,vmax=hi if i<2 else lim)
  fig.colorbar(im,ax=ax,shrink=.75,label=unit,extend='both' if i==2 else 'neither');ax.set_title(['D01：27 km','D02：9 km','D02 − 插值到9 km的D01'][i])
  if key=='wind' and i<2:
   sl=(slice(None,None,2 if i==0 else 6),slice(None,None,2 if i==0 else 6));q=ax.quiver(d['XLONG'][sl],d['XLAT'][sl],d['u'][24:240].mean(0)[sl],d['v'][24:240].mean(0)[sl],transform=pc,scale=80,width=.003);ax.quiverkey(q,.8,1.03,5,'5 m/s')
 fig.suptitle(title+'：相同地图范围对比',fontsize=15)
 fig.text(.5,.01,'气温/风：07-02 00至07-10 23 UTC整点平均；降水：07-02 00至07-11 00 UTC。\n差值含分辨率、地形与物理配置影响（D02关闭积云参数化）；不是误差或显著性检验。',ha='center',fontsize=9)
 fig.subplots_adjust(bottom=.14,wspace=.3);save(fig,name)
(root/'绘图说明.txt').write_text('两个区域均核对241个逐小时时次和所提取字段有限值。平均剔除前24小时只是分析选择，未证明spin-up收敛。风已旋转到地理方向。D01线性插值到D02经纬度点后计算差值，差值图色限取绝对差的99分位；超限以色条端点表示。降水为累计量端点相减。D02关闭积云参数化，因此差异不能全部归因于分辨率。未做观测精度或统计显著性验证。',encoding='utf8')
print('PLOTS_COMPLETE')
