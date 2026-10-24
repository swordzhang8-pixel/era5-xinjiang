"""2020 年代表月（1/4/7/10）风速四联图 + 年平均图。

用法（在仓库根目录）：
    python 2_程序/8_画图_ERA5四季与年平均.py

输出：
    3_成果图/ERA5风速_2020_四季四联图.png
    3_成果图/ERA5风速_2020年平均.png

注意：
- 四张子图共用一套 levels，色标才可比；各自 vmin/vmax 会让"哪个月风大"变成假的。
- 数据只有 1/4/7/10 四个月，所谓"年平均"是这 4 个代表月的平均，不是真正的年均，
  图标题里要写清楚，别拿它当全年结论。
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).resolve().parent.parent      # 仓库根目录
DATA = BASE / "data"
FIG = BASE / "3_成果图"

MONTHS = ["2020-01", "2020-04", "2020-07", "2020-10"]
LABEL = {"2020-01": "1 月", "2020-04": "4 月", "2020-07": "7 月", "2020-10": "10 月"}


def normalize(ds: xr.Dataset) -> xr.Dataset:
    """统一时间维名叫 time，丢掉 expver 标记，纬度转升序。"""
    if "valid_time" in ds.coords:
        ds = ds.rename({"valid_time": "time"})
    if "expver" in ds.coords:
        ds = ds.drop_vars("expver")
    return ds.sortby("latitude")


def wind_speed(ds: xr.Dataset) -> xr.DataArray:
    ws = np.sqrt(ds.u10**2 + ds.v10**2)
    ws.attrs = {"units": "m s-1", "long_name": "10 m wind speed"}
    return ws


def add_map_features(ax) -> None:
    ax.set_extent([70, 100, 35, 50], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="0.3")
    ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="black")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    files = sorted(DATA.glob("era5_*.nc"))
    if len(files) < 4:
        print(f"[error] data 里只有 {len(files)} 个 era5_*.nc，先跑 1_下载ERA5.py --all")
        return 2

    # 四个文件按坐标合并；先规范化再拼，避免 valid_time / expver 打架
    ds = xr.open_mfdataset(files, combine="by_coords", preprocess=normalize,
                           chunks={"time": 124})
    ws = wind_speed(ds)
    monthly = ws.groupby("time.month").mean().compute()

    fields = {m: monthly.sel(month=int(m.split("-")[1])) for m in MONTHS}
    vmax = max(float(f.max()) for f in fields.values())
    vmin = min(float(f.min()) for f in fields.values())
    levels = np.arange(0, np.ceil(vmax * 2) / 2 + 0.5, 0.5)

    print(f"数据: {len(files)} 个文件 → {ds.sizes['time']} 个时次")
    for m in MONTHS:
        f = fields[m]
        print(f"  {LABEL[m]:>4s}  全区 {float(f.mean()):.2f}  最大 {float(f.max()):.2f} m/s")
    print(f"  共用色标: {vmin:.2f} — {vmax:.2f} m/s，{len(levels) - 1} 档")

    proj = ccrs.PlateCarree()
    fig, axes = plt.subplots(2, 2, figsize=(12, 9.5),
                             subplot_kw={"projection": proj})
    cf = None
    for ax, m in zip(axes.ravel(), MONTHS):
        f = fields[m]
        cf = ax.contourf(f.longitude, f.latitude, f.values, levels=levels,
                         cmap="viridis", transform=proj, extend="both")
        add_map_features(ax)
        ax.set_title(f"2020 年 {LABEL[m]}", fontsize=12)

    cb = fig.colorbar(cf, ax=axes, orientation="horizontal", shrink=0.75,
                      pad=0.06, aspect=40)
    cb.set_label("10 米风速 (m s$^{-1}$)")
    fig.suptitle("ERA5 10 米风速 · 2020 年代表月", fontsize=15, y=0.96)

    out4 = FIG / "ERA5风速_2020_四季四联图.png"
    fig.savefig(out4, dpi=200, bbox_inches="tight")
    print(f"已保存: {out4}")

    # 年平均（实为 4 个代表月的平均）
    annual = ws.mean("time").compute()
    fig2, ax2 = plt.subplots(figsize=(9, 6), subplot_kw={"projection": proj})
    cf2 = ax2.contourf(annual.longitude, annual.latitude, annual.values,
                       levels=levels, cmap="viridis", transform=proj, extend="both")
    add_map_features(ax2)
    gl = ax2.gridlines(draw_labels=True, linestyle=":", linewidth=0.4, color="0.5")
    gl.top_labels = False
    gl.right_labels = False
    cb2 = fig2.colorbar(cf2, ax=ax2, shrink=0.85, pad=0.03)
    cb2.set_label("10 米风速 (m s$^{-1}$)")
    ax2.set_title("ERA5 10 米风速 · 2020 年代表月平均（1/4/7/10 月）", pad=12)

    out_year = FIG / "ERA5风速_2020年平均.png"
    fig2.savefig(out_year, dpi=300, bbox_inches="tight")
    print(f"已保存: {out_year}")

    print()
    print(f"代表月平均: 全区 {float(annual.mean()):.2f} m/s，"
          f"最大 {float(annual.max()):.2f} m/s")
    print("说明: 只有 4 个月，别把这张图当'全年平均'用；真年均要 12 个月。")
    ds.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
