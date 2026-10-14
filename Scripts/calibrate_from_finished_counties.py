"""
Mine the already-completed counties' microzones (Salt Lake, Davis, Weber/Box Elder)
to derive empirical calibration targets for automating Utah County's microzones:
  - typical MAZ size (acres)
  - typical shape compactness
  - typical land-use homogeneity (dominant land-use share, category count)

Run with: conda run -n remm python Scripts/calibrate_from_finished_counties.py
"""
import math
import geopandas as gpd
import pandas as pd

M2_TO_ACRES = 0.000247105

COUNTIES = {
    "SaltLake": {
        "maz_gdb": r".\_SaltLake\Inputs\Microzones_DRAFT.gdb",
        "fips": [35],
        "landuse_shp": [
            r".\_SaltLake\Inputs\land_use_dissolved_35_1.shp",
            r".\_SaltLake\Inputs\land_use_dissolved_35_2.shp",
        ],
    },
    "Davis": {
        "maz_gdb": r".\_Davis\Inputs\Microzones_DRAFT.gdb",
        "fips": [11],
        "landuse_shp": [r".\_Davis\Inputs\land_use_dissolved_5711.shp"],
    },
    "Weber_BoxElder": {
        "maz_gdb": r".\_Weber_BoxElder\Inputs\Microzones_DRAFT.gdb",
        "fips": [3, 57],
        "landuse_shp": [r".\_Weber_BoxElder\Inputs\land_use_dissolved_5711.shp"],
    },
}


def load_reviewed_maz(cfg):
    gdf = gpd.read_file(cfg["maz_gdb"], layer="Microzones_DRAFT")
    gdf = gdf[gdf["CO_FIPS"].isin(cfg["fips"]) & (gdf["Status"] == 1)].copy()
    gdf["area_acres"] = gdf.geometry.area * M2_TO_ACRES
    perim = gdf.geometry.length
    gdf["compactness"] = (4 * math.pi * gdf.geometry.area) / (perim**2)
    return gdf


def load_landuse(cfg):
    parts = [gpd.read_file(p)[["land_use", "geometry"]] for p in cfg["landuse_shp"]]
    return pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]


def landuse_mix_stats(maz, landuse):
    maz = maz.reset_index(drop=True)
    maz["maz_uid"] = maz.index
    inter = gpd.overlay(
        maz[["maz_uid", "geometry"]], landuse, how="intersection", keep_geom_type=False
    )
    inter["piece_area"] = inter.geometry.area
    inter = inter[inter["piece_area"] > 0]

    by_zone = inter.groupby("maz_uid")["piece_area"].sum().rename("covered_area")
    by_zone_lu = inter.groupby(["maz_uid", "land_use"])["piece_area"].sum()

    dominant_share = by_zone_lu.groupby("maz_uid").max() / by_zone
    n_categories = (by_zone_lu / by_zone).groupby("maz_uid").apply(lambda s: (s > 0.05).sum())

    def entropy(s):
        p = s / s.sum()
        return float(-(p * p.apply(lambda x: math.log(x, 2) if x > 0 else 0)).sum())

    shannon = by_zone_lu.groupby("maz_uid").apply(entropy)

    out = maz.set_index("maz_uid").join(
        dominant_share.rename("dominant_lu_share")
    ).join(n_categories.rename("n_lu_categories")).join(shannon.rename("lu_shannon_entropy"))
    return out


def summarize(df, county_name):
    s = df[["area_acres", "compactness", "dominant_lu_share", "n_lu_categories", "lu_shannon_entropy"]].describe(
        percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]
    )
    s.insert(0, "county", county_name)
    return s


if __name__ == "__main__":
    all_zone_rows = []
    summaries = []

    for name, cfg in COUNTIES.items():
        print(f"--- {name} ---")
        maz = load_reviewed_maz(cfg)
        print(f"  reviewed MAZ count: {len(maz)}")
        landuse = load_landuse(cfg)
        stats = landuse_mix_stats(maz, landuse)
        stats["county"] = name
        all_zone_rows.append(stats)
        summaries.append(summarize(stats, name))

    combined = pd.concat(all_zone_rows, ignore_index=True)
    combined.to_csv(r".\Scripts\Outputs\reviewed_maz_calibration_stats.csv", index=False)

    combined_summary = summarize(combined, "ALL_FINISHED_COUNTIES")
    summaries.append(combined_summary)

    full_summary = pd.concat(summaries)
    full_summary.to_csv(r".\Scripts\Outputs\reviewed_maz_calibration_summary.csv")
    pd.set_option("display.width", 160)
    print(full_summary)
