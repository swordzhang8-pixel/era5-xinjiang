from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# 中文字体：不设的话标题里的中文会变成方块（DejaVu Sans 没有汉字）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).resolve().parent.parent
DATA= BASE/"data"/"era5_202001.nc"
OUT=BASE/"output"/"第二题.png"
def main() ->None:
    ds = xr.open_dataset(DATA)
    if "valid_time" in ds.coords:        # 坑一
        ds = ds.rename({"valid_time": "time"})
    if "expver" in ds.coords:            # 坑二
        ds = ds.drop_vars("expver")

    ws = np.sqrt(ds.u10**2 + ds.v10**2)  # 算风速
    ws.attrs["units"] = "m s-1"

    point = ws.sel(latitude=43.8, longitude=87.6, method="nearest")  # 取点
    print(f"实际格点: {float(point.latitude):.2f}N {float(point.longitude):.2f}E")

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(point.time, point.values, color="#c0392b", lw=1.4)
    ax.set_xlabel("时间（UTC）")
    ax.set_ylabel("10 米风速 (m s$^{-1}$)")
    ax.set_title("ERA5 10 米风速 · 2020-01 · 43.75N 87.50E")
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    fig.autofmt_xdate()
    OUT.parent.mkdir(parents=True, exist_ok=True)   # savefig 不会自动建目录
    fig.savefig(OUT, dpi=150, bbox_inches="tight")

    vals = point.values
    i = int(np.nanargmax(vals))
    print(f"均值 {vals.mean():.2f}，最小 {vals.min():.2f}，最大 {vals.max():.2f} m/s")
    print(f"峰值 {vals[i]:.2f} m/s @ {str(point.time.values[i])[:16]} UTC")
    print(f"已保存: {OUT}")

if __name__ == "__main__":
    main()