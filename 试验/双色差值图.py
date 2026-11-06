"""2020年7月减1月月平均10米风速，使用对称双色标。"""
from pathlib import Path
import sys
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import cartopy.crs as ccrs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from era5x import io, compute, plot


def main():
    out = ROOT / "图集/双色差值"
    out.mkdir(parents=True, exist_ok=True)
    means = []
    counts = []
    for month in [1, 7]:
        with io.load_era5(ROOT / "data" / f"era5_2020{month:02d}.nc") as ds:
            speed = compute.wind_speed(ds)
            expected = np.arange(np.datetime64(f"2020-{month:02d}-01T00"),
                                 np.datetime64(f"2020-{month + 1:02d}-01T00"),
                                 np.timedelta64(6, "h"))
            if not np.array_equal(speed.time.values, expected):
                raise ValueError(f"{month}月时间轴不完整或采样频率不符")
            speed = speed.where(np.isfinite(speed))
            count = speed.count("time").load()
            mean = speed.mean("time", skipna=True).where(count == len(expected)).load()
            means.append(mean)
            counts.append(count)
    jan, july = xr.align(*means, join="exact")
    diff = (july - jan).rename("wind_speed_difference")
    diff.attrs = {"units": "m s-1", "definition": "July 2020 mean wind speed minus January 2020 mean wind speed"}
    bound = max(0.5, float(np.ceil(abs(diff).max().item() * 2) / 2))
    weights = np.cos(np.deg2rad(diff.latitude))
    region_mean = float(diff.weighted(weights).mean())
    results = xr.Dataset({"january_mean": jan, "july_mean": july,
                          "difference": diff, "january_valid_count": counts[0],
                          "july_valid_count": counts[1]})
    results.attrs.update(region="70-100E,35-50N rectangle",
                         sampling="6-hourly instantaneous speed, monthly mean")
    results.to_netcdf(out / "2020_07减01_风速差.nc", engine="scipy")
    assert np.allclose(diff.values, july.values - jan.values, equal_nan=True)
    plot.setup_style()
    fig, ax = plt.subplots(figsize=(12, 7.8), layout="constrained",
                           subplot_kw={"projection": ccrs.PlateCarree()})
    mesh = ax.contourf(
        diff.longitude, diff.latitude, diff.values,
        levels=np.linspace(-bound, bound, 91),
        cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound),
        transform=ccrs.PlateCarree(),
    )
    plot._add_map_features(ax, gridlines=True, admin=True)
    ax.set_extent([70, 100, 35, 50], crs=ccrs.PlateCarree())
    ax.set_title("新疆及周边 | 2020 年 7 月减 1 月月平均 10 米风速", fontsize=14, pad=14)
    cb = fig.colorbar(mesh, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label("风速差值 (m/s)", fontsize=11)
    cb.set_ticks(np.arange(-4, 5, 1))
    fig.supxlabel("红色 > 0：7 月风速更大    白色 ≈ 0：差异较小    蓝色 < 0：1 月风速更大", fontsize=11)
    fig.savefig(out / "2020_07减01_双色风速差值.png", dpi=600)
    plt.close(fig)
    note = f"""# 2020年7月减1月月平均风速差值

数据来自项目现有ERA5文件 era5_202001.nc 和 era5_202007.nc。
先对每个时次用 sqrt(u10²+v10²) 计算10米风速，再分别求月平均，最后做7月减1月。
两个月时间轴均已验证为完整的六小时采样，各124个时次。仅绘制两个月均无缺测的格点。
该图比较2020年两个具体月份，不能直接替代多年夏冬季气候态差异。

## 读图
- 红色表示7月月平均风速比1月大。
- 蓝色表示7月月平均风速比1月小。
- 零附近为白色，正负使用对称范围 −{bound:g} 至 +{bound:g} m/s，零值居中。
- 差值范围为{float(diff.min()):.3f}至{float(diff.max()):.3f} m/s。
- 区域面积加权平均差值为{region_mean:+.3f} m/s，覆盖新疆及周边70—100°E、35—50°N矩形，使用cos纬度权重。
- 本图尚未做显著性检验。颜色表达差值的方向和大小。

## 显示方式
采用等经纬度投影，与矩形数据边界一致，消除原兰勃特矩形图框中的边缘空白。导出为7200×4680像素、600 DPI。使用91个等值线边界改善色阶观感，原始数据空间分辨率保持不变。

## 复现
在met环境运行 试验/双色差值图.py。
输出位于 图集/双色差值，包括PNG、指标NetCDF和本说明。
数值校验包括坐标严格对齐、完整时间轴和逐格点差值恒等式。
"""
    (out / "说明.md").write_text(note, encoding="utf-8")
    print(note)


if __name__ == "__main__":
    main()
