# 新疆十天 WRF 真实天气个例

用独立案例目录跑通 GFS → WPS → real → WRF 的十天流程。实际运行完成，并核对241个连续逐小时时刻。运行和绘图由助手执行；本仓库不将它记为用户独立完成。

## 实际配置与结果

- 2024-07-01 00 UTC至07-11 00 UTC，共240小时；实际积分约29.4分钟（4个虚拟CPU，非通用耗时承诺）。
- 原版WRF 4.8.0 / WPS 4.7.0；单区域27km，e_we=111、e_sn=101、e_vert=45，质量网格110×100×44；时间步长90s。
- Lambert投影中心85E/42.5N，标准纬线30N/60N；低分辨率地理数据。
- 41份GFS 1度、每6小时f000分析场，约1.73GB；不是单次240小时GFS预报。来源及SHA256见download_manifest.json。
- WSM3微物理、RRTM长波、Dudhia短波、Noah陆面、YSU边界层、MM5近地层、Kain–Fritsch积云；辐射间隔15分钟。
- 无风电/光伏模块；逐小时输出，每日重启。
- SUCCESS COMPLETE REAL_EM INIT与SUCCESS COMPLETE WRF均已核对。11个输出文件共241个时次；关键地表变量有限值与基本温压范围检查通过。详细结果见output_validation.json。

## 重要限制

RRTM各MPI日志共645条TBOUND高温查表警告，最高日志温度342.317K。该方案源码在辐射计算中将超过340K的地表边界温度截为339.99K；没有修改源码掩盖警告。完成流程不代表通过观测精度、能量闭合或科研适用性验证。

前24小时完整保留。平均地图暂剔除前24小时，实际平均216个整点样本（07-02 00至07-10 23UTC）；这不证明24h后已完成spin-up。连续曲线包含天气变化，不能单凭曲线把变化归因于spin-up。

统计覆盖整个模式区域，不是新疆行政区平均。地图覆盖新疆及周边；灰线是地形等高线，风矢量已按COSALPHA/SINALPHA转换为地理方向。单次十天个例不代表多年气候态。

## 文件

- namelist.wps / namelist.input：实际运行配置。
- prepare_xinjiang_domain.py：Ubuntu创建隔离案例并运行geogrid。
- download_xinjiang_gfs.py：下载41份公开驱动、检查GRIB首尾和文件大小、记录SHA256。
- run_xinjiang_10d.py：ungrib、metgrid、读取实际输入层数、real与240小时WRF运行。
- check_xinjiang_output.py：运行完成后核对241时次及地表字段，导出surface_diagnostics.zip；使用系统netCDF库，不额外安装Python包。
- plot_xinjiang_results.py：读取诊断包，生成气温风场地图和连续时间图。
- plot_xinjiang_domain.py：读取geo_em.d01.nc生成区域地形图。
- 逐小时区域诊断.csv：区域面积加权平均；PNG/PDF为实际输出绘图。

GFS驱动、geo_em、完整多层wrfout、重启文件、约95MB诊断包不入库。绘图需使用本地诊断包，或重新运行并导出；不能仅凭仓库中的CSV重画空间地图。

## 复现顺序

需先有可用WRF/WPS以及现有地理资料，默认Ubuntu根目录~/WRF_BUILD。先检查脚本中的本机目录是否匹配。

1. 在本案例目录运行 `python download_xinjiang_gfs.py`，会下载约1.73GB。
2. 将GFS目录中的41个GRIB文件和清单放入Ubuntu的 `~/WRF_BUILD/DATA/xinjiang_gfs_20240701/`。
3. 将案例代码及namelist.wps放在同一目录，运行 `python3 prepare_xinjiang_domain.py`。
4. 运行 `python3 run_xinjiang_10d.py`，其读取 `~/WRF_BUILD/latest_xinjiang_10d_path.txt` 指定的隔离案例。
5. 完成后运行 `python3 check_xinjiang_output.py`，将生成的surface_diagnostics.zip传到本案例目录。
6. Windows在已配置numpy/netCDF4/matplotlib/cartopy的met环境运行：

```powershell
conda run -n met --no-capture-output python plot_xinjiang_results.py
```

区域图另需复制实际geo_em.d01.nc到本目录，再运行plot_xinjiang_domain.py。完整多层NetCDF保留在Ubuntu案例run/目录，Windows诊断包仅包含选定地表字段。
