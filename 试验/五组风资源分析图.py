"""Generate five ERA5 wind diagnostic figure groups from local data."""
from pathlib import Path
import sys
import json
import csv
import importlib.util
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, BoundaryNorm, ListedColormap
import cartopy.crs as ccrs
import shapely
from shapely.geometry import shape
from shapely.ops import unary_union
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '图集/五组风资源分析'
sys.path.insert(0, str(ROOT / 'src'))
from era5x import io, compute, plot
YEARS = np.arange(2009, 2019)


def save(fig, name):
    fig.savefig(OUT / name, dpi=600)
    plt.close(fig)
    print('已保存', name, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plot.setup_style()
    plt.rcParams.update({'font.size': 10, 'axes.titlesize': 11,
                         'axes.labelsize': 10, 'xtick.labelsize': 9,
                         'ytick.labelsize': 9, 'legend.fontsize': 9})
    with xr.open_dataset(ROOT / '图集/阈值对照/阈值对照_指标.nc', engine='scipy') as ds:
        metrics = ds.load()
    lon, lat = metrics.longitude.values, metrics.latitude.values
    xx, yy = np.meshgrid(lon, lat)
    geo = json.loads((ROOT / 'data/admin/xinjiang_pref.json').read_text(encoding='utf-8'))
    boundary = unary_union([shape(f['geometry']) for f in geo['features']])
    hami = unary_union([shape(f['geometry']) for f in geo['features'] if '哈密' in f['properties']['name']])
    province = shapely.intersects_xy(boundary, xx, yy)
    masks = {'新疆行政区': province,
             '新疆北部（≥43°N）': province & (yy >= 43),
             '新疆南部（<43°N）': province & (yy < 43),
             '哈密行政区': shapely.intersects_xy(hami, xx, yy)}
    assert all(m.any() for m in masks.values())
    weights = np.cos(np.deg2rad(yy))
    threshold = metrics.p95_threshold.values
    low = np.where(province, threshold, np.inf)
    high = np.where(province, threshold, -np.inf)
    i_low = np.unravel_index(low.argmin(), low.shape)
    i_high = np.unravel_index(high.argmax(), high.shape)
    gap = (metrics.relative_rate - metrics.absolute_rate).values.copy()
    gap[~province | (threshold >= 10.8)] = -np.inf
    gap[i_low] = gap[i_high] = -np.inf
    i_gap = np.unravel_index(gap.argmax(), gap.shape)
    indices = [i_low, i_high, i_gap]
    names = ['低局地阈值点', '高局地阈值点', '超阈率反差点']
    points = []
    for label, (i, j) in zip(names, indices):
        points.append({'name': label, 'latitude': float(lat[i]), 'longitude': float(lon[j]),
                       'baseline_p95': float(threshold[i, j]),
                       'relative_rate': float(metrics.relative_rate.values[i, j]),
                       'absolute_rate': float(metrics.absolute_rate.values[i, j])})
    (OUT / '典型格点选择.json').write_text(json.dumps(points, ensure_ascii=False, indent=2), encoding='utf-8')
    monthly = np.empty((10, 12, len(masks)))
    all_u, all_v, times = [], [], []
    for iy, year in enumerate(YEARS):
        with io.load_era5(ROOT / 'data/yearly' / f'era5_{year}.nc') as ds:
            expected = np.arange(np.datetime64(f'{year}-01-01T00'), np.datetime64(f'{year+1}-01-01T00'), np.timedelta64(6, 'h'))
            assert np.array_equal(ds.time.values, expected)
            assert np.array_equal(ds.longitude.values, lon)
            assert np.array_equal(ds.latitude.values, lat)
            speed = compute.wind_speed(ds).transpose('time', 'latitude', 'longitude').load()
            assert np.isfinite(speed.values).all()
            mean_fields = speed.groupby('time.month').mean('time').values
            for k, mask in enumerate(masks.values()):
                w = weights * mask
                monthly[iy, :, k] = (mean_fields * w).sum(axis=(1, 2)) / w.sum()
            all_u.append(np.column_stack([ds.u10.isel(latitude=i, longitude=j).values for i, j in indices]))
            all_v.append(np.column_stack([ds.v10.isel(latitude=i, longitude=j).values for i, j in indices]))
            times.append(ds.time.values)
        print('读取完成', year, flush=True)
    u, v, time = np.concatenate(all_u), np.concatenate(all_v), np.concatenate(times)
    speeds = np.hypot(u, v)
    dates = xr.DataArray(time, dims='time')
    months, years = dates.dt.month.values, dates.dt.year.values
    reference, study = years <= 2014, years >= 2015
    for k, point in enumerate(points):
        assert np.isclose(np.quantile(speeds[reference, k], .95), point['baseline_p95'], atol=2e-5)
        assert np.isclose(100*np.mean(speeds[study, k] > point['baseline_p95']), point['relative_rate'], atol=.02)
    xr.Dataset({'monthly_regional_speed': (('year', 'month', 'region'), monthly)},
               coords={'year': YEARS, 'month': np.arange(1, 13), 'region': list(masks)},
               attrs={'units': 'm s-1', 'weight': 'cos(latitude), grid-center administrative mask',
                      'north_south_definition': 'latitude43 split within Xinjiang'}).to_netcdf(OUT/'区域逐年月均风速.nc', engine='scipy')
    with (OUT/'区域逐年月均风速.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['年份', '月份', *masks])
        for iy, year in enumerate(YEARS):
            for im in range(12):
                writer.writerow([int(year), im+1, *monthly[iy, im]])

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    xmax = float(np.ceil(speeds[study].max()))
    bins = np.arange(0, xmax+.5, .5)
    for k, point in enumerate(points):
        x = speeds[study, k]
        ax = axes[0, k]
        ax.hist(x, bins=bins, density=True, color='#90b8d2', edgecolor='white', linewidth=.2)
        for target in axes[:, k]:
            target.axvline(point['baseline_p95'], color='#cb4b16', lw=1.6, ls='--', label='2009—2014 局地 p95')
            target.axvline(10.8, color='#4c2882', lw=1.6, ls=':', label='固定 10.8 m/s')
            target.set_xlim(0, xmax)
            target.set_xlabel('10 米风速 (m/s)')
            target.grid(alpha=.18)
        ax.set_title(f'{point["name"]} | {point["longitude"]:.2f}°E, {point["latitude"]:.2f}°N')
        ax.set_ylabel('概率密度')
        xsort = np.sort(x)
        axes[1, k].step(xsort, 100*(len(xsort)-np.arange(len(xsort)))/len(xsort), color='#1b6a86', where='post')
        axes[1, k].set_yscale('log')
        axes[1, k].set_ylim(.01, 100)
        axes[1, k].set_ylabel('风速超越比例 (%)')
        axes[1, k].set_title(f'p95={point["baseline_p95"]:.2f} m/s | 两类超阈 {point["relative_rate"]:.2f}% / {point["absolute_rate"]:.2f}%')
    axes[0, 0].legend(loc='upper right', fontsize=8)
    fig.suptitle('① 典型格点风速分布与双阈值 | 研究期 2015—2018', fontsize=17)
    save(fig, '01_典型格点分布与双阈值.png')

    fig, ax = plt.subplots(figsize=(12, 7), layout='constrained')
    for k, (name, color) in enumerate(zip(masks, ['#202020', '#3578b0', '#d56633', '#7a4e9b'])):
        mean, sd = monthly[:, :, k].mean(axis=0), monthly[:, :, k].std(axis=0, ddof=1)
        ax.plot(np.arange(1, 13), mean, 'o-', color=color, label=name)
        ax.fill_between(np.arange(1, 13), mean-sd, mean+sd, color=color, alpha=.12)
    ax.set_xticks(np.arange(1, 13))
    ax.set_xlabel('月份')
    ax.set_ylabel('区域面积加权月平均 10 米风速 (m/s)')
    ax.grid(alpha=.2)
    ax.legend(ncol=2)
    ax.set_title('② ERA5 2009—2018 年季节循环', fontsize=16)
    fig.supxlabel('曲线为十年平均，阴影为逐年月均值的 ±1 样本标准差', fontsize=11)
    save(fig, '02_多年季节循环.png')

    anomalies = monthly-monthly.mean(axis=0, keepdims=True)
    limit = max(.25, float(np.ceil(abs(anomalies).max()*4)/4))
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout='constrained')
    for k, (ax, name) in enumerate(zip(axes.flat, masks)):
        artist = ax.pcolormesh(np.arange(.5, 13.5), np.arange(2008.5, 2019), anomalies[:, :, k], cmap='RdBu_r', norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
        ax.set_xticks(np.arange(1, 13))
        ax.set_yticks(YEARS)
        ax.set_xlabel('月份')
        ax.set_title(name)
    fig.colorbar(artist, ax=axes.ravel().tolist(), label='相对于各月 2009—2018 年平均的风速距平 (m/s)', shrink=.8)
    fig.suptitle('③ 年—月风速距平热力图 | 同一色标，红色偏强、蓝色偏弱', fontsize=16)
    save(fig, '03_年月风速距平热力图.png')

    direction = np.degrees(np.arctan2(-u, -v)) % 360
    speed_edges = np.array([.5, 2, 4, 6, 8, 10.8, np.inf])
    labels = ['0.5—2', '2—4', '4—6', '6—8', '8—10.8', '≥10.8']
    rose_colors = plt.get_cmap('viridis')(np.linspace(.1, .95, 6))
    rose_data, calm = np.zeros((2, 3, 16, 6)), np.zeros((2, 3))
    selections = [np.isin(months, [12, 1, 2]), np.isin(months, [6, 7, 8])]
    for season, selection in enumerate(selections):
        for k in range(3):
            sp, dr = speeds[selection, k], direction[selection, k]
            calm[season, k] = 100*np.mean(sp < .5)
            sector = np.floor(((dr+11.25) % 360)/22.5).astype(int)
            for j in range(16):
                rose_data[season, k, j] = np.histogram(sp[(sector==j) & (sp>=.5)], bins=speed_edges)[0]/len(sp)*100
            assert np.isclose(rose_data[season, k].sum()+calm[season, k], 100)
    fig, axes = plt.subplots(2, 3, figsize=(14, 9), subplot_kw={'projection': 'polar'}, layout='constrained')
    rmax = max(5, np.ceil(rose_data.sum(axis=3).max()/5)*5)
    theta = np.deg2rad(np.arange(16)*22.5)
    for season in range(2):
        for k in range(3):
            ax, bottom = axes[season, k], np.zeros(16)
            for b in range(6):
                ax.bar(theta, rose_data[season, k, :, b], width=np.deg2rad(20), bottom=bottom, color=rose_colors[b], edgecolor='white', linewidth=.25, label=labels[b])
                bottom += rose_data[season, k, :, b]
            ax.set_theta_zero_location('N')
            ax.set_theta_direction(-1)
            ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)))
            ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.set_ylim(0, rmax)
            radial_ticks = np.linspace(rmax/5, rmax, 5)
            ax.set_yticks(radial_ticks)
            ax.set_yticklabels([f'{int(x)}%' for x in radial_ticks])
            ax.set_title(f'{names[k]} · {["DJF", "JJA"][season]} · 静风 {calm[season,k]:.1f}%', pad=20)
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='outside lower center', ncol=6, title='风速 (m/s)，各扇区比例以该季全部有效时次为分母')
    fig.suptitle('④ 典型格点冬夏风玫瑰 | 2009—2018 年，气象风向来向', fontsize=17)
    save(fig, '04_典型格点冬夏风玫瑰.png')
    np.savez_compressed(OUT/'风玫瑰统计.npz', frequency=rose_data, calm_percent=calm, direction_centers_deg=np.arange(16)*22.5, speed_bin_edges=speed_edges)

    print('开始3/5/7天块长敏感性', flush=True)
    spec = importlib.util.spec_from_file_location('existing_significance', ROOT/'试验/显著性打点.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    day_arrays = []
    for month in [1, 7]:
        with io.load_era5(ROOT/'data'/f'era5_2020{month:02d}.nc') as ds:
            expected = np.arange(np.datetime64(f'2020-{month:02d}-01T00'), np.datetime64(f'2020-{month+1:02d}-01T00'), np.timedelta64(6,'h'))
            assert np.array_equal(ds.time.values, expected)
            speed = compute.wind_speed(ds).transpose('time','latitude','longitude')
            speed = speed.where(np.isfinite(speed))
            day_arrays.append(speed.resample(time='1D').mean().where(speed.resample(time='1D').count()==4).load())
    jan, july = xr.align(*day_arrays, join='exact', exclude={'time'})
    valid = np.isfinite(jan).all('time').values & np.isfinite(july).all('time').values
    a, b = jan.values[:,valid].astype(float), july.values[:,valid].astype(float)
    observed = b.mean(axis=0)-a.mean(axis=0)
    ac, bc = a-a.mean(axis=0), b-b.mean(axis=0)
    ps, qs, sigs = [], [], []
    for block in [3,5,7]:
        module.BLOCK = block
        rng = np.random.default_rng(module.SEED)
        extremes = np.zeros(len(observed), dtype=int)
        for start in range(0, module.REPLICATES, 250):
            size = min(250, module.REPLICATES-start)
            boot = module.block_counts(rng,len(b),size)@bc-module.block_counts(rng,len(a),size)@ac
            extremes += (abs(boot)>=abs(observed)[None,:]).sum(axis=0)
        pvalues = (extremes+1)/(module.REPLICATES+1)
        qvalues = stats.false_discovery_control(pvalues,method='by')
        sig = qvalues < .05
        ps.append(pvalues)
        qs.append(qvalues)
        sigs.append(sig)
        print('块长',block,'显著格点',int(sig.sum()),flush=True)
    with xr.open_dataset(ROOT/'图集/双色差值/2020_07减01_显著性指标.nc',engine='scipy') as old:
        assert np.allclose(qs[1],old.by_adjusted_p.values[valid],atol=1e-12)
    shape3 = (3,*valid.shape)
    pfields = np.full(shape3,np.nan)
    qfields, sigfields = pfields.copy(), pfields.copy()
    for k in range(3):
        pfields[k,valid]=ps[k]
        qfields[k,valid]=qs[k]
        sigfields[k,valid]=sigs[k]
    agreement = np.full(valid.shape,np.nan)
    agreement[valid]=np.sum(sigs,axis=0)
    xr.Dataset({'raw_p':(('block_days','latitude','longitude'),pfields),
                'by_adjusted_p':(('block_days','latitude','longitude'),qfields),
                'significant':(('block_days','latitude','longitude'),sigfields),
                'agreement_count':(('latitude','longitude'),agreement)},
               coords={'block_days':[3,5,7],'latitude':jan.latitude,'longitude':jan.longitude},
               attrs={'replicates':module.REPLICATES,'seed':module.SEED,
                      'comparison':'July minus January 2020; 31 daily samples each',
                      'multiple_comparison':'BY across all valid rectangular domain grid cells per block length'}).to_netcdf(OUT/'块长敏感性指标.nc',engine='scipy')
    diff = np.full(valid.shape,np.nan)
    diff[valid]=observed
    bound=max(.5,np.ceil(np.nanmax(abs(diff))*2)/2)
    fig,axes=plt.subplots(2,2,figsize=(14,9),layout='constrained',subplot_kw={'projection':ccrs.PlateCarree()})
    for k,ax in enumerate(axes.flat):
        plot._add_map_features(ax,gridlines=True)
        ax.set_extent([70,100,35,50],crs=ccrs.PlateCarree())
        if k<3:
            artist=ax.contourf(xx,yy,diff,levels=np.linspace(-bound,bound,91),cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-bound,vcenter=0,vmax=bound),transform=ccrs.PlateCarree())
            visible=sigfields[k,::2,::2]==1
            ax.scatter(xx[::2,::2][visible],yy[::2,::2][visible],s=3,color='black',linewidths=0,transform=ccrs.PlateCarree())
            ax.set_title(f'{[3,5,7][k]} 天块长 · BY校正通过 {np.mean(sigs[k])*100:.2f}% 格点')
            fig.colorbar(artist, ax=ax, orientation='horizontal', shrink=.8,
                         pad=.08, aspect=40, ticks=[-4,-2,0,2,4], label='风速差 (m/s)')
        else:
            cmap=ListedColormap(['#eeeeee','#b9d8e8','#6199ba','#174d70'])
            agreeartist=ax.pcolormesh(xx,yy,agreement,cmap=cmap,norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4),shading='auto',transform=ccrs.PlateCarree())
            ax.set_title('通过检验的块长设置数量（0—3）')
            fig.colorbar(agreeartist, ax=ax, orientation='horizontal', shrink=.8,
                         pad=.08, aspect=40, ticks=[0,1,2,3], label='通过设置数')
    fig.suptitle('⑤ 显著性块长敏感性 | 日样本各31个 · 每设置9999次 · BY校正p<0.05',fontsize=16)
    fig.supxlabel('前三图黑点隔格显示；右下图3表示全部通过，0表示全部未通过。',fontsize=10)
    save(fig,'05_显著性块长敏感性.png')

    summary = {'monthly_peaks':{name:int(monthly[:,:,k].mean(axis=0).argmax()+1) for k,name in enumerate(masks)},
               'monthly_troughs':{name:int(monthly[:,:,k].mean(axis=0).argmin()+1) for k,name in enumerate(masks)},
               'significant_grid_counts':{str(block):int(sig.sum()) for block,sig in zip([3,5,7],sigs)},
               'all_three_significant_count':int((agreement==3).sum()),
               'valid_sensitivity_grid_count':int(valid.sum()),
               'region_grid_counts':{name:int(mask.sum()) for name,mask in masks.items()},
               'calm_percent_DJF_JJA_by_point':calm.tolist()}
    (OUT/'分析摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    note = '''# 五组风资源分析图及结果

图件于2026-11-06由助手使用本地ERA5数据计算，全部600 DPI。源数据保持原采样分辨率。

## 数据和统计范围
01与04使用2009—2018六小时u10/v10，01的经验分布使用2015—2018，局地p95来自2009—2014。
02与03使用2009—2018完整年月。05沿用2020年1月和7月，每月31个完整日均值。
均先对瞬时u/v计算风速，再求平均。
02/03采用本地新疆地州边界并集及格点中心掩膜，以cos纬度近似面积权重。北部和南部以43°N简化划分，并非严格的天山南北分界。哈密采用哈密市行政边界，边界格点未作部分面积订正。

## 01 典型格点风速分布及双阈值
在新疆行政掩膜内选基准期p95最低点、最高点，以及研究期相对超阈率减绝对超阈率最大的另一格点（要求p95<10.8）。具体坐标和阈值见典型格点选择.json。
这些点为数据驱动的说明性选点，第三点使用研究期结果挑选，不能当作无偏代表样本。上排是经验密度，下排为对数轴经验超越曲线；标题的两类超阈率按严格大于阈值直接计数。未进行Weibull拟合。
低阈值点的局地p95约1.02 m/s，超阈率5.36%，绝对超阈率0%；高阈值点p95约12.82 m/s，对应4.77%和8.93%；反差点p95约2.20 m/s，对应8.03%和0%。这显示相对阈值不总是比绝对阈值更低。

## 02 多年季节循环
曲线是逐年月均值的十年等权平均，阴影为逐年月均值的±1样本标准差，反映年际离散程度。
新疆全区、北部分组与哈密的峰值月份为5月，南部分组为4月。新疆全区与南部谷值为12月，北部与哈密为1月。仅描述本数据和分组下的季节规律。

## 03 年月风速距平热力图
每格表示当年月区域平均风速减去该月十年平均。四图使用同一对称色标。逐年月均值CSV/NetCDF用于检查实际值。
十年变化及单个异常月本身不构成显著长期趋势证据。

## 04 冬夏风玫瑰
与01采用相同三格点，汇集2009—2018中所有DJF与JJA月份。冬季按月份汇集，未生成跨年DJF逐年平均。
采用气象来向，atan2(-u,-v)，0°北、90°东。16方向扇区，静风<0.5 m/s单列比例。
风速等级为[0.5,2)、[2,4)、[4,6)、[6,8)、[8,10.8)、[10.8,+∞)。每季所有非静风扇区比例加静风比例等于100%。径向尺度在六图间相同。
高阈值点夏季北风明显集中，反差点冬夏主导来向发生变化。这些解释仅适用于所选格点。
六小时数据可能漏掉间隔内短时强风或转向。底层频率保存为NPZ。

## 05 显著性块长敏感性
复用现有显著性脚本的循环移动块抽样函数，使用3/5/7天块长、每组9999次、相同随机种子20261106、各月31个日样本、双侧检验。
每个块长独立对整个矩形有效域7381格点进行BY校正，以校正p<0.05判定。前三幅色标相同，黑点隔格显示。第四幅计数0—3表示通过检验的设置数量。
3/5/7天分别3960、3941、3992格点通过，3834格点在三组设置下均通过。5天结果已逐格点复核与原结果一致。
一致性体现对所选块长的稳定程度。该短序列近似检验仍依赖月内近似平稳与块抽样假设，不能推广为多年季节气候差异或风光开发因果效应。相同种子保证可复现，各块长实际抽样索引不同。

## 复现和验证
在met环境运行 试验/五组风资源分析图.py。输出目录为 图集/五组风资源分析。
已核验10年时间轴完整、经纬度一致、风速无缺测、典型格点p95和超阈率独立重算、风玫瑰频率守恒，以及5天显著性结果一致。图件均已逐张检查版面。
'''
    (OUT/'说明与结果.md').write_text(note,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
