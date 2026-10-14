"""Quick test to verify QA setup: API keys, imports, Gemini connectivity."""
import os
from dotenv import load_dotenv

load_dotenv()

print("1. Checking .env file...")
nearmap_key = os.environ.get("NEARMAP_API_KEY")
gemini_key = os.environ.get("GEMINI_API_KEY")

if not nearmap_key:
    print("   ERROR: NEARMAP_API_KEY not found in .env")
else:
    print(f"   ✓ NEARMAP_API_KEY loaded ({len(nearmap_key)} chars)")

if not gemini_key:
    print("   ERROR: GEMINI_API_KEY not found in .env")
else:
    print(f"   ✓ GEMINI_API_KEY loaded ({len(gemini_key)} chars)")

print("\n2. Checking imports...")
try:
    import geopandas as gpd
    import requests
    from google import genai
    from PIL import Image
    from pyproj import Transformer
    print("   ✓ All imports successful")
except ImportError as e:
    print(f"   ERROR: {e}")
    exit(1)

print("\n3. Loading prototype zones...")
try:
    zones = gpd.read_file(r".\Scripts\Outputs\utah_prototype_microzones.gpkg")
    print(f"   ✓ Loaded {len(zones)} zones")
    print(f"     Columns: {list(zones.columns)}")
    print(f"     First zone area: {zones.iloc[0].get('area_acres', 'N/A')} acres")
except Exception as e:
    print(f"   ERROR: {e}")
    exit(1)

print("\n4. Testing Gemini API connectivity...")
try:
    client = genai.Client(api_key=gemini_key)
    # Try a simple text request
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents="Say 'OK' and nothing else.",
        config={"response_mime_type": "text/plain"},
    )
    print(f"   ✓ Gemini API responsive: {response.text.strip()}")
except Exception as e:
    print(f"   ERROR: {e}")
    exit(1)

print("\n5. Testing Nearmap API connectivity...")
try:
    url = f"https://api.nearmap.com/tiles/v3/Vert/19/131052/93830.jpg?apikey={nearmap_key}"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 200:
        print(f"   ✓ Nearmap API responsive (received {len(resp.content)} bytes)")
    else:
        print(f"   ERROR: HTTP {resp.status_code}: {resp.text[:100]}")
except Exception as e:
    print(f"   ERROR: {e}")
    exit(1)

print("\n✓ All setup checks passed! Ready to run full QA script.")
