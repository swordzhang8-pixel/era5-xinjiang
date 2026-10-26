"""看一眼 compute 层算出来的到底是什么——只打印，不画图。

用法（VS Code 里打开本文件，点右上角 ▶ 运行；或在仓库根目录）：
    python 试验/看数据.py

只读不写：不会生成图片，也不会改 data/。
"""

import sys
from pathlib import Path

import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent      # 仓库根目录
sys.path.insert(0, str(BASE / "src"))              # 让 import era5x 可用

from era5x import compute, io                      # noqa: E402

# print 默认会省略中段（...），这三行让数值打印得完整、好读
np.set_printoptions(precision=2, suppress=True, linewidth=120, threshold=30)


def title(text: str) -> None:
    print("\n" + "=" * 64)
    print(text)
    print("=" * 64)


# ----------------------------------------------------------------------
# 1. 读进来长什么样
# ----------------------------------------------------------------------
ds = io.load_era5(BASE / "data" / "era5_202001.nc")
title("1. normalize 之后的结构：print(ds)")
print(ds)

# ----------------------------------------------------------------------
# 2. 风速场
# ----------------------------------------------------------------------
ws = compute.wind_speed(ds)
title("2. 风速 ws：print 只给骨架，数值要 .min()/.values")
print(ws)                                   # 维度、坐标、属性，没有数字
print("shape        :", ws.shape)            # (124, 61, 121)
print("dtype        :", ws.dtype)
print("min / max / 均:", f"{float(ws.min()):.2f} / {float(ws.max()):.2f} / {float(ws.mean()):.2f} m/s")

# ----------------------------------------------------------------------
# 3. 取一个点，看时间序列
# ----------------------------------------------------------------------
title("3. 单点时间序列：sel(..., method='nearest')")
point = ws.sel(latitude=43.8, longitude=87.6, method="nearest")
print("实际落到的格点:", float(point.latitude), "N,", float(point.longitude), "E")
print("前 8 个时次（m/s）:")
print(point.values[:8])
print("整段 均 / 最大:", f"{float(point.mean()):.2f} / {float(point.max()):.2f} m/s")

# ----------------------------------------------------------------------
# 4. 月平均（单个文件只有 month=1）
# ----------------------------------------------------------------------
monthly = compute.monthly_mean(ws).compute()      # 惰性对象一定要 .compute()
title("4. 月平均：compute.monthly_mean(ws)")
print(monthly)                                    # 只有 month=1，数值不打印
print("单月区域均值:", f"{float(monthly.mean()):.2f} m/s")

# ----------------------------------------------------------------------
# 5. 区域平均 → 逐时次曲线
# ----------------------------------------------------------------------
reg = compute.regional_mean(ws)
title("5. 区域平均：compute.regional_mean(ws)")
print(reg)                                        # 一维，time=124
print("前 8 个时次（m/s）:")
print(reg.values[:8])

# ----------------------------------------------------------------------
# 6. 原始数组：.values
# ----------------------------------------------------------------------
title("6. 原始数组：ws.isel(time=0).values  （61 行 × 121 列）")
print("整张会被 threshold 截断：")
print(ws.isel(time=0).values)
print("\n只切左上角 3×5 看真实数字：")
print(ws.isel(time=0).values[:3, :5])

# ----------------------------------------------------------------------
# 7. 转成表格（pandas DataFrame）
# ----------------------------------------------------------------------
title("7. 转表格：.to_dataframe().head()")
print(ds[["u10", "v10"]].isel(time=0).to_dataframe().head())

# ----------------------------------------------------------------------
# 8. 四个月一起看（对应 8 号脚本打印的那几行）
# ----------------------------------------------------------------------
files = sorted((BASE / "data").glob("era5_*.nc"))
if len(files) >= 4:
    ds4 = io.load_era5_months(files)
    ws4 = compute.wind_speed(ds4)
    monthly4 = compute.monthly_mean(ws4).compute()
    title("8. 四个月：每月全区均值 / 最大值")
    print(f"时次总数: {ds4.sizes['time']}")
    for m in (1, 4, 7, 10):
        f = monthly4.sel(month=m)
        print(f"  {m:>2d} 月   全区 {float(f.mean()):.2f}   最大 {float(f.max()):.2f} m/s")
    annual = ws4.mean("time").compute()
    print(f"  代表月平均: 全区 {float(annual.mean()):.2f}   最大 {float(annual.max()):.2f} m/s")
else:
    title("8. 跳过：data/ 里不足 4 个 era5_*.nc")

print("\n完成。")
