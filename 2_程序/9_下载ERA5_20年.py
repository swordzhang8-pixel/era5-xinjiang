"""批量下载 20 年 ERA5（新疆区域、6 小时、u10/v10/t2m）

为什么按“年”下而不是按“月”：
    按月 = 240 个请求，每个都要重新排队；按年 = 20 个请求，排队次数少一个量级。
    一年 12 个月 × 31 天 × 4 个时次 × 3 个变量 ≈ 4464 个场，在 CDS 单次请求上限内。

跑法（VS Code 集成终端，推荐）：
    conda run -n met python 2_程序/9_下载ERA5_20年.py --from-year 1999 --to-year 2018

只检查 key、不发请求：
    conda run -n met python 2_程序/9_下载ERA5_20年.py --check

输出：data/era5_YYYY.nc（每年约 70 MB，20 年约 1.4 GB）+ data/download.log
断点续跑：已存在的年份直接跳过；中断后重跑即可接着下。
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DATA_Y = DATA / "yearly"        # 单独放：避免和已有的 era5_202001.nc（月）混在 data/ 里
LOG = DATA / "download.log"

URL = "https://cds.climate.copernicus.eu/api"
DATASET = "reanalysis-era5-single-levels"
AREA = [50, 70, 35, 100]          # 北、西、南、东（顺序写反会下到南半球去）
VARIABLES = ["10m_u_component_of_wind", "10m_v_component_of_wind", "2m_temperature"]
HOURS = ["00:00", "06:00", "12:00", "18:00"]


def log(msg: str) -> None:
    """同时写屏幕和日志文件——后台跑的时候你只看得到文件。"""
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)          # flush 很关键：不 flush 的话重定向到文件会攒着不写
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_key() -> str | None:
    rc = Path.home() / ".cdsapirc"
    if not rc.exists():
        return None
    for line in rc.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("key:"):
            key = line.split(":", 1)[1].strip().strip('"').strip("'")
            return key or None
    return None


def build_request(year: int) -> dict:
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [str(year)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],   # 多的日子由 ERA5 自动忽略
        "time": HOURS,
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=1999)
    ap.add_argument("--to-year", type=int, default=2018)
    ap.add_argument("--check", action="store_true", help="只验 key 和请求，不下载")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    key = read_key()
    if key is None:
        print("没有可用的 CDS key：先跑 python 2_程序/0_设置CDS密钥.py")
        return 1

    years = list(range(args.from_year, args.to_year + 1))
    todo = [y for y in years if not (DATA_Y / f"era5_{y}.nc").exists()]
    print(f"共 {len(years)} 年：已有 {len(years) - len(todo)}，待下 {len(todo)}")
    print(f"目标目录: {DATA_Y}")
    print(f"单年请求: {VARIABLES} × 12 月 × 4 时次，区域 {AREA}（北西南东）")

    if args.check:
        print("\n--check 通过：key 就绪，请求构造正常（未发请求）。")
        return 0

    import cdsapi
    client = cdsapi.Client(url=URL, key=key)
    DATA.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    DATA_Y.mkdir(parents=True, exist_ok=True)
    ok = 0
    for i, year in enumerate(todo, start=1):
        target = DATA_Y / f"era5_{year}.nc"
        tmp = DATA_Y / f"era5_{year}.tmp.nc"      # 原子写：下完再改名，避免半个文件被当成已完成
        log(f"[{i}/{len(todo)}] 开始 {year}")
        for attempt in range(1, args.retries + 1):
            try:
                client.retrieve(DATASET, build_request(year), str(tmp))
                tmp.replace(target)
                size = target.stat().st_size / 1e6
                ok += 1
                log(f"[{i}/{len(todo)}] {year} 完成 {size:.1f} MB")
                break
            except Exception as exc:            # noqa: BLE001
                msg = str(exc)[:200]
                log(f"[{i}/{len(todo)}] {year} 第 {attempt} 次失败: {msg}")
                if "403" in msg or "forbidden" in msg.lower():
                    log("  → 多半是没同意数据集条款：打开数据集页拉到最底部点 Accept")
                if attempt < args.retries:
                    time.sleep(30 * attempt)    # 退避：30s、60s，别把 CDS 惹毛
        else:
            log(f"[{i}/{len(todo)}] {year} 三次都失败，跳过（重跑会再试）")

    mins = (time.perf_counter() - t0) / 60
    log(f"结束：本次成功 {ok}/{len(todo)} 年，用时 {mins:.1f} 分钟")
    return 0


if __name__ == "__main__":
    sys.exit(main())
