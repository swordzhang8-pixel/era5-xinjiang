"""投影对比：同一份风速场，三种投影画出来差在哪

跑法（VS Code）：Ctrl+F5，或
    conda run -n met python 2_程序\12_投影对比.py

产出：
    3_成果图/投影_三合一对比.png      三张并排（图集里用这张）
    3_成果图/投影_等经纬度.png        单张
    3_成果图/投影_兰勃特.png
    3_成果图/投影_墨卡托.png

为什么值得单独做一张对比图：
    新疆东西跨 30 个经度（70–100°E），不同投影下"形状"差别肉眼可见；
    图集里选错投影，读者会误判面积和相对位置。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # 无界面后端：导出图片不弹窗
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))      # 复用仓库里的三层库

from era5x import compute, io              # noqa: E402
from era5x import plot as eplot            # noqa: E402

FIG = BASE / "3_成果图"
DATA = BASE / "data" / "yearly" / "era5_2015.nc"

# 投影名 → 中文名 + 一句话说明（画到子图标题里）
INFO = {
    "plate": ("等经纬度", "高纬东西向被拉长"),
    "lambert": ("兰勃特等角圆锥", "中纬度形状最准"),
    "mercator": ("墨卡托", "保角，但高纬面积放大"),
}

def main() -> int:
    eplot.setup_style()

    # ---- 读一年的数据、算年平均风速场（和 `era5x plot` 同一条链路）
    ws = compute.wind_speed(io.load_era5(DATA))
    field = ws.mean("time")

    # ---- 单张：验证 plot_map 的新参数，每种投影各出一张
    for name, (cn, _) in INFO.items():
        eplot.plot_map(field, FIG / f"投影_{cn}.png",
                       title=f"2015 年平均风速 · {cn}", projection=name)

    # ---- 三合一：三张不同投影并排，共用一套 levels 才能比色
    levels = eplot.DEFAULT_LEVELS
    data_crs = ccrs.PlateCarree()          # 数据永远是等经纬度坐标
    fig = plt.figure(figsize=(16, 5.2))
    cf = None
    for i, (name, (cn, note)) in enumerate(INFO.items(), start=1):
        proj = eplot.PROJECTIONS[name]()   # 每种投影单独建坐标系
        ax = fig.add_subplot(1, 3, i, projection=proj)
        # transform 必须给数据坐标系，否则数据会画到错误位置，而且不报错
        cf = ax.contourf(field.longitude, field.latitude, field.values,
                         levels=levels, cmap="viridis",
                         transform=data_crs, extend="both")
        ax.set_extent(eplot.EXTENT, crs=data_crs)   # 范围也按经纬度给
        ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="black")
        ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor="0.3")
        gl = ax.gridlines(draw_labels=True, linestyle=":", linewidth=0.4, color="0.5")
        gl.top_labels = False
        gl.right_labels = False
        ax.set_title(f"{cn}\n{note}", fontsize=11)

    # 一个共享色标放底部：色标统一，读者看到的差异才是"投影"造成的
    cb = fig.colorbar(cf, ax=fig.axes, orientation="horizontal", shrink=0.6, pad=0.06)
    cb.set_label(eplot.CBAR_LABEL)
    fig.suptitle("同一份 2015 年平均风速 · 三种投影对比", fontsize=14, y=0.98)

    out = FIG / "投影_三合一对比.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"已保存: {out.name}")
    print("单张:", "、".join(f"投影_{cn}.png" for cn, _ in INFO.values()))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
