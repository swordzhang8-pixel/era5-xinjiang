# -*- coding: utf-8 -*-
"""5. 季节循环图：全区 vs 百里风区热点，12 个月平均风速。

数据准备部分已写好，**绘图部分留给你填**（见文件末尾 TODO）。

为什么要画这张图
----------------
只比较 1 月和 7 月，会得出"夏季风更大"的结论。
但把 12 个月全排开，会发现峰值在 4 月（春季）——结论完全不同。
这张图就是把"季节循环"完整呈现出来。

用法：
    conda activate met
    python 2_程序/5_月气候态.py

输出：
    3_成果图/CMFD风速_季节循环.png
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import xarray as xr

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "3_成果图"

# 两个研究对象
REGION = dict(lat=slice(35, 50), lon=slice(70, 100))   # 新疆全区
HOTSPOT = dict(lat=43.25, lon=91.55)                   # 百里风区热点（单个格点）


def monthly_series(da, time_dim="time") -> np.ndarray:
    """输入一个 DataArray，输出 12 个元素的数组（1—12 月的多年平均）。"""
    by_month = da.groupby(da[time_dim].dt.month).mean(time_dim)
    return np.asarray(by_month.values, dtype=float)


def main() -> None:
    nc = glob.glob(str(DATA_DIR / "*.nc"))[0]
    ds = xr.open_dataset(nc, decode_times=True)
    wind = ds["wind"]

    # ① 全区平均：先按区域裁，再对 lat/lon 求平均，最后按月份分组
    regional = monthly_series(wind.sel(**REGION).mean(["lat", "lon"]))

    # ② 热点单点：取最近的格点，再按月份分组
    hot = monthly_series(wind.sel(**HOTSPOT, method="nearest"))

    ds.close()

    print("月份   全区    热点")
    for m in range(12):
        print(f" {m+1:2d}   {regional[m]:5.2f}   {hot[m]:5.2f}")
    print(f"\n全区峰值：{np.argmax(regional)+1} 月 {regional.max():.2f}")
    print(f"热点峰值：{np.argmax(hot)+1} 月 {hot.max():.2f}")

    # ================================================================
    # TODO 1：准备 x 轴（1—12 月）
    #   提示：months = np.arange(1, 13)
    # ================================================================
    months = np.arange(1, 13)
    # ================================================================
    # TODO 2：创建画布
    #   要求：
    #     - figsize=(8, 5)
    #     - 两条线：regional 用蓝色实线 + 圆点，hot 用红色虚线 + 方块
    #     - 都要 label，最后 plt.legend()
    #     - x 轴刻度 1—12，xlabel "月份"，ylabel "风速 (m s-1)"
    #     - 标题 "新疆风速季节循环（CMFD 1979—2018）"
    #     - 加网格 plt.grid(alpha=0.3)
    #   提示：plt.plot(months, regional, "o-", color="tab:blue", label="新疆全区")
    # ================================================================
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(months, regional, "o-", color="tab:blue", linewidth=1.8,
            markersize=5, label="新疆全区")
    ax.plot(months, hot, "s--", color="tab:red", linewidth=1.8,
            markersize=5, label="百里风区热点（43.25°N, 91.55°E）")

    ax.set_xticks(months)
    ax.set_xlabel("月份", fontsize=11)
    ax.set_ylabel("风速 (m s-1)", fontsize=11)
    ax.set_title("新疆风速季节循环（CMFD 1979—2018）", fontsize=13, weight="bold")
    ax.grid(alpha=0.3, linestyle=":")

    # 标出两条线的峰值月份（竖虚线 + 文字）
    for x, y in [(int(np.argmax(regional)) + 1, regional.max()),
                 (int(np.argmax(hot)) + 1, hot.max())]:
        ax.axvline(x, color="gray", linestyle=":", linewidth=1, alpha=0.6, zorder=0)
        ax.annotate(f"{x}月 {y:.2f}", xy=(x, y), xytext=(10, -14),
                    textcoords="offset points", fontsize=9)

    # 图例放到坐标轴外（下方两列），这样永远不会挡住数据
    ax.legend(fontsize=10, loc="upper center",
              bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)

    ax.set_ylim(bottom=1.8)
    # ================================================================
    # TODO 3：保存
    #   要求：存到 FIG_DIR / "CMFD风速_季节循环.png"，dpi=200，bbox_inches="tight"
    #   提示：FIG_DIR.mkdir(exist_ok=True) 然后 plt.savefig(...)
    # ================================================================
    FIG_DIR.mkdir(exist_ok=True)
    out = FIG_DIR / "CMFD风速_季节循环.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("已保存：", out)

if __name__ == "__main__":
    main()
