"""检查CMFD V0106 NetCDF文件结构"""
import netCDF4
import os

cmfd_dir = r"c:\Users\WH\Desktop\cmfd_temp"

for var_short, fname in [
    ("temp", "temp_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"),
    ("prec", "prec_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"),
    ("wind", "wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"),
]:
    path = os.path.join(cmfd_dir, fname)
    print(f"=== {var_short} ===")
    print(f"  file: {fname}")

    ds = netCDF4.Dataset(path, "r")

    # 维度
    dims = {k: len(v) for k, v in ds.dimensions.items()}
    print(f"  dims: {dims}")

    # 变量
    print(f"  vars: {list(ds.variables.keys())}")

    for v in ds.variables:
        if v not in ("lat", "lon", "time", "latitude", "longitude"):
            var = ds.variables[v]
            units = getattr(var, "units", "?")
            long_name = getattr(var, "long_name", "?")
            print(f"  {v}: shape={var.shape}, dtype={var.dtype}")
            print(f"    units={units}, long_name={long_name}")

    # 时间维度
    if "time" in ds.variables:
        t = ds.variables["time"]
        units = getattr(t, "units", "?")
        print(f"  time: {len(t)} steps, units={units}")
        print(f"    first={float(t[0])}, last={float(t[-1])}")

    # 经纬度范围
    if "lon" in ds.variables:
        lon = ds.variables["lon"][:]
        print(f"  lon: {float(lon[0])} ~ {float(lon[-1])}, n={len(lon)}")
    if "lat" in ds.variables:
        lat = ds.variables["lat"][:]
        print(f"  lat: {float(lat[0])} ~ {float(lat[-1])}, n={len(lat)}")

    ds.close()
    print()
