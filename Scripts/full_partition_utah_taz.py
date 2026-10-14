"""
Full-scale run: constrained partitioning of ALL developed Utah County TAZs into
candidate microzones. Same algorithm as Scripts/prototype_partition_utah_taz.py,
generalized to the whole county and written out in a schema compatible with the
existing Microzones_DRAFT tracker (for staged review, not overwriting the tracked
draft).

Run with: conda run -n general_python python Scripts/full_partition_utah_taz.py
"""
import time

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.ops import polygonize, unary_union
from sklearn.cluster import KMeans

TAZ_PATH = r".\_Utah\Inputs\TAZ.shp"
ROADS_MAJOR = r".\_Utah\Inputs\Major_Roads_WF.shp"
ROADS_LOCAL = r".\_Utah\Inputs\Local_Roads_WF.shp"
LANDUSE_PATH = r".\_Utah\Inputs\land_use_dissolved_49.shp"
BARRIER_PATH = r".\Scripts\Outputs\utah_barrier_candidates.gpkg"
OUT_PATH = r".\Scripts\Outputs\utah_full_auto_microzones.gpkg"

TARGET_ACRES_MEDIAN = 28.0
TARGET_ACRES_MIN = 10.0
TARGET_ACRES_MAX = 90.0
M2_TO_ACRES = 0.000247105

# TAZs with essentially no development don't need microzones (matches existing practice
# of leaving rural/external TAZs as a single MAZ).
MIN_DEVACRES = 1.0
# Skip partitioning huge background/external TAZs even if DEVACRES is nonzero/missing data.
MAX_TAZ_ACRES = 5000.0


def build_elementary_blocks(taz_geom, roads_gdf, crs):
    roads_clip = roads_gdf.clip(taz_geom)
    lines = [taz_geom.boundary] + list(roads_clip.geometry)
    merged = unary_union(lines)
    blocks = list(polygonize(merged))
    blocks_gdf = gpd.GeoDataFrame(geometry=blocks, crs=crs)
    blocks_gdf = blocks_gdf[blocks_gdf.geometry.representative_point().within(taz_geom.buffer(1))]
    blocks_gdf = blocks_gdf[blocks_gdf.geometry.area > 10].reset_index(drop=True)
    return blocks_gdf


def tag_dominant_landuse(blocks_gdf, landuse_sindex_gdf):
    # clip land use to this TAZ's extent first -- keeps the overlay cheap at full scale
    bounds = blocks_gdf.total_bounds
    candidates = list(landuse_sindex_gdf.sindex.intersection(bounds))
    local_landuse = landuse_sindex_gdf.iloc[candidates]
    if len(local_landuse) == 0:
        blocks_gdf["land_use"] = "unknown"
        return blocks_gdf

    inter = gpd.overlay(
        blocks_gdf.reset_index().rename(columns={"index": "block_id"}),
        local_landuse[["land_use", "geometry"]],
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


def process_taz(taz_row, roads, landuse, barrier_union, crs):
    taz_geom = taz_row.geometry
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
    t0 = time.time()
    taz = gpd.read_file(TAZ_PATH)
    utah_taz = taz[taz["CO_FIPS"] == 49].copy()
    crs = utah_taz.crs
    utah_taz["acres"] = utah_taz.geometry.area * M2_TO_ACRES

    roads = gpd.GeoDataFrame(
        pd.concat(
            [
                gpd.read_file(ROADS_MAJOR).to_crs(crs)[["geometry"]],
                gpd.read_file(ROADS_LOCAL).to_crs(crs)[["geometry"]],
            ],
            ignore_index=True,
        ),
        crs=crs,
    )
    landuse = gpd.read_file(LANDUSE_PATH).to_crs(crs)
    barriers = gpd.read_file(BARRIER_PATH, layer="barriers").to_crs(crs)
    barrier_union = unary_union(barriers.geometry) if len(barriers) else None

    # skip huge background/external TAZs and TAZs with ~no development
    devacres = utah_taz["DEVACRES"] if "DEVACRES" in utah_taz.columns else None
    to_process = utah_taz[utah_taz["acres"] <= MAX_TAZ_ACRES].copy()
    skipped_huge = utah_taz[utah_taz["acres"] > MAX_TAZ_ACRES].copy()
    if devacres is not None:
        skipped_no_dev = to_process[to_process["DEVACRES"].fillna(0) < MIN_DEVACRES]
        to_process = to_process[to_process["DEVACRES"].fillna(0) >= MIN_DEVACRES]
    else:
        skipped_no_dev = to_process.iloc[0:0]

    print(f"Total Utah County TAZs: {len(utah_taz)}")
    print(f"  Skipped (background/huge, >{MAX_TAZ_ACRES:.0f} ac): {len(skipped_huge)}")
    print(f"  Skipped (no development): {len(skipped_no_dev)}")
    print(f"  To partition: {len(to_process)}")

    all_zones = []
    n = len(to_process)
    for k, (_, taz_row) in enumerate(to_process.iterrows(), start=1):
        zones = process_taz(taz_row, roads, landuse, barrier_union, crs)
        all_zones.append(zones)
        if k % 50 == 0 or k == n:
            elapsed = time.time() - t0
            print(f"  [{k}/{n}] processed, elapsed {elapsed:.0f}s")

    # pass through skipped TAZs as single zones so every TAZ has coverage
    for _, taz_row in pd.concat([skipped_huge, skipped_no_dev]).iterrows():
        z = gpd.GeoDataFrame(
            {"land_use": ["unknown"], "TAZID": [taz_row["TAZID"]]},
            geometry=[taz_row.geometry],
            crs=crs,
        )
        z["area_acres"] = z.geometry.area * M2_TO_ACRES
        all_zones.append(z)

    result = gpd.GeoDataFrame(pd.concat(all_zones, ignore_index=True), geometry="geometry", crs=crs)
    result["zone_id"] = range(1, len(result) + 1)
    result["CO_FIPS"] = 49
    result["Status"] = 0  # unreviewed -- matches existing tracker convention
    result["MAZ_NOTE"] = "auto-generated candidate, not yet reviewed"

    result.to_file(OUT_PATH, layer="microzones_auto", driver="GPKG")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed/60:.1f} min. Saved {len(result)} candidate microzones "
          f"across {len(utah_taz)} Utah County TAZs to {OUT_PATH}")
    print(result["area_acres"].describe())
