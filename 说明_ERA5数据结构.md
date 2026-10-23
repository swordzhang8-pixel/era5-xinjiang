# ERA5 结构笔记

数据：`data/era5_202001.nc`（5.9 MB，2020-01，新疆 35–50°N / 70–100°E）
下载：`python 2_程序/1_下载ERA5.py`

## 1. 四个维度

| 维度 | 长度 | 含义 |
|---|---|---|
| `valid_time` | 124 | 31 天 × 4 个时次（00/06/12/18 UTC） |
| `latitude` | 61 | 50.0 → 35.0，**降序**，步长 0.25° |
| `longitude` | 121 | 70.0 → 100.0，升序，步长 0.25° |
| （标量） | — | `expver`、`number` 是坐标，不是维度 |

内存占用约 11 MB（3 个变量各 4 MB）。

## 2. 三个变量

| 变量 | 单位 | 说明 |
|---|---|---|
| `u10` | m s-1 | 10 米东西向风分量 |
| `v10` | m s-1 | 10 米南北向风分量 |
| `t2m` | K | 2 米气温，**不是 ℃**，减 273.15 才是 |

风速：`ws = sqrt(u10**2 + v10**2)`。

## 3. 两个必须处理的坑

**① 时间维叫 `valid_time`，不叫 `time`。**
新版 CDS 导出的 netCDF 用 `valid_time`，照旧教程写 `ds.time` 会 `AttributeError`。

**② `expver` 是坐标，值为 `"0001"` / `"0005"`。**
数据缺失时同一时次会出现两条记录，绘图前要合并或挑一条。

一次处理干净：

```python
ds = xr.open_dataset(r"data/era5_202001.nc")
ds = ds.rename({"valid_time": "time"})
if "expver" in ds.coords:
    ds = ds.drop_vars("expver")   # 只是标记位，不是维度，isel 会报错
```

## 4. 路径限制

netCDF4/HDF5 在 Windows 上读写**非 ASCII 路径**会失败：

- 读 → `FileNotFoundError`
- 写 → `PermissionError`

所以 **整个仓库路径必须是纯英文**。现在仓库在 `D:\work\era5-xinjiang`，已经是英文，
数据就直接放 `data/`，脚本用 `BASE / "data"` 定位，不再写死 `D:\era5data`。
（需要临时换目录时用环境变量 `ERA5_DATA_DIR`。）

PNG、CSV、Markdown 不受影响，留在仓库里即可。

## 5. 其它已核对事实

- `latitude` 降序：直接 `plot()` 会让图上下颠倒，需要 `sortby("latitude")` 或 `ax.invert_yaxis()`
- 时间是 UTC，北京时间 = UTC + 8
- 属性里有 `GRIB_centre: ecmf`、`Conventions: CF-1.7`，来自 `cfgrib-0.9.1` 转码
