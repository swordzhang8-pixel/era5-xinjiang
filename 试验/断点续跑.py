"""断点续跑：逐年算 CMFD 的年平均场，每年一个文件，中断后可接着跑

跑法（VS Code）：打开本文件 → Ctrl+S → Ctrl+Shift+B 运行当前文件

三种跑法：
    python 试验/断点续跑.py                    # 正常跑 1979–2018
    python 试验/断点续跑.py --delay 0.3        # 每年慢 0.3 秒，方便按 Ctrl+C 观察中断
    python 试验/断点续跑.py --from-year 2000   # 只跑 2000 年以后

输出：data/processed/years/1979.nc … 2018.nc（每个约 1.1 MB）
注意：data/ 在 .gitignore 里，这些文件不会进仓库，也不该进。
"""
import argparse
import time
from pathlib import Path

import xarray as xr

SRC = Path(r"data/wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc")
OUT_DIR = Path(r"data/processed/years")

# ---- 【为什么先建目录】to_netcdf 不会自动创建父目录，目录不存在直接 FileNotFoundError。
OUT_DIR.mkdir(parents=True, exist_ok=True)


def process_year(year: int, done: int, total: int, delay: float) -> None:
    """算一年的平均场并落盘。"""
    f = OUT_DIR / f"{year}.nc"
    ds = xr.open_dataset(SRC, chunks={"time": 12})
    # sel(time="2010") 只读那一年所在的块；mean("time") 把 12 个月压成一张 400×700 的场
    field = ds.wind.sel(time=str(year)).mean("time").compute()

    # ---- 【原子写】先写 .tmp，写完整了再改名（同盘改名是原子操作）。
    #      直接写 f 的话，中途被杀会留下半个文件，下次 exists() 为真 →
    #      被误判成"已完成"，数据永远缺一半，而且不报错。
    tmp = f.with_suffix(".tmp.nc")
    field.to_netcdf(tmp)
    tmp.replace(f)
    print(f"[{done:>2d}/{total}] {year} 完成  {f.stat().st_size / 1e6:.1f} MB")
    if delay:
        time.sleep(delay)      # 只为了演示中断用，正常跑不要加


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=1979)
    ap.add_argument("--to-year", type=int, default=2018)
    # ---- 默认给 0.5 秒：40 年 ≈ 20 秒，足够按 Ctrl+C 观察中断。
    #      要是嫌慢，跑一次 `--delay 0` 就是全速（约 2 秒跑完 40 年）。
    ap.add_argument("--delay", type=float, default=0.5, help="每年额外等待秒数；0 表示全速")
    args = ap.parse_args()

    years = list(range(args.from_year, args.to_year + 1))
    todo = [y for y in years if not (OUT_DIR / f"{y}.nc").exists()]
    print(f"共 {len(years)} 年：已完成 {len(years) - len(todo)}，待处理 {len(todo)}")
    if not todo:
        print("全部完成，无需重跑。")
        return 0

    t0 = time.perf_counter()
    done_this_run = 0
    # ---- 【为什么要 try/except KeyboardInterrupt】
    #      Ctrl+C 会抛 KeyboardInterrupt，默认会把整个栈打出来、输出很难看。
    #      捕获它只是为了让"已跑到哪年、重跑会从哪继续"这句话能打出来。
    #      注意：续跑能力本身不依赖它——靠的是"每年一个文件 + 开工前检查"。
    try:
        for i, year in enumerate(todo, start=1):
            process_year(year, i, len(todo), args.delay)
            done_this_run += 1
    except KeyboardInterrupt:
        print(f"\n[中断] 本次跑了 {done_this_run} 年，已安全落盘。")
        print(f"       重跑会从剩下 {len(todo) - done_this_run} 年开始，不会重算已完成的。")
        return 130          # 130 = 被 SIGINT 结束的约定退出码

    files = sorted(OUT_DIR.glob("*.nc"))
    print(f"\n完成：{len(files)} 个文件，本次 {done_this_run} 个，用时 {time.perf_counter() - t0:.1f}s")
    sample = xr.open_dataset(files[0])["wind"]
    print(f"抽检 {files[0].name}: 形状 {sample.shape}, 均值 {float(sample.mean()):.2f} m/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
