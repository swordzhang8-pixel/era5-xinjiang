"""内存优化：chunk 尺寸、zarr 落盘、断点续跑

跑法：VS Code 打开 → Ctrl+S → Ctrl+Shift+B
"""
import time
import psutil                      # 读本进程内存占用（met 环境里已装）
import xarray as xr

SRC = r"data\wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"

def bench(chunks):
    """同一份计算，换不同 chunk，量「耗时 + 内存」。"""
    t0 = time.perf_counter()
    # chunks=None 表示不切块，整个数组一次性读进内存
    ds = xr.open_dataset(SRC, chunks=chunks)
    # 平均要把所有数据都碰一遍，所以它能反映真实的读盘成本
    out = ds.wind.mean(("lat", "lon")).compute()
    dt = time.perf_counter() - t0
    rss = psutil.Process().memory_info().rss / 1e6   # 常驻内存，单位 MB
    return dt, rss, out.sizes["time"]

for c in ({"time": 12}, {"time": 120}, None):
    dt, rss, n = bench(c)
    print(f"chunks={str(c):20s} 用时 {dt:5.1f}s  内存 {rss:6.0f} MB")


from pathlib import Path
import numpy as np

OUT = Path(r"data\processed\cmfd_annual.zarr")

# 先把 40 年算成一张年际场（年份 × 纬度 × 经度）
ds = xr.open_dataset(SRC, chunks={"time": 12})
annual = ds.wind.resample(time="1YS").mean().compute()
# to_zarr 是「写一次、以后直接读」：zarr 按块存储，下次读可以只读需要的块
annual.to_zarr(OUT, mode="w")

# 读回来必须校验，否则你不知道写坏了没有
back = xr.open_zarr(OUT)["wind"]
print("形状一致:", back.shape == annual.shape)
print("数值一致:", bool(np.allclose(back.values, annual.values, equal_nan=True)))