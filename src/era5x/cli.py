"""era5x 命令行入口：python -m era5x <子命令>

为什么要有 CLI：
    现在 12 个脚本靠编号 0–11 记住顺序，参数散落在每个文件里；
    有了 CLI，别人（和三个月后的你）只要 `--help` 就知道怎么用，
    也不用记住"画月平均是 6 号脚本、时间序列是 7 号"。

四个子命令：
    info    看一个 nc 的结构（维度、变量、时间范围）
    plot    画平均风速场（可限定某个月）
    series  画某点的时间序列（叠加区域平均）
    index   算分位阈值与超阈次数（极端指数）
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import compute, io
from . import plot as eplot


def cmd_info(args: argparse.Namespace) -> int:
    """era5x info --file data/yearly/era5_2015.nc"""
    ds = io.load_era5(args.file)          # 统一坐标：valid_time→time、删 expver、纬度升序
    print(f"文件   : {args.file}")
    print(f"维度   : {dict(ds.sizes)}")
    print(f"变量   : {list(ds.data_vars)}")
    print(f"时间   : {str(ds.time.values[0])} → {str(ds.time.values[-1])}"
          f"（{ds.sizes['time']} 个时次）")
    print(f"纬度   : {float(ds.latitude[0]):.2f} → {float(ds.latitude[-1]):.2f}")
    print(f"经度   : {float(ds.longitude[0]):.2f} → {float(ds.longitude[-1]):.2f}")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    """era5x plot --file ... --month 2015-07"""
    ws = compute.wind_speed(io.load_era5(args.file))
    if args.month:
        ws = ws.sel(time=args.month)       # 支持 "2015-07" 这种部分字符串索引
        if ws.sizes.get("time", 0) == 0:
            print(f"没有匹配 {args.month} 的时次")
            return 2
    field = ws.mean("time")                # 时间平均 → 一张 2D 场
    out = Path(args.out)
    eplot.plot_map(field, out, title=args.title or f"ERA5 10m 风速 {args.month or '全时段平均'}",
                   levels=None)            # None → 用库里的默认 levels（0–8.5，跨图可比）
    print(f"已保存: {out}")
    return 0


def cmd_series(args: argparse.Namespace) -> int:
    """era5x series --file ... --lat 43.8 --lon 87.6"""
    ws = compute.wind_speed(io.load_era5(args.file))
    # method="nearest"：0.25° 网格上没有 43.8，必须吸附到最近格点
    point = ws.sel(latitude=args.lat, longitude=args.lon, method="nearest")
    domain = compute.regional_mean(ws)     # 区域平均作参照线
    out = Path(args.out)
    eplot.plot_timeseries(point, out, domain=domain,
                          title=args.title or f"ERA5 10m 风速 {args.lat}N {args.lon}E",
                          label=f"{float(point.latitude):.2f}N {float(point.longitude):.2f}E")
    print(f"格点: {float(point.latitude):.2f}N {float(point.longitude):.2f}E")
    print(f"均值 {float(point.mean()):.2f} m/s，最大 {float(point.max()):.2f} m/s")
    print(f"已保存: {out}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """era5x index --file ... --q 0.95"""
    ws = compute.wind_speed(io.load_era5(args.file))
    # 逐格点、沿时间取分位：dim="time" 不能省，省了就把空间差异压成一个数
    thr = ws.quantile(args.q, dim="time")
    count = (ws > thr).sum("time")
    print(f"{args.q:.0%} 分位阈值: {float(thr.min()):.2f} ~ {float(thr.max()):.2f} m/s")
    print(f"平均超阈次数: {float(count.mean()):.1f}（共 {ws.sizes['time']} 个时次，"
          f"理论值 {ws.sizes['time'] * (1 - args.q):.0f}）")
    if args.out:
        out = Path(args.out)
        eplot.plot_map(thr, out, title=f"{args.q:.0%} 分位风速阈值",
                       levels=None, cbar_label="阈值 (m s$^{-1}$)")
        print(f"已保存: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="era5x", description="ERA5 风场分析小工具")
    sub = ap.add_subparsers(dest="cmd", required=True)   # 不给子命令直接报错并打印用法

    p = sub.add_parser("info", help="看 nc 的结构")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("plot", help="画平均风速场")
    p.add_argument("--file", required=True)
    p.add_argument("--month", default=None, help="如 2015-07；省略=全时段平均")
    p.add_argument("--out", default="3_成果图/cli_plot.png")
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("series", help="画单点时间序列")
    p.add_argument("--file", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--out", default="3_成果图/cli_series.png")
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_series)

    p = sub.add_parser("index", help="算分位阈值与超阈次数")
    p.add_argument("--file", required=True)
    p.add_argument("--q", type=float, default=0.95)
    p.add_argument("--out", default=None, help="可选：把阈值场存成图")
    p.set_defaults(func=cmd_index)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)                 # 分发到具体子命令，每个都返回退出码


if __name__ == "__main__":
    raise SystemExit(main())
