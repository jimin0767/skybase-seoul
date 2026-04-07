import requests
import json
import os
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

API_KEY = "CA689AF7-5C7C-37D4-8973-372AEA113858"
DOMAIN = "http://localhost"
BASE_URL = "https://api.vworld.kr/req/wfs"

# Seoul Bounding Box
SEOUL_BBOX = (126.76, 37.42, 127.18, 37.70)
GRID_SIZE = 0.05  # Chunking to bypass API max feature limits (0.05 deg ~ 5km)

def fetch_layer_chunk(layer_name, minx, miny, maxx, maxy):
    """Fetches a specific spatial bounding box chunk from V-World WFS."""
    params = {
        'key': API_KEY,
        'domain': DOMAIN,
        'SERVICE': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'TYPENAME': layer_name,
        'output': 'application/json',
        'srsname': 'EPSG:4326',
        'bbox': f'{minx},{miny},{maxx},{maxy}',
        'maxFeatures': 1000
    }
    
    try:
        res = requests.get(BASE_URL, params=params, verify=False, timeout=30)
        res.raise_for_status()
        data = res.json()
        if 'features' in data:
            return data['features']
    except Exception as e:
        print(f"Error fetching chunk {minx},{miny}: {e}")
    return []

def fetch_all_seoul(layer_name, save_path):
    """Chunks the Seoul geometry and fetches spatial data concurrently."""
    print(f"Starting map fetch for {layer_name} over Seoul...")
    all_features = []
    
    chunks = []
    x = SEOUL_BBOX[0]
    while x < SEOUL_BBOX[2]:
        y = SEOUL_BBOX[1]
        while y < SEOUL_BBOX[3]:
            chunks.append((x, y, x + GRID_SIZE, y + GRID_SIZE))
            y += GRID_SIZE
        x += GRID_SIZE
        
    print(f"Total chunks to fetch: {len(chunks)}")
    
    # Use ThreadPoolExecutor to speed up pagination API requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_chunk = {executor.submit(fetch_layer_chunk, layer_name, *chunk): chunk for chunk in chunks}
        
        for i, future in enumerate(as_completed(future_to_chunk)):
            features = future.result()
            if features:
                all_features.extend(features)
            print(f"Processed chunk {i+1}/{len(chunks)} - Found {len(features)} features. Total so far: {len(all_features)}")
            
    # Deduplicate features by ID (since grids can overlap boundaries)
    unique_features = {f['id']: f for f in all_features if 'id' in f}.values()
    
    geojson = {
        "type": "FeatureCollection",
        "features": list(unique_features)
    }
    
    # Save the resulting massive GeoJSON to disk
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)
        
    print(f"✅ Saved {len(unique_features)} total features to {save_path}\n")

if __name__ == "__main__":
    # 1. Fetch Airspace / Restricted Zones
    # lt_c_ais_prhc = 비행제한구역 (Flight Restricted Zones)
    fetch_all_seoul("lt_c_ais_prhc", "data/spatial/flight_restricted_zones.geojson")
    
    # lt_c_ais_fuz = 비행금지구역 (Flight Prohibited Zones - Absolute no fly)
    fetch_all_seoul("lt_c_ais_fuz", "data/spatial/flight_prohibited_zones.geojson")
    
    # 2. Fetch Building Footprints & Heights
    # lt_c_bldginfo = 건물통합정보 (Building spatial info including heights)
    fetch_all_seoul("lt_c_bldginfo", "data/spatial/seoul_buildings.geojson") 
