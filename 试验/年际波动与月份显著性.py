"""Make interannual variability visible and compare paired calendar months."""
from pathlib import Path
import sys
import csv
import json
import itertools
import numpy as np
import xarray as xr
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '图集/五组风资源分析/区域逐年月均风速.nc'
OUT = ROOT / '图集/年际波动与月份显著性'
sys.path.insert(0, str(ROOT / 'src'))
from era5x import plot


def save(fig, filename):
    fig.savefig(OUT / filename, dpi=600)
    plt.close(fig)
    print('已保存', filename, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(SOURCE, engine='scipy') as ds:
        values = ds.monthly_regional_speed.transpose('year', 'month', 'region').values
        years = ds.year.values
        regions = ds.region.values.tolist()
    assert values.shape == (10, 12, 4)
    assert np.isfinite(values).all()
    mean = values.mean(axis=0)
    sd = values.std(axis=0, ddof=1)
    anomaly = values-mean[None, :, :]
    plot.setup_style()
    plt.rcParams.update({'font.size': 10, 'axes.titlesize': 12,
                         'axes.labelsize': 10, 'xtick.labelsize': 9,
                         'ytick.labelsize': 9, 'legend.fontsize': 9})
    # Subtract the seasonal cycle so interannual spread is on its own vertical scale.
    extent = max(.1, float(np.ceil(abs(anomaly).max()*10)/10))
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout='constrained')
    jitter = np.linspace(-.19, .19, len(years))
    year_colors = plt.get_cmap('viridis')(np.linspace(.05, .95, len(years)))
    for k, (ax, region) in enumerate(zip(axes.flat, regions)):
        ax.boxplot([anomaly[:, m, k] for m in range(12)], positions=np.arange(1, 13),
                   widths=.55, showfliers=False, patch_artist=True,
                   boxprops={'facecolor': '#d9e7ef', 'edgecolor': '#526c7b'},
                   medianprops={'color': '#1e4c6a', 'linewidth': 1.5},
                   whiskerprops={'color': '#526c7b'}, capprops={'color': '#526c7b'})
        for iy, year in enumerate(years):
            ax.scatter(np.arange(1, 13)+jitter[iy], anomaly[iy, :, k],
                       s=18, color=year_colors[iy], edgecolor='white', linewidth=.25,
                       label=str(year), zorder=4)
        ax.errorbar(np.arange(1, 13), np.zeros(12), yerr=sd[:, k], fmt='none',
                    ecolor='#bd542c', elinewidth=1.5, capsize=3, zorder=5)
        ax.axhline(0, color='0.35', linewidth=.8, linestyle='--')
        ax.set_ylim(-extent, extent)
        ax.set_xlim(.4, 12.6)
        ax.set_xticks(np.arange(1, 13))
        ax.set_title(region)
        ax.set_xlabel('月份')
        ax.set_ylabel('相对同月十年平均的风速距平 (m/s)')
        ax.grid(axis='y', alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=10, title='每个点对应一个年份；箱体为四分位范围，橙色误差棒为 ±1 标准差')
    fig.suptitle('① 单独看年际波动 | 去除平均季节循环后的逐年散点与箱线图', fontsize=16)
    save(fig, '01_年际波动散点箱线图.png')

    fig, ax = plt.subplots(figsize=(13, 4.5), layout='constrained')
    im = ax.imshow(sd.T, cmap='YlOrRd', vmin=0, vmax=float(sd.max()), aspect='auto')
    ax.set_xticks(np.arange(12), np.arange(1, 13))
    ax.set_yticks(np.arange(4), regions)
    ax.set_xlabel('月份')
    for k in range(4):
        for m in range(12):
            color = 'white' if sd[m, k] > sd.max()*.6 else '#242424'
            ax.text(m, k, f'{sd[m,k]:.2f}', ha='center', va='center', color=color, fontsize=12)
    fig.colorbar(im, ax=ax, label='逐年月平均风速的样本标准差 (m/s)', shrink=.85)
    ax.set_title('② 年际标准差热力图 | 2009—2018 年，每格 n=10', fontsize=16)
    save(fig, '02_年际标准差热力图.png')

    # Enumerate all 2**10 paired swaps, equivalent to sign reversals of annual differences.
    signs = np.array(list(itertools.product([-1., 1.], repeat=len(years))))
    pairs = list(itertools.combinations(range(12), 2))
    raw, effects, descriptors = [], [], []
    for k in range(4):
        for i, j in pairs:
            differences = values[:, i, k]-values[:, j, k]
            effect = float(differences.mean())
            null = signs@differences/len(years)
            tolerance = 100*np.finfo(float).eps*max(1., abs(effect))
            pvalue = float(np.mean(abs(null) >= abs(effect)-tolerance))
            raw.append(pvalue)
            effects.append(effect)
            descriptors.append((k, i, j))
    raw = np.array(raw)
    q = stats.false_discovery_control(raw, method='by')
    assert len(raw) == 264 and np.all(raw > 0) and np.all(q >= raw-1e-12)
    # Verify enumeration and two-sided convention against SciPy on a representative pair.
    check = values[:, 0, 0]-values[:, 1, 0]
    reference = stats.permutation_test((check,), lambda x: np.mean(x),
                                       permutation_type='samples', n_resamples=np.inf,
                                       alternative='two-sided').pvalue
    assert np.isclose(raw[0], reference)
    effect_matrix = np.zeros((4, 12, 12))
    p_matrix = np.ones_like(effect_matrix)
    q_matrix = np.ones_like(effect_matrix)
    for (k, i, j), effect, pv, qv in zip(descriptors, effects, raw, q):
        effect_matrix[k, i, j] = effect
        effect_matrix[k, j, i] = -effect
        p_matrix[k, i, j] = p_matrix[k, j, i] = pv
        q_matrix[k, i, j] = q_matrix[k, j, i] = qv
    with (OUT/'月份配对检验.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['区域', '行月份', '列月份', '行减列均值差_m_s', '配对年份数', '原始p', 'BY校正p', '校正p小于0.05'])
        for (k, i, j), effect, pv, qv in zip(descriptors, effects, raw, q):
            writer.writerow([regions[k], i+1, j+1, effect, 10, pv, qv, bool(qv<.05)])
    xr.Dataset({'interannual_sd': (('month', 'region'), sd),
                'monthly_mean': (('month', 'region'), mean),
                'pair_difference': (('region', 'row_month', 'column_month'), effect_matrix),
                'raw_p': (('region', 'row_month', 'column_month'), p_matrix),
                'by_adjusted_p': (('region', 'row_month', 'column_month'), q_matrix)},
               coords={'month': np.arange(1,13), 'region': regions,
                       'row_month': np.arange(1,13), 'column_month': np.arange(1,13)},
               attrs={'method': 'Exact two-sided paired sign-flip test, 1024 assignments',
                      'family': 'BY across 264 unique month pairs and regions',
                      'units_effect_and_sd': 'm s-1'}).to_netcdf(OUT/'年际波动与配对检验.nc', engine='scipy')

    bound = max(.5, float(np.ceil(np.max(np.abs(effects))*2)/2))
    fig, axes = plt.subplots(2, 2, figsize=(14, 12), layout='constrained')
    lower = np.tril(np.ones((12,12), dtype=bool))
    for k, (ax, region) in enumerate(zip(axes.flat, regions)):
        matrix = np.ma.masked_where(lower, effect_matrix[k])
        ax.set_facecolor('#eeeeee')
        im = ax.imshow(matrix, cmap='RdBu_r', norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound))
        for i, j in pairs:
            effect = effect_matrix[k,i,j]
            star = '*' if q_matrix[k,i,j] < .05 else ''
            color = 'white' if abs(effect)>bound*.6 else '#222222'
            ax.text(j,i,f'{effect:+.1f}{star}',ha='center',va='center',color=color,fontsize=8)
        count = sum(q_matrix[k,i,j]<.05 for i,j in pairs)
        ax.set_title(f'{region} | {count}/66 对月份通过校正检验')
        ax.set_xticks(np.arange(12), np.arange(1,13))
        ax.set_yticks(np.arange(12), np.arange(1,13))
        ax.set_xlabel('列月份')
        ax.set_ylabel('行月份')
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=.8, label='行月份减列月份的十年平均风速差 (m/s)')
    fig.suptitle('③ 哪些月份差异显著 | 同年配对 n=10，穷举 1024 次交换', fontsize=17)
    fig.supxlabel('* 表示 BY 校正 p<0.05，统一校正全部264次比较；下三角因对称省略。', fontsize=11)
    save(fig, '03_月份配对差异与显著性矩阵.png')

    differences = values[:,6,:]-values[:,0,:]
    lower = min(0., float(np.floor(differences.min()*4)/4))
    upper = max(.25, float(np.ceil(differences.max()*4)/4))
    fig, axes = plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for k,(ax,region) in enumerate(zip(axes.flat,regions)):
        data = differences[:,k]
        ax.bar(years,data,color=np.where(data>=0,'#c45b47','#427ba9'),width=.68)
        ax.axhline(0,color='black',linewidth=.8)
        ax.axhline(data.mean(),color='#414141',linestyle='--',label=f'十年平均 {data.mean():+.2f} m/s')
        ax.set_ylim(lower-.03*(upper-lower), upper+.05*(upper-lower))
        ax.set_xticks(years)
        ax.tick_params(axis='x',rotation=45)
        ax.set_ylabel('当年7月减1月月平均风速 (m/s)')
        ax.set_title(f'{region} | BY校正 p={q_matrix[k,6,0]:.3f}')
        ax.grid(axis='y',alpha=.2)
        ax.legend(loc='lower right')
    fig.suptitle('④ 7月比1月风大是否逐年一致 | 每根柱对应一个年份的差值',fontsize=16)
    fig.supxlabel('统计推断以年份间近似独立及配对交换条件为前提；校正范围与月份矩阵一致。',fontsize=10)
    save(fig,'04_逐年七月减一月差异.png')

    max_idx = np.unravel_index(sd.argmax(), sd.shape)
    result = {'sample_years':years.tolist(),'paired_comparisons':len(raw),
              'significant_pair_counts':{region:sum(bool(q_matrix[k,i,j]<.05) for i,j in pairs) for k,region in enumerate(regions)},
              'max_sd':{'region':regions[max_idx[1]],'month':int(max_idx[0]+1),'sd_m_s':float(sd[max_idx])},
              'july_minus_january_mean':{r:float(differences[:,k].mean()) for k,r in enumerate(regions)},
              'july_minus_january_by_p':{r:float(q_matrix[k,6,0]) for k,r in enumerate(regions)}}
    (OUT/'结果摘要.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    note = '''# 年际波动与月份显著性

数据沿用2009—2018年区域逐年月均风速，共10年、12个月、4个区域。区域、行政掩膜和cos纬度权重与前一组分析一致。北部南部按43°N简化分组。

## 为什么单独展示年际波动
原图阴影为年际标准差，叠加季节循环后不易观察。01先减去各月十年平均，把年际变化单独放在以零为中心的纵轴上。每个月10个点代表10年，左右偏移仅用于防止点重叠。箱体是25%—75%分位数，中线为中位数，须为1.5倍四分位范围内最远观测，全部点仍单独展示。橙色误差棒为±1样本标准差。
02直接画标准差并标数值。值越大，逐年同月区域平均风速的波动越大。标准差描述离散程度，不直接代表统计显著性。区域平均包含空间平滑，小标准差可能是数据本身的特征。

## 月份配对显著性
每个区域的每一对月份按同一年配对，共10个年度差值。统计量为差值平均数。穷举2^10=1024种符号翻转，用绝对统计量不小于观测绝对值的比例定义双侧p值，保留数值容差处理浮点相等。
4区域各66对独立月份比较，合计264个原始p值共同做BY多重比较校正。03仅画上三角，颜色和数值表示行月份减列月份，星号表示校正p<0.05。04是7月减1月的逐年差值，p值沿用同一264比较的校正。
这里的“穷举”指完整列举交换分布。统计推断仍依赖零假设下配对内标签可交换（或差值关于零对称），且年度差值之间近似独立。尚未做长期年际相关结构的专门建模。仅10年，结论范围限于该时段的区域季节差异。区域之间重叠并非独立，本次采用允许比较之间依赖的BY校正，但校正仍要求原始p值满足检验假设。
未通过校正不等于两个月完全相同，颜色也不代表显著性大小。

## 文件与复现
运行 试验/年际波动与月份显著性.py，met环境。输出四张600 DPI图片、配对检验CSV、统计NetCDF和JSON摘要。
已核对数据形状、缺测、p值范围及校正约束，且选一对月份用SciPy精确配对置换函数交叉核验。
方法文档 https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html
'''
    (OUT/'说明与结果.md').write_text(note,encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
