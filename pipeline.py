import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import geopandas as gpd
import h3
from pyproj import Transformer
from shapely.geometry import Polygon, Point
import time
import os
import warnings

warnings.filterwarnings("ignore")

def try_read_coords(df, x_cols, y_cols):
    x_col = next((c for c in x_cols if c in df.columns), None)
    y_col = next((c for c in y_cols if c in df.columns), None)
    if not x_col or not y_col:
        return None
        
    df = df.dropna(subset=[x_col, y_col]).copy()
    if df.empty: return None
        
    sample_x = float(df[x_col].iloc[0])
    if sample_x > 1000:
        transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(df[x_col].values, df[y_col].values)
    else:
        lon, lat = df[x_col].values, df[y_col].values
        
    df['lon_4326'] = lon
    df['lat_4326'] = lat
    return df

def run_triangulation_pipeline():
    start_time = time.time()
    print("🚀 Initializing UAM SkyBase Triangulation Pipeline V6...")
    
    # ---------------------------------------------------------
    # [1] Base Population Map (Grid Foundation)
    # ---------------------------------------------------------
    print(">> [1/8] Generating Base H3 Grids from Population...")
    df_pop = pd.read_csv('data/raw/population/250_LOCAL_RESD_20260324.csv', encoding='cp949')
    df_pop['250M격자'] = df_pop['250M격자'].astype(str).str.strip()
    df_pop = df_pop[df_pop['250M격자'].str.len() == 10].copy()
    x_str = df_pop['250M격자'].str[2:6].astype(int)
    y_str = df_pop['250M격자'].str[6:10].astype(int)
    df_pop['X_m'] = 900000 + x_str * 10 + 125
    df_pop['Y_m'] = 1900000 + y_str * 10 + 125
    
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    df_pop['lon'], df_pop['lat'] = transformer.transform(df_pop['X_m'].values, df_pop['Y_m'].values)
    df_pop['H3_ID'] = df_pop.apply(lambda row: h3.latlng_to_cell(row['lat'], row['lon'], 9), axis=1)
    
    base_df = df_pop.groupby('H3_ID', as_index=False)['생활인구합계'].sum()
    
    unique_h3 = pd.DataFrame({'H3_ID': base_df['H3_ID'].unique()})
    unique_h3['geometry'] = unique_h3['H3_ID'].apply(lambda hid: Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(hid)]))
    gdf_h3 = gpd.GeoDataFrame(unique_h3, geometry='geometry', crs="EPSG:4326")

    # ---------------------------------------------------------
    # [2] F&B Commerce
    # ---------------------------------------------------------
    print(">> [2/8] Processing Commerce demand...")
    try:
        df_shop = pd.read_csv('data/raw/commerce/shop_seoul.csv')
        df_shop = df_shop.dropna(subset=['위도', '경도', '상권업종소분류명'])
        df_shop['H3_ID'] = df_shop.apply(lambda row: h3.latlng_to_cell(row['위도'], row['경도'], 9), axis=1)
        base_df = pd.merge(base_df, df_shop.groupby('H3_ID').size().reset_index(name='FNB_Count'), on='H3_ID', how='left')
    except Exception as e:
        print(f"Shop Data Error: {e}")
        
    if 'FNB_Count' not in base_df.columns: base_df['FNB_Count'] = 0
    else: base_df['FNB_Count'] = base_df['FNB_Count'].fillna(0)

    # ---------------------------------------------------------
    # [3] Storage Hub Assets (Parking + Rain Pumps)
    # ---------------------------------------------------------
    print(">> [3/8] Processing Storage Hub Candidates (Idle Lands)...")
    try:
        df_park = try_read_coords(pd.read_csv('data/raw/infrastructure/parking_info.csv'), ['경도'], ['위도'])
        if df_park is not None:
            df_park['H3_ID'] = df_park.apply(lambda r: h3.latlng_to_cell(r['lat_4326'], r['lon_4326'], 9), axis=1)
            park_agg = df_park.groupby('H3_ID').agg(Parking_Count=('H3_ID','count'), Total_Spaces=('주차구획수','sum')).reset_index()
            base_df = pd.merge(base_df, park_agg, on='H3_ID', how='left')
    except: pass
    
    try:
        gdf_pump = gpd.read_file("data/raw/infrastructure/서울시 빗물펌프장 위치 데이터/RAINPUMP.shp", encoding='cp949')
        if gdf_pump.crs is None: gdf_pump.set_crs(epsg=5186, inplace=True)
        joined_pump = gpd.sjoin(gdf_h3, gdf_pump.to_crs(epsg=4326), how='left', predicate='intersects')
        pump_agg = joined_pump.groupby('H3_ID').apply(lambda x: x['index_right'].notnull().sum()).reset_index(name='RainPump_Count')
        base_df = pd.merge(base_df, pump_agg, on='H3_ID', how='left')
    except Exception as e: print(f"Rain Pump Warning: {e}")

    for col in ['Parking_Count', 'Total_Spaces', 'RainPump_Count']:
        if col not in base_df.columns: base_df[col] = 0
        else: base_df[col] = base_df[col].fillna(0)
    
    # 🧮 STORAGE HUB SCORE
    base_df['Storage_Hub_Score'] = (base_df['Parking_Count'] * 0.5) + (base_df['Total_Spaces'] * 0.02) + (base_df['RainPump_Count'] * 10)

    # ---------------------------------------------------------
    # [4] Delivery Hub Hard-To-Reach Data
    # ---------------------------------------------------------
    print(">> [4/8] Processing Hard-to-Reach Features...")
    
    # Elevation Diff (1:5000 contour lines)
    if os.path.exists('data/raw/00_Buseong_starting_point/N3L_F001.shp'):
        gdf_topo = gpd.read_file('data/raw/00_Buseong_starting_point/N3L_F001.shp')
        if gdf_topo.crs is None: gdf_topo.set_crs(epsg=5174, inplace=True)
        joined_topo = gpd.sjoin(gdf_h3, gdf_topo.to_crs(epsg=4326), how='left', predicate='intersects')
        elev_col = 'CONT' if 'CONT' in joined_topo.columns else ('HEIGHT' if 'HEIGHT' in joined_topo.columns else None)
        if elev_col:
            topo_agg = joined_topo.groupby('H3_ID').agg(Max_Elev=(elev_col, 'max'), Min_Elev=(elev_col, 'min')).reset_index()
            topo_agg['Elevation_Diff'] = topo_agg['Max_Elev'] - topo_agg['Min_Elev']
            base_df = pd.merge(base_df, topo_agg[['H3_ID', 'Elevation_Diff']], on='H3_ID', how='left')
            
    # Parks (using Excel file with valid WGS84 coordinates)
    try:
        df_park_nodes = pd.read_excel('data/raw/leisure/서울시 주요 공원현황(2026 상반기).xlsx')
        df_park_nodes = df_park_nodes.dropna(subset=['X좌표(WGS84)', 'Y좌표(WGS84)'])
        df_park_nodes['H3_ID'] = df_park_nodes.apply(
            lambda r: h3.latlng_to_cell(r['Y좌표(WGS84)'], r['X좌표(WGS84)'], 9), axis=1)
        base_df = pd.merge(base_df, df_park_nodes.groupby('H3_ID').size().reset_index(name='Park_Count'), on='H3_ID', how='left')
    except Exception as e: print(f"Park Data Error: {e}")

    # Hiking Trails (multiple zip files in directory)
    try:
        import glob as glob_module
        hike_frames = []
        hike_dir = 'data/raw/leisure/서울시 등산로'
        for zf in glob_module.glob(os.path.join(hike_dir, '*.zip')):
            try:
                gdf_chunk = gpd.read_file(f'zip://{zf}')
                hike_frames.append(gdf_chunk)
            except: pass
        if hike_frames:
            gdf_hike = gpd.GeoDataFrame(pd.concat(hike_frames, ignore_index=True), geometry='geometry')
            if gdf_hike.crs is None: gdf_hike.set_crs(epsg=5186, inplace=True)
            gdf_hike = gdf_hike.to_crs(epsg=4326)
            joined_hike = gpd.sjoin(gdf_h3, gdf_hike, how='inner', predicate='intersects')
            base_df = pd.merge(base_df, joined_hike.groupby('H3_ID').size().reset_index(name='Hiking_Count'), on='H3_ID', how='left')
    except Exception as e: print(f"Hiking Data Error: {e}")
    
    # Universities (pre-geocoded coordinates)
    try:
        df_univ = pd.read_csv('data/raw/education/univ_geocoded.csv')
        df_univ = df_univ.dropna(subset=['lat', 'lon'])
        df_univ['H3_ID'] = df_univ.apply(
            lambda r: h3.latlng_to_cell(r['lat'], r['lon'], 9), axis=1)
        base_df = pd.merge(base_df, df_univ.groupby('H3_ID').size().reset_index(name='Univ_Count'), on='H3_ID', how='left')
    except Exception as e: print(f"University Data Error: {e}")
    
    for col in ['Elevation_Diff', 'Park_Count', 'Hiking_Count', 'Univ_Count']:
        if col not in base_df.columns: base_df[col] = 0
        else: base_df[col] = base_df[col].fillna(0)

    # 🧮 DELIVERY HUB TYPE 1 (Human Hard-to-reach) SCORE
    base_df['Delivery_HardToReach_Score'] = (base_df['Elevation_Diff'] * 2.0) + (base_df['Park_Count'] * 5.0) + (base_df['Hiking_Count'] * 5.0) + (base_df['Univ_Count'] * 8.0)

    # ---------------------------------------------------------
    # [4.5] Apartment Complex Data (Residential Demand + Parking)
    # ---------------------------------------------------------
    print(">> [4.5] Processing Apartment Complex Data...")
    try:
        df_apt = pd.read_csv('data/raw/residential/서울시 공동주택 아파트 정보.csv', encoding='cp949')
        df_apt = df_apt.dropna(subset=['좌표X', '좌표Y'])
        df_apt['k-전체세대수'] = pd.to_numeric(df_apt['k-전체세대수'], errors='coerce').fillna(0)
        df_apt['주차대수'] = pd.to_numeric(df_apt['주차대수'], errors='coerce').fillna(0)
        df_apt['H3_ID'] = df_apt.apply(
            lambda r: h3.latlng_to_cell(r['좌표Y'], r['좌표X'], 9), axis=1)
        apt_agg = df_apt.groupby('H3_ID').agg(
            Apt_Count=('H3_ID', 'count'),
            Total_Households=('k-전체세대수', 'sum'),
            Apt_Parking=('주차대수', 'sum')
        ).reset_index()
        base_df = pd.merge(base_df, apt_agg, on='H3_ID', how='left')
    except Exception as e: print(f"Apartment Data Error: {e}")

    for col in ['Apt_Count', 'Total_Households', 'Apt_Parking']:
        if col not in base_df.columns: base_df[col] = 0
        else: base_df[col] = base_df[col].fillna(0)

    # Update Storage Hub Score with apartment parking
    base_df['Storage_Hub_Score'] = base_df['Storage_Hub_Score'] + (base_df['Apt_Parking'] * 0.005)

    # ---------------------------------------------------------
    # [4.6] UPIS Zoning — Public Open Space Layer
    # ---------------------------------------------------------
    print(">> [4.6] Processing UPIS Open Space Zoning...")
    try:
        gdf_upis = gpd.read_file('data/spatial/UPIS_SHP_ZON216/UPIS_SHP_ZON216.shp')
        gdf_upis = gdf_upis.to_crs(epsg=4326)
        joined_upis = gpd.sjoin(gdf_h3, gdf_upis, how='left', predicate='intersects')
        upis_agg = joined_upis.groupby('H3_ID').apply(
            lambda x: x['index_right'].notnull().sum()).reset_index(name='OpenSpace_Count')
        base_df = pd.merge(base_df, upis_agg, on='H3_ID', how='left')
    except Exception as e: print(f"UPIS Data Error: {e}")

    if 'OpenSpace_Count' not in base_df.columns: base_df['OpenSpace_Count'] = 0
    else: base_df['OpenSpace_Count'] = base_df['OpenSpace_Count'].fillna(0)

    # Update Storage Hub Score with open spaces (potential drone landing zones)
    base_df['Storage_Hub_Score'] = base_df['Storage_Hub_Score'] + (base_df['OpenSpace_Count'] * 3.0)

    # ---------------------------------------------------------
    # [4.7] Building Height Obstruction Profile
    # ---------------------------------------------------------
    print(">> [4.7] Processing Building Heights...")
    try:
        gdf_bldg = gpd.read_file('data/spatial/seoul_buildings.geojson')
        gdf_bldg['height'] = pd.to_numeric(gdf_bldg['height'], errors='coerce')
        gdf_bldg = gdf_bldg[gdf_bldg['height'] > 0]
        if gdf_bldg.crs is None: gdf_bldg.set_crs(epsg=4326, inplace=True)
        joined_bldg = gpd.sjoin(gdf_h3, gdf_bldg[['height', 'geometry']], how='left', predicate='intersects')
        bldg_agg = joined_bldg.groupby('H3_ID').agg(
            Max_Building_Height=('height', 'max'),
            Avg_Building_Height=('height', 'mean'),
            Building_Count=('index_right', lambda x: x.notnull().sum())
        ).reset_index()
        base_df = pd.merge(base_df, bldg_agg, on='H3_ID', how='left')
    except Exception as e: print(f"Building Data Error: {e}")

    for col in ['Max_Building_Height', 'Avg_Building_Height', 'Building_Count']:
        if col not in base_df.columns: base_df[col] = 0
        else: base_df[col] = base_df[col].fillna(0)

    # ---------------------------------------------------------
    # [5] Spatial Triangulation Algorithms (FNB <-> Storage <-> Delivery)
    # ---------------------------------------------------------
    print(">> [5/8] Computing Optimal Triangulation Networks via H3 k_rings...")

    K_RING_SIZE = 4 # roughly 1km operational radius

    base_dict = base_df.set_index('H3_ID').to_dict('index')
    raw_fnb, raw_deliv, raw_pop, raw_storage = [], [], [], []

    for hex_id in base_df['H3_ID']:
        rings = h3.grid_disk(hex_id, K_RING_SIZE)

        fnb_access = 0
        deliv_access = 0
        pop_access = 0

        for ring_hex in rings:
            if ring_hex in base_dict:
                fnb_access += base_dict[ring_hex].get('FNB_Count', 0)
                deliv_access += base_dict[ring_hex].get('Delivery_HardToReach_Score', 0)
                pop_access += base_dict[ring_hex].get('Total_Households', 0)

        storage_score = base_dict[hex_id].get('Storage_Hub_Score', 0)
        raw_fnb.append(fnb_access)
        raw_deliv.append(deliv_access)
        raw_pop.append(pop_access)
        raw_storage.append(storage_score)

    # Min-max normalize each dimension to 0-1
    def minmax(arr):
        mn, mx = min(arr), max(arr)
        return [(v - mn) / (mx - mn) if mx > mn else 0 for v in arr]

    fnb_n = minmax(raw_fnb)
    deliv_n = minmax(raw_deliv)
    pop_n = minmax(raw_pop)
    storage_n = minmax(raw_storage)

    # Weighted additive formula (0-100 scale)
    base_df['Optimal_Triangulation_Score'] = [
        (f * 0.30 + d * 0.25 + p * 0.25 + s * 0.20) * 100
        for f, d, p, s in zip(fnb_n, deliv_n, pop_n, storage_n)
    ]

    # ---------------------------------------------------------
    # [6] Aviation Restrictions & V-World Scenarios
    # ---------------------------------------------------------
    print(">> [6/8] Enforcing Airspace Restrictions (V-World)...")
    def mask_h3(geojson_path):
        try:
            gdf = gpd.read_file(geojson_path)
            if gdf.empty: return set()
            joined = gpd.sjoin(gdf_h3, gdf, how='inner', predicate='intersects')
            return set(joined['H3_ID'].unique())
        except: return set()
        
    restricted_hexes = mask_h3('data/spatial/flight_restricted_zones.geojson')
    prohibited_hexes = mask_h3('data/spatial/flight_prohibited_zones.geojson')
    
    base_df['Is_Restricted'] = base_df['H3_ID'].apply(lambda x: 1 if x in restricted_hexes else 0)
    base_df['Is_Prohibited'] = base_df['H3_ID'].apply(lambda x: 1 if x in prohibited_hexes else 0)
    
    # The Scenarios!
    base_df['Scen_1_No_Restrict'] = True
    base_df['Scen_2_Only_Prohibited'] = base_df['Is_Prohibited'] == 0
    base_df['Scen_3_All_Restricted'] = (base_df['Is_Prohibited'] == 0) & (base_df['Is_Restricted'] == 0)

    # ---------------------------------------------------------
    # [7] Finalize Structure
    # ---------------------------------------------------------
    print(">> [7/8] Saving V6 Architecture...")
    output_path = 'data/processed/h3_master_skybase_v6.csv'
    base_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ V6 Pipeline Complete! Outputs saved to {output_path}")
    print(f"   Columns: {len(base_df.columns)}")
    print(f"   Hexagons: {len(base_df)}")
    nz = (base_df['Optimal_Triangulation_Score'] > 0).sum()
    print(f"   Non-zero Triangulation Scores: {nz} ({nz/len(base_df)*100:.1f}%)")
    print(f"Elapsed Time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    run_triangulation_pipeline()
