"""Local terrain and near-surface W cross section; no change to model data."""
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':11})
with Dataset('wrf',memory=(root/'wrfout_hill2d.nc').read_bytes()) as d:
    j=d['W'].shape[2]//2
    w=np.asarray(d['W'][-1,:,j,:],float)
    z=(np.asarray(d['PH'][-1,:,j,:])+np.asarray(d['PHB'][-1,:,j,:]))/9.81
    h=np.asarray(d['HGT'][-1,j,:],float)
    us=np.asarray(d['U'][-1,:,j,:],float)
    u=(us[:,:-1]+us[:,1:])/2
    zm=(z[:-1]+z[1:])/2
    wm=(w[:-1]+w[1:])/2
    x=(np.arange(h.size)-h.argmax())*float(d.DX)/1000
sel=np.abs(x)<=40
x,h,z,w=x[sel],h[sel],z[:,sel],w[:,sel]
u,zm,wm=u[:,sel],zm[:,sel],wm[:,sel]
near=z<=1000
vmax=float(np.max(np.abs(w[near])))
fig,(a,b)=plt.subplots(2,1,figsize=(11,8),gridspec_kw={'height_ratios':[1,2]},layout='constrained')
a.fill_between(x,0,h,color='#907650',alpha=.9)
a.plot(x,h,color='#46351f',lw=2)
a.annotate(f'山顶 {h.max():.0f} m',xy=(0,h.max()),xytext=(12,120),arrowprops={'arrowstyle':'->','color':'#46351f'},fontsize=13)
a.annotate('背景气流 →',xy=(-8,115),xytext=(-32,115),arrowprops={'arrowstyle':'->','lw':2},fontsize=12)
a.set(xlim=(-40,40),ylim=(0,160),ylabel='地形高度（m）',title='山丘本身：最高100米（横向只看山顶附近±40千米）')
a.grid(alpha=.2)
im=b.contourf(np.broadcast_to(x,z.shape),z,np.ma.masked_where(z>1800,w),levels=np.linspace(-vmax,vmax,25),cmap='RdBu_r',extend='both')
b.fill_between(x,0,h,color='#907650',zorder=5)
b.plot(x,h,color='#46351f',lw=1.6,zorder=6)
b.annotate('山丘',xy=(0,h.max()),xytext=(15,280),arrowprops={'arrowstyle':'->','color':'#46351f'},zorder=8)
b.set(xlim=(-40,40),ylim=(0,1000),xlabel='距山顶的水平距离（km）',ylabel='几何高度（m）',title='第10小时：近地层垂直速度（仅显示0—1000米）')
b.grid(alpha=.14)
# Interpolate collocated U/W onto geometric-height sampling points.
# x uses km, z uses m: convert U to km/s before angles='xy'.
qx=[];qz=[];qu=[];qw=[]
for col in range(1,len(x)-1,3):
    for height in [200,400,600,800]:
        if height <= h[col]+40 or height<zm[0,col] or height>zm[-1,col]:continue
        qx.append(x[col]);qz.append(height)
        qu.append(np.interp(height,zm[:,col],u[:,col])/1000)
        qw.append(np.interp(height,zm[:,col],wm[:,col]))
q=b.quiver(qx,qz,qu,qw,angles='xy',scale_units='xy',scale=1/250,
           color='#17232c',width=.003,pivot='mid',headwidth=4,headlength=5,zorder=7)
b.quiverkey(q,.83,.95,.01,'水平风 10 m/s',coordinates='axes',labelpos='N',fontproperties={'size':10})
fig.colorbar(im,ax=b,label='垂直速度 W（m/s）｜红色上升，蓝色下沉',pad=.02)
fig.suptitle('二维山丘试验 · 地形与近地气流放大图',fontsize=17)
fig.supxlabel('箭头：沿剖面气流（U、W）；水平向右为正。坐标非等比例，垂直风速未额外放大。',fontsize=10)
for ext in ['png','pdf']:fig.savefig(root/('04_山丘与近地气流_风向箭头.'+ext),dpi=300,bbox_inches='tight')
plt.close(fig)
print('Local W scale:',vmax,'m/s; terrain:',h.max(),'m')
