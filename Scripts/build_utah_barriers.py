"""
Build a first-pass "hard barrier" layer for Utah County: features that a microzone
boundary should never cross (limited-access highways, railroads). Local/collector
streets are NOT barriers -- they're valid split lines, just not forced boundaries.

Known gap: no canal/river (hydrography) layer is included yet. That needs to be
sourced separately (see printed note at the end) before the barrier layer is complete.

Run with: conda run -n remm python Scripts/build_utah_barriers.py
"""
import geopandas as gpd

ROADS_PATH = r".\_Utah\Inputs\Major_Roads_WF.shp"
TAZ_PATH = r".\_Utah\Inputs\TAZ.shp"
RAIL_PATH = r".\Scripts\Outputs\utah_railroads_raw.gpkg"
OUT_PATH = r".\Scripts\Outputs\utah_barrier_candidates.gpkg"

# UGRC CARTOCODE: 1 = Interstate, 2 = Expressway/other freeway (limited access).
# These are the only road-derived features treated as hard barriers.
FREEWAY_CARTOCODES = ["1", "2"]

if __name__ == "__main__":
    taz = gpd.read_file(TAZ_PATH)
    print("TAZ columns:", taz.columns.tolist())
    taz_col = "CO_FIPS" if "CO_FIPS" in taz.columns else None
    if taz_col:
        utah_taz = taz[taz[taz_col] == 49].copy()
        print(f"Utah County TAZs: {len(utah_taz)} of {len(taz)}")
    else:
        utah_taz = taz
        print("No CO_FIPS field found on TAZ layer -- using all TAZ features as extent")

    utah_extent = utah_taz.union_all().convex_hull

    roads = gpd.read_file(ROADS_PATH)
    if roads.crs != taz.crs:
        roads = roads.to_crs(taz.crs)

    freeways = roads[roads["CARTOCODE"].isin(FREEWAY_CARTOCODES)].copy()
    freeways = freeways[freeways.geometry.intersects(utah_extent)].copy()
    freeways["barrier_type"] = "freeway"
    freeways = freeways[["barrier_type", "geometry"]]

    print(f"Freeway/expressway barrier segments in Utah County extent: {len(freeways)}")

    rail = gpd.read_file(RAIL_PATH)
    if rail.crs != taz.crs:
        rail = rail.to_crs(taz.crs)
    # ABANDONED is populated only for lines that ARE abandoned; blank/None = active line.
    rail = rail[rail["ABANDONED"].isna() | (rail["ABANDONED"].str.strip() == "")].copy()
    rail = rail[rail.geometry.intersects(utah_extent)].copy()
    rail["barrier_type"] = "railroad"
    rail = rail[["barrier_type", "geometry"]]

    print(f"Active railroad barrier segments in Utah County extent: {len(rail)}")

    barriers = gpd.GeoDataFrame(
        gpd.pd.concat([freeways, rail], ignore_index=True), geometry="geometry", crs=taz.crs
    )
    barriers.to_file(OUT_PATH, layer="barriers", driver="GPKG")
    print(f"Saved: {OUT_PATH} (layer=barriers, {len(barriers)} total segments)")

    print()
    print("GAP: no canal/river (hydrography) layer is included yet. Canals/rivers")
    print("are common walking barriers per the project rules. Add a source and")
    print("append to this barrier layer before it's used for zone partitioning.")
