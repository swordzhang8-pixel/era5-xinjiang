# xarray 处理 ERA5 的七个坑

用 CDS 下的 ERA5 做新疆风速，一周踩了七个坑。每个都不是"报错—搜一下—解决"那么简单，而是**图能出来、数字不对**的那种。记下来，省下一个人的一周。

数据背景：ERA5 单层，10 米风场 + 2 米气温，新疆 35–50°N / 70–100°E，0.25° 网格（61×121），6 小时一个时次，2020 年 1、4、7、10 四个月，共 492 个时次。

---

## 坑 1：中文路径，HDF5 直接不认

`data/新疆风速/era5.nc` 这种路径，`xr.open_dataset()` 报 `FileNotFoundError`，写文件报 `PermissionError`。

原因不在 xarray，在底层的 HDF5/C 库：它按系统 ANSI 编码处理路径，非 ASCII 直接失败。

**解法**：整个仓库路径保持纯英文（`D:\work\era5-xinjiang`），中文只放在子目录名和文件名之外的地方。这也是我后来把 `data/` 单独留成英文的原因——**脚本名可以中文，数据路径不行**。

## 坑 2：新版 ERA5 的时间维叫 `valid_time`，不叫 `time`

照老教程写 `ds.groupby("time.month").mean()`，直接 `KeyError: 'time'`。

新版 CDS 导出的 netCDF 把时间维命名成 `valid_time`（维度名和坐标名都是它）。

**解法**：读进来第一件事就统一口径，后面所有代码只认 `time`。

```python
ds = ds.rename({"valid_time": "time"})
```

## 坑 3：`expver` 看着是个坐标，其实是颗雷

`expver` 是 ECMWF 的版本标记（`0001` = ERA5，`0005` = ERA5T 近实时）。

单月下载时它是**标量坐标**，只有 `'0001'`，看起来人畜无害。但一旦请求跨了 ERA5 / ERA5T 的边界，它**会变成真正的维度（size=2）**，于是 `u10` 莫名多一维，`contourf` 报 3D 错误。

**解法**：一律删掉，别赌它是不是标量。

```python
if "expver" in ds.coords:
    ds = ds.drop_vars("expver")
```

## 坑 4：纬度是降序的，图和切片都会错

ERA5 原始 `latitude` 从 50 排到 35。`contourf(lon, lat, field)` 把数组第一行当图的下边，画出来整张图**上下颠倒**。

更隐蔽的是第二个症状：对降序坐标做 `slice(35, 50)` 会返回**空结果**，然后在区域平均那里抛 `ValueError: 区域内没有格点`——你看着像"区域错了"，其实是排序问题。

**解法**：

```python
ds = ds.sortby("latitude")   # 35 → 50，升序
```

## 坑 5：四联图各自 `vmin/vmax`，颜色全部不可比

这是最坑的一个，因为它**不报错**。

`contourf` 的颜色是"数值 → 区间"的映射。每张子图各自归一化时，同样的深蓝色代表完全不同的风速。实测四个月最大值：1 月 7.16、7 月 6.41、10 月 5.98 m/s。各自归一化的话，10 月的 5.98 会被画成和 1 月 7.16 一样的"最深色"，读者得出"四个月差不多"的结论——**结论错了，图还很好看**。

**解法**：先扫一遍所有场取全局最大值，再统一生成 `levels`，四张子图共用一个色标。

```python
vmax = max(float(f.max()) for f in fields.values())
levels = np.arange(0, np.ceil(vmax * 2) / 2 + 0.5, 0.5)   # 0–7.5，15 档
```

| 月份 | 全区均值 (m/s) | 最大值 (m/s) |
|---|---|---|
| 1 月 | 2.34 | 7.16 |
| 4 月 | 2.78 | 6.36 |
| 7 月 | 2.85 | 6.41 |
| 10 月 | 2.62 | 5.98 |

## 坑 6：`open_mfdataset` 不排序，时间轴会错位

多个月份文件合并时，`glob` 的返回顺序**不保证**是文件名的字典序。`open_mfdataset(combine="by_coords")` 按传入顺序拼时间轴，于是 1 月和 10 月可能串位——数据都在，时间标签乱了，算出来的气候态全错。

**解法**：

```python
files = sorted(Path("data").glob("era5_*.nc"))
ds = xr.open_mfdataset(files, combine="by_coords", preprocess=normalize)
```

## 坑 7：直接调用 `envs\met\python.exe`，进程会静默崩掉

这个最吓人：双击、或在编辑器里直接指向 `...\envs\met\python.exe` 跑脚本，进程退出码 `-1066598273`（`0xC067001F`），**没有任何 traceback**，看起来像代码崩了。

原因是 conda 环境没激活时，`Library\bin` 不在 `PATH` 里，netCDF/HDF5 的 DLL 加载失败，Python 还没执行到第一行就死了。

**解法**：要么先 `conda activate met`，要么用 `conda run -n met python 脚本.py`。判断环境对不对的最快方式：

```powershell
python -c "import sys; print(sys.executable)"
```

## 彩蛋：第八个坑，等你踩到再说

如果你要把 ERA5 和国产数据（CMFD，0.1°）做差，别指望 `align` 能救你——它只做**标签配对，不做插值**。

实测这两套数据：纬度只重合 30/61、经度 60/121，`inner` 对齐后只剩 **24%** 的格点，空间分辨率悄悄从 0.25° 变成 0.5°，而且**不报错**。名字还不一样（`latitude` vs `lat`），直接相减会广播成四维数组。

必须 `rename` → `resample` 到同一时间尺度 → `interp_like` 插值到同一网格，三步缺一不可。

---

## 一条总原则

这七个坑里有五个的共同点：**不报错，但结果错**。

所以写地理数据代码时，$验证$比写代码更重要：

```python
print(ds)                                   # 维度、坐标、单位
print(float(ds.u10.min()), float(ds.u10.max()))   # 数值范围合不合理
print(ds.time.values[[0, -1]])              # 时间起止、是不是 UTC
```

三行代码，能提前发现上面一半的问题。

> 配套代码：[era5-xinjiang](https://github.com/swordzhang8-pixel/era5-xinjiang)
> 图：`3_成果图/ERA5风速_2020_四季四联图.png`、`ERA5风速_2020年平均.png`
