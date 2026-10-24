"""era5x：ERA5 数据的小工具包。

分三层，各管一件事：
    io      —— 读文件（valid_time/expver/纬度降序都在这里处理掉）
    compute —— 算物理量（风速、月平均、区域平均）
    plot    —— 画图（每个函数返回 fig/ax）

典型用法：
    from era5x import io, compute, plot as eplot

    ds = io.load_era5("data/era5_202001.nc")
    ws = compute.wind_speed(ds)
    eplot.plot_map(ws.mean("time"), "3_成果图/x.png", title="2020 年 1 月")
"""

from __future__ import annotations

from . import compute, io, plot

__all__ = ["io", "compute", "plot"]
__version__ = "0.1.0"
