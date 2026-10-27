"""三个动词：resample / groupby / interp 到底差在哪

跑法（VS Code）：打开本文件 → Ctrl+S → Ctrl+Shift+B 运行当前文件。

这三个都是"改变数据形状/标签"的工具，但改的东西完全不同：
    resample  → 改时间标签的粒度（月 → 年），保留时间轴
    groupby   → 按某个"分类"重组，结果轴变成分类值（年份整数）
    interp    → 在已有网格上取"坐标之间"的值（最近邻 vs 双线性）

最后一段会撞到一个真实存在的坑：CMFD 只覆盖中国陆地，框里一半是 NaN。
"""
from pathlib import Path

import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent
CMFD = BASE / "data" / "wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
ERA5 = BASE / "data" / "era5_202001.nc"

# ---- 【chunks 照旧】不切块会把 537 MB 一次读进内存；切 12 个月一块，边算边读。
cm = xr.open_dataset(CMFD, chunks={"time": 12})

# ======================================================================
# 一、resample vs groupby：数值一样，标签完全不一样
# ======================================================================
# ---- 【先压成时间序列】40 年 × 400 × 700，直接按时间聚合太贵。
#      先沿空间求平均压成一维（480 个数），后面的对比才便宜。
# ---- 【.compute()】加了 chunks 之后 mean 是惰性的，这里要落到内存才能比较。
ts = cm.wind.mean(("lat", "lon")).compute()

# ---- resample("1YS")：按"每年 1 月 1 日"为起点重新分箱，再对每箱求平均。
#      结果轴仍叫 time，但标签是 datetime（1979-01-01、1980-01-01…）。
by_resample = ts.resample(time="1YS").mean()

# ---- groupby("time.year")：按"年份"这个分类值分组，结果轴直接变成 year（整数）。
#      .mean() 之后得到 year=1979, 1980, …，注意坐标不再是时间！
by_groupby = ts.groupby("time.year").mean()

print("resample 维度 :", by_resample.dims, by_resample.shape)
print("resample 前 2 个标签 :", by_resample.time.values[:2])
print("groupby  维度 :", by_groupby.dims, by_groupby.shape)
print("groupby  前 2 个标签 :", by_groupby.year.values[:2])
# ---- 【为什么数值完全相同】两组都只是把 12 个月平均成 1 个数，分组边界也一致，
#      所以数值一定相等（np.allclose 返回 True）。差别只在标签。
print("两者数值相同吗:", np.allclose(by_resample.values, by_groupby.values))
print("前 3 年 :", np.round(by_resample.values[:3], 3), np.round(by_groupby.values[:3], 3))

# ---- 【什么时候用哪个】
#      要接着画时间序列 / 和别的日数据做时间对齐 → resample（标签是时间，能对齐）
#      要按"年份"这个类别做统计（比如挑最热的 5 年）→ groupby（标签是整数，好索引）
#      注意：groupby 之后 time 轴没了，再想和 ERA5 对比时间，得手动转回去。

# ======================================================================
# 二、sel（最近邻） vs interp（插值）：取同一个点，值能差 0.3 以上
# ======================================================================
s0 = cm.wind.isel(time=0)      # 只取 1979-01 一个时刻，算得快

# ---- 【先看真实标签】CMFD 是 float32 存的，43.85 在内存里其实是 43.85000228881836，
#      所以 sel(lat=43.85) 会精确匹配失败。这是第二个"坐标标签"坑：
#      float32 的 0.1° 网格，你手写的十进制数经常对不上。
try:
    s0.sel(lat=43.85, lon=87.55)
except KeyError as e:
    print("\n[演示] sel(lat=43.85) 直接报错:", str(e)[:60], "...")

# ---- 最近邻：取离 (43.85, 87.55) 最近的那个格点，不做任何加权。
nearest = s0.sel(lat=43.85, lon=87.55, method="nearest")
# ---- 双线性：用周围 4 个格点按距离加权，算出"坐标之间"的值。
#      好处是连续、好看；坏处是平滑，峰值会被削。
bilinear = s0.interp(lat=43.8, lon=87.6)
print("最近邻  :", round(float(nearest), 4))
print("双线性  :", round(float(bilinear), 4))
print("差值    :", round(float(bilinear - nearest), 4), "m/s")
# ---- 【结论】同一位置两种取法差 0.3 m/s 以上（这里 17%）。
#      所以：做单点分析要统一口径并在图注里写明，别一会儿 nearest 一会儿 interp。

# ======================================================================
# 三、interp_like：把 CMFD 插到 ERA5 网格上（名字不对会静默失效）
# ======================================================================
era = xr.open_dataset(ERA5)
era0 = era.u10.isel(valid_time=0)        # ERA5 一个时次的 2D 场，用来当"目标网格"
print("\nERA5 维度:", era0.dims, era0.shape, "| CMFD 维度:", s0.dims)

# ---- 【坑】CMFD 叫 lat/lon，ERA5 叫 latitude/longitude。
#      interp_like 找不到同名维度时，什么也不做，直接把原数组还给你——不报错！
#      结果形状还是 (400, 700)，你以为插好了，其实没动。
wrong = s0.interp_like(era0)
print("名字不一致时 interp_like →", wrong.shape, "（没变，等于没插）")

# ---- 【正确做法】先把维度名统一，再插值。
s0_renamed = s0.rename({"lat": "latitude", "lon": "longitude"})
aligned = s0_renamed.interp_like(era0)
print("改名后 interp_like →", aligned.dims, aligned.shape)

# ---- 【为什么一大堆 NaN】两个来源：
#      ① 边界：ERA5 经度从 70.0 开始，CMFD 从 70.05 开始，70.0 那一列取不到 → NaN
#      ② 覆盖：CMFD 只有中国陆地，新疆框里 35–50N / 70–100E 有约一半是哈萨克斯坦、
#         吉尔吉斯斯坦等境外区域，源数据本身就是 NaN，插值后仍是 NaN。
finite = int(np.isfinite(aligned.values).sum())
print(f"插值后有值: {finite} / {aligned.size}  ({finite / aligned.size:.0%})")
box = s0_renamed.sel(latitude=slice(35, 50), longitude=slice(70, 100))
print("CMFD 原图框内有值比例:", f"{float((~box.isnull()).mean()):.1%}")

# ---- 【所以】做区域平均前必须先处理 NaN：
#      .mean() 默认 skipna=True 会跳过 NaN（数值能算），但样本数会随区域变，
#      跨区域比较就不公平。严谨做法是按中国边界做 mask，再统一统计。

# ======================================================================
# 四、一张对照表（记这四行就够）
# ======================================================================
print("\n" + "=" * 60)
print("resample : 改时间粒度, 轴还是 time（datetime 标签）")
print("groupby  : 按分类重组, 轴变成 year（整数标签）")
print("sel+nearest : 取最近格点, 不平滑, 但和真实坐标有偏差")
print("interp   : 取坐标之间的加权值, 平滑, 峰值会被削")
print("=" * 60)
