"""计算层：只放「Dataset / DataArray → DataArray / 数字」的纯函数。

约束：
- 不读文件（文件由 io 层读好传进来）；
- 不画图（画图由 plot 层负责）；
- 输入输出都是 xarray 对象，方便单测和复用。
"""

from __future__ import annotations

import numpy as np
import xarray as xr

DEFAULT_LON = (70.0, 100.0)
DEFAULT_LAT = (35.0, 50.0)


def wind_speed(ds: xr.Dataset) -> xr.DataArray:
    """10 米风速 = sqrt(u10² + v10²)。"""
    ws = np.sqrt(ds.u10**2 + ds.v10**2)
    ws.attrs = {"units": "m s-1", "long_name": "10 m wind speed"}
    return ws


def monthly_mean(ws: xr.DataArray) -> xr.DataArray:
    """按月份分组求平均，得到 month=1..12 的 DataArray。"""
    return ws.groupby("time.month").mean()


def regional_mean(
    da: xr.DataArray,
    lon: tuple[float, float] = DEFAULT_LON,
    lat: tuple[float, float] = DEFAULT_LAT,
) -> xr.DataArray:
    """先按经纬度裁出区域，再对空间求平均（时间维保留）。"""
    sub = da.sel(longitude=slice(*lon), latitude=slice(*lat))
    if sub.sizes.get("latitude", 0) == 0 or sub.sizes.get("longitude", 0) == 0:
        raise ValueError(f"区域内没有格点：lon={lon}, lat={lat}")
    return sub.mean(["latitude", "longitude"])
