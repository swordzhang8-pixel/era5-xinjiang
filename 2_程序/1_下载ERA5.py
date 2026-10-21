# -*- coding: utf-8 -*-
"""
下载 ERA5 单层数据（W1 第二步：拿到真实数据）。

前置条件（只需做一次）：
    1. 已注册 https://cds.climate.copernicus.eu
    2. 已在该数据集页面点击 "Accept licence"
    3. C:\\Users\\<你的用户名>\\.cdsapirc 里填好了 url 和 key

用法：
    conda activate met
    python scripts/download_era5.py
    python scripts/download_era5.py --year 2020 --month 1
    python scripts/download_era5.py --dry-run     # 只看请求内容，不下载

输出：
    1_原始数据/era5_<year><month>.nc
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# 新疆区域：北 50、西 70、南 35、东 100（顺序必须是 N/W/S/E）
AREA = [50.0, 70.0, 35.0, 100.0]

VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "surface_pressure",
]

# 先只下 4 个时次（00/06/12/18），一次请求小、下得快；
# 跑通后想按时次全下，把下面改成 [f"{h:02d}:00" for h in range(24)]
TIMES = ["00:00", "06:00", "12:00", "18:00"]


def build_request(year: int, month: int) -> dict:
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": TIMES,
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def check_rcfile() -> bool:
    rc = Path.home() / ".cdsapirc"
    if not rc.exists():
        print(f"[错误] 找不到配置文件：{rc}", file=sys.stderr)
        print("       请在其中写入两行：", file=sys.stderr)
        print("       url: https://cds.climate.copernicus.eu/api", file=sys.stderr)
        print("       key: 你的个人访问令牌", file=sys.stderr)
        return False
    text = rc.read_text(encoding="utf-8", errors="ignore")
    if "在这里" in text or "PASTE" in text or "你的" in text:
        print(f"[错误] {rc} 里还是占位符，请把 key 换成你自己的令牌", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2020)
    ap.add_argument("--month", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true", help="只打印请求，不下载")
    args = ap.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"era5_{args.year}{args.month:02d}.nc"
    request = build_request(args.year, args.month)

    print(f"区域      : {AREA}  (N/W/S/E)")
    print(f"变量      : {len(VARIABLES)} 个")
    print(f"时次      : {TIMES}")
    print(f"输出      : {out}")

    if args.dry_run:
        print("\n[dry-run] 请求内容：")
        for k, v in request.items():
            print(f"  {k}: {v}")
        return 0

    if not check_rcfile():
        return 2

    import cdsapi  # 延迟导入，--dry-run 时不需要它

    try:
        client = cdsapi.Client()
        print("\n正在提交请求（首次可能排队几分钟，不要关窗口）...")
        client.retrieve("reanalysis-era5-single-levels", request, str(out))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        print(f"\n[失败] {msg}", file=sys.stderr)
        if "licence" in msg.lower() or "403" in msg:
            print("→ 去数据集页面点 'Accept licence'，然后重试", file=sys.stderr)
        elif "401" in msg or "authentication" in msg.lower():
            print("→ key 不对或过期，去 https://cds.climate.copernicus.eu/profile 重新复制", file=sys.stderr)
        return 1

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"\n完成：{out}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
