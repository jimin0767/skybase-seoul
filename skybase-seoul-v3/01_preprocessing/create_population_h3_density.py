"""
서울시 생활인구 데이터 → 행정동 집계 → H3 격자 밀도 레이어 생성

입력:  00_data/LOCAL__/LOCAL_PEOPLE_DONG_*.csv  (월별 12개)
       processed/seoul_boundary.gpkg             (dong 레이어)
출력:  processed/population_h3_density.gpkg
       processed/population_h3_density.csv
       processed/population_hourly_by_dong.parquet
"""

import io
import sys
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon

# ── configuration ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "00_data" / "LOCAL__"
BOUNDARY_PATH = PROJECT_ROOT / "processed" / "seoul_boundary.gpkg"
OUT_DIR = PROJECT_ROOT / "processed"

H3_RES = 9

YOUNG_ACTIVE_COLS = [
    "남자20세부터24세생활인구수", "남자25세부터29세생활인구수",
    "남자30세부터34세생활인구수", "남자35세부터39세생활인구수",
    "남자40세부터44세생활인구수", "남자45세부터49세생활인구수",
    "여자20세부터24세생활인구수", "여자25세부터29세생활인구수",
    "여자30세부터34세생활인구수", "여자35세부터39세생활인구수",
    "여자40세부터44세생활인구수", "여자45세부터49세생활인구수",
]

USE_COLS = ["기준일ID", "시간대구분", "행정동코드", "총생활인구수"] + YOUNG_ACTIVE_COLS

DAYTIME_HOURS = range(10, 18)   # 10:00-17:00
EVENING_HOURS = range(18, 24)   # 18:00-23:00
NIGHT_HOURS   = range(0, 7)     # 00:00-06:00


# ── H3 compatibility helpers ─────────────────────────────────────────────
def _cell_to_boundary(h3_index: str) -> list:
    if hasattr(h3, "cell_to_boundary"):
        return h3.cell_to_boundary(h3_index)
    return h3.h3_to_geo_boundary(h3_index, geo_json=False)


def _h3_polygon(h3_index: str) -> Polygon:
    coords = _cell_to_boundary(h3_index)
    ring = [(lng, lat) for lat, lng in coords]
    ring.append(ring[0])
    return Polygon(ring)


def _geo_to_cells(geojson: dict, res: int) -> set:
    """Polyfill a GeoJSON polygon/multipolygon with H3 cells (v3/v4 compatible)."""
    if hasattr(h3, "geo_to_cells"):
        return h3.geo_to_cells(geojson, res)
    # h3 v3 fallback
    return h3.polyfill_geojson(geojson, res)


# ── H3 grid generation from dong boundaries ──────────────────────────────
def build_dong_h3_grid(boundary_path: Path) -> gpd.GeoDataFrame:
    """Generate H3 cells at res 9 by polyfilling each dong in seoul_boundary.gpkg."""
    dongs = gpd.read_file(boundary_path, layer="dong").to_crs("EPSG:4326")

    rows = []
    for _, row in dongs.dropna(subset=["CSV_ADMI_CD"]).iterrows():
        geojson = row.geometry.__geo_interface__
        cells = _geo_to_cells(geojson, H3_RES)
        adm_cd = str(int(row["CSV_ADMI_CD"]))
        for cell in cells:
            rows.append({
                "h3_index":    cell,
                "CSV_ADMI_CD": adm_cd,
                "ADM_NM":      row["ADM_NM"],
                "GU_NM":       row["GU_NM"],
            })

    grid_df = pd.DataFrame(rows)
    grid_df["geometry"] = grid_df["h3_index"].apply(_h3_polygon)
    return gpd.GeoDataFrame(grid_df, geometry="geometry", crs="EPSG:4326")


# ── IO helpers ───────────────────────────────────────────────────────────
def read_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    # strip stray leading byte (rare BOM variant)
    if raw[0:1] == b"\x3f" and raw[1:2] == b'"':
        raw = raw[1:]
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc,
                               index_col=False, usecols=USE_COLS)
        except (UnicodeDecodeError, KeyError):
            continue
    sys.exit(f"CSV 읽기 실패: {path}")


def load_all_csvs() -> tuple[pd.DataFrame, int, int]:
    files = sorted(DATA_DIR.glob("LOCAL_PEOPLE_DONG_*.csv"))
    if not files:
        sys.exit(f"입력 파일 없음: {DATA_DIR}/LOCAL_PEOPLE_DONG_*.csv")
    print(f"  CSV 파일 {len(files)}개 발견")

    frames = []
    total_rows = 0
    for f in files:
        df = read_csv(f)
        total_rows += len(df)
        frames.append(df)
        print(f"    {f.name}: {len(df):,} rows")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  총 행 수: {total_rows:,}")
    return combined, len(files), total_rows


# ── data cleaning ────────────────────────────────────────────────────────
def clean(df: pd.DataFrame) -> pd.DataFrame:
    df["행정동코드"] = df["행정동코드"].astype(str)
    df["시간대구분"] = pd.to_numeric(df["시간대구분"], errors="coerce").astype("Int64")
    df["총생활인구수"] = pd.to_numeric(df["총생활인구수"], errors="coerce")
    for col in YOUNG_ACTIVE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["총생활인구수", "시간대구분"])
    df["young_active_pop"] = df[YOUNG_ACTIVE_COLS].sum(axis=1)
    return df


# ── aggregation by dong ─────────────────────────────────────────────────
def aggregate_dong(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    hourly = (
        df.groupby(["행정동코드", "시간대구분"])
        .agg(avg_total_pop=("총생활인구수", "mean"),
             young_active_pop=("young_active_pop", "mean"))
        .reset_index()
    )

    avg_total = hourly.groupby("행정동코드")["avg_total_pop"].mean().rename("avg_total_pop")

    daytime = (
        hourly[hourly["시간대구분"].isin(DAYTIME_HOURS)]
        .groupby("행정동코드")["avg_total_pop"].mean().rename("daytime_pop")
    )
    evening = (
        hourly[hourly["시간대구분"].isin(EVENING_HOURS)]
        .groupby("행정동코드")["avg_total_pop"].mean().rename("evening_pop")
    )
    night = (
        hourly[hourly["시간대구분"].isin(NIGHT_HOURS)]
        .groupby("행정동코드")["avg_total_pop"].mean().rename("night_pop")
    )

    peak = hourly.loc[hourly.groupby("행정동코드")["avg_total_pop"].idxmax()]
    peak = peak.set_index("행정동코드")[["시간대구분", "avg_total_pop"]].rename(
        columns={"시간대구분": "peak_hour", "avg_total_pop": "peak_hour_pop"}
    )

    ya = hourly.groupby("행정동코드")["young_active_pop"].mean().rename("young_active_pop")

    dong_agg = (
        avg_total.to_frame()
        .join(daytime).join(evening).join(night)
        .join(peak).join(ya)
        .reset_index()
        .rename(columns={"행정동코드": "CSV_ADMI_CD"})
    )
    dong_agg["peak_hour"] = dong_agg["peak_hour"].astype(int)
    return dong_agg, hourly


# ── H3 layer construction ────────────────────────────────────────────────
def minmax_norm(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    return ((s - lo) / (hi - lo)).round(6)


def build_h3_layer(
    dong_agg: pd.DataFrame, grid: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, int, int]:
    grid = grid.copy()
    grid["CSV_ADMI_CD"] = grid["CSV_ADMI_CD"].astype(str)
    dong_agg = dong_agg.copy()
    dong_agg["CSV_ADMI_CD"] = dong_agg["CSV_ADMI_CD"].astype(str)

    cells_per_dong = grid.groupby("CSV_ADMI_CD").size().rename("h3_cells_in_dong")
    dong_agg = dong_agg.merge(cells_per_dong.reset_index(), on="CSV_ADMI_CD", how="left")

    merged = grid[["h3_index", "CSV_ADMI_CD", "ADM_NM", "GU_NM", "geometry"]].merge(
        dong_agg, on="CSV_ADMI_CD", how="left"
    )

    n_missing = int(merged["avg_total_pop"].isna().sum())

    pop_cols = ["avg_total_pop", "daytime_pop", "evening_pop", "night_pop",
                "peak_hour_pop", "young_active_pop"]
    for c in pop_cols:
        merged[c] = merged[c].fillna(0)
    merged["peak_hour"] = merged["peak_hour"].fillna(0).astype(int)
    merged["h3_cells_in_dong"] = merged["h3_cells_in_dong"].fillna(1).astype(int)

    for src, dst in [
        ("avg_total_pop",   "estimated_h3_pop"),
        ("daytime_pop",     "estimated_h3_daytime_pop"),
        ("evening_pop",     "estimated_h3_evening_pop"),
        ("night_pop",       "estimated_h3_night_pop"),
    ]:
        merged[dst] = (merged[src] / merged["h3_cells_in_dong"]).round(2)

    merged["pop_density_index"]      = minmax_norm(merged["estimated_h3_pop"])
    merged["daytime_pop_index"]      = minmax_norm(merged["estimated_h3_daytime_pop"])
    merged["evening_pop_index"]      = minmax_norm(merged["estimated_h3_evening_pop"])
    merged["night_pop_index"]        = minmax_norm(merged["estimated_h3_night_pop"])
    merged["young_active_pop_index"] = minmax_norm(
        merged["young_active_pop"] / merged["h3_cells_in_dong"]
    )

    n_zero = int((merged["estimated_h3_pop"] == 0).sum())

    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326"), n_missing, n_zero


# ── main ─────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("서울시 생활인구 → H3 밀도 레이어 생성")
    print("=" * 60)

    if not BOUNDARY_PATH.exists():
        sys.exit(f"경계 파일 없음: {BOUNDARY_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Read CSVs
    print("\n[1] CSV 읽기 …")
    df, n_files, n_raw = load_all_csvs()

    # 2) Clean
    print("\n[2] 데이터 정제 …")
    df = clean(df)
    n_dongs = df["행정동코드"].nunique()
    print(f"  유효 행: {len(df):,}  |  행정동: {n_dongs}")

    # 3) Aggregate
    print("\n[3] 행정동 집계 …")
    dong_agg, hourly = aggregate_dong(df)
    print(f"  집계 동 수: {len(dong_agg)}")

    # 4) Save hourly parquet
    print("\n[4] 시간대별 parquet 저장 …")
    hourly_out = hourly.rename(columns={"행정동코드": "CSV_ADMI_CD", "시간대구분": "TIME_CD"})
    hourly_path = OUT_DIR / "population_hourly_by_dong.parquet"
    hourly_out.to_parquet(hourly_path, index=False)
    print(f"  {hourly_path}  ({len(hourly_out):,} rows)")

    # 5) Build H3 grid from dong boundaries
    print("\n[5] H3 격자 생성 (dong 폴리곤 polyfill) …")
    grid = build_dong_h3_grid(BOUNDARY_PATH)
    n_grid = len(grid)
    print(f"  생성된 H3 셀: {n_grid:,}")

    # 6) Build H3 density layer
    print("\n[6] H3 격자 밀도 레이어 생성 …")
    gdf, n_missing, n_zero = build_h3_layer(dong_agg, grid)

    # 7) Save outputs
    print("\n[7] 저장 …")
    gpkg_path = OUT_DIR / "population_h3_density.gpkg"
    csv_path  = OUT_DIR / "population_h3_density.csv"

    gdf.to_file(gpkg_path, layer="population_h3_density", driver="GPKG")

    csv_cols = [c for c in gdf.columns if c != "geometry"]
    gdf[csv_cols].to_csv(csv_path, index=False, encoding="utf-8-sig")

    # ── summary ──────────────────────────────────────────────────────
    est = gdf["estimated_h3_pop"]
    pdi = gdf["pop_density_index"]

    print("\n" + "=" * 60)
    print("완료 요약")
    print("=" * 60)
    print(f"  입력 CSV 파일         : {n_files}")
    print(f"  총 원본 행            : {n_raw:,}")
    print(f"  고유 행정동코드       : {n_dongs}")
    print(f"  출력 H3 셀            : {len(gdf):,}")
    print(f"  인구 누락 셀 (fill전) : {n_missing}")
    print(f"  인구=0 셀   (fill후)  : {n_zero}")
    print(f"  estimated_h3_pop      : min={est.min():.2f}  max={est.max():.2f}  mean={est.mean():.2f}")
    print(f"  pop_density_index     : min={pdi.min():.4f}  max={pdi.max():.4f}  mean={pdi.mean():.4f}")
    print(f"\n  GPKG           : {gpkg_path}")
    print(f"  CSV            : {csv_path}")
    print(f"  시간대 parquet : {hourly_path}")


if __name__ == "__main__":
    main()
