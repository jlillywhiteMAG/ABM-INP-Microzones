"""Explore existing Utah geodatabase schema to match output format."""
import geopandas as gpd
from pathlib import Path

# Check what exists in Utah folder
utah_folder = Path(r'_Utah')
print("Files in _Utah folder:")
for item in utah_folder.iterdir():
    if item.is_file():
        print(f"  {item.name}")
    elif item.is_dir():
        print(f"  {item.name}/ (directory)")

# Try to read from Default.gdb if it exists
gdb_path = utah_folder / 'Default.gdb'
if gdb_path.exists():
    print(f"\nDefault.gdb found at: {gdb_path}")
    try:
        # List available layers
        import pyogrio
        layers = pyogrio.list_layers(str(gdb_path))
        print(f"Available layers in Default.gdb:")
        for layer in layers:
            print(f"  {layer}")
    except Exception as e:
        print(f"  Error reading: {e}")

# Load our generated output
print("\n" + "="*50)
print("Generated output schema:")
zones = gpd.read_file(r'Scripts\Outputs\utah_full_auto_microzones.gpkg')
print(f"Geometry type: {zones.geometry.type.unique()}")
print(f"CRS: {zones.crs}")
print(f"Columns: {list(zones.columns)}")
print(f"Sample row:")
print(zones.iloc[0].to_dict())
