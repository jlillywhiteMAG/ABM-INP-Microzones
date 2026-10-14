"""
Prototype: constrained partitioning of Utah County TAZs into microzones (MAZs),
calibrated against the empirical stats mined from finished counties
(Scripts/calibrate_from_finished_counties.py).

Algorithm (per TAZ):
  1. Build "elementary blocks" by polygonizing the TAZ boundary + all local/major
     roads inside it (finest-grain split, same over-splitting the old auto-draft did).
  2. Tag each block with its dominant land-use category (overlay with land_use_dissolved).
  3. Build a block-adjacency graph. Mark an adjacency as "blocked" if the shared
     edge lies on a hard barrier (freeway/railroad) -- these can never be merged across.
  4. Merge adjacent blocks that share the same dominant land-use category and are
     not separated by a barrier (union-find over allowed, same-land-use edges).
  5. If a merged zone is bigger than the calibrated upper-size target, split it
     back down with a balanced spatial k-means on block centroids (weighted by area)
     so each piece is close to the calibrated median size.
  6. If a merged zone is a sliver smaller than the calibrated lower-size target,
     merge it into its largest neighboring zone (crossing land-use if necessary,
     but never crossing a barrier).

Run with: conda run -n general_python python Scripts/prototype_partition_utah_taz.py
"""
import math

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union
from sklearn.cluster import KMeans

TAZ_PATH = r".\_Utah\Inputs\TAZ.shp"
ROADS_MAJOR = r".\_Utah\Inputs\Major_Roads_WF.shp"
ROADS_LOCAL = r".\_Utah\Inputs\Local_Roads_WF.shp"
LANDUSE_PATH = r".\_Utah\Inputs\land_use_dissolved_49.shp"
BARRIER_PATH = r".\Scripts\Outputs\utah_barrier_candidates.gpkg"
OUT_PATH = r".\Scripts\Outputs\utah_prototype_microzones.gpkg"

# Calibrated from finished counties (see reviewed_maz_calibration_summary.csv)
TARGET_ACRES_MEDIAN = 28.0
TARGET_ACRES_MIN = 10.0
TARGET_ACRES_MAX = 90.0
M2_TO_ACRES = 0.000247105

# Sample a handful of TAZs across a range of sizes for the prototype.
N_SAMPLE_TAZ = 6


def build_elementary_blocks(taz_geom, roads_gdf, crs):
    """Polygonize TAZ boundary + all roads clipped to the TAZ."""
    roads_clip = roads_gdf.clip(taz_geom)
    lines = [taz_geom.boundary] + list(roads_clip.geometry)
    merged = unary_union(lines)
    blocks = list(polygonize(merged))
    blocks_gdf = gpd.GeoDataFrame(geometry=blocks, crs=crs)
    # keep only pieces actually inside the TAZ (polygonize can produce slivers outside)
    blocks_gdf = blocks_gdf[blocks_gdf.geometry.representative_point().within(taz_geom.buffer(1))]
    blocks_gdf = blocks_gdf[blocks_gdf.geometry.area > 10].reset_index(drop=True)
    return blocks_gdf


def tag_dominant_landuse(blocks_gdf, landuse_gdf):
    inter = gpd.overlay(
        blocks_gdf.reset_index().rename(columns={"index": "block_id"}),
        landuse_gdf[["land_use", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    inter["piece_area"] = inter.geometry.area
    dominant = (
        inter.sort_values("piece_area", ascending=False)
        .drop_duplicates("block_id")
        .set_index("block_id")["land_use"]
    )
    blocks_gdf["land_use"] = blocks_gdf.index.map(dominant).fillna("unknown")
    return blocks_gdf


def build_adjacency_graph(blocks_gdf, barrier_union):
    G = nx.Graph()
    G.add_nodes_from(blocks_gdf.index)
    sindex = blocks_gdf.sindex
    for i, geom in blocks_gdf.geometry.items():
        candidates = list(sindex.intersection(geom.bounds))
        for j in candidates:
            if j <= i:
                continue
            other = blocks_gdf.geometry.iloc[j]
            shared = geom.boundary.intersection(other.boundary)
            if shared.is_empty or shared.length == 0:
                continue
            blocked = barrier_union is not None and shared.buffer(0.5).intersects(barrier_union)
            G.add_edge(i, j, blocked=blocked)
    return G


def merge_same_landuse(blocks_gdf, G):
    """Union-find merge of adjacent, non-barrier-separated, same-land-use blocks."""
    uf = {i: i for i in blocks_gdf.index}

    def find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[ra] = rb

    for u, v, data in G.edges(data=True):
        if data["blocked"]:
            continue
        if blocks_gdf.loc[u, "land_use"] == blocks_gdf.loc[v, "land_use"]:
            union(u, v)

    blocks_gdf["group"] = [find(i) for i in blocks_gdf.index]
    return blocks_gdf


def dissolve_groups(blocks_gdf, crs):
    zones = blocks_gdf.dissolve(by="group", aggfunc={"land_use": "first"}).reset_index(drop=True)
    zones = gpd.GeoDataFrame(zones, geometry="geometry", crs=crs)
    zones["area_acres"] = zones.geometry.area * M2_TO_ACRES
    return zones


def split_oversized(zones_gdf, blocks_gdf, crs):
    """Balanced spatial k-means split of any zone larger than the max target."""
    out_rows = []
    for _, zone in zones_gdf.iterrows():
        if zone["area_acres"] <= TARGET_ACRES_MAX:
            out_rows.append(zone)
            continue
        n_pieces = max(2, round(zone["area_acres"] / TARGET_ACRES_MEDIAN))
        member_blocks = blocks_gdf[blocks_gdf.geometry.within(zone.geometry.buffer(0.5))]
        if len(member_blocks) < n_pieces:
            out_rows.append(zone)
            continue
        centroids = np.array([[g.centroid.x, g.centroid.y] for g in member_blocks.geometry])
        weights = member_blocks.geometry.area.values
        km = KMeans(n_clusters=n_pieces, n_init=5, random_state=0)
        # weight influence by repeating heavier blocks' centroids isn't ideal; use sample_weight via fit
        km.fit(centroids, sample_weight=weights)
        member_blocks = member_blocks.copy()
        member_blocks["cluster"] = km.labels_
        for _, sub in member_blocks.dissolve(by="cluster").iterrows():
            out_rows.append(
                pd.Series(
                    {
                        "geometry": sub.geometry,
                        "land_use": zone["land_use"],
                        "area_acres": sub.geometry.area * M2_TO_ACRES,
                    }
                )
            )
    result = gpd.GeoDataFrame(out_rows, geometry="geometry", crs=crs).reset_index(drop=True)
    return result


def merge_slivers(zones_gdf, crs):
    """Merge zones smaller than the min target into their largest touching neighbor."""
    zones_gdf = zones_gdf.reset_index(drop=True)
    changed = True
    while changed:
        changed = False
        small_idx = zones_gdf.index[zones_gdf["area_acres"] < TARGET_ACRES_MIN].tolist()
        if not small_idx:
            break
        i = small_idx[0]
        geom = zones_gdf.geometry.iloc[i]
        touching = zones_gdf.index[
            (zones_gdf.index != i) & zones_gdf.geometry.touches(geom)
        ].tolist()
        if not touching:
            break
        best = max(touching, key=lambda j: zones_gdf.geometry.iloc[j].area)
        merged_geom = unary_union([geom, zones_gdf.geometry.iloc[best]])
        zones_gdf.at[best, "geometry"] = merged_geom
        zones_gdf.at[best, "area_acres"] = merged_geom.area * M2_TO_ACRES
        zones_gdf = zones_gdf.drop(index=i).reset_index(drop=True)
        changed = True
    return zones_gdf


def process_taz(taz_row, roads_major, roads_local, landuse, barrier_union, crs):
    taz_geom = taz_row.geometry
    roads = gpd.GeoDataFrame(
        pd.concat([roads_major[["geometry"]], roads_local[["geometry"]]], ignore_index=True),
        crs=crs,
    )
    blocks = build_elementary_blocks(taz_geom, roads, crs)
    if len(blocks) == 0:
        blocks = gpd.GeoDataFrame(geometry=[taz_geom], crs=crs)
        blocks["land_use"] = "unknown"
    else:
        blocks = tag_dominant_landuse(blocks, landuse)

    if len(blocks) == 1:
        zones = blocks.copy()
        zones["area_acres"] = zones.geometry.area * M2_TO_ACRES
    else:
        G = build_adjacency_graph(blocks, barrier_union)
        blocks = merge_same_landuse(blocks, G)
        zones = dissolve_groups(blocks, crs)
        zones = split_oversized(zones, blocks, crs)
        zones = merge_slivers(zones, crs)

    zones["TAZID"] = taz_row["TAZID"]
    return zones


if __name__ == "__main__":
    taz = gpd.read_file(TAZ_PATH)
    utah_taz = taz[taz["CO_FIPS"] == 49].copy()
    crs = utah_taz.crs

    roads_major = gpd.read_file(ROADS_MAJOR).to_crs(crs)
    roads_local = gpd.read_file(ROADS_LOCAL).to_crs(crs)
    landuse = gpd.read_file(LANDUSE_PATH).to_crs(crs)
    barriers = gpd.read_file(BARRIER_PATH, layer="barriers").to_crs(crs)
    barrier_union = unary_union(barriers.geometry) if len(barriers) else None

    # sample TAZs spanning small/medium/large so the prototype is representative
    utah_taz["acres"] = utah_taz.geometry.area * M2_TO_ACRES
    utah_taz_sorted = utah_taz.sort_values("acres")
    idx = np.linspace(0, len(utah_taz_sorted) - 1, N_SAMPLE_TAZ).astype(int)
    sample = utah_taz_sorted.iloc[idx]

    all_zones = []
    for _, taz_row in sample.iterrows():
        print(f"TAZID {taz_row['TAZID']}: TAZ area {taz_row['acres']:.1f} acres")
        zones = process_taz(taz_row, roads_major, roads_local, landuse, barrier_union, crs)
        print(f"  -> {len(zones)} candidate microzones, "
              f"median {zones['area_acres'].median():.1f} acres")
        all_zones.append(zones)

    result = gpd.GeoDataFrame(pd.concat(all_zones, ignore_index=True), geometry="geometry", crs=crs)
    result.to_file(OUT_PATH, layer="prototype_microzones", driver="GPKG")
    print(f"\nSaved {len(result)} candidate microzones across {len(sample)} sample TAZs to {OUT_PATH}")
    print(result[["TAZID", "area_acres", "land_use"]].describe(include="all"))
