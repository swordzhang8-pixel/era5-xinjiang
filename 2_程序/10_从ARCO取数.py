"""从 Google Cloud 的 ARCO-ERA5 直接取数（绕过 CDS 排队）

背景：CDS 从 2026-10 起对批量请求限流，一个月要排十几分钟甚至不动；
      同一份 ERA5 在 Google 公开桶里有 zarr 版本，匿名可读、无需排队。

数据源：
    https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3
    —— 0.25°、逐小时、1900–2050，含 10m u/v 风分量

代价：它按“每个时次一个全球块”存，只要新疆也得整块下
      → 每个时次约 4 MB，10 年 × 4 时次 × 2 变量 ≈ 120 GB 流量、约 4 小时

跑法（VS Code 集成终端）：
    # 先试一年，看速度再决定全量
    conda run -n met python 10_从ARCO取数.py --from-year 2009 --to-year 2009

    # 全量 10 年
    conda run -n met python 10_从ARCO取数.py --from-year 2009 --to-year 2018

只取两个时次（流量减半）：
    conda run -n met python 10_从ARCO取数.py --hours 00,12

输出：data/yearly/era5_YYYY.nc（变量名 u10/v10，维度 time/latitude/longitude，
      和现有 io.load_era5* 完全兼容）
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent
DATA_Y = BASE / "data" / "yearly"
LOG = BASE / "data" / "download.log"

URL = "https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
VAR_MAP = {"u10": "10m_u_component_of_wind", "v10": "10m_v_component_of_wind"}
AREA = {"latitude": slice(50, 35), "longitude": slice(70, 100)}   # 新疆：50–35N / 70–100E


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_year(ds: xr.Dataset, year: int, hours: list[int], names: list[str]) -> xr.Dataset:
    """把某一年、指定时次、新疆范围的数据真正读进内存（按月读，方便看进度）。"""
    parts = []
    for month in range(1, 13):
        # 先用坐标筛出该月、该时次的下标，再 isel —— 这样 zarr 只会去取这些时次的块
        mask = (
            (ds.time.dt.year == year)
            & (ds.time.dt.month == month)
            & ds.time.dt.hour.isin(hours)
        )
        idx = np.where(mask.values)[0]
        if idx.size == 0:
            continue
        chunk = ds[names].isel(time=idx).sel(AREA).load()   # .load() 才真的下载
        parts.append(chunk)
        print(f"    {year}-{month:02d}: {chunk.sizes['time']} 个时次", flush=True)

    if not parts:
        raise ValueError(f"{year} 年没有匹配到时次")
    return xr.concat(parts, dim="time").sortby("time")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=2009)
    ap.add_argument("--to-year", type=int, default=2018)
    ap.add_argument("--vars", default="u10,v10")
    ap.add_argument("--hours", default="00,06,12,18")
    ap.add_argument("--overwrite", action="store_true", help="已存在也重下")
    args = ap.parse_args()

    hours = [int(h) for h in args.hours.split(",")]
    names = [VAR_MAP[v] for v in args.vars.split(",")]
    short = [v for v in args.vars.split(",")]
    DATA_Y.mkdir(parents=True, exist_ok=True)

    years = list(range(args.from_year, args.to_year + 1))
    todo = [y for y in years if args.overwrite or not (DATA_Y / f"era5_{y}.nc").exists()]
    print(f"共 {len(years)} 年：已有 {len(years) - len(todo)}，待取 {len(todo)}")
    print(f"时次: {hours} | 变量: {short} | 区域: 35–50N / 70–100E")
    if not todo:
        print("全部已存在，无需重取。")
        return 0

    log(f"打开 ARCO zarr（首次约 40 秒）…")
    t_open = time.perf_counter()
    ds = xr.open_zarr(URL, consolidated=True)
    log(f"打开完成，用时 {time.perf_counter() - t_open:.0f}s")

    t_all = time.perf_counter()
    for i, year in enumerate(todo, start=1):
        target = DATA_Y / f"era5_{year}.nc"
        tmp = target.with_suffix(".tmp.nc")
        log(f"[{i}/{len(todo)}] 开始 {year}")
        t0 = time.perf_counter()
        try:
            one = load_year(ds, year, hours, names)
            # 变量改名成和现有数据一致（u10/v10），下游 io.load_era5* 直接能用
            one = one.rename({VAR_MAP[v]: v for v in short})
            one = one.astype("float32")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            one.to_netcdf(tmp, encoding={v: {"zlib": True, "complevel": 4} for v in short})
            tmp.replace(target)                    # 原子写：写完才改名
            dt = time.perf_counter() - t0
            size = target.stat().st_size / 1e6
            eta = dt * (len(todo) - i) / 60
            log(f"[{i}/{len(todo)}] {year} 完成 {size:.0f} MB，用时 {dt/60:.1f} 分钟，"
                f"剩余约 {eta:.0f} 分钟")
        except Exception as exc:                   # noqa: BLE001
            log(f"[{i}/{len(todo)}] {year} 失败: {type(exc).__name__}: {str(exc)[:160]}")

    log(f"结束：总用时 {(time.perf_counter() - t_all)/60:.1f} 分钟")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
