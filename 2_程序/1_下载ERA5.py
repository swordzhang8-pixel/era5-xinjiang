"""下载 ERA5 单层数据（新疆区域 35-50N / 70-100E，6 小时，风+气温）。

用法（在仓库根目录）：
    python 2_程序/1_下载ERA5.py --check            # 只检查 key，不发请求
    python 2_程序/1_下载ERA5.py                    # 下载默认月份 2020-01
    python 2_程序/1_下载ERA5.py 2020-01 2020-04    # 指定月份
    python 2_程序/1_下载ERA5.py --all              # 下载 4 个代表月

首次使用前先设置 key：
    python 2_程序/0_设置CDS密钥.py

输出：data/era5_<年><月>.nc（可用环境变量 ERA5_DATA_DIR 覆盖目录）
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent      # 仓库根目录（era5-xinjiang/）

# 数据放 data/：netCDF4/HDF5 在 Windows 上读写非 ASCII 路径会失败，
# 所以整个仓库路径都必须保持英文。
# 可用环境变量 ERA5_DATA_DIR 覆盖。
DATA = Path(os.environ.get("ERA5_DATA_DIR", BASE / "data"))
RC = Path(os.path.expanduser("~/.cdsapirc"))

URL = "https://cds.climate.copernicus.eu/api"
DATASET = "reanalysis-era5-single-levels"

# 新疆区域：北, 西, 南, 东
AREA = [50, 70, 35, 100]

VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
]

HOURS = ["00:00", "06:00", "12:00", "18:00"]

DEFAULT_MONTHS = ["2020-01"]
ALL_MONTHS = ["2020-01", "2020-04", "2020-07", "2020-10"]


def read_key() -> str | None:
    """读 .cdsapirc，返回可用的 key；不可用返回 None。"""
    if not RC.exists():
        return None
    key = ""
    for line in RC.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("key:"):
            key = line.split(":", 1)[1].strip()
            break
    key = key.strip('"').strip("'").strip()
    if not key:
        return None
    return key


def explain_missing_key() -> None:
    print("还没有可用的 API key。")
    print()
    print("  1. 浏览器登录 https://cds.climate.copernicus.eu")
    print("  2. 打开 https://cds.climate.copernicus.eu/profile")
    print("  3. 找到「API key」，复制整串（形如 123456:abcdef...）")
    print("  4. 运行：python 2_程序/0_设置CDS密钥.py")
    print()
    print(f"（配置文件位置：{RC}）")


def build_request(year: str, month: str) -> dict:
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [year],
        "month": [month],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": HOURS,
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def describe(path: Path) -> None:
    """下载后用 xarray 打印结构，顺手验证文件可读。"""
    try:
        import xarray as xr
    except ImportError:
        print("  （没装 xarray，跳过结构检查）")
        return

    if path.read_bytes()[:2] == b"PK":
        print("  ⚠ 拿到的是 zip，不是 nc。用 unzip 解开后再打开。")
        return

    with xr.open_dataset(path) as ds:
        dims = " × ".join(f"{k}={v}" for k, v in ds.sizes.items())
        print(f"  维度: {dims}")
        print(f"  变量: {', '.join(ds.data_vars)}")
        if "time" in ds.coords:
            t = ds.time.values
            print(f"  时间: {t[0]} → {t[-1]}（UTC，{len(t)} 个时次）")


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 ERA5 单层数据")
    parser.add_argument("months", nargs="*", help="月份，如 2020-01；留空用默认")
    parser.add_argument("--all", action="store_true", help="下载 4 个代表月")
    parser.add_argument("--check", action="store_true", help="只检查 key，不下载")
    parser.add_argument("--force", action="store_true", help="已存在也重下")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    key = read_key()

    if args.check:
        if key is None:
            explain_missing_key()
            return 1
        print(f"key 已就位（{len(key)} 字符，{RC}）")
        print(f"目标区域: {AREA}（北西南东，即 35-50N / 70-100E）")
        print(f"变量: {', '.join(VARIABLES)}")
        print(f"输出目录: {DATA}")
        print("可以直接跑了：python 2_程序/1_下载ERA5.py")
        return 0

    if key is None:
        explain_missing_key()
        return 1

    months = ALL_MONTHS if args.all else (args.months or DEFAULT_MONTHS)

    DATA.mkdir(parents=True, exist_ok=True)

    import cdsapi

    client = cdsapi.Client(url=URL, key=key)
    print(f"准备下载 {len(months)} 个月：{', '.join(months)}")
    print("提交后会在 CDS 排队，进度条走完才落盘；别关窗口。")
    print()

    for ym in months:
        year, month = ym.split("-")
        target = DATA / f"era5_{year}{month}.nc"

        if target.exists() and not args.force:
            print(f"[跳过] {target.name} 已存在（{target.stat().st_size / 1e6:.1f} MB）")
            continue

        print(f"[下载] {ym} → {target.name}")
        try:
            client.retrieve(DATASET, build_request(year, month), str(target))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            print(f"  失败：{type(exc).__name__}: {msg[:300]}")
            if "403" in msg or "forbidden" in msg.lower():
                print("  多半是没同意数据集条款：打开数据集页拉到最底部点 Accept")
            elif "401" in msg:
                print("  key 不对：重跑 python 2_程序/0_设置CDS密钥.py")
            continue

        size_mb = target.stat().st_size / 1e6
        print(f"  完成：{target.name}（{size_mb:.1f} MB）")
        describe(target)
        print()

    print(f"完成。文件在 {DATA}；用 xarray 打开即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
