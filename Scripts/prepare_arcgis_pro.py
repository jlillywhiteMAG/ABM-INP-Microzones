"""Prepare Utah microzones for ArcGIS Pro review workflow.

This script:
1. Loads the auto-generated candidate zones from the full partition
2. Exports as a shapefile (compatible with ArcGIS Pro)
3. Creates a staging geodatabase-ready format
4. Generates import instructions
"""
import geopandas as gpd
from pathlib import Path

# Load the full partition output
print("Loading auto-generated zones...")
zones = gpd.read_file(r'Scripts\Outputs\utah_full_auto_microzones.gpkg')
print(f"Loaded {len(zones)} zones")

# Create outputs folder if needed
output_folder = Path(r'Scripts\Outputs')
output_folder.mkdir(exist_ok=True)

# Export as shapefile (widely compatible with ArcGIS Pro)
shapefile_path = output_folder / 'utah_microzones_candidates.shp'
print(f"\nExporting to shapefile: {shapefile_path.name}")
zones.to_file(str(shapefile_path), index=False)
print(f"  ✓ Shapefile exported ({len(zones)} features)")

# Also keep the GeoPackage (no need to export, already exists)
print(f"\nGeoPackage available: utah_full_auto_microzones.gpkg")
print(f"  Use this in ArcGIS Pro if you prefer")

# Create import instructions
instructions = f"""
UTAH MICROZONES — ArcGIS PRO IMPORT INSTRUCTIONS
==================================================

Generated candidates: {len(zones)} zones
Date: 2026-09-17
Status: All zones unreviewed (Status=0)

FILES AVAILABLE FOR IMPORT:
---------------------------

Option 1 (RECOMMENDED): Use GeoPackage directly in ArcGIS Pro
  File: Scripts/Outputs/utah_full_auto_microzones.gpkg
  - Native GIS format, preserves all geometry precision
  - Easily opens as a layer in ArcGIS Pro
  - Steps:
    1. Open MICROZONES_UTAH.aprx in ArcGIS Pro
    2. Right-click Map layers > Add Data
    3. Select utah_full_auto_microzones.gpkg
    4. Choose the "microzones" layer (default layer name)

Option 2: Import Shapefile to Geodatabase
  File: Scripts/Outputs/utah_microzones_candidates.shp
  - Compatible with standard ArcGIS workflows
  - Steps:
    1. Open ArcCatalog or ArcGIS Pro Catalog
    2. Navigate to Default.gdb or new geodatabase
    3. Right-click > Import > Feature Class (Single)
    4. Select utah_microzones_candidates.shp
    5. Set output feature class name: "Microzones_CANDIDATES" or similar

SCHEMA:
-------
Columns in the imported layer:
  - zone_id: Unique zone identifier (1-indexed per TAZ)
  - TAZID: Parent Traffic Analysis Zone ID
  - CO_FIPS: County FIPS code (49 = Utah County)
  - area_acres: Zone area in acres
  - land_use: Dominant land-use category from overlay
  - Status: Review status (0=unreviewed)
  - MAZ_NOTE: Metadata/notes field
  - geometry: Polygon geometries (MULTIPOLYGON format)

WORKFLOW:
---------
1. Import the candidate zones layer
2. Add Nearmap imagery basemap for visual reference
3. Review each zone by:
   - Examining boundary alignment with land features
   - Checking for mixed land uses
   - Verifying boundaries don't cross major barriers
4. Update Status field:
   - 0 = Unreviewed (default)
   - 1 = Approved
   - 2 = Needs revision
   - 3 = Rejected/Invalid
5. Add notes in MAZ_NOTE field as needed
6. Export reviewed zones when complete

CALIBRATION TARGETS (for reference):
------------------------------------
From 8,316 reviewed zones across finished counties:
  Median area: 28.3 acres
  10th-90th percentile: 5.0-93.2 acres
  Median compactness: 0.642
  Median dominant land-use share: 0.830 (83%)

Generated candidates:
  Median area: 52.4 acres (larger due to limited internal roads in some TAZs)
  90th percentile: 233.5 acres
  Note: Some large zones are undeveloped rural areas or constrained by TAZ structure

SUPPORT:
--------
If zones need further refinement:
- Re-run partition script with adjusted parameters (size targets, road thresholds)
- Manually split large zones in ArcGIS Pro
- Merge small zones into neighbors
- Add missing land-use or barrier data as needed

Questions? See readme.md for project overview.
"""

readme_path = output_folder / 'ARCGIS_PRO_IMPORT_README.txt'
with open(readme_path, 'w') as f:
    f.write(instructions)

print(f"\n✓ Import instructions saved to: {readme_path.name}")
print("\nREADY FOR ARCGIS PRO REVIEW")
print("=" * 50)
print(f"Next step: Open MICROZONES_UTAH.aprx and import the candidate zones layer")
