"""绘图层：只负责「DataArray → 图片」。

每个函数都返回 (fig, ax)，在脚本里可以继续加标题、改范围；测试里也能拿到对象断言。
约定：不读文件、不算物理量，进来什么画什么。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

EXTENT = [70, 100, 35, 50]                       # 新疆：70–100°E / 35–50°N
DEFAULT_LEVELS = np.arange(0, 8.5, 0.5)          # 固定的等值线，跨图可比
CBAR_LABEL = "10 米风速 (m s$^{-1}$)"


def setup_style() -> None:
    """中文字体（Windows 自带雅黑/黑体），负号正常显示。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _add_map_features(ax, gridlines: bool = False) -> None:
    proj = ccrs.PlateCarree()
    ax.set_extent(EXTENT, crs=proj)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="0.3")
    ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="black")
    if gridlines:
        gl = ax.gridlines(draw_labels=True, linestyle=":", linewidth=0.4, color="0.5")
        gl.top_labels = False
        gl.right_labels = False


def _save(fig, out, dpi: int) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    return out


def plot_map(
    field: xr.DataArray,
    out: str | Path,
    *,
    title: str = "",
    levels=None,
    cmap: str = "viridis",
    dpi: int = 300,
    gridlines: bool = True,
    cbar_label: str = CBAR_LABEL,
):
    """单张填色图：风速场 + 国界 + 海岸线 + 色标。"""
    setup_style()
    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(9, 6), subplot_kw={"projection": proj})
    lv = DEFAULT_LEVELS if levels is None else levels
    cf = ax.contourf(field.longitude, field.latitude, field.values, levels=lv,
                     cmap=cmap, transform=proj, extend="both")
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label(cbar_label)
    _add_map_features(ax, gridlines=gridlines)
    if title:
        ax.set_title(title, pad=12)
    _save(fig, out, dpi)
    return fig, ax


def plot_panels(
    fields: dict[str, xr.DataArray],
    out: str | Path,
    *,
    suptitle: str = "",
    levels=None,
    cmap: str = "viridis",
    dpi: int = 200,
    ncols: int = 2,
):
    """多子图：共用一套 levels 和一个色标，避免「各自 vmin/vmax」导致不可比。"""
    setup_style()
    proj = ccrs.PlateCarree()
    n = len(fields)
    nrows = int(np.ceil(n / ncols))
    lv = DEFAULT_LEVELS if levels is None else levels

    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4.7 * nrows),
                             subplot_kw={"projection": proj}, squeeze=False)
    flat = axes.ravel()
    cf = None
    for ax, (name, field) in zip(flat, fields.items()):
        cf = ax.contourf(field.longitude, field.latitude, field.values, levels=lv,
                         cmap=cmap, transform=proj, extend="both")
        _add_map_features(ax)
        ax.set_title(name, fontsize=12)
    for ax in flat[n:]:          # 子图数量不整除时，把空位藏掉
        ax.set_visible(False)

    cb = fig.colorbar(cf, ax=axes, orientation="horizontal", shrink=0.75,
                      pad=0.05, aspect=40)
    cb.set_label(CBAR_LABEL)
    if suptitle:
        fig.suptitle(suptitle, fontsize=15, y=0.97)
    _save(fig, out, dpi)
    return fig, axes


def plot_timeseries(
    series: xr.DataArray,
    out: str | Path,
    *,
    domain: xr.DataArray | None = None,
    title: str = "",
    label: str = "",
    ylabel: str = "风速 (m s$^{-1}$)",
    dpi: int = 150,
):
    """单点时间序列；可叠加一条区域平均线作参照。"""
    setup_style()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(series.time, series.values, color="#c0392b", lw=1.4, label=label)
    if domain is not None:
        ax.plot(domain.time, domain.values, color="#7f8c8d", lw=1.0, ls="--",
                alpha=0.8, label="区域平均")
    ax.set_xlabel("时间（UTC）")
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    fig.autofmt_xdate()
    _save(fig, out, dpi)
    return fig, ax
