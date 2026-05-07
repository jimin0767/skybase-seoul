import pandas as pd
import geopandas as gpd
import numpy as np
import h3
from shapely.geometry import Polygon
from pathlib import Path

BASE = Path(r"E:\서울시데이터경진대회\Aero-Logic-Seoul")
OUT = BASE / "processed"

# 입력 데이터 로드
# [수정] 행정동 단위가 아닌 H3 단위로 분배된 배달 수요 데이터 로드
demand = pd.read_parquet(OUT / "card_delivery_demand_h3.parquet")
flow_pop = pd.read_parquet(OUT / "flow_pop_agg.parquet")
crosswalk = pd.read_csv(OUT / "admin_code_crosswalk.csv")
seoul = gpd.read_file(OUT / "seoul_boundary.gpkg", layer="dong")

# 행정동 코드 타입을 통일 (문자열)
seoul["CSV_ADMI_CD"] = pd.to_numeric(seoul["CSV_ADMI_CD"], errors="coerce").astype("Int64").astype(str)
demand["admi_cty_no"] = pd.to_numeric(demand["admi_cty_no"], errors="coerce").astype("Int64").astype(str)
flow_pop["CSV_ADMI_CD"] = pd.to_numeric(flow_pop["CSV_ADMI_CD"], errors="coerce").astype("Int64").astype(str)
crosswalk["CSV_ADMI_CD"] = pd.to_numeric(crosswalk["CSV_ADMI_CD"], errors="coerce").astype("Int64").astype(str)
crosswalk["SHP_ADM_CD"] = pd.to_numeric(crosswalk["SHP_ADM_CD"], errors="coerce").astype("Int64").astype(str)

# demand 데이터는 SHP_ADM_CD를 사용하므로 crosswalk를 통해 CSV_ADMI_CD를 병합해 줍니다
# [수정 참고] 아래 과정은 기존 맥락 유지를 위해 남겨둡니다 (이제 H3 기준으로 병합하므로 필수는 아님)
demand = demand.merge(crosswalk[["SHP_ADM_CD", "CSV_ADMI_CD"]], left_on="admi_cty_no", right_on="SHP_ADM_CD", how="left")

if "CSV_ADMI_CD" not in demand.columns:   
    demand = demand.merge(crosswalk[["SHP_ADM_CD", "CSV_ADMI_CD"]], left_on="admi_cty_no", right_on="SHP_ADM_CD", how="left")
print(f"카드 배달수요: {len(demand)} H3 cells") # [수정] 출력 문구 변경 (dongs -> H3 cells)
print(f"유동인구: {len(flow_pop)} dongs")
print(f"행정동 경계: {len(seoul)} dongs")

H3_RES = 9

def h3_cell_to_polygon(h3_index):
    """H3 셀 인덱스를 Shapely Polygon으로 변환"""
    boundary = h3.cell_to_boundary(h3_index)
    # h3 v4는 (lat, lng) 순서로 반환 → Polygon은 (lng, lat) 필요
    return Polygon([(lng, lat) for lat, lng in boundary])

# 성남시 경계 내 H3 셀 생성
city = seoul.dissolve()
city_geojson = city.geometry.iloc[0].__geo_interface__

# geo_to_cells: GeoJSON dict → H3 셀 (h3 v4.4+)
h3_cells = list(h3.geo_to_cells(city_geojson, H3_RES))
print(f"H3 Resolution {H3_RES}: {len(h3_cells)} 셀 생성")

# GeoDataFrame으로 변환
hex_geoms = [h3_cell_to_polygon(h) for h in h3_cells]
hex_centers = [h3.cell_to_latlng(h) for h in h3_cells]

gdf_hex = gpd.GeoDataFrame(
    {
        "h3_index": h3_cells,
        "lat": [c[0] for c in hex_centers],
        "lon": [c[1] for c in hex_centers],
    },
    geometry=hex_geoms,
    crs="EPSG:4326",
)
print(f"그리드 생성 완료: {len(gdf_hex)} hexagons")
gdf_hex.head()


# 헥사곤 중심점 → 행정동 spatial join
hex_centers_gdf = gpd.GeoDataFrame(
    gdf_hex[["h3_index"]],
    geometry=gpd.points_from_xy(gdf_hex["lon"], gdf_hex["lat"]),
    crs="EPSG:4326",
)

hex_dong = gpd.sjoin(hex_centers_gdf, seoul[["CSV_ADMI_CD", "ADM_NM", "GU_NM", "geometry"]],
                     predicate="within", how="left")
hex_dong = hex_dong.drop_duplicates(subset=["h3_index"])
hex_dong = hex_dong.drop(columns=["geometry", "index_right"])

existing_cols = ["CSV_ADMI_CD", "ADM_NM", "GU_NM", "delivery_demand_index", "flow_pop_index"]
gdf_hex = gdf_hex.drop(columns=[c for c in existing_cols if c in gdf_hex.columns])

# gdf_hex에 동 정보 병합
gdf_hex = gdf_hex.merge(hex_dong[["h3_index", "CSV_ADMI_CD", "ADM_NM", "GU_NM"]], on="h3_index", how="left")

# 카드매출 배달수요 병합
# [수정] 행정동(CSV_ADMI_CD) 단위가 아닌 H3 셀(h3_index) 단위로 직접 매핑되도록 변경
gdf_hex = gdf_hex.merge(
    demand[["h3_index", "delivery_demand_index"]],
    on="h3_index", how="left",
)

# 유동인구 지수 병합
gdf_hex = gdf_hex.merge(
    flow_pop[["CSV_ADMI_CD", "flow_pop_index"]],
    on="CSV_ADMI_CD", how="left",
)

print(f"병합 결과: {len(gdf_hex)} hexagons")
print(f"배달수요 null: {gdf_hex['delivery_demand_index'].isna().sum()}")
print(f"유동인구 null: {gdf_hex['flow_pop_index'].isna().sum()}")

# null은 0으로 채움 (경계 밖 헥사곤)
gdf_hex["delivery_demand_index"] = gdf_hex["delivery_demand_index"].fillna(0)
gdf_hex["flow_pop_index"] = gdf_hex["flow_pop_index"].fillna(0)

# 종합 배송 시급도 지수
gdf_hex["urgency"] = (
    0.6 * gdf_hex["delivery_demand_index"]
    + 0.4 * gdf_hex["flow_pop_index"]
)

print(f"배송 시급도 지수 통계:")
print(gdf_hex["urgency"].describe())
print(f"\n상위 10 셀:")
top = gdf_hex.nlargest(10, "urgency")
print(top[["h3_index", "ADM_NM", "urgency", "delivery_demand_index", "flow_pop_index"]])


import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(1, 1, figsize=(10, 10))

# 행정동 경계
seoul.boundary.plot(ax=ax, color="gray", linewidth=0.5)

# 히트맵
gdf_hex.plot(
    ax=ax, column="urgency", cmap="YlOrRd", legend=True,
    alpha=0.7, edgecolor="none",
    legend_kwds={"label": "배송 시급도 지수", "shrink": 0.6},
)

ax.set_title("서울시 배송 시급도 히트맵 (Baseline Layer)", fontsize=14)
ax.set_axis_off()
plt.tight_layout()
plt.show()