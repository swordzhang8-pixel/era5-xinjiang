"""读写层：只负责「文件 → Dataset」和「Dataset → 文件」，不碰任何物理量计算。

这一层只做三件事：
1. 把 ERA5 的 `valid_time` 改名成 `time`；
2. 丢掉 `expver` 标记位（它不是维度，留着会影响 isel/sel）；
3. 纬度转升序（ERA5 原始是降序，画图会上下颠倒）。

其它模块（compute / plot）不应该直接调用 xarray 的 open_dataset。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import xarray as xr


def normalize(ds: xr.Dataset) -> xr.Dataset:
    """统一 ERA5 的坐标：时间维叫 time、去掉 expver、纬度升序。"""
    if "valid_time" in ds.coords:
        ds = ds.rename({"valid_time": "time"})
    if "expver" in ds.coords:
        ds = ds.drop_vars("expver")
    return ds.sortby("latitude")


def load_era5(path: str | Path) -> xr.Dataset:
    """读单个月份的 ERA5 netCDF。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    return normalize(xr.open_dataset(path))


def load_era5_months(paths: Iterable[str | Path], chunks: dict | None = None) -> xr.Dataset:
    """按月合并多个 ERA5 文件（依赖 dask）。"""
    files = sorted(Path(p) for p in paths)
    if not files:
        raise FileNotFoundError("没有可合并的 ERA5 文件")
    return xr.open_mfdataset(
        files,
        combine="by_coords",
        preprocess=normalize,
        chunks=chunks or {"time": 124},
    )


def save_zarr(ds: xr.Dataset, path: str | Path) -> Path:
    """把 Dataset 存成 zarr（比 netCDF 更快，适合反复读取的中间结果）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_zarr(path, mode="w")
    return path
