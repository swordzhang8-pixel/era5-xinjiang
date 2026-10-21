# -*- coding: utf-8 -*-
"""
W1 第一个端到端脚本：验证 xarray + cartopy + matplotlib 整条链路。

现在还不用真实 ERA5 数据——先用一个"合成风场"把工具链跑通。
明天拿到 CDS 权限后，只需要把 build_demo_field() 换成 read_era5()，
其余代码一行都不用改。

运行：
    conda activate met
    python src/main.py

输出：
    figures/wind_demo.png
"""
import sys
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib

matplotlib.use("Agg")          # 不开窗，直接存图（服务器上也能跑）
import matplotlib.pyplot as plt

# 中文字体（Windows 自带微软雅黑），否则标题里的中文会变成方块
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


def build_demo_field(seed: int = 0) -> xr.DataArray:
    """造一个"像风场"的合成数据：新疆区域 10 m 风速。

    形状 (lat=61, lon=121)，0.25 度网格，覆盖 35—50°N / 70—100°E。
    用纬向正弦 + 地形抬升项 + 一点随机噪声，纯粹为了出图好看且可复现。
    """
    rng = np.random.default_rng(seed)
    lat = np.arange(35.0, 50.01, 0.25)
    lon = np.arange(70.0, 100.01, 0.25)

    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    # 大尺度：西风带（越往西越强）+ 南北梯度
    base = 5.0 + 3.0 * np.cos((LAT - 42.0) / 8.0) + 2.0 * np.sin((LON - 85.0) / 12.0)
    # 地形项：天山一带（约 42—44°N）风速加大
    terrain = 4.0 * np.exp(-((LAT - 43.0) ** 2) / (2 * 0.8 ** 2))
    noise = rng.normal(0.0, 0.4, LAT.shape)

    ws = np.clip(base + terrain + noise, 0.0, None)

    da = xr.DataArray(
        ws.astype("float32"),
        coords={"latitude": ("latitude", lat, {"units": "degrees_north"}),
                "longitude": ("longitude", lon, {"units": "degrees_east"})},
        dims=("latitude", "longitude"),
        name="wind_speed_10m",
        attrs={"units": "m s-1", "long_name": "10 m wind speed", "source": "synthetic demo"},
    )
    return da


def plot_field(da: xr.DataArray, out_png: Path) -> None:
    """画一张带国界、色标、经纬度刻度的填色图。"""
    fig, ax = plt.subplots(
        figsize=(9, 6),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    cf = ax.contourf(
        da.longitude, da.latitude, da,
        levels=20, cmap="viridis", transform=ccrs.PlateCarree(),
    )
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label(da.attrs.get("units", ""), fontsize=10)

    # 海岸线/国界需要联网下载 Natural Earth 数据，第一次可能较慢；
    # 失败也不影响出图，所以包一层 try。
    try:
        ax.coastlines(linewidth=0.5, edgecolor="0.3")
        ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="k")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] coastlines/borders failed (figure still ok): {exc}", file=sys.stderr)

    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False

    ax.set_extent([70, 100, 35, 50], crs=ccrs.PlateCarree())
    ax.set_title(f"新疆区域 10 m 风速（合成演示数据·{da.attrs['source']}）", fontsize=13)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    print(f"python      : {sys.version.split()[0]}")
    print(f"xarray      : {xr.__version__}")
    print(f"matplotlib  : {matplotlib.__version__}")
    print(f"numpy       : {np.__version__}")

    da = build_demo_field(seed=42)
    print(f"\nshape       : {da.shape}")
    print(f"dims        : {da.dims}")
    print(f"lat/lon     : {float(da.latitude.min())}-{float(da.latitude.max())}N, "
          f"{float(da.longitude.min())}-{float(da.longitude.max())}E")
    print(f"wind range  : {float(da.min()):.2f}-{float(da.max()):.2f} m/s")
    print(f"area mean   : {float(da.mean()):.2f} m/s")

    out_png = FIG_DIR / "wind_demo.png"
    plot_field(da, out_png)
    print(f"\nsaved       : {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
