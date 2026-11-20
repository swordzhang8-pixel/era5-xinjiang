#!/usr/bin/env bash
set -euo pipefail
BASE="$(cat "$HOME/WRF_BUILD/latest_xinjiang_10d_path.txt")"
CASE="$HOME/WRF_BUILD/cases/xinjiang_nested_20240701_20261120"
mkdir -p "$CASE/wps" "$CASE/run"
WPS="$CASE/wps"
ln -sfn "$HOME/WRF_BUILD/WPS/geogrid" "$WPS/geogrid"
ln -sfn "$HOME/WRF_BUILD/WPS/metgrid" "$WPS/metgrid"
for f in "$BASE"/wps/FILE:*; do [ -e "$f" ] && ln -sfn "$f" "$WPS/$(basename "$f")"; done
cat > "$WPS/namelist.wps" <<'EOF'
&share
 wrf_core='ARW', max_dom=2,
 start_date='2024-07-01_00:00:00','2024-07-01_00:00:00',
 end_date='2024-07-11_00:00:00','2024-07-11_00:00:00',
 interval_seconds=21600, io_form_geogrid=2,
/
&geogrid
 parent_id=1,1,
 parent_grid_ratio=1,3,
 i_parent_start=1,68,
 j_parent_start=1,41,
 e_we=111,76,
 e_sn=101,76,
 geog_data_res='lowres','lowres',
 dx=27000,
 dy=27000,
 map_proj='lambert',
 ref_lat=42.5, ref_lon=85.0,
 truelat1=30.0, truelat2=60.0, stand_lon=85.0,
 geog_data_path='/home/zhangjian/WRF_BUILD/DATA/wps_practice/WPS_GEOG_LOW_RES',
/
&ungrib
 out_format='WPS', prefix='FILE',
/
&metgrid
 fg_name='FILE', io_form_metgrid=2,
/
EOF
cd "$WPS"
"$HOME/WRF_BUILD/WPS/geogrid.exe" > geogrid.console.log 2>&1
tail -n 8 geogrid.console.log
[ -s geo_em.d01.nc ] && [ -s geo_em.d02.nc ]
"$HOME/WRF_BUILD/WPS/metgrid.exe" > metgrid.console.log 2>&1
tail -n 10 metgrid.console.log
echo MET_COUNTS
printf 'd01 '; find . -maxdepth 1 -name 'met_em.d01.*.nc' | wc -l
printf 'd02 '; find . -maxdepth 1 -name 'met_em.d02.*.nc' | wc -l
echo CASE="$CASE"
df -h "$HOME" | tail -n 1
