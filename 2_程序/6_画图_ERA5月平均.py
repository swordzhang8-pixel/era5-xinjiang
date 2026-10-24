"""2020-01 新疆 10 米风速月平均分布图。

业务逻辑已经拆进 src/era5x/：读数据在 io.py，算风速在 compute.py，画图在 plot.py。
本文件只负责「串起来 + 打印 + 存图」。

用法（在仓库根目录）：
    python 2_程序/6_画图_ERA5月平均.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

from era5x import compute, io
from era5x import plot as eplot

DATA = BASE / "data"
FIG = BASE / "3_成果图"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ds = io.load_era5(DATA / "era5_202001.nc")
    ws = compute.wind_speed(ds)
    field = ws.mean("time")

    print(f"数据: {ds.sizes['time']} 个时次，"
          f"{ds.sizes['latitude']}×{ds.sizes['longitude']} 格点")
    print(f"月均风速: {float(field.min()):.2f} — {float(field.max()):.2f} m/s")
    print(f"全区平均: {float(compute.regional_mean(field)):.2f} m/s")

    out = FIG / "ERA5风速_2020-01_月平均.png"
    eplot.plot_map(field, out, title="ERA5 10 米平均风速 · 2020 年 1 月")
    print(f"已保存: {out}")
    print()
    print("说明: 10 米高度、单月；风资源评估应换 100 米变量并跑多年。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
