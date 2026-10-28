"""断点续跑：逐年算 CMFD 的年平均场，每年一个文件，中断后可接着跑

跑法（VS Code）：打开本文件 → Ctrl+S → Ctrl+Shift+B 运行当前文件
验证：跑到一半按 Ctrl+C，再跑一遍，前面完成的年份应该全部「跳过」

输出：data/processed/years/1979.nc … 2018.nc（每个约 1.1 MB，共 40 个）
注意：data/ 在 .gitignore 里，这些文件不会进仓库，也不该进。
"""
import time
from pathlib import Path

import xarray as xr

SRC = Path(r"data/wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc")
OUT_DIR = Path(r"data/processed/years")

# ---- 【为什么先建目录】to_netcdf 不会自动创建父目录，目录不存在直接 FileNotFoundError。
#      parents=True 建多级，exist_ok=True 让重复运行不报错。
OUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = range(1979, 2019)


def process_year(year: int, done: int, total: int) -> None:
    """算一年的平均场并落盘。单独成函数，方便以后换成并行或换算法。"""
    f = OUT_DIR / f"{year}.nc"
    ds = xr.open_dataset(SRC, chunks={"time": 12})   # 每次重开：避免长期持有句柄
    # sel(time="2010") 只读那一年所在的块；.mean("time") 把 12 个月压成一张 400×700 的场
    field = ds.wind.sel(time=str(year)).mean("time").compute()

    # ---- 【原子写】先写 .tmp，写完整了再改名。改名在同盘内是原子操作。
    #      如果直接写 f，程序在中途被杀会留下一个"半个文件"，
    #      下次运行 f.exists() 为真 → 被误判成"已完成"，数据永远缺一半。
    tmp = f.with_suffix(".tmp.nc")
    field.to_netcdf(tmp)
    tmp.replace(f)
    print(f"[{done:>2d}/{total}] {year} 完成  {f.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    t0 = time.perf_counter()
    todo = [y for y in YEARS if not (OUT_DIR / f"{y}.nc").exists()]
    skipped = len(list(YEARS)) - len(todo)
    print(f"共 {len(list(YEARS))} 年：已完成 {skipped}，待处理 {len(todo)}")
    if not todo:
        print("全部完成，无需重跑。")
        return

    for i, year in enumerate(todo, start=1):
        process_year(year, i, len(todo))

    # ---- 【收尾自检】续跑最容易出的错是"文件数对、内容不全"，所以数一遍并读一个验证。
    files = sorted(OUT_DIR.glob("*.nc"))
    print(f"\n完成：{len(files)} 个文件，用时 {time.perf_counter() - t0:.1f}s")
    sample = xr.open_dataset(files[0])["wind"]
    print(f"抽检 {files[0].name}: 形状 {sample.shape}, 均值 {float(sample.mean()):.2f} m/s")


if __name__ == "__main__":
    main()
