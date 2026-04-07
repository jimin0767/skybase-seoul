import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import folium
from folium.plugins import TimestampedGeoJson
import h3
import branca.colormap as cm
import datetime
import os

def create_skybase_map():
    print("1. Loading V5 SkyBase Data...")
    df = pd.read_csv('data/processed/h3_master_skybase_v6.csv')

    # Compute Demand Score using our new Triangulation Network score
    df['Demand_Score'] = df['Optimal_Triangulation_Score']
    # Add a static time so Folium TimeSlider still renders the geometries
    df['시간'] = 12

    print("2. Formatting Time Data...")
    base_date = pd.to_datetime('2026-03-24')
    df['Timestamp'] = base_date + pd.to_timedelta(df['시간'], unit='h')
    df['Time_Str'] = df['Timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')

    print("3. Generating GeoJSON features... (this might take a moment)")
    features = []
    lat_list, lng_list = [], []

    records = df.to_dict('records')
    
    min_score = df['Demand_Score'].min()
    max_score = df['Demand_Score'].max()
    colormap = cm.LinearColormap(
        colors=['#3182bd', '#e6550d', '#de2d26'],
        vmin=min_score, vmax=max_score, caption='UAM Hub Triangulation Score (0-100)'
    )

    for row in records:
        h3_id = row['H3_ID']
        score = row['Demand_Score']
        is_restricted = row.get('Is_Restricted', 0)
        is_prohibited = row.get('Is_Prohibited', 0)
        
        boundary = h3.cell_to_boundary(h3_id)
        coords = [[[lng, lat] for lat, lng in boundary]]
        
        center_lat, center_lng = h3.cell_to_latlng(h3_id)
        lat_list.append(center_lat)
        lng_list.append(center_lng)

        if is_prohibited == 1:
            fill_color = "black"
            fill_opacity = 0.9
            status_text = "<b style='color:red;'>[PROHIBITED FLIGHT ZONE]</b>"
        elif is_restricted == 1:
            fill_color = "gray"
            fill_opacity = 0.8
            status_text = "<b style='color:orange;'>[RESTRICTED AIRSPACE]</b>"
        else:
            fill_color = colormap(score)
            fill_opacity = 0.6
            status_text = "<b style='color:green;'>[SAFE FLY ZONE]</b>"

        popup_html = f"""
        <div style="font-family: Arial; font-size: 12px; width: 220px;">
            {status_text}<br>
            <b>Triangulation Score:</b> {score:.1f}/100<br>
            <hr>
            <b>Storage Hub Score:</b> {row.get('Storage_Hub_Score', 0):.1f}<br>
            <b>Delivery Hub Score:</b> {row.get('Delivery_HardToReach_Score', 0):.1f}<br>
            <ul>
               <li>F&B: {int(row.get('FNB_Count', 0))}</li>
               <li>Parks: {int(row.get('Park_Count', 0))}</li>
               <li>Open Spaces: {int(row.get('OpenSpace_Count', 0))}</li>
               <li>Hiking: {int(row.get('Hiking_Count', 0))}</li>
               <li>Univ: {int(row.get('Univ_Count', 0))}</li>
               <li>Parking: {int(row.get('Total_Spaces', 0))} ({int(row.get('Parking_Count', 0))} lots)</li>
               <li>Apartments: {int(row.get('Total_Households', 0))} households</li>
               <li>Max Bldg: {row.get('Max_Building_Height', 0):.0f}m</li>
            </ul>
        </div>
        """

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': coords
            },
            'properties': {
                'time': row['Time_Str'],
                'style': {
                    'fillColor': fill_color,
                    'color': 'white', 
                    'weight': 0.5,
                    'fillOpacity': fill_opacity
                },
                'popup': popup_html
            }
        }
        features.append(feature)

    print("4. Rendering Map...")
    map_center = [sum(lat_list)/len(lat_list), sum(lng_list)/len(lng_list)] if lat_list else [37.5665, 126.9780]
    m = folium.Map(location=map_center, zoom_start=11, tiles='CartoDB positron')

    TimestampedGeoJson(
        {'type': 'FeatureCollection', 'features': features},
        period='PT1H',
        add_last_point=False,
        auto_play=False,
        loop=False,
        max_speed=1,
        date_options='YYYY-MM-DD',
        time_slider_drag_update=True
    ).add_to(m)

    colormap.add_to(m)
    
    output_file = 'SkyBase_Map.html'
    m.save(output_file)
    print(f"✅ Map created successfully at {output_file}")

if __name__ == "__main__":
    create_skybase_map()
