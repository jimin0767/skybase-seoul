#!/usr/bin/env python3
"""
Build a competition-ready interactive HTML dashboard for
서울시 드론·로봇 배송 거점 최적화 의사결정 지원 시스템

Dynamic hub recomputation: layer toggles re-run greedy set-cover in the browser.
Pre-computation here: coverage matrix (172 facilities × 1947 cells within 500m).
"""

import csv
import json
import math
import os
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = str(_SCRIPT_DIR / "tableau_data")
OUT_HTML = str(_SCRIPT_DIR / "dashboard.html")
PROJECT_ROOT = _SCRIPT_DIR.parent
STORE_GPKG = PROJECT_ROOT / "processed" / "store_h3_industry_counts_large.gpkg"
POP_GPKG = PROJECT_ROOT / "processed" / "population_h3_density.gpkg"

SERVICE_RADIUS_M = 500  # metres — coverage radius per hub


def read_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_geojson(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ── Load data ──────────────────────────────────────────────────────────────
grid_scores     = read_csv("grid_scores.csv")
final_hubs      = read_csv("final_hubs.csv")
dong_summary    = read_csv("dong_summary.csv")
hourly_demand   = read_csv("hourly_demand.csv")
mode_comparison = read_csv("mode_comparison.csv")
mode_radar      = read_csv("mode_radar_scores.csv")
delivery_routes = read_csv("delivery_routes_summary.csv")
public_facs     = read_csv("public_facilities.csv")

drone_routes_geo  = read_geojson("drone_routes.geojson")
final_hubs_geo    = read_geojson("final_hubs.geojson")
service_areas_geo = read_geojson("service_areas.geojson")

# ── POI layers (from Overpass / OSM) ─────────────────────────────────────────
poi_path = os.path.join(DATA_DIR, "poi_layers.json")
with open(poi_path, encoding="utf-8") as f:
    poi_raw = json.load(f)

# Slim down: keep only lat/lon/name (drop any extra keys)
poi_js = {}
for cat, items in poi_raw.items():
    poi_js[cat] = [
        {"lat": round(it["lat"], 6), "lon": round(it["lon"], 6),
         "name": it.get("name", "")}
        for it in items
    ]
counts = {k: len(v) for k, v in poi_js.items()}
print(f"POI layers loaded: {counts}")


# ── Load store industry counts (음식 only) ───────────────────────────────
store_lookup = {}
if STORE_GPKG.exists():
    import geopandas as _gpd
    _store_gdf = _gpd.read_file(STORE_GPKG, layer="store_industry_large_wide")
    for _, row in _store_gdf.iterrows():
        h3_id = row["h3_index"]
        val = int(row["count_음식"]) if ("count_음식" in row.index and row["count_음식"] == row["count_음식"]) else 0
        store_lookup[h3_id] = val
    del _store_gdf, _gpd
    print(f"Store data loaded: {len(store_lookup)} H3 cells (음식 only)")
else:
    print(f"⚠ Store GeoPackage not found: {STORE_GPKG}")

# ── Load population H3 density (exploratory) ────────────────────────────
POP_FIELDS = [
    "estimated_h3_pop", "estimated_h3_daytime_pop",
    "estimated_h3_evening_pop", "estimated_h3_night_pop",
    "pop_density_index", "daytime_pop_index",
    "evening_pop_index", "night_pop_index", "peak_hour",
]
pop_lookup = {}
if POP_GPKG.exists():
    import geopandas as _gpd2
    _pop_gdf = _gpd2.read_file(POP_GPKG, layer="population_h3_density")
    for _, row in _pop_gdf.iterrows():
        h3_id = row["h3_index"]
        entry = {}
        for col in POP_FIELDS:
            v = row.get(col, 0)
            entry[col] = 0 if (v != v) else v  # NaN check
        pop_lookup[h3_id] = entry
    del _pop_gdf, _gpd2
    print(f"Population data loaded: {len(pop_lookup)} H3 cells")
else:
    print(f"⚠ Population GeoPackage not found: {POP_GPKG}")

# ── Grid: full data + raw urgency float ───────────────────────────────────
grid_js = []
for r in grid_scores:
    h3_id = r["h3_index"]
    entry = {
        "h3":   h3_id,
        "lat":  float(r["lat"]),
        "lon":  float(r["lon"]),
        "dong": r["ADM_NM"],
        "gu":   r["GU_NM"],
        "cs":   round(float(r["composite_score"]), 4),
        "sa":   round(float(r["score_airspace"]),  4),
        "so":   round(float(r["score_obstacle"]),  4),
        "sn":   round(float(r["score_noise"]),     4),
        "st":   round(float(r["score_terrain"]),   4),
        "sw":   round(float(r["score_weather"]),   4),
        "ddi":  round(float(r["delivery_demand_index"]), 3),
        "fpi":  round(float(r["flow_pop_index"]),  3),
        "urg":  r["urgency_level"],
        "urgv": round(float(r["urgency"]), 4),
        "cl":   r["composite_level"],
        "c_food": store_lookup.get(h3_id, 0),
    }
    # Population fields (exploratory — does not affect scoring)
    pop = pop_lookup.get(h3_id, {})
    entry["pop"]       = round(float(pop.get("estimated_h3_pop", 0)), 1)
    entry["pop_day"]   = round(float(pop.get("estimated_h3_daytime_pop", 0)), 1)
    entry["pop_eve"]   = round(float(pop.get("estimated_h3_evening_pop", 0)), 1)
    entry["pop_night"] = round(float(pop.get("estimated_h3_night_pop", 0)), 1)
    entry["pop_idx"]       = round(float(pop.get("pop_density_index", 0)), 4)
    entry["pop_day_idx"]   = round(float(pop.get("daytime_pop_index", 0)), 4)
    entry["pop_eve_idx"]   = round(float(pop.get("evening_pop_index", 0)), 4)
    entry["pop_night_idx"] = round(float(pop.get("night_pop_index", 0)), 4)
    entry["peak_hour"]     = int(pop.get("peak_hour", 0))
    grid_js.append(entry)

# urgency threshold for hotspot: 28th-percentile of all urgency values
# (mirrors NB10 which uses 0.285 quantile)
urg_vals = sorted(g["urgv"] for g in grid_js)
URG_THRESHOLD = urg_vals[int(len(urg_vals) * 0.285)]
print(f"Urgency threshold (28.5th pct): {URG_THRESHOLD:.4f}")


# ── All candidate facilities ───────────────────────────────────────────────
# 172 public facilities that were considered as hub candidates
fac_js = []
for r in public_facs:
    fac_js.append({
        "id":       r["id"],
        "name":     r["name"],
        "facility": r["facility"],
        "lat":      float(r["lat"]),
        "lon":      float(r["lon"]),
        "capacity": int(float(r["capacity"])) if r["capacity"] else 0,
        "idle":     round(float(r["idle_score"]), 4),
    })
print(f"Candidate facilities: {len(fac_js)}")


# ── Coverage matrix (pre-computed, sparse) ────────────────────────────────
# COVERAGE[f] = list of grid-cell indices i where distance(facility_f, cell_i) ≤ 500m
print("Computing coverage matrix…")
coverage = []
for f_idx, fac in enumerate(fac_js):
    within = []
    for c_idx, cell in enumerate(grid_js):
        d = haversine_m(fac["lat"], fac["lon"], cell["lat"], cell["lon"])
        if d <= SERVICE_RADIUS_M:
            within.append(c_idx)
    coverage.append(within)

total_pairs = sum(len(v) for v in coverage)
print(f"Coverage pairs: {total_pairs} (avg {total_pairs/len(fac_js):.1f} cells/facility)")


# ── Static hubs (all-layers baseline for first render) ────────────────────
hubs_js = []
for r in final_hubs:
    hubs_js.append({
        "name":          r["name"],
        "facility":      r["facility"],
        "lat":           float(r["lat"]),
        "lon":           float(r["lon"]),
        "capacity":      int(float(r["capacity"])),
        "mode":          r["delivery_mode"],
        "new_covered":   int(r["new_covered"]),
        "total_covered": int(r["total_covered"]),
        "coverage_pct":  round(float(r["coverage_pct"]) * 100, 1),
    })

# ── Dong summary ──────────────────────────────────────────────────────────
dong_js = []
for r in dong_summary:
    dong_js.append({
        "name":    r["ADM_NM"],
        "gu":      r["GU_NM"],
        "n":       int(r["n_cells"]),
        "avg_cs":  round(float(r["avg_composite"]), 3),
        "avg_urg": round(float(r["avg_urgency"]),   3),
        "pct_f":   round(float(r["pct_feasible"]),  1),
        "avg_air": round(float(r["avg_airspace"]),  3),
        "avg_obs": round(float(r["avg_obstacle"]),  3),
        "avg_noi": round(float(r["avg_noise"]),     3),
        "avg_ter": round(float(r["avg_terrain"]),   3),
        "avg_wea": round(float(r["avg_weather"]),   3),
    })

# ── Hourly demand ─────────────────────────────────────────────────────────
hour_agg = {}
for r in hourly_demand:
    h = int(r["hour"])
    if h not in hour_agg:
        hour_agg[h] = {"cnt": 0, "ratio_sum": 0.0, "n": 0}
    hour_agg[h]["cnt"]       += int(float(r["total_del_cnt"]))
    hour_agg[h]["ratio_sum"] += float(r["hour_ratio"])
    hour_agg[h]["n"]         += 1
hourly_js = [
    {"hour": h, "cnt": v["cnt"], "avg_ratio": round(v["ratio_sum"] / v["n"], 4)}
    for h, v in sorted(hour_agg.items())
]

# ── Radar / mode comparison ────────────────────────────────────────────────
radar_js = [
    {"metric": r["metric"],
     "motorcycle": round(float(r["motorcycle"]), 4),
     "drone":      round(float(r["drone_robot"]), 4)}
    for r in mode_radar
]
mode_js = [
    {"indicator":  r["지표"],
     "motorcycle": r["오토바이"],
     "drone":      r["드론+로봇"],
     "advantage":  r["드론 우위"]}
    for r in mode_comparison
]

# ── Service area polygons (initial, all-layers) ───────────────────────────
service_js = []
for feat in service_areas_geo["features"]:
    coords = feat["geometry"]["coordinates"][0]
    service_js.append({
        "name":   feat["properties"]["name"],
        "coords": [[c[1], c[0]] for c in coords],
    })

# ── Route lines ───────────────────────────────────────────────────────────
route_lines_js = []
for feat in drone_routes_geo["features"]:
    coords = feat["geometry"]["coordinates"]
    route_lines_js.append({
        "hub":    feat["properties"]["hub_name"],
        "dong":   feat["properties"]["target_dong"],
        "dist":   feat["properties"]["distance_m"],
        "coords": [[c[1], c[0]] for c in coords],
    })

# ── KPIs (initial state, all layers on) ───────────────────────────────────
total_cells   = len(grid_scores)
feasible_cells = sum(1 for r in grid_scores if float(r["composite_score"]) > 0)
avg_composite  = sum(float(r["composite_score"]) for r in grid_scores) / total_cells

kpi_js = {
    "total_cells":   total_cells,
    "feasible_cells": feasible_cells,
    "num_hubs":      len(hubs_js),
    "coverage_rate": hubs_js[-1]["coverage_pct"] if hubs_js else 0,
    "avg_composite": round(avg_composite, 3),
}

# ── Update grid_scores.csv with store + population columns ───────────────
enriched_path = os.path.join(DATA_DIR, "grid_scores.csv")
with open(enriched_path, encoding="utf-8-sig") as _f:
    _reader = csv.DictReader(_f)
    _fieldnames = list(_reader.fieldnames)

# Remove stale store/ratio columns from previous runs
_stale = {c for c in _fieldnames
          if (c.startswith("count_") and c != "count_음식")
          or c in ("total_stores", "음식_ratio", "소매_ratio", "과학기술_ratio")}
_fieldnames = [c for c in _fieldnames if c not in _stale]

# Ensure current enrichment columns are present
_enrich_cols = ["count_음식"] + list(POP_FIELDS)
for col in _enrich_cols:
    if col not in _fieldnames:
        _fieldnames.append(col)

with open(enriched_path, "w", encoding="utf-8-sig", newline="") as _f:
    _writer = csv.DictWriter(_f, fieldnames=_fieldnames, extrasaction="ignore")
    _writer.writeheader()
    for r in grid_scores:
        h3_id = r["h3_index"]
        row = dict(r)
        row["count_음식"] = store_lookup.get(h3_id, 0)
        pop = pop_lookup.get(h3_id, {})
        for col in POP_FIELDS:
            v = pop.get(col, 0)
            row[col] = round(float(v), 4) if isinstance(v, float) else int(v)
        _writer.writerow(row)
print(f"Enriched grid_scores.csv with count_음식 + {len(POP_FIELDS)} population columns")

# ── Serialise to JS ───────────────────────────────────────────────────────
GRID_JSON     = json.dumps(grid_js,      ensure_ascii=False)
HUBS_JSON     = json.dumps(hubs_js,      ensure_ascii=False)
FACS_JSON     = json.dumps(fac_js,       ensure_ascii=False)
COV_JSON      = json.dumps(coverage,     ensure_ascii=False)
DONG_JSON     = json.dumps(dong_js,      ensure_ascii=False)
HOURLY_JSON   = json.dumps(hourly_js,    ensure_ascii=False)
RADAR_JSON    = json.dumps(radar_js,     ensure_ascii=False)
MODE_JSON     = json.dumps(mode_js,      ensure_ascii=False)
SERVICE_JSON  = json.dumps(service_js,   ensure_ascii=False)
ROUTES_JSON   = json.dumps(route_lines_js, ensure_ascii=False)
KPI_JSON      = json.dumps(kpi_js,       ensure_ascii=False)
POI_JSON      = json.dumps(poi_js,       ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════════
# HTML template
# ═══════════════════════════════════════════════════════════════════════════
html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>서울시 드론·로봇 배송 거점 최적화</title>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css"/>
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Noto Sans KR',sans-serif; background:#0f0f1a; color:#e0e0e0; overflow-x:hidden; }}
::-webkit-scrollbar {{ width:8px; }}
::-webkit-scrollbar-track {{ background:#1a1a2e; }}
::-webkit-scrollbar-thumb {{ background:#0f3460; border-radius:4px; }}

.hero {{
  background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 50%, #16213e 100%);
  padding: 24px 40px 18px;
  border-bottom: 3px solid #e94560;
  text-align:center;
}}
.hero h1 {{ font-size:26px; font-weight:700; color:#fff; letter-spacing:1px; text-shadow:0 2px 12px rgba(233,69,96,.35); }}
.hero .subtitle {{ font-size:13px; color:#aab; margin-top:5px; }}
.hero .badge {{ display:inline-block; background:#e94560; color:#fff; font-size:11px; padding:3px 12px; border-radius:20px; margin-top:6px; font-weight:500; }}

.dashboard {{ max-width:1600px; margin:0 auto; padding:16px 20px; }}

/* KPI row */
.kpi-row {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:16px; }}
.kpi-card {{
  background:linear-gradient(145deg,#16213e,#1a1a2e);
  border:1px solid #0f3460; border-radius:12px; padding:16px 14px; text-align:center;
  transition:transform .2s,box-shadow .2s;
}}
.kpi-card:hover {{ transform:translateY(-3px); box-shadow:0 6px 24px rgba(15,52,96,.5); }}
.kpi-card .kpi-value {{ font-size:28px; font-weight:700; color:#53d769; line-height:1.2; transition:color .4s; }}
.kpi-card .kpi-label {{ font-size:11px; color:#8899aa; margin-top:5px; }}
.kpi-card.accent .kpi-value {{ color:#e94560; }}
.kpi-card.blue   .kpi-value {{ color:#4fc3f7; }}

/* Main grid */
.main-grid {{ display:grid; grid-template-columns:1fr 420px; gap:16px; margin-bottom:16px; }}
@media(max-width:1100px) {{ .main-grid {{ grid-template-columns:1fr; }} .kpi-row {{ grid-template-columns:repeat(3,1fr); }} }}

.map-panel {{ background:#16213e; border-radius:12px; border:1px solid #0f3460; position:relative; overflow:hidden; }}
#map {{ height:600px; width:100%; }}
.maplibregl-canvas {{ border-radius:11px; }}

.side-panel {{ display:flex; flex-direction:column; gap:12px; }}

/* Layer toggles */
.layer-panel {{ background:linear-gradient(145deg,#16213e,#1a1a2e); border:1px solid #0f3460; border-radius:12px; padding:16px 18px; }}
.panel-title {{ font-size:13px; font-weight:600; color:#4fc3f7; margin-bottom:12px; letter-spacing:.5px; text-transform:uppercase; }}
.layer-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.layer-toggle {{
  display:flex; align-items:center; gap:8px; padding:9px 12px;
  background:#0f1928; border:1px solid #1a3a5c; border-radius:8px;
  cursor:pointer; transition:all .2s; user-select:none;
}}
.layer-toggle.active {{ background:#0f3460; border-color:#4fc3f7; }}
.layer-toggle input {{ display:none; }}
.layer-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
.layer-toggle span {{ font-size:12px; font-weight:500; }}
.formula-box {{ margin-top:10px; padding:8px 12px; background:#0a1020; border-radius:6px; border:1px solid #1a3a5c; font-size:11px; color:#7ba; }}
.formula-box b {{ color:#4fc3f7; }}

/* Full-width hub section below map row */
.hub-section {{
  background: linear-gradient(145deg,#16213e,#1a1a2e);
  border: 1px solid #0f3460; border-radius:12px; padding:16px 20px; margin-bottom:16px;
}}
.hub-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px; margin-top: 4px;
}}
.hub-item {{
  background:#0f1928; border:1px solid #1a3a5c; border-radius:8px; padding:12px 14px;
  transition:all .35s ease; position:relative; overflow:hidden;
}}
.hub-item.new-hub {{ border-color:#53d769; background:#0a1f0f; animation:hubPop .5s ease; }}
.hub-item.removed {{ opacity:.4; border-color:#e94560; }}
@keyframes hubPop {{ 0%{{transform:scale(.95);opacity:0}} 60%{{transform:scale(1.03)}} 100%{{transform:scale(1);opacity:1}} }}
@keyframes hubPulse {{ 0%,100%{{transform:scale(1);opacity:.45}} 50%{{transform:scale(1.55);opacity:.1}} }}
.hub-item .hub-name {{ font-size:13px; font-weight:600; color:#e0e0e0; }}
.hub-item .hub-detail {{ font-size:11px; color:#8899aa; margin-top:3px; }}
.hub-rank {{ position:absolute; top:8px; right:10px; font-size:20px; opacity:.5; }}
.hub-coverage-bar {{ height:4px; border-radius:2px; margin-top:7px; background:#1a3a5c; overflow:hidden; }}
.hub-coverage-fill {{ height:100%; border-radius:2px; background:linear-gradient(90deg,#53d769,#4fc3f7); transition:width .6s ease; }}

/* Chart grid */
.chart-row {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }}
.chart-row3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:16px; }}
.chart-card {{ background:linear-gradient(145deg,#16213e,#1a1a2e); border:1px solid #0f3460; border-radius:12px; padding:16px 18px; }}
.chart-card h3 {{ font-size:12px; font-weight:600; color:#4fc3f7; margin-bottom:10px; text-transform:uppercase; letter-spacing:.5px; }}
.chart-box {{ height:220px; }}
.chart-box-tall {{ height:280px; }}

/* Comparison table */
.comp-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.comp-table th {{ padding:8px 10px; text-align:left; color:#4fc3f7; border-bottom:1px solid #0f3460; font-weight:600; }}
.comp-table td {{ padding:7px 10px; border-bottom:1px solid #0f346033; }}
.comp-table tr:last-child td {{ border-bottom:none; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; }}
.tag-green {{ background:#53d76922; color:#53d769; border:1px solid #53d76944; }}
.tag-red   {{ background:#e9456022; color:#e94560; border:1px solid #e9456044; }}

/* POI layer toggle panel */
.poi-panel {{ background:linear-gradient(145deg,#16213e,#1a1a2e); border:1px solid #0f3460; border-radius:12px; padding:16px 18px; }}
.poi-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:7px; }}
.poi-toggle {{
  display:flex; align-items:center; gap:8px; padding:8px 11px;
  background:#0f1928; border:1px solid #1a3a5c; border-radius:8px;
  cursor:pointer; transition:all .2s; user-select:none;
}}
.poi-toggle.active {{ background:#1a0a2e; border-color:#ce93d8; }}
.poi-toggle input {{ display:none; }}
.poi-dot {{ width:9px; height:9px; border-radius:50%; flex-shrink:0; }}
.poi-toggle span {{ font-size:11px; font-weight:500; }}
.poi-count {{ margin-left:auto; font-size:10px; color:#556; }}

/* Status bar */
.status-bar {{ font-size:11px; color:#556; padding:8px 0 4px; text-align:center; }}

/* Spinning update indicator */
.updating {{ display:none; }}
.updating.show {{ display:inline-block; animation:spin .6s linear infinite; }}
@keyframes spin {{ to{{transform:rotate(360deg)}} }}
select:focus {{ outline:none; border-color:#4fc3f7; }}
select option {{ background:#0f1928; color:#e0e0e0; }}
</style>
</head>
<body>

<div class="hero">
  <h1>🚁 서울시 드론·로봇 융합 배송 거점 최적 입지 분석</h1>
  <div class="subtitle">Multi-Layered Decision Support System · 2026 서울시 공공데이터 활용 시각화 경진대회</div>
  <span class="badge">레이어 조합 → 실시간 거점 재최적화</span>
</div>

<div class="dashboard">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-value" id="kpi-total-cells">{kpi_js["total_cells"]:,}</div>
      <div class="kpi-label">전체 H3 셀 (res.9)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="kpi-feasible">0</div>
      <div class="kpi-label">적합 셀 수 <span style="font-size:10px;color:#556">(레이어 조합)</span></div>
    </div>
    <div class="kpi-card accent">
      <div class="kpi-value" id="kpi-num-hubs">{kpi_js["num_hubs"]}</div>
      <div class="kpi-label">선정 거점 수</div>
    </div>
    <div class="kpi-card blue">
      <div class="kpi-value" id="kpi-coverage">0%</div>
      <div class="kpi-label">핫스팟 커버리지 (500m)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="kpi-avg-cs">0</div>
      <div class="kpi-label">평균 종합 적합도</div>
    </div>
  </div>

  <!-- Map + Side Panel -->
  <div class="main-grid">
    <div class="map-panel">
      <div id="map"></div>
    </div>
    <div class="side-panel">
      <!-- Layer Toggles -->
      <div class="layer-panel">
        <div class="panel-title">⚙️ 제약 레이어 조합 선택</div>
        <div class="layer-grid">
          <label class="layer-toggle active" data-layer="sa">
            <input type="checkbox" data-layer="sa" checked>
            <div class="layer-dot" style="background:#e94560"></div>
            <span>✈️ 공역 제한</span>
          </label>
          <label class="layer-toggle active" data-layer="so">
            <input type="checkbox" data-layer="so" checked>
            <div class="layer-dot" style="background:#ff9800"></div>
            <span>🏢 장애물</span>
          </label>
          <label class="layer-toggle active" data-layer="sn">
            <input type="checkbox" data-layer="sn" checked>
            <div class="layer-dot" style="background:#ffeb3b"></div>
            <span>🔊 소음 민감</span>
          </label>
          <label class="layer-toggle active" data-layer="st">
            <input type="checkbox" data-layer="st" checked>
            <div class="layer-dot" style="background:#4caf50"></div>
            <span>⛰️ 지형 경사</span>
          </label>
          <label class="layer-toggle active" data-layer="sw" style="grid-column:1/-1">
            <input type="checkbox" data-layer="sw" checked>
            <div class="layer-dot" style="background:#2196f3"></div>
            <span>🌬️ 기상 (바람)</span>
          </label>
        </div>
        <div class="formula-box">
          <b>현재 스코어 :</b> <span id="formula-display">공역 × 장애물 × 소음 × 지형 × 기상</span>
          <span id="update-spin" class="updating">🔄</span>
        </div>
        <div style="margin-top:10px;">
          <label style="font-size:11px;color:#8899aa;">🗺️ 맵 색상 모드</label>
          <select id="color-mode-select" style="width:100%;margin-top:4px;padding:7px 10px;
            background:#0f1928;color:#e0e0e0;border:1px solid #1a3a5c;border-radius:6px;
            font-family:'Noto Sans KR';font-size:12px;cursor:pointer;">
            <option value="score">종합 적합도</option>
            <option value="food">음식 상권 밀도</option>
            <option value="pop">🏘️ 생활인구 밀도</option>
            <option value="pop_day">☀️ 주간 생활인구</option>
            <option value="pop_eve">🌆 저녁 생활인구</option>
            <option value="pop_night">🌙 야간 생활인구</option>
          </select>
        </div>
        <div style="margin-top:10px;">
          <label style="font-size:11px;color:#8899aa;">🔲 H3 셀 표시 모드</label>
          <div id="h3-vis-control" style="display:flex;gap:6px;margin-top:4px;">
            <button class="h3-vis-btn" data-mode="all"
              style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
                     background:#0f1928;color:#8899aa;border:1px solid #1a3a5c;
                     border-radius:6px;cursor:pointer;">전체 H3 표시</button>
            <button class="h3-vis-btn h3-vis-active" data-mode="hub"
              style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
                     background:#0f3460;color:#4fc3f7;border:1px solid #4fc3f7;
                     border-radius:6px;cursor:pointer;">거점 관련만</button>
            <button class="h3-vis-btn" data-mode="none"
              style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
                     background:#0f1928;color:#8899aa;border:1px solid #1a3a5c;
                     border-radius:6px;cursor:pointer;">H3 숨김</button>
          </div>
        </div>
      </div>

      <!-- POI Layer Toggles -->
      <div class="poi-panel">
        <div class="panel-title">📍 POI 레이어 표시</div>
        <div class="poi-grid">
          <label class="poi-toggle" data-poi="park">
            <input type="checkbox" data-poi="park">
            <div class="poi-dot" style="background:#ffffff"></div>
            <span>🌳 공원</span>
            <span class="poi-count">{counts.get("park", 0)}</span>
          </label>
          <label class="poi-toggle" data-poi="commercial">
            <input type="checkbox" data-poi="commercial">
            <div class="poi-dot" style="background:#9c27b0"></div>
            <span>🏪 상권</span>
            <span class="poi-count">{counts.get("commercial", 0)}</span>
          </label>
          <label class="poi-toggle" data-poi="medical">
            <input type="checkbox" data-poi="medical">
            <div class="poi-dot" style="background:#e040fb"></div>
            <span>🏥 의료</span>
            <span class="poi-count">{counts.get("medical", 0)}</span>
          </label>
          <label class="poi-toggle" data-poi="subway">
            <input type="checkbox" data-poi="subway">
            <div class="poi-dot" style="background:#7c4dff"></div>
            <span>🚇 지하철</span>
            <span class="poi-count">{counts.get("subway", 0)}</span>
          </label>
          <label class="poi-toggle" data-poi="school" style="grid-column:1/-1">
            <input type="checkbox" data-poi="school">
            <div class="poi-dot" style="background:#b39ddb"></div>
            <span>🏫 학교</span>
            <span class="poi-count">{counts.get("school", 0)}</span>
          </label>
        </div>
      </div>
    </div>
  </div>

  <!-- Full-width Hub Results — below map + controls row -->
  <div class="hub-section">
    <div class="panel-title" style="margin-bottom:12px;">
      📍 최적 거점
      <span id="hub-count-badge" style="background:#e9456033;color:#e94560;border-radius:10px;padding:1px 8px;font-size:12px;margin-left:8px;"></span>
    </div>
    <div id="hub-list" class="hub-grid">
      <div style="color:#556;font-size:12px;padding:8px;">레이어 조합 중…</div>
    </div>
  </div>

  <!-- Chart Row 1: dong ranking + hourly demand -->
  <div class="chart-row">
    <div class="chart-card">
      <h3>📊 동별 종합 적합도 순위 (Top 15)</h3>
      <div id="chart-bar" class="chart-box"></div>
    </div>
    <div class="chart-card">
      <h3>🕐 시간대별 배송 수요 패턴</h3>
      <div id="chart-hourly" class="chart-box"></div>
    </div>
  </div>

  <!-- Chart Row 2: radar + feasible pct -->
  <div class="chart-row">
    <div class="chart-card">
      <h3>🔄 배송 모드 비교 (드론+로봇 vs 오토바이)</h3>
      <div id="chart-radar" class="chart-box"></div>
    </div>
    <div class="chart-card">
      <h3>📈 동별 적합 셀 비율 (%)</h3>
      <div id="chart-feasible" class="chart-box-tall" style="height:260px;overflow-y:auto;"></div>
    </div>
  </div>

  <!-- Comparison table -->
  <div class="chart-card" style="margin-bottom:16px;">
    <h3>📋 배송 수단 비교 분석</h3>
    <table class="comp-table">
      <thead>
        <tr><th>지표</th><th>오토바이</th><th>드론+로봇</th><th>드론 우위</th></tr>
      </thead>
      <tbody id="comp-tbody"></tbody>
    </table>
  </div>

  <div class="status-bar">
    ⬛ H3 res.9 · 500m 서비스 반경 · 그리디 셋 커버 알고리즘 · 실시간 레이어 재최적화
    &nbsp;|&nbsp; 데이터: 서울시 공공데이터포털 · NGII · 배달의민족 2023
  </div>
</div>

<script>
// ═══════════════════════════════════════════════════════════════
// Embedded data (generated by build_dashboard.py)
// ═══════════════════════════════════════════════════════════════
const GRID     = {GRID_JSON};
const HUBS_0   = {HUBS_JSON};        // all-layers baseline (4 hubs)
const FACS     = {FACS_JSON};        // all 172 candidate facilities
const COV      = {COV_JSON};         // COV[f] = [cell_idx, ...] within 500m
const DONG     = {DONG_JSON};
const HOURLY   = {HOURLY_JSON};
const RADAR    = {RADAR_JSON};
const MODE     = {MODE_JSON};
const SERVICE0 = {SERVICE_JSON};     // initial service area polygons
const ROUTES0  = {ROUTES_JSON};      // initial route lines
const KPI0     = {KPI_JSON};
const URG_THR  = {URG_THRESHOLD:.4f};  // hotspot urgency threshold
const POI      = {POI_JSON};           // POI layers: park/commercial/medical/subway/school

// ═══════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════
let colorMode = 'score';
let h3VisMode = 'hub';            // 'all' | 'hub' | 'none'
let lastHubCoveredSet = new Set(); // cell indices covered by current hubs

document.querySelectorAll('.h3-vis-btn').forEach(btn => {{
  btn.addEventListener('click', function() {{
    h3VisMode = this.dataset.mode;
    document.querySelectorAll('.h3-vis-btn').forEach(b => {{
      const on = b.dataset.mode === h3VisMode;
      b.style.background   = on ? '#0f3460' : '#0f1928';
      b.style.color        = on ? '#4fc3f7' : '#8899aa';
      b.style.borderColor  = on ? '#4fc3f7' : '#1a3a5c';
    }});
    if (window._lastScores) renderH3Layer(window._lastScores);
  }});
}});

function scoreToColor(v) {{
  if (v <= 0)   return '#e94560';
  if (v < 0.2)  return '#ff5722';
  if (v < 0.4)  return '#ff9800';
  if (v < 0.6)  return '#ffeb3b';
  if (v < 0.75) return '#8bc34a';
  if (v < 0.9)  return '#4caf50';
  return '#00c853';
}}

function densityToColor(count, maxVal) {{
  if (count <= 0) return '#1a1a2e';
  const t = Math.min(count / (maxVal * 0.5), 1);
  const r = Math.round(10 + t * 50);
  const g = Math.round(30 + t * 100);
  const b = Math.round(80 + t * 175);
  return `rgb(${{r}},${{g}},${{b}})`;
}}

// Population index color ramp (warm orange-red, 0-1 normalized input)
function popToColor(idx) {{
  if (idx <= 0) return '#1a1a2e';
  // Warm sequential: dark → orange → bright yellow-white
  const t = Math.min(idx, 1);
  const r = Math.round(40 + t * 215);
  const g = Math.round(15 + t * 140);
  const b = Math.round(15 + t * 30);
  return `rgb(${{r}},${{g}},${{b}})`;
}}

const COLOR_MODES = {{
  score:     {{ label: '종합 적합도',   field: null }},
  food:      {{ label: '음식 상권 밀도', field: 'c_food', max: Math.max(...GRID.map(c => c.c_food || 0)) || 1 }},
  pop:       {{ label: '생활인구 밀도', field: 'pop_idx',       pop: true }},
  pop_day:   {{ label: '주간 생활인구', field: 'pop_day_idx',   pop: true }},
  pop_eve:   {{ label: '저녁 생활인구', field: 'pop_eve_idx',   pop: true }},
  pop_night: {{ label: '야간 생활인구', field: 'pop_night_idx', pop: true }},
}};

function recalcScore(cell, active) {{
  let v = 1.0, n = 0;
  if (active.sa) {{ v *= cell.sa; n++; }}
  if (active.so) {{ v *= cell.so; n++; }}
  if (active.sn) {{ v *= cell.sn; n++; }}
  if (active.st) {{ v *= cell.st; n++; }}
  if (active.sw) {{ v *= cell.sw; n++; }}
  return n === 0 ? 0 : v;
}}

function getActiveLayers() {{
  const a = {{}};
  document.querySelectorAll('.layer-toggle input').forEach(inp => {{
    a[inp.dataset.layer] = inp.checked;
  }});
  return a;
}}

function haversineM(lat1, lon1, lat2, lon2) {{
  const R = 6371000, r = Math.PI / 180;
  const f1 = lat1 * r, f2 = lat2 * r;
  const df = (lat2 - lat1) * r, dl = (lon2 - lon1) * r;
  const a = Math.sin(df/2)**2 + Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}}

// ═══════════════════════════════════════════════════════════════
// Greedy set-cover hub selection
// ═══════════════════════════════════════════════════════════════
function selectHubs(scores, maxHubs=10, coverageTarget=0.9) {{
  // 1. Identify feasible cells and hotspots
  const feasible  = new Set();
  const hotspots  = new Set();
  let   totalUrg  = 0;

  scores.forEach((sc, i) => {{
    if (sc > 0) {{
      feasible.add(i);
      if (GRID[i].urgv >= URG_THR) {{
        hotspots.add(i);
        totalUrg += GRID[i].urgv;
      }}
    }}
  }});

  if (hotspots.size === 0) return {{ hubs: [], feasible, hotspots, totalUrg }};

  const uncovered = new Set(hotspots);
  const selected  = [];   // facility indices

  for (let k = 0; k < maxHubs && uncovered.size > 0; k++) {{
    let bestFac = -1, bestScore = -Infinity;

    for (let f = 0; f < FACS.length; f++) {{
      if (selected.includes(f)) continue;

      // Facility must sit in a feasible cell or be near one
      const cells = COV[f];
      const coveredNew = cells.filter(ci => uncovered.has(ci));
      if (coveredNew.length === 0) continue;

      // Score = covered hotspots + 0.1 × urgency sum (mirrors NB10)
      const urgSum = coveredNew.reduce((s, ci) => s + GRID[ci].urgv, 0);
      const sc = coveredNew.length + 0.1 * urgSum;

      if (sc > bestScore) {{ bestScore = sc; bestFac = f; }}
    }}

    if (bestFac < 0) break;
    selected.push(bestFac);
    COV[bestFac].forEach(ci => uncovered.delete(ci));

    // Early stop if coverage target reached
    const coveredCount = hotspots.size - uncovered.size;
    if (coveredCount / hotspots.size >= coverageTarget) break;
  }}

  return {{ hubs: selected, feasible, hotspots, uncovered, totalUrg }};
}}

// ═══════════════════════════════════════════════════════════════
// Map setup — MapLibre GL JS
// ═══════════════════════════════════════════════════════════════
const map = new maplibregl.Map({{
  container: 'map',
  style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  center: [126.9780, 37.5665],
  zoom: 11,
  pitch: 45,
  bearing: 0,
  antialias: true,
}});
map.addControl(new maplibregl.NavigationControl(), 'top-right');

// ── Pitch controls ────────────────────────────────────────────
// Two-finger touchpad swipe → pitch (disable default scroll-zoom)
// Swipe up (−deltaY) = increase pitch (more side-on)
// Swipe down (+deltaY) = decrease pitch (more top-down)
map.scrollZoom.disable();
map.getCanvas().addEventListener('wheel', e => {{
  e.preventDefault();
  const newPitch = Math.max(0, Math.min(75, map.getPitch() - e.deltaY * 0.15));
  map.setPitch(newPitch);
}}, {{ passive: false }});

// Right-click drag → also controls pitch (for mouse users)
// Drag upward (−dy) = increase pitch; drag downward (+dy) = decrease pitch
map.dragRotate.disable();
let _rcDrag = null;
map.getCanvas().addEventListener('mousedown', e => {{
  if (e.button !== 2) return;
  e.preventDefault();
  _rcDrag = {{ y: e.clientY, pitch: map.getPitch() }};
}});
window.addEventListener('mousemove', e => {{
  if (!_rcDrag) return;
  const dy = e.clientY - _rcDrag.y;
  map.setPitch(Math.max(0, Math.min(75, _rcDrag.pitch - dy * 0.35)));
}});
window.addEventListener('mouseup', e => {{ if (e.button === 2) _rcDrag = null; }});
map.getCanvas().addEventListener('contextmenu', e => e.preventDefault());

// ═══════════════════════════════════════════════════════════════
// POI config (used both in toggle listeners and map.on('load'))
// ═══════════════════════════════════════════════════════════════
const POI_CONFIG = {{
  park:       {{ color:'#ffffff', radius:5,  emoji:'🌳' }},
  commercial: {{ color:'#9c27b0', radius:6,  emoji:'🏪' }},
  medical:    {{ color:'#e040fb', radius:5,  emoji:'🏥' }},
  subway:     {{ color:'#7c4dff', radius:6,  emoji:'🚇' }},
  school:     {{ color:'#b39ddb', radius:5,  emoji:'🏫' }},
}};

// POI toggle buttons — use setLayoutProperty once map is loaded
document.querySelectorAll('.poi-toggle').forEach(label => {{
  label.addEventListener('click', function(e) {{
    const inp = this.querySelector('input');
    inp.checked = !inp.checked;
    this.classList.toggle('active', inp.checked);
    const cat = this.dataset.poi;
    const vis = inp.checked ? 'visible' : 'none';
    if (map._loaded) map.setLayoutProperty(`poi-${{cat}}`, 'visibility', vis);
    e.preventDefault();
  }});
}});

// ── H3 cell layer (3-state: all / hub-related / none) ────────
// Uses MapLibre GeoJSON source 'h3-source' + circle layer 'h3-cells'
function buildH3GeoJSON(scores, filterSet) {{
  const features = [];
  GRID.forEach((cell, i) => {{
    if (filterSet !== null && !filterSet.has(i)) return;
    features.push({{
      type: 'Feature',
      geometry: {{ type: 'Point', coordinates: [cell.lon, cell.lat] }},
      properties: {{
        score: scores[i], dong: cell.dong, gu: cell.gu, h3: cell.h3,
        sa: cell.sa, so: cell.so, sn: cell.sn, st: cell.st, sw: cell.sw,
        urg: cell.urg, urgv: cell.urgv, ddi: cell.ddi,
        c_food: cell.c_food || 0,
        pop_idx: cell.pop_idx || 0, pop_day_idx: cell.pop_day_idx || 0,
        pop_eve_idx: cell.pop_eve_idx || 0, pop_night_idx: cell.pop_night_idx || 0,
        pop: cell.pop || 0, pop_day: cell.pop_day || 0,
        pop_eve: cell.pop_eve || 0, pop_night: cell.pop_night || 0,
        peak_hour: cell.peak_hour || 0,
      }}
    }});
  }});
  return {{ type: 'FeatureCollection', features }};
}}

function renderH3Layer(scores) {{
  if (!map._loaded) return;
  if (h3VisMode === 'none') {{
    map.setLayoutProperty('h3-cells', 'visibility', 'none');
    return;
  }}
  map.setLayoutProperty('h3-cells', 'visibility', 'visible');
  const filterSet = h3VisMode === 'hub' ? lastHubCoveredSet : null;
  map.getSource('h3-source').setData(buildH3GeoJSON(scores, filterSet));

  // Update color expression based on colorMode
  let colorExpr;
  if (colorMode === 'score') {{
    colorExpr = ['case',
      ['<=', ['get', 'score'], 0],    '#e94560',
      ['<',  ['get', 'score'], 0.2],  '#ff5722',
      ['<',  ['get', 'score'], 0.4],  '#ff9800',
      ['<',  ['get', 'score'], 0.6],  '#ffeb3b',
      ['<',  ['get', 'score'], 0.75], '#8bc34a',
      ['<',  ['get', 'score'], 0.9],  '#4caf50',
      '#00c853'
    ];
  }} else {{
    const field = colorMode === 'food' ? 'c_food' :
                  colorMode === 'pop' ? 'pop_idx' :
                  colorMode === 'pop_day' ? 'pop_day_idx' :
                  colorMode === 'pop_eve' ? 'pop_eve_idx' : 'pop_night_idx';
    // Normalize food by max value; pop fields are already 0-1 indices
    if (colorMode === 'food') {{
      const maxFood = Math.max(...GRID.map(c => c.c_food || 0)) || 1;
      colorExpr = ['interpolate', ['linear'],
        ['/', ['get', field], maxFood],
        0, '#1a1a2e', 0.3, '#0d47a1', 0.7, '#1565c0', 1, '#ffeb3b'
      ];
    }} else {{
      colorExpr = ['interpolate', ['linear'], ['get', field],
        0, '#1a1a2e', 0.3, '#e65100', 0.7, '#ff9800', 1, '#ffeb3b'
      ];
    }}
  }}
  map.setPaintProperty('h3-cells', 'circle-color', colorExpr);
}}

// ── Hub + service layers (all GeoJSON — geographically anchored) ─
const PALETTE = [
  '#00e5ff', '#ff4081', '#b2ff59', '#ffd740', '#ea80fc',
  '#ff6d00', '#40c4ff', '#f50057', '#69ff47', '#ffab40',
];

// Generate a GeoJSON polygon approximating a circle of radiusM metres
function makeCirclePolygon(lat, lon, radiusM, color, rank) {{
  const n = 64;
  const mPerDegLat = 111320;
  const mPerDegLon = 111320 * Math.cos(lat * Math.PI / 180);
  const coords = [];
  for (let i = 0; i <= n; i++) {{
    const a = (2 * Math.PI * i) / n;
    coords.push([lon + radiusM * Math.sin(a) / mPerDegLon,
                 lat + radiusM * Math.cos(a) / mPerDegLat]);
  }}
  return {{ type: 'Feature',
    properties: {{ color, rank }},
    geometry: {{ type: 'Polygon', coordinates: [coords] }} }};
}}

function buildHubLayer(selFacIndices, scores) {{
  // Rebuild covered-cell set used by renderH3Layer 'hub' mode
  lastHubCoveredSet = new Set();
  selFacIndices.forEach(fi => COV[fi].forEach(ci => lastHubCoveredSet.add(ci)));

  const hubFeatures     = [];
  const serviceFeatures = [];
  const routeFeatures   = [];
  const targetFeatures  = [];

  selFacIndices.forEach((fi, rank) => {{
    const fac    = FACS[fi];
    const color  = PALETTE[rank % PALETTE.length];
    const cov    = COV[fi].filter(ci => scores[ci] > 0).length;
    const hotCov = COV[fi].filter(ci => scores[ci] > 0 && GRID[ci].urgv >= URG_THR).length;

    // Hub point feature (rendered as circle + emoji symbol layer — no HTML markers)
    hubFeatures.push({{
      type: 'Feature',
      properties: {{ color, rank, name: fac.name, facility: fac.facility, capacity: fac.capacity, cov, hotCov }},
      geometry: {{ type: 'Point', coordinates: [fac.lon, fac.lat] }}
    }});

    // Service circle polygon (500 m)
    serviceFeatures.push(makeCirclePolygon(fac.lat, fac.lon, 500, color, rank));

    // Route lines + explicit target point markers (top-5 urgent cells)
    const topCells = COV[fi]
      .filter(ci => scores[ci] > 0 && GRID[ci].urgv >= URG_THR)
      .sort((a, b) => (scores[b] + GRID[b].urgv) - (scores[a] + GRID[a].urgv))
      .slice(0, 5);
    topCells.forEach(ci => {{
      routeFeatures.push({{
        type: 'Feature',
        properties: {{ color, rank }},
        geometry: {{ type: 'LineString',
          coordinates: [[fac.lon, fac.lat], [GRID[ci].lon, GRID[ci].lat]] }}
      }});
      targetFeatures.push({{
        type: 'Feature',
        properties: {{
          color, rank,
          dong: GRID[ci].dong, gu: GRID[ci].gu, h3: GRID[ci].h3,
          score: scores[ci], urg: GRID[ci].urg, urgv: GRID[ci].urgv, ddi: GRID[ci].ddi
        }},
        geometry: {{ type: 'Point', coordinates: [GRID[ci].lon, GRID[ci].lat] }}
      }});
    }});
  }});

  if (map._loaded) {{
    map.getSource('hubs').setData({{ type: 'FeatureCollection', features: hubFeatures }});
    map.getSource('service-circles').setData({{ type: 'FeatureCollection', features: serviceFeatures }});
    map.getSource('route-lines').setData({{ type: 'FeatureCollection', features: routeFeatures }});
    map.getSource('target-points').setData({{ type: 'FeatureCollection', features: targetFeatures }});
  }}
}}

// ── Render hub list panel ─────────────────────────────────────
function renderHubList(selFacIndices, scores, hotspots) {{
  const container = document.getElementById('hub-list');
  const badge = document.getElementById('hub-count-badge');
  badge.textContent = selFacIndices.length + '개 거점';

  if (selFacIndices.length === 0) {{
    container.innerHTML = '<div style="color:#e94560;font-size:12px;padding:8px;">⚠️ 선택된 레이어로는 적합한 거점이 없습니다.</div>';
    return;
  }}

  let covSoFar = new Set();
  container.innerHTML = '';
  selFacIndices.forEach((fi, rank) => {{
    const fac = FACS[fi];
    const color = PALETTE[rank % PALETTE.length];
    const newHot = COV[fi].filter(ci => hotspots.has(ci) && !covSoFar.has(ci));
    newHot.forEach(ci => covSoFar.add(ci));
    const pct = hotspots.size > 0 ? (covSoFar.size / hotspots.size * 100) : 0;

    const item = document.createElement('div');
    item.className = 'hub-item new-hub';
    item.innerHTML = `
      <span class="hub-rank">${{rank === 0 ? '🥇' : rank === 1 ? '🥈' : rank === 2 ? '🥉' : '📍'}}</span>
      <div class="hub-name" style="color:${{color}};">#${{rank+1}} ${{fac.name}}</div>
      <div class="hub-detail">${{fac.facility}} · 수용 ${{fac.capacity}}대 · 신규 핫스팟 ${{newHot.length}}셀</div>
      <div class="hub-detail" style="color:#7ba;">누적 커버: ${{pct.toFixed(1)}}%</div>
      <div class="hub-coverage-bar"><div class="hub-coverage-fill" style="width:${{pct}}%;"></div></div>
    `;
    container.appendChild(item);
  }});
}}

// ═══════════════════════════════════════════════════════════════
// Master update function — runs on every layer toggle
// ═══════════════════════════════════════════════════════════════
function updateDashboard() {{
  if (!map._loaded) return;
  const active = getActiveLayers();

  // 1. Recompute all cell scores
  const scores = GRID.map(cell => recalcScore(cell, active));

  // 2. Avg composite KPI — computed directly from scores, independent of H3 rendering
  const avgCs = scores.reduce((s, v) => s + v, 0) / scores.length;
  document.getElementById('kpi-avg-cs').textContent = avgCs.toFixed(3);
  window._lastScores = scores;

  // 3. Run greedy set-cover
  const result = selectHubs(scores);
  const selFacIndices = result.hubs;
  const feasible = result.feasible;
  const hotspots = result.hotspots;
  const uncovered = result.uncovered;

  // 4. Hub layer first — populates lastHubCoveredSet used by renderH3Layer
  buildHubLayer(selFacIndices, scores);

  // 5. H3 layer after — uses lastHubCoveredSet for 'hub' mode
  renderH3Layer(scores);

  // 6. Update hub list panel
  renderHubList(selFacIndices, scores, hotspots);

  // 7. Update KPIs
  document.getElementById('kpi-feasible').textContent = feasible.size.toLocaleString();
  document.getElementById('kpi-num-hubs').textContent = selFacIndices.length;
  const coveredHots = hotspots.size - (uncovered ? uncovered.size : 0);
  const covPct = hotspots.size > 0 ? (coveredHots / hotspots.size * 100).toFixed(1) : '0.0';
  document.getElementById('kpi-coverage').textContent = covPct + '%';

  // 8. Update formula display
  const names = {{sa:'공역',so:'장애물',sn:'소음',st:'지형',sw:'기상'}};
  const parts = Object.entries(active).filter(([,v])=>v).map(([k])=>names[k]);
  document.getElementById('formula-display').textContent =
    parts.length ? parts.join(' × ') : '(선택 없음 — 모든 셀 점수 0)';
}}

// ═══════════════════════════════════════════════════════════════
// map.on('load') — create all GeoJSON sources + layers, then initial render
// ═══════════════════════════════════════════════════════════════
map.on('load', () => {{
  map._loaded = true;

  // ── H3 source + circle layer ──────────────────────────────
  map.addSource('h3-source', {{ type:'geojson', data:{{ type:'FeatureCollection', features:[] }} }});
  map.addLayer({{
    id: 'h3-cells', type: 'circle', source: 'h3-source',
    paint: {{
      'circle-radius': 5,
      'circle-color': '#4caf50',
      'circle-opacity': 0.7,
    }},
    layout: {{ visibility: 'visible' }}
  }});

  // Click popup on H3 cells
  map.on('click', 'h3-cells', e => {{
    const p = e.features[0].properties;
    const sc = p.score || 0;
    const storeSection = p.c_food > 0
      ? `<hr style="border-color:#334;margin:4px 0"><span style="color:#4fc3f7">음식 상권</span>: ${{p.c_food}}개` : '';
    const popSection = p.pop > 0
      ? `<hr style="border-color:#334;margin:4px 0"><span style="color:#ff9800">추정 생활인구</span>: ${{Math.round(p.pop)}}명<br>주간: ${{Math.round(p.pop_day)}} | 저녁: ${{Math.round(p.pop_eve)}} | 야간: ${{Math.round(p.pop_night)}}<br>피크: ${{p.peak_hour}}시` : '';
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(
        `<div style="font-family:'Noto Sans KR';font-size:12px;">` +
        `<b>${{p.dong}}</b> (${{p.gu}})<br>` +
        `종합: <b>${{sc.toFixed(3)}}</b><br>` +
        `공역: ${{p.sa}} | 장애물: ${{p.so}}<br>` +
        `소음: ${{p.sn}} | 지형: ${{p.st}} | 기상: ${{p.sw}}<br>` +
        `긴급도: ${{p.urg}} | 수요지수: ${{p.ddi}}${{storeSection}}${{popSection}}</div>`
      ).addTo(map);
  }});
  map.on('mouseenter', 'h3-cells', () => map.getCanvas().style.cursor = 'pointer');
  map.on('mouseleave', 'h3-cells', () => map.getCanvas().style.cursor = '');

  // ── Service circles ───────────────────────────────────────
  map.addSource('service-circles', {{ type:'geojson', data:{{ type:'FeatureCollection', features:[] }} }});
  map.addLayer({{
    id: 'service-circles-fill', type: 'fill', source: 'service-circles',
    paint: {{ 'fill-color': ['get', 'color'], 'fill-opacity': 0.07 }}
  }});
  map.addLayer({{
    id: 'service-circles-outline', type: 'line', source: 'service-circles',
    paint: {{ 'line-color': ['get', 'color'], 'line-width': 2, 'line-opacity': 0.8, 'line-dasharray': [3, 2] }}
  }});

  // ── Route lines ───────────────────────────────────────────
  map.addSource('route-lines', {{ type:'geojson', data:{{ type:'FeatureCollection', features:[] }} }});
  map.addLayer({{
    id: 'route-lines-layer', type: 'line', source: 'route-lines',
    paint: {{ 'line-color': ['get', 'color'], 'line-width': 2, 'line-opacity': 0.55, 'line-dasharray': [4, 3] }}
  }});

  // ── Target points ─────────────────────────────────────────
  map.addSource('target-points', {{ type:'geojson', data:{{ type:'FeatureCollection', features:[] }} }});
  map.addLayer({{
    id: 'target-points-layer', type: 'circle', source: 'target-points',
    paint: {{
      'circle-radius': 6,
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.9,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#ffffff',
    }}
  }});
  map.on('click', 'target-points-layer', e => {{
    const p = e.features[0].properties;
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(
        `<div style="font-family:'Noto Sans KR';font-size:12px;">` +
        `<b>${{p.dong}}</b> (${{p.gu}})<br>` +
        `H3: <code style="font-size:10px">${{p.h3}}</code><br>` +
        `종합: <b>${{parseFloat(p.score).toFixed(3)}}</b><br>` +
        `긴급도: ${{p.urg}} | 수요지수: ${{p.ddi}}</div>`
      ).addTo(map);
  }});
  map.on('mouseenter', 'target-points-layer', () => map.getCanvas().style.cursor = 'pointer');
  map.on('mouseleave', 'target-points-layer', () => map.getCanvas().style.cursor = '');

  // ── Hub GeoJSON layers (circle + emoji — geographically anchored) ──
  // Using GeoJSON layers instead of HTML markers so hubs are rendered in
  // the same WebGL projection pass as tiles — eliminates pitch/zoom drift.
  map.addSource('hubs', {{ type: 'geojson', data: {{ type: 'FeatureCollection', features: [] }} }});

  // Glow ring (opacity + radius animated via setInterval below)
  map.addLayer({{
    id: 'hub-glow', type: 'circle', source: 'hubs',
    paint: {{
      'circle-radius': 20,
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.0,
      'circle-stroke-width': 3,
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-opacity': 0.4,
      'circle-pitch-alignment': 'map',
    }}
  }});

  // Solid hub dot
  map.addLayer({{
    id: 'hub-circle', type: 'circle', source: 'hubs',
    paint: {{
      'circle-radius': 13,
      'circle-color': ['get', 'color'],
      'circle-opacity': 1.0,
      'circle-stroke-width': 2.5,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-opacity': 0.95,
      'circle-pitch-alignment': 'map',
    }}
  }});

  // Helicopter emoji symbol on top
  map.addLayer({{
    id: 'hub-labels', type: 'symbol', source: 'hubs',
    layout: {{
      'text-field': '🚁',
      'text-size': 13,
      'text-anchor': 'center',
      'text-allow-overlap': true,
      'text-ignore-placement': true,
      'text-pitch-alignment': 'map',
    }},
    paint: {{ 'text-color': '#ffffff' }}
  }});

  // Hub click popup
  map.on('click', 'hub-circle', e => {{
    const p = e.features[0].properties;
    new maplibregl.Popup({{ offset: 18, maxWidth: '220px' }})
      .setLngLat(e.lngLat)
      .setHTML(
        `<div style="font-family:'Noto Sans KR';font-size:12px;">` +
        `<b style="font-size:13px;color:${{p.color}};">#${{p.rank+1}} ${{p.name}}</b><br>` +
        `시설: ${{p.facility}}<br>수용: ${{p.capacity}}대<br>` +
        `적합셀: <b>${{p.cov}}</b> | 핫스팟: <b>${{p.hotCov}}</b></div>`
      ).addTo(map);
  }});
  map.on('mouseenter', 'hub-circle', () => map.getCanvas().style.cursor = 'pointer');
  map.on('mouseleave', 'hub-circle', () => map.getCanvas().style.cursor = '');

  // ── POI sources + layers ──────────────────────────────────
  Object.entries(POI_CONFIG).forEach(([cat, cfg]) => {{
    const features = (POI[cat] || []).map(p => ({{
      type: 'Feature',
      geometry: {{ type: 'Point', coordinates: [p.lon, p.lat] }},
      properties: {{ name: p.name || '' }}
    }}));
    map.addSource(`poi-${{cat}}`, {{ type:'geojson', data:{{ type:'FeatureCollection', features }} }});
    map.addLayer({{
      id: `poi-${{cat}}`, type: 'circle', source: `poi-${{cat}}`,
      paint: {{
        'circle-radius': cfg.radius,
        'circle-color': cfg.color,
        'circle-opacity': 0.85,
        'circle-stroke-width': 1,
        'circle-stroke-color': cfg.color,
      }},
      layout: {{ visibility: 'none' }}
    }});
    map.on('click', `poi-${{cat}}`, e => {{
      const name = e.features[0].properties.name;
      new maplibregl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(`<div style="font-family:'Noto Sans KR';font-size:12px;">${{cfg.emoji}} ${{name || cat}}</div>`)
        .addTo(map);
    }});
  }});

  // ── 3D Buildings ──────────────────────────────────────────
  map.addSource('buildings-3d', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }},
  }});
  map.addLayer({{
    id: 'buildings-3d-layer',
    type: 'fill-extrusion',
    source: 'buildings-3d',
    minzoom: 12,
    paint: {{
      'fill-extrusion-color': [
        'interpolate', ['linear'], ['get', 'height_m'],
         0,  '#1a2a3a',
        30,  '#1e3a5f',
        80,  '#1e4976',
        150, '#1a5276',
        300, '#145374',
      ],
      'fill-extrusion-height':   ['get', 'height_m'],
      'fill-extrusion-base':     0,
      'fill-extrusion-opacity':  0.75,
      'fill-extrusion-vertical-gradient': true,
    }},
  }});
  fetch('./tableau_data/seoul_buildings_3d.geojson')
    .then(r => r.json())
    .then(data => {{
      map.getSource('buildings-3d').setData(data);
      console.log('3D buildings loaded:', data.features.length, 'features');
    }})
    .catch(err => console.warn('Buildings load failed (need http server):', err));

  // ── Terrain (3D mountains + hillshade) ───────────────────────
  // exaggeration: 1.0 = real-world scale; keeps flat-area building bases stable.
  // Buildings on hillsides may show slight base warp — acceptable since Seoul's
  // dense urban grid sits on flat ground; mountain slopes have no buildings.
  map.addSource('terrain-dem', {{
    type: 'raster-dem',
    tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{{z}}/{{x}}/{{y}}.png'],
    encoding: 'terrarium',
    tileSize: 256,
    maxzoom: 15,
    attribution: 'Terrain &copy; <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen/AWS</a>',
  }});
  map.setTerrain({{ source: 'terrain-dem', exaggeration: 1.0 }});
  map.addLayer({{
    id: 'hillshade', type: 'hillshade', source: 'terrain-dem',
    paint: {{
      'hillshade-exaggeration': 0.5,
      'hillshade-shadow-color': '#0a0a1a',
      'hillshade-highlight-color': '#1e3a5f',
      'hillshade-accent-color': '#0f2a4a',
      'hillshade-illumination-anchor': 'map',
    }},
  }}, 'h3-cells');

  // ── Initial dashboard render ──────────────────────────────
  updateDashboard();
}});

// ── Hub glow animation (~15 fps — no per-frame setPaintProperty overhead) ──
let _glowT = 0;
setInterval(() => {{
  _glowT += 0.12;
  const t = (Math.sin(_glowT) + 1) / 2;   // 0 → 1 oscillation
  if (map._loaded && map.getLayer('hub-glow')) {{
    map.setPaintProperty('hub-glow', 'circle-stroke-opacity', 0.12 + 0.38 * t);
    map.setPaintProperty('hub-glow', 'circle-radius', 16 + 8 * t);
  }}
}}, 67);  // ~15 fps

// ── Layer toggle events ───────────────────────────────────────
document.querySelectorAll('.layer-toggle').forEach(label => {{
  label.addEventListener('click', function(e) {{
    const inp = this.querySelector('input');
    inp.checked = !inp.checked;
    this.classList.toggle('active', inp.checked);
    const spin = document.getElementById('update-spin');
    spin.classList.add('show');
    setTimeout(() => {{ updateDashboard(); spin.classList.remove('show'); }}, 30);
    e.preventDefault();
  }});
}});

// Color mode selector — only re-draws H3 layer, doesn't rerun hub selection
document.getElementById('color-mode-select').addEventListener('change', function() {{
  colorMode = this.value;
  if (window._lastScores) renderH3Layer(window._lastScores);
}});

// ═══════════════════════════════════════════════════════════════
// Static charts (Plotly)
// ═══════════════════════════════════════════════════════════════
const plotlyLayout = {{
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  font: {{ family:'Noto Sans KR', color:'#bbc', size:12 }},
  margin: {{ l:50, r:20, t:10, b:50 }},
}};

// ── Bar: Top 15 dong by composite ────────────────────────────
(() => {{
  const sorted = [...DONG].sort((a,b) => b.avg_cs - a.avg_cs).slice(0,15);
  Plotly.newPlot('chart-bar', [{{
    type: 'bar',
    x: sorted.map(d => d.name),
    y: sorted.map(d => d.avg_cs),
    marker: {{ color: sorted.map(d => scoreToColor(d.avg_cs)), line: {{color:'#0f3460',width:1}} }},
    text: sorted.map(d => d.avg_cs.toFixed(3)),
    textposition: 'outside',
    textfont: {{ size:10, color:'#aab' }},
    hovertemplate: '%{{x}}<br>종합점수: %{{y:.3f}}<extra></extra>',
  }}], {{
    ...plotlyLayout,
    xaxis: {{ tickangle:-35, tickfont:{{size:11}}, gridcolor:'#0f346033' }},
    yaxis: {{ gridcolor:'#0f346044', zeroline:false }},
    margin: {{ ...plotlyLayout.margin, b:80 }},
  }}, {{ responsive:true, displayModeBar:false }});
}})();

// ── Radar: motorcycle vs drone ────────────────────────────────
(() => {{
  const metrics = RADAR.map(r => r.metric);
  Plotly.newPlot('chart-radar', [
    {{ type:'scatterpolar', r:RADAR.map(r=>r.motorcycle), theta:metrics,
       fill:'toself', fillcolor:'rgba(255,112,67,0.15)', line:{{color:'#ff7043',width:2}},
       name:'오토바이', marker:{{size:6}} }},
    {{ type:'scatterpolar', r:RADAR.map(r=>r.drone), theta:metrics,
       fill:'toself', fillcolor:'rgba(79,195,247,0.15)', line:{{color:'#4fc3f7',width:2}},
       name:'드론+로봇', marker:{{size:6}} }},
  ], {{
    ...plotlyLayout,
    polar: {{ bgcolor:'rgba(0,0,0,0)',
      radialaxis: {{ visible:true, range:[0,1], gridcolor:'#0f346055', tickfont:{{size:9}} }},
      angularaxis: {{ gridcolor:'#0f346055', tickfont:{{size:10}} }} }},
    legend: {{ x:0.85, y:1.1, font:{{size:11}} }},
    margin: {{ l:30, r:30, t:20, b:20 }},
  }}, {{ responsive:true, displayModeBar:false }});
}})();

// ── Line: hourly demand ───────────────────────────────────────
(() => {{
  const labels = {{1:'0-2h',2:'2-4h',3:'6-8h',4:'8-10h',5:'10-12h',
                   6:'12-14h',7:'14-18h',8:'18-21h',9:'21-23h',10:'23-24h'}};
  Plotly.newPlot('chart-hourly', [{{
    type:'scatter', mode:'lines+markers',
    x: HOURLY.map(h => labels[h.hour] || ('T'+h.hour)),
    y: HOURLY.map(h => h.avg_ratio),
    line: {{ color:'#4fc3f7', width:3, shape:'spline' }},
    marker: {{ size:8, color:'#4fc3f7', line:{{color:'#fff',width:1}} }},
    fill:'tozeroy', fillcolor:'rgba(79,195,247,0.1)',
    hovertemplate:'%{{x}}<br>비율: %{{y:.3f}}<extra></extra>',
  }}], {{
    ...plotlyLayout,
    xaxis: {{ tickangle:-25, gridcolor:'#0f346033' }},
    yaxis: {{ gridcolor:'#0f346044', zeroline:false }},
  }}, {{ responsive:true, displayModeBar:false }});
}})();

// ── Horizontal bar: feasible % ────────────────────────────────
(() => {{
  const sorted = [...DONG].filter(d=>d.pct_f>0).sort((a,b)=>a.pct_f-b.pct_f);
  Plotly.newPlot('chart-feasible', [{{
    type:'bar', orientation:'h',
    y: sorted.map(d => d.name+' ('+d.gu+')'),
    x: sorted.map(d => d.pct_f),
    marker: {{
      color: sorted.map(d => d.pct_f>=80?'#53d769':d.pct_f>=40?'#ffb74d':'#e94560'),
      line: {{color:'#0f3460',width:1}}
    }},
    text: sorted.map(d => d.pct_f.toFixed(1)+'%'),
    textposition:'outside', textfont:{{size:10,color:'#aab'}},
    hovertemplate:'%{{y}}<br>적합 비율: %{{x:.1f}}%<extra></extra>',
  }}], {{
    ...plotlyLayout,
    xaxis: {{ range:[0,115], gridcolor:'#0f346044' }},
    yaxis: {{ tickfont:{{size:10}}, automargin:true }},
    margin: {{ l:150, r:40, t:10, b:40 }},
    height: Math.max(220, sorted.length * 22),
  }}, {{ responsive:true, displayModeBar:false }});
}})();

// ── Mode comparison table ─────────────────────────────────────
(() => {{
  const tbody = document.getElementById('comp-tbody');
  MODE.forEach(r => {{
    const tr = document.createElement('tr');
    const adv = r.advantage === '드론+로봇';
    tr.innerHTML = `<td>${{r.indicator}}</td><td>${{r.motorcycle}}</td><td>${{r.drone}}</td>
      <td><span class="tag ${{adv?'tag-green':'tag-red'}}">${{r.advantage}}</span></td>`;
    tbody.appendChild(tr);
  }});
}})();
</script>
</body>
</html>"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Dashboard written: {OUT_HTML}")
print(f"  Grid cells:          {len(grid_js)}")
print(f"  Candidate facilities:{len(fac_js)}")
print(f"  Coverage pairs:      {total_pairs}")
print(f"  File size:           {os.path.getsize(OUT_HTML)/1024:.0f} KB")
