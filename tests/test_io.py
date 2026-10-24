"""io 层的单元测试：只验证「读进来之后坐标是否规范」，不依赖真实文件。"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from era5x.io import load_era5, normalize


def _raw_dataset() -> xr.Dataset:
    time = np.array(["2020-01-01T00:00", "2020-01-01T06:00"], dtype="datetime64[ns]")
    return xr.Dataset(
        {"u10": (("valid_time", "latitude", "longitude"), np.zeros((2, 3, 2)))},
        coords={
            "valid_time": time,
            "latitude": [50.0, 42.5, 35.0],        # ERA5 原始：降序
            "longitude": [70.0, 70.25],
            "expver": ("valid_time", ["0001", "0005"]),
        },
    )


def test_normalize_renames_time():
    out = normalize(_raw_dataset())
    assert "time" in out.dims
    assert "valid_time" not in out.dims


def test_normalize_drops_expver():
    out = normalize(_raw_dataset())
    assert "expver" not in out.coords


def test_normalize_sorts_latitude_ascending():
    out = normalize(_raw_dataset())
    assert np.all(np.diff(out.latitude.values) > 0)


def test_load_era5_missing_file():
    with pytest.raises(FileNotFoundError):
        load_era5("data/这个文件不存在.nc")
