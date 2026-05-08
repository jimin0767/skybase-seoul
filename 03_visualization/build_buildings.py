#!/usr/bin/env python3
"""
Pre-process processed/seoul_buildings.gpkg → tableau_data/seoul_buildings_3d.geojson
for MapLibre fill-extrusion.

Height cleaning:
  1. If HEIGHT is numeric and 2 ≤ HEIGHT ≤ 300 → use HEIGHT
  2. Else if GRND_FLR >= 1 → use GRND_FLR * 3
  3. Else → default 6 m
  Cap at 300 m.

Filter: keep only buildings where computed height_m >= 10 m.
"""
import json
from pathlib import Path
import geopandas as gpd
from shapely.validation import make_valid

_SCRIPT_DIR = Path(__file__).resolve().parent
# Support both main repo layout and git-worktree layout
# Main repo:  <root>/03_visualization/build_buildings.py  → go up 1
# Worktree:   <root>/.claude/worktrees/<name>/03_visualization/... → go up 4
def _find_project_root(start: Path) -> Path:
    for p in [start.parent, start.parent.parent.parent.parent]:
        if (p / "processed" / "seoul_buildings.gpkg").exists():
            return p
    return start.parent  # fallback
PROJECT_ROOT = _find_project_root(_SCRIPT_DIR)
GPKG = PROJECT_ROOT / "processed" / "seoul_buildings.gpkg"
OUT = Path(__file__).resolve().parent / "tableau_data" / "seoul_buildings_3d.geojson"
LAYER = "buildings_4326"
SIMPLIFY_TOL = 0.0001    # degrees ≈ 10 m
MIN_HEIGHT_M = 15.0
MAX_HEIGHT_M = 300.0


def compute_height(row):
    h = row["HEIGHT"]
    if h == h and h is not None:
        h = float(h)
        if 2.0 <= h <= MAX_HEIGHT_M:
            return h
    flr = row["GRND_FLR"]
    if flr == flr and flr is not None:
        flr = float(flr)
        if flr >= 1.0:
            return min(flr * 3.0, MAX_HEIGHT_M)
    return 6.0


def main():
    print(f"Reading {GPKG} layer={LAYER} …")
    gdf = gpd.read_file(GPKG, layer=LAYER)
    print(f"  Total: {len(gdf):,} buildings")

    gdf["height_m"] = gdf.apply(compute_height, axis=1)
    gdf = gdf[gdf["height_m"] >= MIN_HEIGHT_M].copy()
    print(f"  After height filter (>={MIN_HEIGHT_M} m): {len(gdf):,} buildings")

    print("  Simplifying and validating geometries …")
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g).simplify(SIMPLIFY_TOL, preserve_topology=True)
    )
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    print(f"  After simplify: {len(gdf):,} buildings")

    out_gdf = gdf[["height_m", "geometry"]].copy()
    out_gdf.to_file(OUT, driver="GeoJSON")
    size_mb = OUT.stat().st_size / 1_048_576
    print(f"Written: {OUT}")
    print(f"  {len(out_gdf):,} features, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
