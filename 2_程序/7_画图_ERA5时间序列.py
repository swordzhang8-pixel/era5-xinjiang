"""2020-01 新疆（乌鲁木齐附近）10 米风速时间序列。

业务逻辑已经拆进 src/era5x/：读数据在 io.py，算风速在 compute.py，画图在 plot.py。

用法（在仓库根目录）：
    python 2_程序/7_画图_ERA5时间序列.py
    python 2_程序/7_画图_ERA5时间序列.py --lat 43.8 --lon 87.6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

from era5x import compute, io
from era5x import plot as eplot

DATA = BASE / "data"
FIG = BASE / "3_成果图"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nc", default=str(DATA / "era5_202001.nc"))
    parser.add_argument("--lat", type=float, default=43.8)
    parser.add_argument("--lon", type=float, default=87.6)
    parser.add_argument("--out", default=str(FIG / "ERA5风速_2020-01_时间序列.png"))
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ds = io.load_era5(Path(args.nc))
    ws = compute.wind_speed(ds)

    point = ws.sel(latitude=args.lat, longitude=args.lon, method="nearest")
    plat, plon = float(point.latitude), float(point.longitude)
    domain = ws.mean(["latitude", "longitude"])

    # 峰值时刻的风向（气象约定：风从哪来）
    i = int(np.nanargmax(point.values))
    u_t = float(ds.u10.isel(time=i).sel(latitude=plat, longitude=plon))
    v_t = float(ds.v10.isel(time=i).sel(latitude=plat, longitude=plon))
    direction = (270.0 - np.degrees(np.arctan2(v_t, u_t))) % 360.0

    vals = point.values
    print(f"格点: {plat:.2f}N, {plon:.2f}E（请求 {args.lat}N, {args.lon}E 的最近点）")
    print(f"时次: {point.time.size} 个，{str(point.time.values[0])[:16]} → "
          f"{str(point.time.values[-1])[:16]} UTC")
    print(f"风速: 均值 {np.nanmean(vals):.2f}，最小 {np.nanmin(vals):.2f}，"
          f"最大 {np.nanmax(vals):.2f} m/s")
    print(f"峰值时刻: {str(point.time.values[i])[:16]} UTC，此时风向约 {direction:.0f}°（来向）")
    print(f"全场均值: {float(domain.mean()):.2f} m/s")

    eplot.plot_timeseries(
        point, Path(args.out), domain=domain,
        title=f"ERA5 10 米风速 · 2020-01 · {plat:.2f}N {plon:.2f}E",
        label=f"({plat:.2f}N, {plon:.2f}E)",
    )
    print(f"已保存: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
