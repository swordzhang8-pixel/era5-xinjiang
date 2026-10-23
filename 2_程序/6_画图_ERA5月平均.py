"""画 2020-01 新疆 10 米风速月平均分布图（cartopy）。

首次运行会下载 Natural Earth 的国界/海岸线数据（约 10 MB），需要联网。
下载失败时手动把 shapefile 放到 cartopy 数据目录。

用法（在仓库根目录）：
    python 2_程序/6_画图_ERA5月平均.py

数据默认读 data/era5_202001.nc；用环境变量 ERA5_DATA_DIR 可指向别处。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent      # 仓库根目录（era5-xinjiang/）
DATA = Path(os.environ.get("ERA5_DATA_DIR", BASE / "data"))
FIG = BASE / "3_成果图"


def load(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path)
    if "valid_time" in ds.coords:
        ds = ds.rename({"valid_time": "time"})
    if "expver" in ds.coords:
        ds = ds.drop_vars("expver")
    return ds.sortby("latitude")  # ERA5 是降序，画图前转成升序


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    nc = DATA / "era5_202001.nc"
    ds = load(nc)
    ws = np.sqrt(ds.u10**2 + ds.v10**2)
    ws.attrs["units"] = "m s-1"
    field = ws.mean("time")

    print(f"数据: {nc}，{field.sizes['latitude']}×{field.sizes['longitude']} 格点")
    print(f"月均风速: {float(field.min()):.2f} — {float(field.max()):.2f} m/s")

    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(9, 6), subplot_kw={"projection": proj})
    ax.set_extent([70, 100, 35, 50], crs=proj)

    lon, lat = field.longitude.values, field.latitude.values
    levels = np.arange(0, 8.5, 0.5)
    cf = ax.contourf(lon, lat, field.values, levels=levels, cmap="viridis",
                     transform=proj, extend="both", alpha=0.95)
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label("10 m wind speed (m s$^{-1}$)")

    ax.add_feature(cfeature.COASTLINE, linewidth=0.6, edgecolor="0.25")
    ax.add_feature(cfeature.BORDERS, linewidth=0.9, edgecolor="black")
    ax.add_feature(cfeature.RIVERS, linewidth=0.3, edgecolor="#4a90d9", alpha=0.6)

    gl = ax.gridlines(draw_labels=True, linestyle=":", linewidth=0.4, color="0.5")
    gl.top_labels = False
    gl.right_labels = False

    ax.set_title("ERA5 10 m mean wind speed · 2020-01", pad=12)

    out = FIG / "ERA5风速_2020-01_月平均.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"已保存: {out}")
    print()
    print("说明: 10 米高度、单月；风资源评估应换 100 米变量并跑多年。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
