"""极端指数正式版：基准期定阈值、研究期数超阈

数据：data/yearly/era5_YYYY.nc（2009–2018，0.25°，6 小时，u10/v10）
谱系：基准期 2009–2014 出 p95 阈值；研究期 2015–2018 统计频次/强度/持续

为什么必须分开：
    阈值如果也用研究期算，超阈率会恒等于 5%，等于什么都没说——这叫循环论证。
    基准期定阈值、研究期统计，才有“这段时间比常年更极端吗”的含义。

跑法（VS Code 集成终端）：
    conda run -n met python 2_程序\11_极端指数_正式.py
    conda run -n met python 2_程序\11_极端指数_正式.py --q 0.99      # 换 99 分位
    conda run -n met python 2_程序\11_极端指数_正式.py --base 2009:2012 --study 2013:2018

输出：3_成果图/极端_*.png 五张
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import xarray as xr

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))          # 复用仓库的三层库，不重复造轮子
from era5x import compute, io                  # noqa: E402
from era5x import plot as eplot                # noqa: E402

FIG = BASE / "3_成果图"
DATA_Y = BASE / "data" / "yearly"


def load_years(y0: int, y1: int) -> xr.DataArray:
    """读入若干年的风速场，拼成一条时间轴。

    - 每年一个文件，读进来先算风速（勾股），再丢掉 u/v，省一半内存；
    - float32 一路到底：14608×61×121 约 431 MB，能放进 16 GB 机器。
    """
    parts = []
    for y in range(y0, y1 + 1):
        f = DATA_Y / f"era5_{y}.nc"
        if not f.exists():
            raise FileNotFoundError(f"缺文件 {f}")
        ds = io.load_era5(f)                       # 内部处理了 valid_time/expver/纬度顺序
        ws = compute.wind_speed(ds).astype("float32")
        parts.append(ws)
        print(f"  读入 {y}: {ws.sizes['time']} 个时次")
    return xr.concat(parts, dim="time").sortby("time")


def max_run_length(mask: np.ndarray) -> np.ndarray:
    """沿时间轴（axis=0）求每个格点“连续 True 的最长长度”。

    做法：首尾各补一圈 False，再找 0→1 和 1→0 的跳变位置，
    两者下标相减就是每段连续长度——全程向量化，不做 Python 循环。
    """
    pad = np.zeros((1,) + mask.shape[1:], dtype=bool)
    padded = np.concatenate([pad, mask, pad], axis=0)
    d = np.diff(padded.astype(np.int8), axis=0)
    starts = np.where(d == 1)          # (t, i, j)
    ends = np.where(d == -1)
    lengths = ends[0] - starts[0]      # 每段的长度
    out = np.zeros(mask.shape[1:], dtype=np.int16)
    # np.maximum.at：同一格点有多段时取最大（"at" 才是逐元素累加，别用 np.maximum）
    np.maximum.at(out, (starts[1], starts[2]), lengths)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="2009:2014", help="基准期，格式 起始年:结束年")
    ap.add_argument("--study", default="2015:2018", help="研究期，格式 起始年:结束年")
    ap.add_argument("--q", type=float, default=0.95, help="分位数阈值，默认 0.95")
    args = ap.parse_args()

    b0, b1 = (int(x) for x in args.base.split(":"))
    s0, s1 = (int(x) for x in args.study.split(":"))
    q = args.q
    tag = f"p{int(q * 100)}"

    print(f"基准期 {b0}–{b1}（定阈值），研究期 {s0}–{s1}（数超阈），分位 {q}")
    print("读基准期…")
    base = load_years(b0, b1).compute()
    print("读研究期…")
    study = load_years(s0, s1).compute()

    # ---- 阈值：逐格点、沿时间取分位。dim="time" 不能省，
    #      省了就变成“全部时空混在一起”的一个数，空间差异全丢。
    thr = base.quantile(q, dim="time").astype("float32")
    print(f"阈值范围: {float(thr.min()):.2f} ~ {float(thr.max()):.2f} m/s")

    # ---- 超阈：布尔场，三种指数都从它派生
    over = (study > thr)
    n_study = study.sizes["time"]

    # ① 频次：研究期内超过阈值的时次数（除以 4 近似折算成“天”）
    count = over.sum("time")
    days = (count / 4.0).rename("days")

    # ② 强度：只对超阈的时刻求“超出量”的平均（不超的不参与，否则被稀释）
    excess = (study - thr).where(over).mean("time").astype("float32")

    # ③ 持续：连续超阈的最长时次（×6 小时 = 小时数）
    dur = xr.DataArray(
        max_run_length(over.values),
        coords={"latitude": thr.latitude, "longitude": thr.longitude},
        dims=("latitude", "longitude"),
        name="max_run",
    )

    # ---- 出图：四张场 + 一张趋势
    eplot.setup_style()
    eplot.plot_map(thr, FIG / f"极端_阈值_{tag}.png",
                   title=f"逐格点 {tag} 风速阈值（基准期 {b0}–{b1}）",
                   levels=np.arange(3, 13, 0.5))
    eplot.plot_map(days, FIG / f"极端_超阈天数_{tag}.png",
                   title=f"研究期 {s0}–{s1} 超阈天数（共 {n_study} 个时次）",
                   levels=np.arange(0, 200, 10), cmap="OrRd",
                   cbar_label="超阈天数 (d)")
    eplot.plot_map(excess, FIG / f"极端_强度_{tag}.png",
                   title=f"平均超阈强度（{tag} 以上部分的均值）",
                   levels=np.arange(0, 4.1, 0.2), cmap="YlOrRd",
                   cbar_label="超出量 (m s$^{-1}$)")
    eplot.plot_map(dur, FIG / f"极端_持续_{tag}.png",
                   title="最长连续超阈时长",
                   levels=np.arange(0, 25, 1), cmap="magma",
                   cbar_label="连续时次 (×6 h)")

    # ---- 趋势：用同一套阈值回算每一年，看“超阈天数”随年份怎么变
    print("算逐年趋势…")
    yearly = load_years(b0, s1).compute()          # 基准+研究，共 10 年
    per_year = []
    for y in range(b0, s1 + 1):
        one = yearly.sel(time=str(y))
        per_year.append(float(((one > thr).sum("time") / 4.0).mean()))
    years = np.arange(b0, s1 + 1)

    from scipy import stats
    lr = stats.linregress(years, per_year)
    print(f"趋势: {lr.slope:+.2f} 天/年, p = {lr.pvalue:.3f}")

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(years, per_year, "o-", color="#c0392b")
    ax.plot(years, lr.intercept + lr.slope * years, "--", color="0.4",
            label=f"趋势 {lr.slope:+.2f} d/a (p={lr.pvalue:.3f})")
    ax.set_xlabel("年份"); ax.set_ylabel("区域平均超阈天数 (d)")
    ax.set_title(f"逐年超阈天数（阈值取自 {b0}–{b1} 的 {tag}）")
    ax.grid(alpha=0.3); ax.legend()
    fig.savefig(FIG / f"极端_趋势_{tag}.png", dpi=150, bbox_inches="tight")

    # ---- 汇总
    print("\n--- 汇总（研究期）---")
    print(f"超阈天数  区域均值 {float(days.mean()):.1f} d，最大 {float(days.max()):.1f} d")
    print(f"平均强度  区域均值 {float(excess.mean()):.2f} m/s，最大 {float(excess.max()):.2f}")
    print(f"最长持续  区域最长 {int(dur.max())} 个时次（{int(dur.max()) * 6} 小时）")
    print(f"理论超阈率 {q:.0%}；实际 {(float(over.mean()) * 100):.1f}%（阈值与样本不同期，本就不该等于 {q:.0%}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
