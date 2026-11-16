from pathlib import Path
import numpy as np
from netCDF4 import Dataset
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
root=Path(__file__).parent
with Dataset('memory',memory=(root/'geo_em.d01.nc').read_bytes()) as d:
 lat=np.asarray(d['XLAT_M'][0]);lon=np.asarray(d['XLONG_M'][0]);hgt=np.asarray(d['HGT_M'][0])
 print('DOMAIN',float(lon.min()),float(lon.max()),float(lat.min()),float(lat.max()),flush=True)
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'pdf.fonttype':42})
proj=ccrs.LambertConformal(central_longitude=85,central_latitude=42.5,standard_parallels=(30,60));pc=ccrs.PlateCarree()
fig=plt.figure(figsize=(10,8));ax=fig.add_subplot(111,projection=proj)
im=ax.pcolormesh(lon,lat,hgt,cmap='terrain',vmin=0,vmax=6000,shading='auto',transform=pc)
for x,y in [(lon[0],lat[0]),(lon[-1],lat[-1]),(lon[:,0],lat[:,0]),(lon[:,-1],lat[:,-1])]:ax.plot(x,y,color='#334155',lw=.7,transform=pc)
ax.scatter([85],[42.5],marker='+',s=70,color='black',transform=pc)
gl=ax.gridlines(draw_labels=True,linestyle=':',alpha=.5);gl.top_labels=False;gl.right_labels=False
ax.set_title('新疆十天真实天气个例：地形与计算区域\n27 km · 111 × 101 网格 · 2024-07-01 至 07-11 UTC',pad=15)
fig.colorbar(im,ax=ax,shrink=.8,pad=.06,label='模式地形高度 / m')
fig.text(.5,.03,'区域图为WPS实际输出；尚不代表十天积分完成。低分辨率地形用于入门案例。',ha='center',fontsize=10,color='#475569')
fig.savefig(root/'新疆计算区域与地形.png',dpi=300,bbox_inches='tight');plt.close(fig)
