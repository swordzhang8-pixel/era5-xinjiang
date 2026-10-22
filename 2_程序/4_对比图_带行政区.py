# -*- coding: utf-8 -*-
"""三联对比图：1 月 | 7 月 | 差值（7 月 − 1 月），叠加新疆地州边界。

为什么画这张图
--------------
单看一张图很难判断"哪里不一样"。三张并排：
  ① 1 月          ② 7 月          ③ 差值（红=夏季更大，蓝=冬季更大）
**只有第③张能一眼看出空间格局**——它就是"差异图"，科研里最常用的表达方式。

用法：
    conda activate met
    python 2_程序/4_对比图_带行政区.py

输出：
    3_成果图/CMFD风速_季节对比_带行政区.png
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import xarray as xr

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ADMIN_DIR = DATA_DIR / "admin"
FIG_DIR = ROOT / "3_成果图"

EXTENT = [73.0, 97.0, 34.0, 50.0]      # 新疆范围（稍放宽，保证边界完整）
GEO_URL = "https://geo.datav.aliyun.com/areas_v3/bound/650000_full.json"
GEO_FILE = ADMIN_DIR / "xinjiang_pref.json"

VMAX_ABS = 8.5          # ①② 共用色标上限（下限 0.5），保证两图可比
DIFF_LIM = 4.0          # 差值图对称范围 ±4 m/s

# adcode → 简称。只给这 14 个地州加标注，直管市（659xxx）不标，否则北部会糊成一片。
SHORT = {
    "650100": "乌鲁木齐", "650200": "克拉玛依", "650400": "吐鲁番", "650500": "哈密",
    "652300": "昌吉", "652700": "博州", "652800": "巴州", "652900": "阿克苏",
    "653000": "克州", "653100": "喀什", "653200": "和田", "654000": "伊犁",
    "654200": "塔城", "654300": "阿勒泰",
}


def load_admin():
    """返回 [(adcode, 简称或None, 几何), ...]。"""
    ADMIN_DIR.mkdir(parents=True, exist_ok=True)
    if not GEO_FILE.exists():
        print(f"下载行政区边界：{GEO_URL}")
        with urllib.request.urlopen(GEO_URL, timeout=30) as r:
            GEO_FILE.write_bytes(r.read())

    data = json.loads(GEO_FILE.read_text(encoding="utf-8"))
    out = []
    for feat in data["features"]:
        code = str(feat["properties"].get("adcode", ""))
        out.append((code, SHORT.get(code), shape(feat["geometry"])))
    print(f"行政区数量：{len(out)}（其中会标注 {sum(1 for _, s, _ in out if s)} 个地州）")
    return out


def load_fields():
    nc = sorted(DATA_DIR.glob("*.nc"))[0]
    ds = xr.open_dataset(nc, decode_times=True)
    w = ds["wind"].sel(lat=slice(EXTENT[2], EXTENT[3]), lon=slice(EXTENT[0], EXTENT[1]))
    jan = w.sel(time=w["time"].dt.month == 1).mean("time")
    jul = w.sel(time=w["time"].dt.month == 7).mean("time")
    ds.close()
    return jan, jul, jul - jan


def add_admin(ax, admin):
    ax.add_geometries([g for _, _, g in admin], crs=ccrs.PlateCarree(),
                      facecolor="none", edgecolor="0.1", linewidth=0.45, zorder=5)

    for code, short, geom in admin:
        if not short:                      # 直管市不标注，避免拥挤
            continue
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        big = max(polys, key=lambda p: p.area)
        pt = big.representative_point()
        ax.text(pt.x, pt.y, short, fontsize=7, ha="center", va="center", zorder=7,
                bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=0.6))


def add_grid(ax):
    gl = ax.gridlines(draw_labels=True, linewidth=0.25, color="gray", alpha=0.4)
    gl.top_labels = False
    gl.right_labels = False


def main() -> None:
    admin = load_admin()
    jan, jul, diff = load_fields()
    print(f"1 月 {float(jan.mean()):.2f} | 7 月 {float(jul.mean()):.2f} | 差 {float(diff.mean()):+.2f} m/s")

    fig, axes = plt.subplots(1, 3, figsize=(19, 6.0),
                             subplot_kw={"projection": ccrs.PlateCarree()},
                             layout="constrained")

    common = dict(transform=ccrs.PlateCarree(), extend="both")

    # ① 1 月
    ax = axes[0]
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    im1 = ax.contourf(jan.lon, jan.lat, jan, levels=np.linspace(0.5, VMAX_ABS, 21),
                      cmap="viridis", **common)
    add_admin(ax, admin)
    add_grid(ax)
    ax.set_title("① 1 月平均风速", fontsize=13, weight="bold")

    # ② 7 月
    ax = axes[1]
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.contourf(jul.lon, jul.lat, jul, levels=np.linspace(0.5, VMAX_ABS, 21),
                cmap="viridis", **common)
    add_admin(ax, admin)
    add_grid(ax)
    ax.set_title("② 7 月平均风速", fontsize=13, weight="bold")

    # ③ 差值（发散色标，0 居中）
    ax = axes[2]
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    im3 = ax.contourf(diff.lon, diff.lat, diff, levels=np.linspace(-DIFF_LIM, DIFF_LIM, 21),
                      cmap="RdBu_r", norm=TwoSlopeNorm(0, -DIFF_LIM, DIFF_LIM), **common)
    add_admin(ax, admin)
    add_grid(ax)
    ax.set_title("③ 差值：7 月 − 1 月", fontsize=13, weight="bold")

    cb1 = fig.colorbar(im1, ax=axes[0], pad=0.02, shrink=0.8)
    cb1.set_label("风速 (m s-1)", fontsize=10)
    cb3 = fig.colorbar(im3, ax=axes[2], pad=0.02, shrink=0.8)
    cb3.set_label("差值 (m s-1)", fontsize=10)

    fig.suptitle("新疆近地面风速：冬夏对比与差值（CMFD 1979—2018）", fontsize=15, weight="bold")

    FIG_DIR.mkdir(exist_ok=True)
    out = FIG_DIR / "CMFD风速_季节对比_带行政区.png"
    fig.savefig(out, dpi=200, pad_inches=0.25)
    plt.close(fig)
    print("已保存：", out)


if __name__ == "__main__":
    main()
