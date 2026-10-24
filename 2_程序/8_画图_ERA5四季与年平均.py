"""2020 年代表月（1/4/7/10）风速四联图 + 代表月平均图。

业务逻辑已经拆进 src/era5x/：多文件合并在 io.py，月平均在 compute.py，画图在 plot.py。

用法（在仓库根目录）：
    python 2_程序/8_画图_ERA5四季与年平均.py

输出：
    3_成果图/ERA5风速_2020_四季四联图.png
    3_成果图/ERA5风速_2020年平均.png

注意：
- 四张子图共用一套 levels，色标才可比；各自 vmin/vmax 会让"哪个月风大"变成假的。
- 数据只有 1/4/7/10 四个月，所谓"年平均"是这 4 个代表月的平均，不是真正的年均。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

from era5x import compute, io
from era5x import plot as eplot

DATA = BASE / "data"
FIG = BASE / "3_成果图"

MONTHS = (1, 4, 7, 10)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    files = sorted(DATA.glob("era5_*.nc"))
    if len(files) < len(MONTHS):
        print(f"[error] data 里只有 {len(files)} 个 era5_*.nc，"
              f"先跑 1_下载ERA5.py --all")
        return 2

    ds = io.load_era5_months(files)
    ws = compute.wind_speed(ds)
    monthly = compute.monthly_mean(ws).compute()

    fields = {f"2020 年 {m} 月": monthly.sel(month=m) for m in MONTHS}
    vmax = max(float(f.max()) for f in fields.values())
    levels = np.arange(0, np.ceil(vmax * 2) / 2 + 0.5, 0.5)

    print(f"数据: {len(files)} 个文件 → {ds.sizes['time']} 个时次")
    for m in MONTHS:
        f = fields[f"2020 年 {m} 月"]
        print(f"  {m:>2d} 月  全区 {float(f.mean()):.2f}  最大 {float(f.max()):.2f} m/s")
    print(f"  共用色标: 0 — {levels[-1]:.1f} m/s，{len(levels) - 1} 档")

    out4 = FIG / "ERA5风速_2020_四季四联图.png"
    eplot.plot_panels(fields, out4, suptitle="ERA5 10 米风速 · 2020 年代表月",
                      levels=levels)
    print(f"已保存: {out4}")

    annual = ws.mean("time").compute()
    out_year = FIG / "ERA5风速_2020年平均.png"
    eplot.plot_map(annual, out_year,
                   title="ERA5 10 米风速 · 2020 年代表月平均（1/4/7/10 月）",
                   levels=levels)
    print(f"已保存: {out_year}")
    print()
    print(f"代表月平均: 全区 {float(annual.mean()):.2f} m/s，"
          f"最大 {float(annual.max()):.2f} m/s")
    print("说明: 只有 4 个月，别把这张图当'全年平均'用；真年均要 12 个月。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
