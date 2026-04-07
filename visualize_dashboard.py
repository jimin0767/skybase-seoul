import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import folium
import h3
import branca.colormap as cm
import os

def create_interactive_dashboard():
    print("1. Loading V5 SkyBase Data...")
    df = pd.read_csv('data/processed/h3_master_skybase_v6.csv')

    print("2. Setting up Map & Dashboard UI...")
    map_center = [37.5665, 126.9780]
    m = folium.Map(location=map_center, zoom_start=11, tiles='CartoDB positron', prefer_canvas=True)

    # Main Base Heatmap
    min_score = df['Optimal_Triangulation_Score'].min()
    max_score = df['Optimal_Triangulation_Score'].max()
    colormap = cm.LinearColormap(
        colors=['#3182bd', '#e6550d', '#de2d26'],
        vmin=min_score, vmax=max_score, caption='[SCORE] UAM Hub Triangulation Efficiency'
    )
    colormap.add_to(m)

    # Initialize Feature Groups for check-box layer controls
    # Triangulation Heatmap (Base layer technically, but as a feature group so it can be toggled)
    fg_heatmap = folium.FeatureGroup(name="🧲 [Base] Triangulation Heatmap", show=True)
    
    # Airspace Constraints
    fg_prohibited = folium.FeatureGroup(name="⚠️ [제한] 비행 금지 구역 (Prohibited)", show=False)
    fg_restricted = folium.FeatureGroup(name="⚠️ [제한] 비행 제한 구역 (Restricted)", show=False)
    
    # Storage Constraints
    fg_parking = folium.FeatureGroup(name="🅿️ [Storage] 유휴공간 - 공영 주차장", show=False)
    fg_pump = folium.FeatureGroup(name="💧 [Storage] 유휴공간 - 빗물 펌프장", show=False)
    
    # Delivery Constraints
    fg_parks = folium.FeatureGroup(name="🌳 [Delivery] 공공장소 - 공원", show=False)
    fg_univ = folium.FeatureGroup(name="🏫 [Delivery] 공공장소 - 대학교", show=False)
    fg_hiking = folium.FeatureGroup(name="⛰️ [Delivery] 배달소외 - 등산로", show=False)
    fg_slope = folium.FeatureGroup(name="📉 [Delivery] 배달소외 - 고경사지", show=False)
    
    # Demand
    fg_fnb = folium.FeatureGroup(name="🍔 [Demand] 배달/상권 밀집지", show=False)
    fg_apartments = folium.FeatureGroup(name="🏢 [Demand] 아파트 단지", show=False)
    fg_openspace = folium.FeatureGroup(name="🌿 [Storage] UPIS 공공공간", show=False)
    fg_buildings = folium.FeatureGroup(name="🏗️ [Constraint] 건물 고도 50m+", show=False)

    print("3. Generating Interactive Layers... (This may take a minute)")

    # Iterating through H3 hexes and adding them to the corresponding groups
    for _, row in df.iterrows():
        h3_id = row['H3_ID']
        boundary = h3.cell_to_boundary(h3_id)
        
        # Build strict HTML Popup
        popup_html = f"""
        <div style="font-family: Arial; font-size: 11px; width: 250px;">
            <b>Triangulation Score:</b> {row['Optimal_Triangulation_Score']:.1f}/100<br>
            <hr>
            <b>Storage Hub Score:</b> {row.get('Storage_Hub_Score', 0):.1f}<br>
            <b>Delivery Hub Score:</b> {row.get('Delivery_HardToReach_Score', 0):.1f}<br>
            <ul>
               <li>F&B Shops: {int(row.get('FNB_Count', 0))}</li>
               <li>Parks: {int(row.get('Park_Count', 0))}</li>
               <li>Open Spaces: {int(row.get('OpenSpace_Count', 0))}</li>
               <li>Hiking: {int(row.get('Hiking_Count', 0))}</li>
               <li>University: {int(row.get('Univ_Count', 0))}</li>
               <li>Elevation Diff: {row.get('Elevation_Diff', 0):.1f}m</li>
               <li>Parking: {int(row.get('Total_Spaces', 0))} ({int(row.get('Parking_Count', 0))} lots)</li>
               <li>Apartments: {int(row.get('Total_Households', 0))} households</li>
               <li>Max Bldg Height: {row.get('Max_Building_Height', 0):.0f}m</li>
            </ul>
        </div>
        """
        
        def add_poly(fg, color, opacity):
            p = folium.Polygon(
                locations=boundary,
                color="white", weight=0.3,
                fill=True, fill_color=color, fill_opacity=opacity
            )
            folium.Popup(popup_html, max_width=300).add_to(p)
            p.add_to(fg)

        # Base Triangulation Map
        score = row['Optimal_Triangulation_Score']
        add_poly(fg_heatmap, colormap(score), 0.6)
        
        # Add to Layers if conditions met
        if row.get('Is_Prohibited', 0) == 1:
            add_poly(fg_prohibited, "black", 0.9)
        elif row.get('Is_Restricted', 0) == 1:
            add_poly(fg_restricted, "gray", 0.7)
            
        if row.get('Parking_Count', 0) > 0:
            add_poly(fg_parking, "#1E90FF", 0.7) # DodgerBlue
        if row.get('RainPump_Count', 0) > 0:
            add_poly(fg_pump, "#00FFFF", 0.7) # Cyan
            
        if row.get('Park_Count', 0) > 0:
            add_poly(fg_parks, "#32CD32", 0.7) # Green
        if row.get('Univ_Count', 0) > 0:
            add_poly(fg_univ, "#8A2BE2", 0.7) # Purple
        if row.get('Hiking_Count', 0) > 0:
            add_poly(fg_hiking, "#8B4513", 0.7) # Brown
        if row.get('Elevation_Diff', 0) > 30: 
            add_poly(fg_slope, "#FF4500", 0.7) # OrangeRed
            
        if row.get('FNB_Count', 0) > 10:
            add_poly(fg_fnb, "#FFD700", 0.7) # Gold
        if row.get('Total_Households', 0) > 0:
            add_poly(fg_apartments, "#FF69B4", 0.7) # HotPink
        if row.get('OpenSpace_Count', 0) > 0:
            add_poly(fg_openspace, "#7CFC00", 0.7) # LawnGreen
        if row.get('Max_Building_Height', 0) > 50:
            add_poly(fg_buildings, "#FF6347", 0.6) # Tomato

    print("4. Finalizing Map Render...")
    # Add Feature Groups to Map
    fg_heatmap.add_to(m)
    fg_prohibited.add_to(m)
    fg_restricted.add_to(m)
    fg_parking.add_to(m)
    fg_pump.add_to(m)
    fg_parks.add_to(m)
    fg_univ.add_to(m)
    fg_hiking.add_to(m)
    fg_slope.add_to(m)
    fg_fnb.add_to(m)
    fg_apartments.add_to(m)
    fg_openspace.add_to(m)
    fg_buildings.add_to(m)

    # ADD THE LAYER CONTROL MENU (Bottom Right)
    folium.LayerControl(position='bottomright', collapsed=False).add_to(m)

    output_file = 'SkyBase_Dashboard.html'
    m.save(output_file)
    print(f"✅ Dynamic Dashboard generated successfully at {output_file}")

if __name__ == "__main__":
    create_interactive_dashboard()
