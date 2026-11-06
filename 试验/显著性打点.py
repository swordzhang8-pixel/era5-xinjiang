"""2020年7月减1月风速差，日平均样本的循环移动块自助检验。"""
from pathlib import Path
import sys
import numpy as np
import xarray as xr
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import cartopy.crs as ccrs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from era5x import io, compute, plot

SEED = 20261106
REPLICATES = 9999
BLOCK = 5


def block_counts(rng, n, size):
    starts = rng.integers(0, n, size=(size, int(np.ceil(n / BLOCK))))
    indices = ((starts[:, :, None] + np.arange(BLOCK)) % n).reshape(size, -1)[:, :n]
    counts = np.zeros((size, n), dtype=float)
    np.add.at(counts, (np.arange(size)[:, None], indices), 1)
    return counts / n


def main():
    out = ROOT / "图集/双色差值"
    daily = []
    correlations = []
    for month in [1, 7]:
        with io.load_era5(ROOT / "data" / f"era5_2020{month:02d}.nc") as ds:
            speed = compute.wind_speed(ds).transpose("time", "latitude", "longitude")
            expected = np.arange(np.datetime64(f"2020-{month:02d}-01T00"),
                                 np.datetime64(f"2020-{month + 1:02d}-01T00"),
                                 np.timedelta64(6, "h"))
            if not np.array_equal(speed.time.values, expected):
                raise ValueError("需要完整六小时时间轴")
            finite = speed.where(np.isfinite(speed))
            day = finite.resample(time="1D").mean().where(
                finite.resample(time="1D").count() == 4).load()
            daily.append(day)
    jan, july = xr.align(*daily, join="exact", exclude={"time"})
    valid = np.isfinite(jan.values).all(axis=0) & np.isfinite(july.values).all(axis=0)
    a = jan.values[:, valid].astype(float)
    b = july.values[:, valid].astype(float)
    for arr in [a, b]:
        left = arr[:-1] - arr[:-1].mean(axis=0)
        right = arr[1:] - arr[1:].mean(axis=0)
        denom = np.sqrt((left ** 2).sum(axis=0) * (right ** 2).sum(axis=0))
        rho = np.divide((left * right).sum(axis=0), denom,
                        out=np.full_like(denom, np.nan), where=denom > 0)
        correlations.append(rho)
    observed = b.mean(axis=0) - a.mean(axis=0)
    a_centered = a - a.mean(axis=0)
    b_centered = b - b.mean(axis=0)
    rng = np.random.default_rng(SEED)
    extreme = np.zeros(len(observed), dtype=int)
    for start in range(0, REPLICATES, 250):
        size = min(250, REPLICATES - start)
        boot = block_counts(rng, len(b), size) @ b_centered
        boot -= block_counts(rng, len(a), size) @ a_centered
        extreme += (abs(boot) >= abs(observed)[None, :]).sum(axis=0)
    pvals = (extreme + 1) / (REPLICATES + 1)
    adjusted = stats.false_discovery_control(pvals, method="by")
    significant = adjusted < 0.05
    raw_welch = stats.ttest_ind(b, a, axis=0, equal_var=False).pvalue
    assert np.all((pvals > 0) & (pvals <= 1))
    assert np.all(adjusted >= pvals - 1e-12)
    assert np.all(~significant | (pvals < 0.05))
    coords = {"latitude": jan.latitude, "longitude": jan.longitude}
    dims = ("latitude", "longitude")

    def field(values):
        data = np.full(valid.shape, np.nan)
        data[valid] = values
        return xr.DataArray(data, coords=coords, dims=dims)

    diff = field(observed)
    result = xr.Dataset({
        "difference": diff,
        "block_bootstrap_p": field(pvals),
        "by_adjusted_p": field(adjusted),
        "significant_by_005": field(significant.astype(float)),
        "welch_p_independence_assumed": field(raw_welch),
        "january_lag1_correlation": field(correlations[0]),
        "july_lag1_correlation": field(correlations[1]),
    })
    result.attrs.update(method="Centered circular moving-block bootstrap; two-sided; BY FDR",
                        block_days=BLOCK, replicates=REPLICATES, seed=SEED,
                        sample_days_each=31, domain="70-100E 35-50N rectangle",
                        interpretation="Exploratory comparison of January and July 2020")
    result.to_netcdf(out / "2020_07减01_显著性指标.nc", engine="scipy")
    with xr.open_dataset(out / "2020_07减01_风速差.nc", engine="scipy") as previous:
        assert np.allclose(diff, previous.difference, atol=1e-5, equal_nan=True)
    bound = max(0.5, float(np.ceil(abs(diff).max().item() * 2) / 2))
    plot.setup_style()
    fig, ax = plt.subplots(figsize=(12, 7.8), layout="constrained",
                           subplot_kw={"projection": ccrs.PlateCarree()})
    artist = ax.contourf(diff.longitude, diff.latitude, diff.values,
                        levels=np.linspace(-bound, bound, 91), cmap="RdBu_r",
                        norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound),
                        transform=ccrs.PlateCarree())
    plot._add_map_features(ax, gridlines=True, admin=True)
    ax.set_extent([70, 100, 35, 50], crs=ccrs.PlateCarree())
    sigfield = field(significant.astype(float)).values == 1
    # 绘图每隔两个格点展示一个显著性点，统计和NetCDF保留全部格点。
    lon, lat = np.meshgrid(diff.longitude.values[::2], diff.latitude.values[::2])
    shown = sigfield[::2, ::2]
    ax.scatter(lon[shown], lat[shown], s=5, c="black", marker=".",
               linewidths=0, transform=ccrs.PlateCarree(), zorder=6)
    ax.set_title("2020 年 7 月减 1 月月平均 10 米风速及显著性", fontsize=14, pad=14)
    cb = fig.colorbar(artist, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label("风速差值 (m/s)", fontsize=11)
    cb.set_ticks(np.arange(-4, 5))
    fig.supxlabel("黑点：5 天块自助检验，BY 校正 p < 0.05（点位隔格显示）", fontsize=11)
    fig.savefig(out / "2020_07减01_双色差值_显著性打点.png", dpi=600)
    plt.close(fig)
    note = f"""# 显著性打点方法与结果

本图沿用2020年7月减1月的月平均10米风速差。采用每月31个日平均值，每日须有4个有效六小时时次。两个月完整有效格点共{int(valid.sum())}个。

## 检验方法
零假设为两个月对应随机过程的平均风速相同。先对每个月逐格点减去各自均值，再分别循环抽取连续5天的块，拼成31天序列，得到零假设下的均值差分布。两个月独立抽样，全空间共用每次抽样的时间索引，保留空间相关结构。
使用9999次抽样，随机种子20261106。双侧p=(绝对自助差值不小于绝对观测差值的次数+1)/10000。
在全部有效格点上用Benjamini–Yekutieli方法校正p值，校正p<0.05打点。BY允许检验之间存在依赖，但其统计保证仍以输入p值有效为前提。
绘图每隔两个格点显示一次黑点，以便读底色。NetCDF保留全部格点的显著性掩膜。

## 结果
1月日风速滞后1天相关系数的空间中位数为{np.nanmedian(correlations[0]):.3f}，7月为{np.nanmedian(correlations[1]):.3f}。
块自助原始p<0.05格点为{int((pvals < .05).sum())}个。
BY校正后为{int(significant.sum())}个，占有效格点{100 * significant.mean():.2f}%（按格点计数）。
图上实际展示{int(shown.sum())}个黑点。
未处理时间相关的日样本Welch检验原始p<0.05有{int((raw_welch < .05).sum())}个，仅作方法对照。

## 使用范围
这是短时间序列的探索性近似检验。5天块长是本次明确选定的设置，尚未做块长敏感性分析。月内近似平稳与块内相关能代表依赖结构是方法假设。仅31天，p值尾部的蒙特卡洛精度与长程相关的估计有限。
本图支持的是2020年两个月的比较，不能推广为多年季节气候态差异，也不能解释为风电或光伏的因果效应。
黑点表示通过本次检验，未打点表示未达到该证据门槛，不能据此认定差异为零。
差值已与原月均图逐格点核对，绝对容差1e-5 m/s（日均再月均与原float32直接月均的浮点求和顺序不同）。已验证p值范围、BY校正单调约束和显著掩膜一致性。

## 文件
试验/显著性打点.py 可在met环境运行。图集/双色差值中保存高清PNG和显著性指标NetCDF。
方法参考 https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html
"""
    (out / "显著性检验说明.md").write_text(note, encoding="utf-8")
    print(note)


if __name__ == "__main__":
    main()
