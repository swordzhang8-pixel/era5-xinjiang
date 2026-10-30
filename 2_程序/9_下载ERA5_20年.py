"""批量下载 20 年 ERA5（新疆区域、6 小时、u10/v10/t2m）

★ 2026-10-29 更新：按年请求在 CDS 上排了 45 分钟没动，改为**按月拆小**。
   小请求在 CDS 队列里跑得更快，而且失败一次只丢一个月，不用重来。

跑法（VS Code 集成终端）：
    # 默认：按月、三个变量、4 个时次 → 20 年 240 个文件，每个约 5.6 MB
    conda run -n met python 2_程序/9_下载ERA5_20年.py --from-year 1999 --to-year 2018

    # 只想更快：只要风、只要 00/12 两个时次（数据量降到 1/3）
    conda run -n met python 2_程序/9_下载ERA5_20年.py --vars u10,v10 --hours 00,12

    # 只检查 key / 请求构造，不发请求
    conda run -n met python 2_程序/9_下载ERA5_20年.py --check

    # 换 ADS 队列（同一份 ERA5，另一套排队；需要 ADS 的 key）
    conda run -n met python 2_程序/9_下载ERA5_20年.py --ads

输出：data/yearly/era5_YYYYMM.nc（或 era5_YYYY.nc）+ data/download.log
断点续跑：已存在的文件跳过；中断后重跑同一命令即可。
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_Y = BASE / "data" / "yearly"
LOG = BASE / "data" / "download.log"

CDS_URL = "https://cds.climate.copernicus.eu/api"
ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
DATASET = "reanalysis-era5-single-levels"
AREA = [50, 70, 35, 100]          # 北、西、南、东（顺序写反会下到南半球去）

VAR_MAP = {
    "u10": "10m_u_component_of_wind",
    "v10": "10m_v_component_of_wind",
    "t2m": "2m_temperature",
}


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)          # flush 关键：重定向到文件时不 flush 会攒着
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_key(rc: Path) -> str | None:
    """从 cdsapi 风格的 rc 文件里读 key。

    CDS 和 ADS 是两个独立服务，key 不通用，所以各用各的文件：
        ~/.cdsapirc      → url: https://cds.climate.copernicus.eu/api
        ~/.cdsapirc_ads  → url: https://ads.atmosphere.copernicus.eu/api
    """
    if not rc.exists():
        return None
    for line in rc.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("key:"):
            key = line.split(":", 1)[1].strip().strip('"').strip("'")
            if not key or "REPLACE" in key.upper():
                return None                      # 还是占位符，等于没填
            # 新版 CDS/ADS 的 key 是单个 UUID（36 字符、无冒号）；老版是 uid:token。
            # 所以只查长度，不强制要求冒号——否则新版 key 会被误判。
            if len(key) < 20:
                print(f"⚠ {rc} 里的 key 看起来不完整（长度 {len(key)}）")
                return None
            return key
    return None


def build_request(year: int, month: str | None, variables: list[str], hours: list[str]) -> dict:
    return {
        "product_type": ["reanalysis"],
        "variable": variables,
        "year": [str(year)],
        "month": [month] if month else [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],   # 多的日子由 ERA5 自动忽略
        "time": hours,
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def fname(year: int, month: str | None) -> str:
    return f"era5_{year}{month}.nc" if month else f"era5_{year}.nc"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=1999)
    ap.add_argument("--to-year", type=int, default=2018)
    ap.add_argument("--vars", default="u10,v10,t2m", help="u10,v10,t2m 任选，逗号分隔")
    ap.add_argument("--hours", default="00,06,12,18", help="只要部分时次就写 00,12")
    ap.add_argument("--yearly", action="store_true", help="按年请求（默认按月，更稳）")
    ap.add_argument("--ads", action="store_true", help="改用 ADS 队列（凭据读 ~/.cdsapirc_ads）")
    ap.add_argument("--rc", default=None, help="指定凭据文件，默认 ~/.cdsapirc 或 ~/.cdsapirc_ads")
    ap.add_argument("--check", action="store_true", help="只验 key 和请求，不下载")
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    variables = [VAR_MAP[v.strip()] for v in args.vars.split(",") if v.strip()]
    hours = [f"{h.strip()}:00" for h in args.hours.split(",") if h.strip()]
    url = ADS_URL if args.ads else CDS_URL

    # ---- 凭据：ADS 用独立文件，否则会把 ADS 的 key 发到 CDS 上（401）
    rc = Path(args.rc).expanduser() if args.rc else Path.home() / (".cdsapirc_ads" if args.ads else ".cdsapirc")
    key = read_key(rc)
    if key is None:
        print(f"没有可用的 key：{rc} 不存在或缺 key 行。")
        if args.ads:
            print("→ 去 https://ads.atmosphere.copernicus.eu/profile 复制 API key，")
            print(f"  新建 {rc}，内容两行：")
            print("    url: https://ads.atmosphere.copernicus.eu/api")
            print("    key: <你的 key>")
        else:
            print("→ 先跑 python 2_程序/0_设置CDS密钥.py")
        return 1

    # ---- 任务清单：按月 = (年, 月)；按年 = (年, None)
    if args.yearly:
        tasks = [(y, None) for y in range(args.from_year, args.to_year + 1)]
    else:
        tasks = [(y, f"{m:02d}") for y in range(args.from_year, args.to_year + 1) for m in range(1, 13)]

    todo = [(y, m) for (y, m) in tasks if not (DATA_Y / fname(y, m)).exists()]
    print(f"共 {len(tasks)} 个任务：已有 {len(tasks) - len(todo)}，待下 {len(todo)}")
    print(f"数据源: {url}")
    print(f"目标目录: {DATA_Y}")
    print(f"变量: {variables}")
    print(f"时次: {hours}")

    if args.check:
        print(f"\n示例请求: {build_request(*tasks[0], variables, hours)}")
        print("\n--check 通过（未发请求）。")
        return 0

    import cdsapi
    client = cdsapi.Client(url=url, key=key)
    DATA_Y.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    ok = 0
    for i, (y, m) in enumerate(todo, start=1):
        target = DATA_Y / fname(y, m)
        tmp = target.with_suffix(".tmp.nc")
        tag = f"{y}-{m}" if m else str(y)
        log(f"[{i}/{len(todo)}] 开始 {tag}")
        for attempt in range(1, args.retries + 1):
            try:
                client.retrieve(DATASET, build_request(y, m, variables, hours), str(tmp))
                tmp.replace(target)          # 原子写：写完整了再改名
                ok += 1
                log(f"[{i}/{len(todo)}] {tag} 完成 {target.stat().st_size / 1e6:.1f} MB")
                break
            except Exception as exc:         # noqa: BLE001
                msg = str(exc)[:200]
                log(f"[{i}/{len(todo)}] {tag} 第 {attempt} 次失败: {msg}")
                if "403" in msg or "forbidden" in msg.lower():
                    log("  → 多半是没同意数据集条款：数据集页拉到最底部点 Accept")
                if attempt < args.retries:
                    time.sleep(20 * attempt)
        else:
            log(f"[{i}/{len(todo)}] {tag} 跳过（重跑会再试）")

    mins = (time.perf_counter() - t0) / 60
    log(f"结束：成功 {ok}/{len(todo)}，用时 {mins:.1f} 分钟")
    return 0


if __name__ == "__main__":
    sys.exit(main())
