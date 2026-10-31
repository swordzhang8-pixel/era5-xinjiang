"""CLI 的单元测试：只验证参数解析，不读数据、不出图（1 秒内跑完）。"""

from __future__ import annotations

import pytest

from era5x.cli import build_parser


def test_no_subcommand_exits():
    """不给子命令时 argparse 应该报错退出（退出码 2），而不是静默什么都不做。"""
    with pytest.raises(SystemExit) as ei:
        build_parser().parse_args([])
    assert ei.value.code == 2


def test_index_defaults():
    """index 子命令：--q 默认 0.95，并且能分发到 cmd_index。"""
    args = build_parser().parse_args(["index", "--file", "x.nc"])
    assert args.q == pytest.approx(0.95)
    assert args.func.__name__ == "cmd_index"


def test_plot_month_optional():
    """plot 子命令：不给 --month 时是 None（全时段平均），给了就原样带下来。"""
    ap = build_parser()
    assert ap.parse_args(["plot", "--file", "x.nc"]).month is None
    assert ap.parse_args(["plot", "--file", "x.nc", "--month", "2015-07"]).month == "2015-07"


def test_series_requires_lat_lon():
    """series 必须给 --lat/--lon，缺一个就要报错。"""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["series", "--file", "x.nc", "--lat", "43.8"])
