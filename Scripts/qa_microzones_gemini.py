"""
Vision-LLM QA pass: for each candidate microzone, fetch a Nearmap aerial tile
covering its extent, draw the proposed boundary on top, and ask Gemini to flag
zones that look wrong per the project's delineation rules (readme.md).

Secrets: reads NEARMAP_API_KEY and GEMINI_API_KEY from the environment. Never
hardcode keys here.

Run with: conda run -n general_python python Scripts/qa_microzones_gemini.py
"""
import io
import json
import math
import os
import time

import geopandas as gpd
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from pyproj import Transformer

load_dotenv()
NEARMAP_API_KEY = os.environ["NEARMAP_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

ZONES_PATH = r".\Scripts\Outputs\utah_prototype_microzones.gpkg"
OUT_PATH = r".\Scripts\Outputs\utah_qa_results.csv"

TILE_ZOOM = 19  # ~0.3 m/pixel at this latitude; good balance of detail vs. tile count
TILE_URL = "https://api.nearmap.com/tiles/v3/Vert/{z}/{x}/{y}.jpg?apikey={key}"

to_wgs84 = Transformer.from_crs("EPSG:26912", "EPSG:4326", always_xy=True)

QA_PROMPT = """You are reviewing a proposed "microzone" (MAZ) boundary drawn on an aerial
photo, for a travel demand model. Microzones should follow these rules:
- Contain similar land use throughout (residential, commercial, industrial, etc. should
  not be mixed within one zone).
- Be walkable in about 5 minutes -- not too large, and not crossed by a real barrier to
  walking such as a fence, railroad, canal, or freeway.
- Have a simple shape (no donut holes, no unnecessary thin extrusions).

The red outline in the image is the proposed zone boundary. Given the image and the
zone's computed metrics below, decide if this zone needs human review.

Zone metrics: area_acres={area_acres:.1f}, dominant_land_use={land_use}

Respond with ONLY a JSON object matching this schema:
{{"needs_review": bool, "confidence": float (0-1), "issues": [string], "notes": string}}
Valid issue values: "mixed_land_use", "possible_barrier_not_modeled", "bad_shape",
"too_large", "too_small", "other".
"""


def lonlat_to_tile(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x, y, zoom):
    n = 2**zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def fetch_zone_image(zone_geom, zoom=TILE_ZOOM, buffer_ratio=0.15, tile_size=256, max_tiles=64):
    """Fetch and stitch Nearmap tiles covering the zone extent, with boundary drawn on top.
    If zone is too large at current zoom, automatically try lower zoom levels."""
    
    # Auto-reduce zoom if zone too large
    minx, miny, maxx, maxy = zone_geom.bounds
    w, h = maxx - minx, maxy - miny
    minx -= w * buffer_ratio
    maxx += w * buffer_ratio
    miny -= h * buffer_ratio
    maxy += h * buffer_ratio

    lon_min, lat_min = to_wgs84.transform(minx, miny)
    lon_max, lat_max = to_wgs84.transform(maxx, maxy)

    # Try to find appropriate zoom level
    current_zoom = zoom
    while current_zoom >= 15:  # Don't go below zoom 15 (too blurry)
        tx_min, ty_max = lonlat_to_tile(lon_min, lat_min, current_zoom)
        tx_max, ty_min = lonlat_to_tile(lon_max, lat_max, current_zoom)
        
        col_min, col_max = int(math.floor(tx_min)), int(math.floor(tx_max))
        row_min, row_max = int(math.floor(ty_min)), int(math.floor(ty_max))
        
        n_cols = col_max - col_min + 1
        n_rows = row_max - row_min + 1
        n_tiles = n_cols * n_rows
        
        if n_tiles <= max_tiles:
            break  # Found a suitable zoom level
        current_zoom -= 1
    
    if current_zoom < 15:
        raise ValueError(f"Zone too large even at zoom 15: would need {n_cols}x{n_rows} tiles")
    
    # Fetch tiles at the chosen zoom level
    zoom = current_zoom
    mosaic = Image.new("RGB", (n_cols * tile_size, n_rows * tile_size))
    for col in range(col_min, col_max + 1):
        for row in range(row_min, row_max + 1):
            url = TILE_URL.format(z=zoom, x=col, y=row, key=NEARMAP_API_KEY)
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            tile_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            mosaic.paste(tile_img, ((col - col_min) * tile_size, (row - row_min) * tile_size))

    # geographic extent of the stitched mosaic
    mosaic_lon_min, mosaic_lat_max = tile_to_lonlat(col_min, row_min, zoom)
    mosaic_lon_max, mosaic_lat_min = tile_to_lonlat(col_max + 1, row_max + 1, zoom)

    def lonlat_to_px(lon, lat):
        px = (lon - mosaic_lon_min) / (mosaic_lon_max - mosaic_lon_min) * mosaic.width
        py = (lat - mosaic_lat_max) / (mosaic_lat_min - mosaic_lat_max) * mosaic.height
        return px, py

    draw = ImageDraw.Draw(mosaic)
    xs, ys = zone_geom.exterior.coords.xy
    pts = []
    for x, y in zip(xs, ys):
        lon, lat = to_wgs84.transform(x, y)
        pts.append(lonlat_to_px(lon, lat))
    draw.line(pts + [pts[0]], fill=(255, 0, 0), width=4)

    return mosaic


def ask_gemini(client, image, area_acres, land_use, retries=3):
    prompt = QA_PROMPT.format(area_acres=area_acres, land_use=land_use)
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # exponential backoff
                    print(f"    Gemini API rate limited, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
            raise


if __name__ == "__main__":
    print(f"Loading zones from {ZONES_PATH}...")
    zones = gpd.read_file(ZONES_PATH)
    print(f"Loaded {len(zones)} zones")
    
    print(f"Connecting to Gemini API...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"Gemini client created")

    results = []
    for i, row in zones.iterrows():
        print(f"\nProcessing zone {i}...")
        try:
            print(f"  - Fetching Nearmap tiles...")
            img = fetch_zone_image(row.geometry)
            print(f"  - Fetched image, asking Gemini...")
            qa = ask_gemini(client, img, row["area_acres"], row.get("land_use", "unknown"))
            print(f"  - Gemini response: needs_review={qa.get('needs_review')}")
        except Exception as e:
            print(f"  - ERROR: {e}")
            qa = {"needs_review": True, "confidence": 0.0, "issues": ["error"], "notes": str(e)}
        qa["zone_index"] = i
        qa["TAZID"] = row.get("TAZID")
        results.append(qa)
        print(f"  ✓ Zone {i} complete")
        time.sleep(1)  # be polite to the free-tier rate limit

    import pandas as pd

    print(f"\nSaving results to {OUT_PATH}...")
    pd.DataFrame(results).to_csv(OUT_PATH, index=False)
    print(f"✓ Saved QA results for {len(results)} zones to {OUT_PATH}")
