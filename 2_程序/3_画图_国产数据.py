# -*- coding: utf-8 -*-
"""
读取 CMFD（中国区域地面气象要素驱动数据集）并出图。

这是一个**独立文件**，与 src/main.py（ERA5/合成数据版）互不干扰。
两个文件共用同一套绘图风格，方便你对比"同一区域、两种数据源"的差异。

CMFD 基本信息（v1.6，中科院青藏所，TPDC 发布）：
    分辨率  0.1°（比 ERA5 的 0.25° 更细）
    时间    1979—2018，逐 3 小时
    范围    15—55°N，70—140°E（覆盖整个中国）
    变量    temp / pres / shum / wind / srad / lrad / prec
    单位    风速 m/s，温度 K，气压 Pa，降水 mm/3h

注意：CMFD 的 **wind 是风速标量**（不是 u/v 分量），所以不需要 sqrt(u²+v²)。
      缺测值通常是 -9999，xarray 默认会按 _FillValue 自动转成 NaN。

用法：
    conda activate met
    python src/main_cmfd.py --file data/CMFD_wind_2018_0p1d.nc
    python src/main_cmfd.py --file data/xxx.nc --month 7      # 只看 7 月
    python src/main_cmfd.py --file data/xxx.nc --inspect      # 只看结构不出图

输出：
    3_成果图/cmfd_wind_<tag>.png
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "3_成果图"
DATA_DIR = ROOT / "data"

# 新疆范围（N/W/S/E），与 main.py 保持一致，方便对比
AREA = [50.0, 70.0, 35.0, 100.0]


# ----------------------------------------------------------------------
# 1. 结构探查：不同数据集的坐标名/变量名都不一样，必须先看清楚
# ----------------------------------------------------------------------
def find_name(pool, candidates):
    """在候选列表里找一个真实存在的名字（大小写不敏感）。"""
    lower = {str(p).lower(): p for p in pool}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def inspect(ds: xr.Dataset) -> dict:
    """识别变量名、经纬度坐标名，并打印诊断信息。"""
    print("=" * 62)
    print("structure")
    print("=" * 62)
    print(ds)

    var_name = find_name(ds.data_vars, ["wind", "wind_speed", "ws", "u10", "wspd"])
    if var_name is None:
        # 退路：找第一个二维以上的数值变量
        for name, da in ds.data_vars.items():
            if da.ndim >= 2 and np.issubdtype(da.dtype, np.number):
                var_name = name
                break
    if var_name is None:
        raise SystemExit("没有找到可用的数值变量，请把 ds 的打印结果发给我")

    lat_name = find_name(ds.coords, ["lat", "latitude"])
    lon_name = find_name(ds.coords, ["lon", "longitude"])
    if lat_name is None or lon_name is None:
        raise SystemExit("没有识别到经纬度坐标（lat/lon 或 latitude/longitude）")

    da = ds[var_name]
    print("-" * 62)
    print(f"variable : {var_name}   dims={da.dims}   shape={da.shape}")
    print(f"lat/lon  : {lat_name} / {lon_name}")
    print(f"attr     : {dict(list(da.attrs.items())[:6])}")

    if "time" in da.dims:
        t = ds["time"].values
        print(f"time     : {t[0]}  ->  {t[-1]}   (n={len(t)})")

    vmin, vmax = float(da.min()), float(da.max())
    print(f"range    : {vmin:.3f} - {vmax:.3f}")
    if np.isnan(vmin):
        print("[warn] all NaN，可能缺测值没识别对（检查 _FillValue）", file=sys.stderr)
    elif vmin < -900 or vmax > 1e4:
        print(f"[warn] value range suspicious（{vmin} ~ {vmax}），很可能是缺测值 -9999 没被屏蔽",
              file=sys.stderr)

    return {"var": var_name, "lat": lat_name, "lon": lon_name}


# ----------------------------------------------------------------------
# 2. 选区 + 时间平均（自动处理纬度正序/倒序）
# ----------------------------------------------------------------------
def subset(da: xr.DataArray, lat_name: str, lon_name: str,
           month: int | None = None) -> xr.DataArray:
    lat_vals = da[lat_name].values
    lon_vals = da[lon_name].values

    if lat_vals[0] < lat_vals[-1]:          # 纬度递增
        lat_sl = slice(AREA[2], AREA[0])    # (35, 50)
    else:                                    # 纬度递减
        lat_sl = slice(AREA[0], AREA[2])    # (50, 35)
    lon_sl = slice(AREA[1], AREA[3])

    sub = da.sel({lat_name: lat_sl, lon_name: lon_sl})

    if "time" in sub.dims and month is not None:
        sub = sub.sel(time=sub["time"].dt.month == month)

    if "time" in sub.dims:
        sub = sub.mean("time")

    return sub


# ----------------------------------------------------------------------
# 3. 出图（与 main.py 同一套审美）
# ----------------------------------------------------------------------
def plot(da: xr.DataArray, lat_name: str, lon_name: str, title: str, out_png: Path,
         vmin=None, vmax=None) -> None:
    fig, ax = plt.subplots(figsize=(9, 6), subplot_kw={"projection": ccrs.PlateCarree()})

    # ⚠️ contourf 的坑：一旦 levels 给整数，matplotlib 会按数据自身的范围重新划分等值线，
    #    此时 vmin/vmax 会被忽略（色标仍然跟着数据走）。所以必须显式构造 levels 数组。
    if vmin is not None and vmax is not None:
        levels = np.linspace(vmin, vmax, 21)
    else:
        levels = 20

    cf = ax.contourf(da[lon_name], da[lat_name], da, levels=levels, cmap="viridis",
                     transform=ccrs.PlateCarree(), extend="both",
                     vmin=vmin, vmax=vmax)
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label(da.attrs.get("units", da.attrs.get("unit", "")), fontsize=10)

    try:
        ax.coastlines(linewidth=0.5, edgecolor="0.3")
        ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="k")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 海岸线/国界失败（不影响出图）：{exc}", file=sys.stderr)

    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False

    ax.set_extent([AREA[1], AREA[3], AREA[2], AREA[0]], crs=ccrs.PlateCarree())
    ax.set_title(title, fontsize=13)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None,
                    help="CMFD 的 .nc 文件路径（不填则自动用 data 里最新的 .nc）")
    ap.add_argument("--month", type=int, default=None, help="只取某个月（1—12）")
    ap.add_argument("--inspect", action="store_true", help="只打印结构，不出图")
    ap.add_argument("--vmin", type=float, default=None, help="色标下限（做多图对比时固定它）")
    ap.add_argument("--vmax", type=float, default=None, help="色标上限（做多图对比时固定它）")
    args = ap.parse_args()

    # 不传 --file 时自动找：避免在命令行里手敲中文路径（PowerShell 5.1 会乱码）
    if args.file:
        path = Path(args.file)
    else:
        # 只挑 CMFD 等国产数据，跳过 ERA5（era5_*.nc 归 6/7 号脚本）
        cands = sorted((p for p in DATA_DIR.glob("*.nc") if not p.name.startswith("era5_")),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            print(f"[error] {DATA_DIR} 里没有 .nc 文件", file=sys.stderr)
            print("       先把 CMFD/ERA5 的数据文件放进 data 文件夹", file=sys.stderr)
            return 2
        path = cands[0]
        print(f"自动选用 : {path.name}（如需指定，用 --file 参数）")

    if not path.exists():
        print(f"[error] file not found: {path}", file=sys.stderr)
        return 2

    # decode_times 自动解析 CF 时间；mask_and_scale 自动处理 _FillValue
    ds = xr.open_dataset(path, decode_times=True, mask_and_scale=True)
    try:
        info = inspect(ds)
        if args.inspect:
            return 0

        da = subset(ds[info["var"]], info["lat"], info["lon"], month=args.month)

        # 文件名里通常带 "197901-201812" 这样的时间区间，抽出来做标题，
        # 否则标题会变成一长串文件名，非常难看。
        period = ""
        m = re.search(r"(\d{6})-(\d{6})", path.stem)
        if m:
            period = f"{m.group(1)[:4]}—{m.group(2)[:4]}"
        else:
            period = path.stem

        tag = period.replace("—", "-")
        if args.month:
            tag += f"-{args.month:02d}月"
        FIG_DIR.mkdir(exist_ok=True)
        out_png = FIG_DIR / f"CMFD风速_{tag}.png"

        what = f"{args.month} 月平均" if args.month else "多年平均"
        title = f"新疆区域 近地面风速（CMFD，{period}，{what}）"
        plot(da, info["lat"], info["lon"], title, out_png, vmin=args.vmin, vmax=args.vmax)

        print("-" * 62)
        print(f"area mean: {float(da.mean()):.2f} m/s")
        print(f"saved    : {out_png}")
        return 0
    finally:
        ds.close()


if __name__ == "__main__":
    raise SystemExit(main())
