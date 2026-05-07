import pandas as pd
import numpy as np
import os
from pathlib import Path
try:
    import h3
except ImportError:
    pass # Will be imported later or handled


# 1. Load Data
print("Loading Survey Data...")
df_survey = pd.read_excel(r"c:\Users\박부성\Desktop\상권\[데이터] 2024 외식업체 경영실태 조사.xlsx")
if df_survey.iloc[0]['업종'] == 'UPJONG':
    df_survey = df_survey.iloc[1:]

print("Loading Sales Data...")
try:
    df_sales = pd.read_csv(r"c:\Users\박부성\Desktop\상권\서울시 상권분석서비스(추정매출-행정동)_2024년.csv", encoding='euc-kr')
except:
    df_sales = pd.read_csv(r"c:\Users\박부성\Desktop\상권\서울시 상권분석서비스(추정매출-행정동)_2024년.csv", encoding='utf-8')

OUT = Path(r"c:\Users\박부성\Desktop\상권\processed")
OUT.mkdir(exist_ok=True)

# 2. Map Industry Categories
csv_to_excel_mapping = {
    '한식음식점': [1, 2, 3, 4],
    '일식음식점': [6],
    '양식음식점': [7],
    '제과점': [11],
    '치킨전문점': [13],
    '분식전문점': [14],
    '호프-간이주점': [15, 16, 17],
    '커피-음료': [18, 19],
    '중식음식점': [5],
    '패스트푸드점': [12]
}

del_col = 'B20. 총 매출액 대비 판매유형별 비중(배달)(%)'
df_survey[del_col] = pd.to_numeric(df_survey[del_col], errors='coerce').fillna(0)

delivery_ratios = {}
for csv_cat, excel_cats in csv_to_excel_mapping.items():
    cond_seoul = df_survey['A4. 사업장 주소(시도)'] == '서울'
    cond_ind = df_survey['업종'].isin(excel_cats)
    mean_seoul = df_survey[cond_seoul & cond_ind][del_col].mean()
    if pd.isna(mean_seoul):
        mean_nat = df_survey[cond_ind][del_col].mean()
        ratio = mean_nat / 100.0 if not pd.isna(mean_nat) else 0.0
    else:
        ratio = mean_seoul / 100.0
    delivery_ratios[csv_cat] = ratio

# 3. Process Seoul Data into Hour-based long format
print("Transforming Seoul data into long format...")
# Time periods and hour mapping
time_map = {
    '00~06': 1,
    '06~11': 2,
    '11~14': 3,
    '14~17': 4,
    '17~21': 5,
    '21~24': 6
}

# Unpivot the data for amounts and counts
dfs = []
for t_str, h_idx in time_map.items():
    amt_col = f'시간대_{t_str}_매출_금액'
    # handle typo in the csv columns
    cnt_col = f'시간대_건수~{t_str.split("~")[1]}_매출_건수'
    if cnt_col not in df_sales.columns:
        cnt_col = amt_col.replace('금액', '건수') # fallback
        if cnt_col == '시간대_00~06_매출_건수' and '시간대_건수~06_매출_건수' in df_sales.columns:
            cnt_col = '시간대_건수~06_매출_건수'
            
    # Sub-dataframe for this hour
    df_h = df_sales[['행정동_코드', '서비스_업종_코드_명', '기준_년분기_코드', amt_col, cnt_col]].copy()
    df_h['hour'] = h_idx
    df_h.rename(columns={
        '행정동_코드': 'admi_cty_no',
        '서비스_업종_코드_명': 'card_tpbuz_nm_1',
        '기준_년분기_코드': 'ym',
        amt_col: 'total_amt',
        cnt_col: 'total_cnt'
    }, inplace=True)
    dfs.append(df_h)

df_long = pd.concat(dfs, ignore_index=True)
df_long['ym'] = df_long['ym'].astype(str)

# 행정동 코드 매핑 (CSV_ADMI_CD -> SHP_ADM_CD)
print("Mapping Admin Codes...")
cw = pd.read_csv(r"c:\Users\박부성\Desktop\상권\admin_code_crosswalk.csv")
csv_to_shp = dict(zip(cw['CSV_ADMI_CD'], cw['SHP_ADM_CD']))
df_long['admi_cty_no'] = df_long['admi_cty_no'].map(csv_to_shp)
df_long.dropna(subset=['admi_cty_no'], inplace=True)
df_long['admi_cty_no'] = df_long['admi_cty_no'].astype(int)

# Save card_sales_agg.parquet
df_sales_agg = df_long.groupby(['admi_cty_no', 'card_tpbuz_nm_1', 'hour', 'ym']).agg(
    total_amt=('total_amt', 'sum'),
    total_cnt=('total_cnt', 'sum')
).reset_index()

# 기존 성남 파이프라인과 동일한 컬럼 순서로 맞춤
df_sales_agg = df_sales_agg[['admi_cty_no', 'card_tpbuz_nm_1', 'hour', 'total_amt', 'total_cnt', 'ym']]

df_sales_agg.to_parquet(OUT / "card_sales_agg.parquet", index=False)
print(f"Saved card_sales_agg.parquet ({len(df_sales_agg)} rows)")

# 4. Calculate Delivery Demand
print("Calculating Delivery Demand...")
df_del = df_sales_agg[df_sales_agg['card_tpbuz_nm_1'].isin(csv_to_excel_mapping.keys())].copy()
df_del['delivery_ratio'] = df_del['card_tpbuz_nm_1'].map(delivery_ratios).fillna(0)
df_del['del_amt'] = df_del['total_amt'] * df_del['delivery_ratio']
df_del['del_cnt'] = df_del['total_cnt'] * df_del['delivery_ratio']

# Hourly weights for Seoul (1-6)
# 1: 00~06 (0.5), 2: 06~11 (0.5), 3: 11~14 (1.0), 4: 14~17 (0.8), 5: 17~21 (1.2), 6: 21~24 (1.0)
HOUR_WEIGHTS = {1: 0.5, 2: 0.5, 3: 1.0, 4: 0.8, 5: 1.2, 6: 1.0}
df_del['hour_weight'] = df_del['hour'].map(HOUR_WEIGHTS)
df_del['weighted_amt'] = df_del['del_amt'] * df_del['hour_weight']

# Aggregate by Dong
# Assume 1 quarter data or full year data is sum, the notebook divides by 12 for avg_monthly
# Since we have YearQuarter strings (e.g. 20241), let's see how many quarters. 
n_quarters = df_del['ym'].nunique()
n_months = n_quarters * 3

demand_by_dong = df_del.groupby("admi_cty_no").agg(
    avg_monthly_del_amt=("del_amt", lambda x: x.sum() / n_months),
    avg_monthly_del_cnt=("del_cnt", lambda x: x.sum() / n_months),
    avg_monthly_weighted_amt=("weighted_amt", lambda x: x.sum() / n_months)
).reset_index()

# 0-1 Normalization
for col in ["avg_monthly_del_amt", "avg_monthly_del_cnt", "avg_monthly_weighted_amt"]:
    vmin, vmax = demand_by_dong[col].min(), demand_by_dong[col].max()
    demand_by_dong[f"{col}_norm"] = (demand_by_dong[col] - vmin) / (vmax - vmin) if vmax > vmin else 0

# Delivery Demand Index
demand_by_dong["delivery_demand_index"] = (
    0.6 * demand_by_dong["avg_monthly_weighted_amt_norm"]
    + 0.4 * demand_by_dong["avg_monthly_del_cnt_norm"]
)

demand_by_dong.to_parquet(OUT / "card_delivery_demand_dong.parquet", index=False)
print(f"Saved card_delivery_demand_dong.parquet ({len(demand_by_dong)} rows)")

# =============================================================================
# 4.5. Distribute Demand to H3 Cells using Store Data
# =============================================================================
print("Distributing Demand to H3 Cells using Store Data...")
stores_file = r"e:\서울시데이터경진대회\Aero-Logic-Seoul\00_data\소상공인시장진흥공단_상가(상권)정보_서울_202603.csv"
try:
    df_stores = pd.read_csv(stores_file, usecols=['상권업종대분류명', '행정동코드', '경도', '위도'], encoding='utf-8')
except UnicodeDecodeError:
    df_stores = pd.read_csv(stores_file, usecols=['상권업종대분류명', '행정동코드', '경도', '위도'], encoding='cp949')

# 음식점만 필터링 (배달 수요 기준이므로)
df_stores = df_stores[df_stores['상권업종대분류명'] == '음식'].copy()
df_stores.dropna(subset=['위도', '경도'], inplace=True)

# 행정동코드 매핑 (CSV_ADMI_CD -> SHP_ADM_CD)
df_stores['admi_cty_no'] = df_stores['행정동코드'].map(csv_to_shp)
df_stores.dropna(subset=['admi_cty_no'], inplace=True)
df_stores['admi_cty_no'] = df_stores['admi_cty_no'].astype(int)

# H3 Index 변환 (Resolution 9)
def get_h3(row):
    try:
        return h3.latlng_to_cell(row['위도'], row['경도'], 9)
    except AttributeError:
        return h3.geo_to_h3(row['위도'], row['경도'], 9)

df_stores['h3_index'] = df_stores.apply(get_h3, axis=1)

# 행정동별 전체 상권(음식점) 수
stores_by_dong = df_stores.groupby('admi_cty_no').size().reset_index(name='dong_total_stores')
# 행정동 내 H3별 상권(음식점) 수
stores_by_h3 = df_stores.groupby(['admi_cty_no', 'h3_index']).size().reset_index(name='h3_stores')

# 비율 계산
stores_by_h3 = pd.merge(stores_by_h3, stores_by_dong, on='admi_cty_no', how='left')
stores_by_h3['store_ratio'] = stores_by_h3['h3_stores'] / stores_by_h3['dong_total_stores']

# 배달 수요 분배
demand_h3 = pd.merge(stores_by_h3, demand_by_dong[['admi_cty_no', 'avg_monthly_del_amt', 'avg_monthly_del_cnt', 'avg_monthly_weighted_amt']], on='admi_cty_no', how='inner')

for col in ["avg_monthly_del_amt", "avg_monthly_del_cnt", "avg_monthly_weighted_amt"]:
    demand_h3[col] = demand_h3[col] * demand_h3["store_ratio"]

# H3 레벨에서 다시 0-1 정규화 및 Index 산출
for col in ["avg_monthly_del_amt", "avg_monthly_del_cnt", "avg_monthly_weighted_amt"]:
    vmin, vmax = demand_h3[col].min(), demand_h3[col].max()
    demand_h3[f"{col}_norm"] = (demand_h3[col] - vmin) / (vmax - vmin) if vmax > vmin else 0

demand_h3["delivery_demand_index"] = (
    0.6 * demand_h3["avg_monthly_weighted_amt_norm"]
    + 0.4 * demand_h3["avg_monthly_del_cnt_norm"]
)

demand_h3.to_parquet(OUT / "card_delivery_demand_h3.parquet", index=False)
print(f"Saved card_delivery_demand_h3.parquet ({len(demand_h3)} rows)")


# 5. Hourly Demand by Dong
hourly_demand = df_del.groupby(["admi_cty_no", "hour"]).agg(
    total_del_amt=("del_amt", "sum"),
    total_del_cnt=("del_cnt", "sum")
).reset_index()

dong_totals = hourly_demand.groupby("admi_cty_no")["total_del_amt"].transform("sum")
hourly_demand["hour_ratio"] = hourly_demand["total_del_amt"] / dong_totals

hourly_demand.to_parquet(OUT / "card_hourly_demand.parquet", index=False)
print(f"Saved card_hourly_demand.parquet ({len(hourly_demand)} rows)")
print("Done!")
