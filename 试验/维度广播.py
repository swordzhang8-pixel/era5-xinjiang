"""W2D1 练习：坐标 / 维度 / 广播 / 对齐

运行：Ctrl+F5，或右上角 ▶，输出在下面「终端」面板

读 data/era5_202001.nc
  ↓
改维名 valid_time→time、删 expver        ← 把数据"摆正"
  ↓
第 1 段：按名字取点，看 sel / isel 的区别
第 2 段：加减维度，看聚合后形状怎么变
第 3 段：算距平，看 3 维怎么减 2 维
第 4 段：两个错开的时间切片相加，看结果剩几个时刻
"""

from pathlib import Path
import xarray as xr

BASE = Path(__file__).resolve().parent.parent
ds = xr.open_dataset(BASE / "data" / "era5_202001.nc")

# 0. 先统一坐标（后面都要用）
ds = ds.rename({"valid_time": "time"})
if "expver" in ds.coords:
    ds = ds.drop_vars("expver")

print("dims  :", dict(ds.sizes))
print("coords:", list(ds.coords))

# 1. 坐标：sel 按标签 / isel 按位置
print("\n--- 1. 坐标 ---")
print("isel(0)      :", float(ds.isel(latitude=0).latitude))
print("sel(35.0)    :", float(ds.sel(latitude=35.0).latitude))
print("nearest 43.8 :", float(ds.sel(latitude=43.8, method="nearest").latitude))

# 猜一猜下面这行会怎样？看完输出再取消注释跑一次
# print(ds.sel(latitude=43.8))

# 2. 维度：聚合怎么消维
print("\n--- 2. 维度 ---")
print("原始        :", ds.u10.shape)
print("mean(time)  :", ds.u10.mean("time").shape)
print("mean(2维)   :", ds.u10.mean(("latitude", "longitude")).shape)
print("expand_dims :", ds.u10.isel(time=0).expand_dims("month").shape)

# 3. 广播：距平
print("\n--- 3. 广播 ---")
anom = ds.u10 - ds.u10.mean("time")
print("anom shape  :", anom.shape)
print("anom 时间平均最大（应≈0）:", float(anom.mean("time").max()))

# 4. 对齐：错开 6 小时的两个切片
print("\n--- 4. 对齐 ---")
a = ds.u10.isel(time=slice(0, 2))
b = ds.u10.isel(time=slice(1, 3))
print("a+b time 长度（默认 inner）:", (a + b).sizes["time"])
print("outer 的 time 长度:", xr.align(a, b, join="outer")[0].sizes["time"])