"""Run: python plot_hill.py [case_directory]. Requires numpy, matplotlib, netCDF4."""
from pathlib import Path
import sys,json
import numpy as np
from netCDF4 import Dataset,chartostring
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':11})
with Dataset('wrf',memory=(root/'wrfout_hill2d.nc').read_bytes()) as d:
    times=chartostring(d['Times'][:]).tolist()
    # W and geopotential are at vertical interfaces. Average to mass levels.
    wi=np.asarray(d['W'][:],float)
    w=(wi[:,:-1]+wi[:,1:])/2
    zi=(np.asarray(d['PH'][:])+np.asarray(d['PHB'][:]))/9.81
    z=(zi[:,:-1]+zi[:,1:])/2
    us=np.asarray(d['U'][:],float)
    u=(us[:,:,:,:-1]+us[:,:,:,1:])/2
    theta=np.asarray(d['T'][:],float)+300
    h=np.asarray(d['HGT'][:],float)
    dx=float(d.DX)
# 2-D solution: take one y row; retain geometric height above sea level.
j=w.shape[2]//2
w,z,u,theta,h=w[:,:,j,:],z[:,:,j,:]/1000,u[:,:,j,:],theta[:,:,j,:],h[:,j,:]/1000
x=(np.arange(w.shape[-1])-np.argmax(h[0]))*dx/1000
X=np.broadcast_to(x,z[0].shape)
assert all(np.isfinite(a).all() for a in [w,z,u,theta,h])
ids=sorted(set([0,len(times)//3,2*len(times)//3,len(times)-1]))
limit=float(np.max(np.abs(w[ids])))
limit=max(limit,1e-8)
lev=np.linspace(-limit,limit,25)
top=float(np.max(z))
def ground(ax,t):
    ax.fill_between(x,0,h[t],color='#554f45',zorder=5)
    ax.set(xlabel='距山顶的水平距离（km）',ylabel='几何高度（km）',ylim=(0,top),xlim=(x[0],x[-1]))
    ax.grid(alpha=.13)
def save(fig,name):
    fig.savefig(root/(name+'.png'),dpi=300,bbox_inches='tight')
    fig.savefig(root/(name+'.pdf'),bbox_inches='tight')
    plt.close(fig)
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
for ax,t in zip(axes.flat,ids):
    im=ax.contourf(X,z[t],w[t],levels=lev,cmap='RdBu_r',extend='both')
    ground(ax,t)
    ax.set_title('模拟第 '+times[t][11:13]+' 小时')
fig.suptitle('二维山丘试验：垂直速度随时间演变',fontsize=17)
fig.colorbar(im,ax=axes.ravel().tolist(),label='垂直速度 W（m/s）：红色上升，蓝色下沉',shrink=.88)
save(fig,'01_山地波演变')

t=len(times)-1
fig,axes=plt.subplots(1,2,figsize=(14,6),layout='constrained')
im=axes[0].contourf(X,z[t],w[t],levels=lev,cmap='RdBu_r',extend='both')
ct=axes[0].contour(X,z[t],theta[t],levels=12,colors='#333333',linewidths=.65)
axes[0].clabel(ct,fontsize=8,fmt='%.0f K')
axes[0].set_title('垂直速度填色与位温等值线')
fig.colorbar(im,ax=axes[0],orientation='horizontal',pad=.12,label='垂直速度 W（m/s）')
im2=axes[1].contourf(X,z[t],u[t],levels=22,cmap='viridis')
axes[1].set_title('沿剖面水平方向风速 U')
fig.colorbar(im2,ax=axes[1],orientation='horizontal',pad=.12,label='水平风速 U（m/s）')
for ax in axes:ground(ax,t)
fig.suptitle('二维山丘试验：第10小时气流结构',fontsize=17)
save(fig,'02_末时刻气流剖面')
summary={'time_records':times,'horizontal_spacing_m':dx,'mass_grid_shape':list(w.shape),'terrain_max_m':float(h.max()*1000),'last_W_range_m_s':[float(w[-1].min()),float(w[-1].max())],'last_U_range_m_s':[float(u[-1].min()),float(u[-1].max())],'W_all_range_m_s':[float(w.min()),float(w.max())]}
(root/'绘图数据核对.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'图片说明.md').write_text('''# 二维山丘试验绘图

数据：wrfout_hill2d.nc，0—10小时共11个时刻。模型时间从公元1年开始，是理想化试验的时间标签，不是真实天气日期。

01_山地波演变：统一色标比较初始及后续时刻，红色表示上升、蓝色表示下沉。横坐标以地形最高点为零点；灰褐色为真实模型地形，没有人为放大山高。

02_末时刻气流剖面：左图为第10小时垂直速度与位温等值线，右图为同一时刻水平风速。等位温面上下起伏可用于观察山地波结构。图中不使用夸大垂直风速的风矢量。

高度由(PH+PHB)/9.81计算；W、高度在垂直方向去交错，U在水平方向去交错；位温=T+300 K。使用中间y行绘制二维x-z剖面。未使用经纬度地图。

重新绘图：在本目录运行 python plot_hill.py。依赖numpy、matplotlib、netCDF4。图片同时保存300dpi PNG和矢量PDF。

本人终端已确认IDEAL INIT及WRF运行成功；绘图代码与图片由助手制作，未据此将本人“出图”学习任务自动打卡。
''',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
