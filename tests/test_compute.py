"""compute 层的单元测试：只用 3×3 的已知数组，不碰真实数据。"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from era5x.compute import monthly_mean, regional_mean, wind_speed


def test_wind_speed_3x3():
    # 对角线上 (3,4) 合成 5；其余为 0
    u = np.array([[3.0, 0.0, 0.0],
                  [0.0, 3.0, 0.0],
                  [0.0, 0.0, 3.0]])
    v = np.array([[4.0, 0.0, 0.0],
                  [0.0, 4.0, 0.0],
                  [0.0, 0.0, 4.0]])
    ds = xr.Dataset(
        {"u10": (("latitude", "longitude"), u),
         "v10": (("latitude", "longitude"), v)}
    )
    ws = wind_speed(ds)
    expected = np.array([[5.0, 0.0, 0.0],
                         [0.0, 5.0, 0.0],
                         [0.0, 0.0, 5.0]])
    np.testing.assert_allclose(ws.values, expected)
    assert ws.attrs["units"] == "m s-1"


def test_wind_speed_negative_components():
    # 风速与风向无关：(−3,−4) 也是 5
    ds = xr.Dataset({
        "u10": (("latitude", "longitude"), [[-3.0]]),
        "v10": (("latitude", "longitude"), [[-4.0]]),
    })
    assert wind_speed(ds).values[0, 0] == pytest.approx(5.0)


def test_regional_mean_constant_field():
    lat = np.arange(30.0, 56.0)          # 30..55
    lon = np.arange(60.0, 111.0)         # 60..110
    da = xr.DataArray(
        np.ones((lat.size, lon.size)),
        coords={"latitude": lat, "longitude": lon},
        dims=("latitude", "longitude"),
    )
    assert float(regional_mean(da)) == pytest.approx(1.0)


def test_regional_mean_crops_outside_points():
    lat = np.arange(30.0, 56.0)
    lon = np.arange(60.0, 111.0)
    # 只有纬度 40 这一行是 10，其余 0；裁剪后 35—50 内仍应包含它
    values = np.zeros((lat.size, lon.size))
    values[list(lat).index(40.0), :] = 10.0
    da = xr.DataArray(values, coords={"latitude": lat, "longitude": lon},
                      dims=("latitude", "longitude"))
    out = float(regional_mean(da, lon=(70, 100), lat=(35, 50)))
    assert 0 < out < 10


def test_regional_mean_rejects_empty_region():
    lat = np.arange(0.0, 10.0)
    lon = np.arange(0.0, 10.0)
    da = xr.DataArray(np.zeros((lat.size, lon.size)),
                      coords={"latitude": lat, "longitude": lon},
                      dims=("latitude", "longitude"))
    with pytest.raises(ValueError):
        regional_mean(da, lon=(70, 100), lat=(35, 50))


def test_monthly_mean_groups_by_month():
    time = np.array(["2020-01-01", "2020-01-15", "2020-02-01"],
                    dtype="datetime64[ns]")
    da = xr.DataArray([1.0, 3.0, 10.0], coords={"time": time}, dims="time")
    out = monthly_mean(da)
    assert out.sel(month=1).item() == pytest.approx(2.0)
    assert out.sel(month=2).item() == pytest.approx(10.0)
