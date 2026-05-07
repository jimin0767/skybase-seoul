"""
상가(상권) 정보 CSV → H3 격자별 업종 카운트 GeoPackage 생성

입력:  00_data/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv
출력:  processed/store_h3_industry_counts_<level>.gpkg
       processed/store_h3_industry_counts_<level>_long.csv
"""

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon

# ── configuration ────────────────────────────────────────────────────────
INDUSTRY_LEVEL = "large"  # "large" | "middle" | "small"

H3_RES = 9

LEVEL_MAP = {
    "large": "상권업종대분류명",
    "middle": "상권업종중분류명",
    "small": "상권업종소분류명",
}

# ── paths (project-relative) ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = (
    PROJECT_ROOT
    / "00_data"
    / "소상공인시장진흥공단_상가(상권)정보_서울_202603.csv"
)
BASE_GRID_PATH = PROJECT_ROOT / "processed" / "delivery_urgency_grid.gpkg"

USE_COLS = [
    "상가업소번호",
    "상권업종대분류명",
    "상권업종중분류명",
    "상권업종소분류명",
    "행정동코드",
    "행정동명",
    "경도",
    "위도",
]

LON_MIN, LON_MAX = 126.7, 127.2
LAT_MIN, LAT_MAX = 37.4, 37.7


# ── H3 compatibility helpers ────────────────────────────────────────────
def _latlng_to_cell(lat: float, lng: float, res: int) -> str:
    if hasattr(h3, "latlng_to_cell"):
        return h3.latlng_to_cell(lat, lng, res)
    return h3.geo_to_h3(lat, lng, res)


def _cell_to_boundary(h3_index: str) -> list:
    if hasattr(h3, "cell_to_boundary"):
        return h3.cell_to_boundary(h3_index)
    return h3.h3_to_geo_boundary(h3_index, geo_json=False)


def _h3_polygon(h3_index: str) -> Polygon:
    coords = _cell_to_boundary(h3_index)
    ring = [(lng, lat) for lat, lng in coords]
    ring.append(ring[0])
    return Polygon(ring)


# ── IO helpers ───────────────────────────────────────────────────────────
def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "cp949"):
        try:
            return pd.read_csv(path, usecols=USE_COLS, encoding=enc)
        except (UnicodeDecodeError, ValueError):
            continue
    sys.exit(f"CSV 읽기 실패: {path}")


def load_base_grid(path: Path) -> gpd.GeoDataFrame | None:
    if not path.exists():
        return None
    gdf = gpd.read_file(path)
    if "h3_index" not in gdf.columns:
        warnings.warn(f"base grid에 h3_index 컬럼 없음: {path}")
        return None
    return gdf[["h3_index", "geometry"]].copy()


# ── data cleaning ────────────────────────────────────────────────────────
def clean(df: pd.DataFrame, industry_col: str) -> tuple[pd.DataFrame, int]:
    n_raw = len(df)

    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df = df.dropna(subset=["경도", "위도"])

    mask = (
        df["경도"].between(LON_MIN, LON_MAX)
        & df["위도"].between(LAT_MIN, LAT_MAX)
    )
    df = df.loc[mask].copy()

    df = df.dropna(subset=[industry_col])
    df = df[df[industry_col].str.strip() != ""].copy()

    return df, n_raw


# ── aggregation ──────────────────────────────────────────────────────────
def aggregate(
    df: pd.DataFrame,
    industry_col: str,
    base_grid: gpd.GeoDataFrame | None,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    df["h3_index"] = [
        _latlng_to_cell(lat, lng, H3_RES)
        for lat, lng in zip(df["위도"], df["경도"])
    ]

    total = df.groupby("h3_index").size().rename("total_stores")

    pivot = (
        df.groupby(["h3_index", industry_col])
        .size()
        .unstack(fill_value=0)
    )
    pivot.columns = [f"count_{c}" for c in pivot.columns]

    store_wide = total.to_frame().join(pivot).reset_index()

    long = (
        df.groupby(["h3_index", industry_col])
        .size()
        .reset_index(name="store_count")
    )

    if base_grid is not None:
        wide = base_grid.merge(store_wide, on="h3_index", how="left")
        orphan_cells = set(store_wide["h3_index"]) - set(base_grid["h3_index"])
        if orphan_cells:
            orphans = store_wide[store_wide["h3_index"].isin(orphan_cells)].copy()
            orphans["geometry"] = orphans["h3_index"].apply(_h3_polygon)
            wide = pd.concat([wide, orphans], ignore_index=True)
        count_cols = [c for c in wide.columns if c.startswith("count_")]
        wide["total_stores"] = wide["total_stores"].fillna(0).astype(int)
        for c in count_cols:
            wide[c] = wide[c].fillna(0).astype(int)
    else:
        store_wide["geometry"] = store_wide["h3_index"].apply(_h3_polygon)
        wide = store_wide

    gdf_wide = gpd.GeoDataFrame(wide, geometry="geometry", crs="EPSG:4326")

    gdf_long = gdf_wide[["h3_index", "geometry"]].merge(long, on="h3_index")
    gdf_long = gpd.GeoDataFrame(gdf_long, geometry="geometry", crs="EPSG:4326")

    return gdf_wide, gdf_long, long


# ── main ─────────────────────────────────────────────────────────────────
def main() -> None:
    if INDUSTRY_LEVEL not in LEVEL_MAP:
        sys.exit(f"잘못된 INDUSTRY_LEVEL: {INDUSTRY_LEVEL!r}  (허용: {list(LEVEL_MAP)})")

    industry_col = LEVEL_MAP[INDUSTRY_LEVEL]
    out_gpkg = PROJECT_ROOT / "processed" / f"store_h3_industry_counts_{INDUSTRY_LEVEL}.gpkg"
    out_csv = PROJECT_ROOT / "processed" / f"store_h3_industry_counts_{INDUSTRY_LEVEL}_long.csv"
    layer_wide = f"store_industry_{INDUSTRY_LEVEL}_wide"
    layer_long = f"store_industry_{INDUSTRY_LEVEL}_long"

    print("=" * 60)
    print(f"상가 H3 업종 카운트 생성  (level={INDUSTRY_LEVEL})")
    print("=" * 60)

    if not DATA_PATH.exists():
        sys.exit(f"입력 파일 없음: {DATA_PATH}")

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)

    # 1) 읽기 & 정제
    print("\n[1] CSV 읽기 …")
    df = read_csv(DATA_PATH)

    print("[2] 데이터 정제 …")
    df, n_raw = clean(df, industry_col)
    n_valid = len(df)
    print(f"  원본 행: {n_raw:,}")
    print(f"  유효 행: {n_valid:,}  (제거 {n_raw - n_valid:,})")

    # 2) base grid
    print("[3] 베이스 H3 격자 로드 …")
    base_grid = load_base_grid(BASE_GRID_PATH)
    if base_grid is not None:
        print(f"  delivery_urgency_grid.gpkg 사용  ({len(base_grid):,} cells)")
        used_base = True
    else:
        print("  ⚠ delivery_urgency_grid.gpkg 없음 — 상가 위치 H3 셀만 사용")
        used_base = False

    # 3) 집계
    print("[4] H3 격자 + 업종 집계 …")
    gdf_wide, gdf_long, df_long = aggregate(df, industry_col, base_grid)

    # 4) 저장
    print("[5] 저장 …")
    gdf_wide.to_file(out_gpkg, layer=layer_wide, driver="GPKG")
    gdf_long.to_file(out_gpkg, layer=layer_long, driver="GPKG")
    df_long.to_csv(out_csv, index=False, encoding="utf-8-sig")

    # ── summary ──────────────────────────────────────────────────────
    cells_with_stores = int((gdf_wide["total_stores"] > 0).sum())
    total_store_count = int(gdf_wide["total_stores"].sum())
    cats = df_long.groupby(industry_col)["store_count"].sum().sort_values(ascending=False)

    print("\n" + "=" * 60)
    print("완료 요약")
    print("=" * 60)
    print(f"  입력 행          : {n_raw:,}")
    print(f"  유효 좌표 행     : {n_valid:,}")
    print(f"  베이스 H3 셀     : {len(gdf_wide):,}  (delivery_urgency_grid: {'예' if used_base else '아니오'})")
    print(f"  상가 있는 셀     : {cells_with_stores:,}")
    print(f"  총 상가 수       : {total_store_count:,}")
    print(f"  업종 수준        : {INDUSTRY_LEVEL} ({industry_col})")
    print(f"  업종 카테고리 수 : {len(cats)}")
    print(f"\n  상위 10 업종:")
    for i, (cat, cnt) in enumerate(cats.items()):
        if i >= 10:
            break
        print(f"    {cat:30s}  {cnt:>8,}")
    print(f"\n  Wide GPKG  : {out_gpkg}  ({len(gdf_wide):,} rows, layer={layer_wide})")
    print(f"  Long GPKG  : {out_gpkg}  ({len(gdf_long):,} rows, layer={layer_long})")
    print(f"  Long CSV   : {out_csv}  ({len(df_long):,} rows)")


if __name__ == "__main__":
    main()
