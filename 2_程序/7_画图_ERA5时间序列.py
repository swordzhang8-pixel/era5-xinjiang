"""画 2020-01 新疆（乌鲁木齐附近）10 米风速时间序列。

用法（在仓库根目录）：
    python 2_程序/7_画图_ERA5时间序列.py
    python 2_程序/7_画图_ERA5时间序列.py --lat 43.8 --lon 87.6 --out 3_成果图/ws.png

数据默认读 data/era5_202001.nc；用环境变量 ERA5_DATA_DIR 可指向别处。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent      # 仓库根目录（era5-xinjiang/）
DATA = Path(os.environ.get("ERA5_DATA_DIR", BASE / "data"))
FIG = BASE / "3_成果图"


def load(path: Path) -> xr.Dataset:
    """读 ERA5，规范成 time 维，处理 expver 标记。"""
    ds = xr.open_dataset(path)
    if "valid_time" in ds.coords:
        ds = ds.rename({"valid_time": "time"})
    if "expver" in ds.coords:
        # expver 只是挂在 time 上的标记位（"0001"/"0005"），不是维度
        ds = ds.drop_vars("expver")
    if np.unique(ds.time.values).size != ds.time.size:
        # 缺测时同一时次会有两条记录，按时间去重
        _, idx = np.unique(ds.time.values, return_index=True)
        ds = ds.isel(time=np.sort(idx))
    return ds


def wind_speed(ds: xr.Dataset) -> xr.DataArray:
    ws = np.sqrt(ds.u10**2 + ds.v10**2)
    ws.attrs = {"units": "m s-1", "long_name": "10 m wind speed"}
    return ws


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nc", default=str(DATA / "era5_202001.nc"))
    parser.add_argument("--lat", type=float, default=43.8)
    parser.add_argument("--lon", type=float, default=87.6)
    parser.add_argument("--out", default=str(FIG / "ERA5风速_2020-01_时间序列.png"))
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ds = load(Path(args.nc))
    ws = wind_speed(ds)

    point = ws.sel(latitude=args.lat, longitude=args.lon, method="nearest")
    plat, plon = float(point.latitude), float(point.longitude)

    # 风向：风从哪来（气象约定），只取一个代表时刻看个大概
    i = int(np.nanargmax(point.values))
    u_t = float(ds.u10.isel(time=i).sel(latitude=plat, longitude=plon))
    v_t = float(ds.v10.isel(time=i).sel(latitude=plat, longitude=plon))
    direction = (270.0 - np.degrees(np.arctan2(v_t, u_t))) % 360.0

    domain = ws.mean(dim=["latitude", "longitude"])

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(point.time, point.values, color="#c0392b", lw=1.4,
            label=f"({plat:.2f}N, {plon:.2f}E)")
    ax.plot(domain.time, domain.values, color="#7f8c8d", lw=1.0, ls="--", alpha=0.8,
            label="domain mean")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Wind speed (m s$^{-1}$)")
    ax.set_title(f"ERA5 10 m wind speed · 2020-01 · {plat:.2f}N {plon:.2f}E")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    fig.autofmt_xdate()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")

    vals = point.values
    print(f"格点: {plat:.2f}N, {plon:.2f}E（请求 {args.lat}N, {args.lon}E 的最近点）")
    print(f"时次: {point.time.size} 个，{str(point.time.values[0])[:16]} → {str(point.time.values[-1])[:16]} UTC")
    print(f"风速: 均值 {np.nanmean(vals):.2f}，最小 {np.nanmin(vals):.2f}，最大 {np.nanmax(vals):.2f} m/s")
    print(f"峰值时刻: {str(point.time.values[i])[:16]} UTC，此时风向约 {direction:.0f}°（来向）")
    print(f"全场均值: {float(domain.mean()):.2f} m/s")
    print()
    print("按小时平均（只有 4 个时次，谈不了日变化，仅作参考）:")
    hours = ws["time"].dt.hour.values
    for h in sorted(set(hours.tolist())):
        sel = ws.where(xr.DataArray(hours == h, dims="time"), drop=True)
        print(f"  {int(h):02d}:00 UTC  {float(sel.mean()):.2f} m/s")
    print()
    print(f"已保存: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
