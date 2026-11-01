"""绘图层：只负责「DataArray → 图片」。

每个函数都返回 (fig, ax)，在脚本里可以继续加标题、改范围；测试里也能拿到对象断言。
约定：不读文件、不算物理量，进来什么画什么。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from shapely.geometry import shape

EXTENT = [70, 100, 35, 50]                       # 新疆：70–100°E / 35–50°N
DEFAULT_LEVELS = np.arange(0, 8.5, 0.5)          # 固定的等值线，跨图可比
CBAR_LABEL = "10 米风速 (m s$^{-1}$)"
ADMIN_GEOJSON = Path(__file__).resolve().parents[2] / "data" / "admin" / "xinjiang_pref.json"

# 投影选择表：名字 → 构造函数（用 lambda 是为了延迟创建，图与图之间不共享状态）
# - plate   等经纬度：画得快，但高纬东西向被拉长，面积失真
# - lambert 兰勃特等角圆锥：中纬度区域最常用（天气图标准），新疆东西跨 30 个经度时形状最准
# - mercator 墨卡托：保角（航向不变），但高纬面积严重放大
PROJECTIONS = {
    "plate": ccrs.PlateCarree,
    "lambert": lambda: ccrs.LambertConformal(central_longitude=85.0, central_latitude=42.5),
    "mercator": ccrs.Mercator,
}


def setup_style() -> None:
    """中文字体（Windows 自带雅黑/黑体），负号正常显示。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


@lru_cache(maxsize=2)
def _load_admin_geoms(path: str):
    """读新疆地州边界 GeoJSON，返回几何列表（缓存，避免每张图重读 116 KB）。

    为什么不用 shapefile：cartopy 的 shapereader 只认 shp；GeoJSON 用 json + shapely 两行就够。
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [shape(f["geometry"]) for f in data["features"]]


# 地州简称表（按 adcode）。不缩写的话，图上会出现
# "克孜勒苏柯尔克孜自治州" 这种 10 个字压在半张图上。
ADMIN_SHORT = {
    "650100": "乌鲁木齐", "650200": "克拉玛依", "650400": "吐鲁番", "650500": "哈密",
    "652300": "昌吉", "652700": "博州", "652800": "巴州", "652900": "阿克苏",
    "653000": "克州", "653100": "喀什", "653200": "和田", "654000": "伊犁",
    "654200": "塔城", "654300": "阿勒泰",
}
# 兵团直管市（石河子、五家渠、北屯…）面积小、彼此挤在一起，图集里不标注
SKIP_LABEL = {"659001", "659002", "659003", "659004", "659005", "659006",
              "659007", "659008", "659009", "659010", "659011", "659012"}


@lru_cache(maxsize=2)
def _load_admin_labels(path: str):
    """地州名 + 标注点：取每个地州最大那块多边形的代表点，避免标到飞地上。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for feat in data["features"]:
        code = str(feat["properties"].get("adcode", ""))
        if code in SKIP_LABEL:
            continue
        name = ADMIN_SHORT.get(code) or (feat["properties"].get("name") or "")
        geom = shape(feat["geometry"])
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        big = max(polys, key=lambda p: p.area)       # 只用最大的一块
        pt = big.representative_point()
        out.append((name, pt.x, pt.y))
    return out


def _add_scale_bar(ax, length_km: int = 400, lat: float = 36.2, lon: float = 74.0) -> None:
    """左下角画比例尺。

    经度方向的 1° 对应的实际距离随纬度收缩：1° ≈ 111.32·cos(lat) km，
    所以同样 400 km，在 36°N 需要 400 / (111.32·cos36°) ≈ 4.4 个经度。
    位置刻意放在 36°N 附近——那里是塔里木盆地南缘，数据连续、没有国界穿过。
    """
    deg = length_km / (111.32 * np.cos(np.deg2rad(lat)))
    ax.plot([lon, lon + deg], [lat, lat], color="black", lw=3.5,
            transform=ccrs.PlateCarree(), zorder=8, solid_capstyle="butt")
    ax.text(lon + deg / 2, lat + 0.5, f"{length_km} km", ha="center", va="bottom",
            fontsize=8, transform=ccrs.PlateCarree(), zorder=8)


def _add_north_arrow(ax) -> None:
    """右上角画指北针（axes 坐标，不随投影变）。"""
    ax.annotate("N", xy=(0.94, 0.94), xytext=(0.94, 0.82),
                xycoords="axes fraction", textcoords="axes fraction",
                ha="center", va="center", fontsize=10, fontweight="bold", zorder=9,
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2))


def _add_map_features(ax, gridlines: bool = False, *, rivers: bool = False,
                      admin: str | Path | None = None, scalebar: bool = False,
                      north: bool = False) -> None:
    """统一加地图要素。默认只加海岸线与国界，其余按需打开。"""
    data_crs = ccrs.PlateCarree()
    ax.set_extent(EXTENT, crs=data_crs)          # 范围按经纬度给，投影自己换算
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="0.3")
    ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="black")

    if rivers:
        # Natural Earth 河流数据首次会联网下载；失败不该让整张图报废
        try:
            ax.add_feature(cfeature.RIVERS.with_scale("50m"), linewidth=0.45,
                           edgecolor="#2f6fb3", zorder=4)
        except Exception as exc:                 # noqa: BLE001
            print(f"⚠ 河流要素加载失败（跳过）：{type(exc).__name__}")

    if admin:
        path = str(admin) if admin is not True else str(ADMIN_GEOJSON)
        geoms = _load_admin_geoms(path)
        ax.add_geometries(geoms, crs=data_crs, facecolor="none",
                          edgecolor="0.15", linewidth=0.6, zorder=5)
        # 地州名：不标的话，读者只能看到一堆无意义的黑线
        for name, lon, lat in _load_admin_labels(path):
            if not name:
                continue
            ax.text(lon, lat, name, fontsize=6.5, ha="center", va="center",
                    transform=data_crs, zorder=7,
                    bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=0.8))

    if gridlines:
        gl = ax.gridlines(draw_labels=True, linestyle=":", linewidth=0.4, color="0.5")
        gl.top_labels = False
        gl.right_labels = False

    if scalebar:
        _add_scale_bar(ax)
    if north:
        _add_north_arrow(ax)


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
    projection: str = "plate",
    rivers: bool = False,
    admin: str | Path | None = None,
    scalebar: bool = False,
    north: bool = False,
):
    """单张填色图：风速场 + 国界 + 海岸线 + 色标。

    projection: "plate" | "lambert" | "mercator"，默认 plate（与旧行为一致）。
    rivers/admin/scalebar/north: 可选要素，默认全关，保证旧图不变样。
    """
    setup_style()
    if projection not in PROJECTIONS:
        raise ValueError(f"未知投影 {projection!r}，可选：{list(PROJECTIONS)}")
    data_crs = ccrs.PlateCarree()      # 数据本身的坐标参考系，永远是等经纬度
    proj = PROJECTIONS[projection]()   # 只决定"怎么摊到纸上"
    fig, ax = plt.subplots(figsize=(9, 6), subplot_kw={"projection": proj})
    lv = DEFAULT_LEVELS if levels is None else levels
    # transform=data_crs 不能省：省了数据会画到错误位置，而且不报错
    cf = ax.contourf(field.longitude, field.latitude, field.values, levels=lv,
                     cmap=cmap, transform=data_crs, extend="both")
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label(cbar_label)
    _add_map_features(ax, gridlines=gridlines, rivers=rivers, admin=admin,
                      scalebar=scalebar, north=north)
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
    cbar_label: str = CBAR_LABEL,
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
    cb.set_label(cbar_label)
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
