"""比较逐格点 p95 与固定 10.8 m/s。基准 2009—2014，研究 2015—2018。"""
from pathlib import Path
import sys
import csv
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from era5x import io, compute, plot


def load_speed(first, last):
    parts = []
    for year in range(first, last + 1):
        with io.load_era5(ROOT / "data/yearly" / f"era5_{year}.nc") as ds:
            speed = compute.wind_speed(ds).astype("float32").load()
            speed = speed.transpose("time", "latitude", "longitude")
            parts.append(speed)
    result = xr.concat(parts, dim="time", join="exact").sortby("time")
    expected = np.arange(
        np.datetime64(f"{first}-01-01T00"),
        np.datetime64(f"{last + 1}-01-01T00"),
        np.timedelta64(6, "h"),
    )
    if not np.array_equal(result.time.values, expected):
        raise ValueError("时间轴不是完整且唯一的六小时时次，停止比较")
    return result.where(np.isfinite(result))


def main():
    out = ROOT / "图集/阈值对照"
    out.mkdir(parents=True, exist_ok=True)
    base = load_speed(2009, 2014)
    study = load_speed(2015, 2018)
    base, study = xr.align(base, study, join="exact", exclude={"time"})
    threshold = base.quantile(0.95, dim="time", skipna=True).drop_vars("quantile")
    base_valid = base.count("time")
    threshold = threshold.where(base_valid >= 0.9 * base.sizes["time"])
    del base
    absolute = xr.full_like(threshold, 10.8)
    valid = np.isfinite(study) & np.isfinite(threshold)
    nvalid = valid.sum("time")
    relative_over = valid & (study > threshold)
    absolute_over = valid & (study > absolute)
    relative_count = relative_over.sum("time").where(nvalid > 0)
    absolute_count = absolute_over.sum("time").where(nvalid > 0)
    relative_rate = (100 * relative_count / nvalid).where(nvalid > 0)
    absolute_rate = (100 * absolute_count / nvalid).where(nvalid > 0)
    # 当局地 p95 不高于绝对阈值时，绝对超阈集合必须包含于相对超阈集合。
    assert not bool(((absolute_count > relative_count) & (threshold <= 10.8)).any())
    assert bool(((relative_count <= nvalid) | (nvalid == 0)).all())
    assert bool(((absolute_count <= nvalid) | (nvalid == 0)).all())

    result = xr.Dataset({
        "p95_threshold": threshold,
        "absolute_threshold": absolute,
        "baseline_valid_count": base_valid,
        "study_valid_count": nvalid,
        "relative_count": relative_count,
        "absolute_count": absolute_count,
        "relative_rate": relative_rate,
        "absolute_rate": absolute_rate,
    })
    for name in ["p95_threshold", "absolute_threshold"]:
        result[name].attrs["units"] = "m s-1"
    for name in ["relative_rate", "absolute_rate"]:
        result[name].attrs["units"] = "%"
    result.attrs.update(
        baseline="2009-2014", study="2015-2018",
        comparison="strictly greater than threshold",
        sampling="6-hourly; counts are sampled exceedance times, not calendar days",
        baseline_coverage_minimum=0.9,
        region="70-100E,35-50N rectangular domain, not Xinjiang administrative mask",
    )
    result.to_netcdf(out / "阈值对照_指标.nc", engine="scipy")

    weights = np.cos(np.deg2rad(study.latitude))
    relative_mean = float(relative_rate.weighted(weights).mean())
    absolute_mean = float(absolute_rate.weighted(weights).mean())
    with (out / "阈值对照_汇总.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["方法", "基准期", "研究期", "区域面积加权平均超阈率_%", "格点超阈率最大值_%"])
        writer.writerow(["逐格点p95", "2009-2014", "2015-2018", relative_mean, float(relative_rate.max())])
        writer.writerow(["固定10.8m/s", "不依赖基准期", "2015-2018", absolute_mean, float(absolute_rate.max())])

    plot.setup_style()
    fig, axes = plt.subplots(
        2, 2, figsize=(12, 8.4), layout="constrained",
        subplot_kw={"projection": ccrs.LambertConformal(central_longitude=85, central_latitude=42.5)},
    )
    threshold_max = np.ceil(max(10.8, float(threshold.max())))
    rate_max = max(1, np.ceil(max(float(relative_rate.max()), float(absolute_rate.max()))))
    groups = [
        ([threshold, absolute], ["(a) 局地 p95 阈值", "(b) 固定阈值 10.8 m/s"],
         np.linspace(0, threshold_max, 17), "viridis", "10 米风速阈值 (m/s)"),
        ([relative_rate, absolute_rate], ["(c) 超过局地 p95 的有效样本比例", "(d) 超过 10.8 m/s 的有效样本比例"],
         np.linspace(0, rate_max, 17), "YlOrRd", "超阈率 (%)"),
    ]
    for row, (fields, titles, levels, cmap, label) in enumerate(groups):
        for col, (field, title) in enumerate(zip(fields, titles)):
            ax = axes[row, col]
            artist = ax.contourf(
                field.longitude, field.latitude, field.values,
                levels=levels, cmap=cmap, transform=ccrs.PlateCarree(),
            )
            plot._add_map_features(ax, gridlines=True)
            ax.set_title(title, loc="left", fontsize=11)
        fig.colorbar(artist, ax=axes[row, :].tolist(), orientation="horizontal",
                     shrink=0.8, aspect=45, pad=0.04, label=label)
    fig.suptitle("新疆及周边 | 相对阈值与绝对阈值对照\n基准期 2009—2014 · 研究期 2015—2018 · 六小时采样", fontsize=15)
    fig.savefig(out / "相对与绝对阈值对照.png", dpi=240)
    plt.close(fig)

    note = f"""# 相对阈值与绝对阈值对照

本次使用现有 ERA5 u10/v10 年文件，先逐时次计算 sqrt(u10²+v10²)，再统计超阈。
基准期为2009—2014，研究期为2015—2018，共{study.sizes['time']}个六小时时次。

## 定义
- 相对阈值为各格点基准期风速的p95，使用xarray默认线性分位数插值。
- 绝对阈值为各格点相同的10.8 m/s，是本次指定的演示对照阈值。它用于10米风速，具体工程应用需要另行确认指标定义与高度。
- 两种方法均使用风速严格大于阈值，使用共同有效样本。
- 基准期有效样本不足90%的格点不纳入。研究期缺测从分母排除，零有效样本保留缺测。
- 超阈率为超阈时次数/有效时次数。六小时采样不能直接给出自然日超阈天数或真实事件持续时间。

## 结果
- p95范围为{float(threshold.min()):.2f}—{float(threshold.max()):.2f} m/s。
- 相对阈值的区域面积加权平均超阈率为{relative_mean:.3f}%。
- 绝对阈值的区域面积加权平均超阈率为{absolute_mean:.3f}%。
- 两者格点最大超阈率分别为{float(relative_rate.max()):.3f}%和{float(absolute_rate.max()):.3f}%。
- 研究期原始有限样本总数为{int(np.isfinite(study).sum())}，共同有效样本总数为{int(nvalid.sum())}。

## 怎样读图
上排两幅图共用风速色标，下排共用超阈率色标。相同颜色对应相同数值。
局地p95回答某个地点超过自身历史高值的频繁程度。固定10.8 m/s回答各地点达到同一风速标准的频繁程度。
低风速区域的p95可能很低，超过自身p95并不代表达到同样强的绝对风速。
研究期超阈率可以偏离5%，因为阈值使用另一时段估计。有限样本、重复值和分位数插值也会影响基准期自身的超阈比例。
固定阈值图较淡或近零的格点表示该标准较少被超过，共用色标便于诚实比较。

## 统计范围与限制
区域汇总覆盖70—100°E、35—50°N矩形区域，包含新疆周边地区。采用cos(纬度)面积近似权重。
本次是阈值定义的描述性对照，未检验差异显著性，未从短研究期推断长期趋势。
图中不单独解析风电场尾流或轮毂高度风速。
完整时间轴已检查为六小时连续且唯一。另核验了在p95<=10.8的格点，绝对超阈次数不超过相对超阈次数。

## 复现
在met环境从任意目录运行本脚本。
输入位于data/yearly，输出为图集/阈值对照中的PNG、指标NetCDF、汇总CSV和本说明。
"""
    (out / "结果说明.md").write_text(note, encoding="utf-8")
    print(note)


if __name__ == "__main__":
    main()
