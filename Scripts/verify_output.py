"""Verify full partition output statistics."""
import geopandas as gpd

zones = gpd.read_file(r'Scripts\Outputs\utah_full_auto_microzones.gpkg')
print(f'Loaded {len(zones)} zones')
print(f'Columns: {list(zones.columns)}')
print(f'\nArea stats (acres):')
print(f'  Min: {zones["area_acres"].min():.1f}')
print(f'  Mean: {zones["area_acres"].mean():.1f}')
print(f'  Median: {zones["area_acres"].median():.1f}')
print(f'  Max: {zones["area_acres"].max():.1f}')
print(f'  90th percentile: {zones["area_acres"].quantile(0.9):.1f}')
print(f'\nUnique values:')
print(f'  CO_FIPS: {sorted(zones["CO_FIPS"].unique())}')
print(f'  Status: {sorted(zones["Status"].unique())}')
print(f'\nSample MAZ_NOTE values:')
print(zones['MAZ_NOTE'].value_counts().head(3))
