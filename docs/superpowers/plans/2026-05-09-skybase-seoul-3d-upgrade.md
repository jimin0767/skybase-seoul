# SkyBase Seoul 3D Dashboard Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the competition HTML dashboard from a flat Leaflet map to a MapLibre GL JS 3D map with pitch, 3D buildings, terrain, cleaned H3 visibility, and a fixed layout where `최적 거점` lives below the map row.

**Architecture:** All durable changes live in `03_visualization/build_dashboard.py`; `dashboard.html` is always regenerated from it. A one-time script `03_visualization/build_buildings.py` pre-processes the 696 K-polygon building GPKG into a filtered, simplified `tableau_data/seoul_buildings_3d.geojson` that the dashboard loads via `fetch`. Terrain uses the free public Terrarium tile service so no local conversion is needed.

**Tech Stack:** Python 3 + geopandas + shapely + rasterio (already installed); MapLibre GL JS 4.x CDN; CARTO dark-matter-gl-style (free, no API key); Plotly CDN (unchanged); AWS Elevation Tiles (Terrarium, free, no key).

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `03_visualization/build_dashboard.py` | Modify | Python generator — HTML/CSS/JS template |
| `03_visualization/dashboard.html` | Regenerate | Final deliverable (never hand-edit) |
| `03_visualization/build_buildings.py` | Create | One-time: process GPKG → buildings GeoJSON |
| `03_visualization/tableau_data/seoul_buildings_3d.geojson` | Generate | Height-cleaned, simplified building polygons |

---

## Task 1 — Fix Dashboard Layout

**Goal:** Move `최적 거점` hub panel out of the right side-panel and into a full-width row below the map+controls row. Convert the hub list from a narrow column to a responsive card grid.

**Files:** Modify `03_visualization/build_dashboard.py` (CSS + HTML template only, no JS changes yet).

- [ ] **Step 1: Remove hub-panel from side-panel in the HTML template**

In `build_dashboard.py`, find the `<!-- Dynamic Hub Results -->` block (lines 587–593 in the current file) and delete it from inside `<div class="side-panel">`.

The side-panel should now contain only two children:
```html
<div class="side-panel">
  <!-- Layer Toggles -->
  <div class="layer-panel"> ... </div>
  <!-- POI Layer Toggles -->
  <div class="poi-panel"> ... </div>
</div>
```

- [ ] **Step 2: Add full-width hub section below `.main-grid`**

Immediately after the closing `</div>` of `.main-grid` (and before the chart rows), insert:

```html
<!-- Full-width Hub Results -->
<div class="hub-section">
  <div class="panel-title" style="margin-bottom:12px;">
    📍 최적 거점
    <span id="hub-count-badge" style="background:#e9456033;color:#e94560;border-radius:10px;padding:1px 8px;font-size:12px;margin-left:8px;"></span>
  </div>
  <div id="hub-list" class="hub-grid">
    <div style="color:#556;font-size:12px;padding:8px;">레이어 조합 중…</div>
  </div>
</div>
```

- [ ] **Step 3: Replace CSS for `.hub-panel` and `#hub-list` with hub-section + hub-grid styles**

Remove the existing `.hub-panel` and `#hub-list` CSS blocks. Add:

```css
/* Full-width hub section */
.hub-section {
  background: linear-gradient(145deg,#16213e,#1a1a2e);
  border: 1px solid #0f3460;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

/* Responsive card grid for hubs */
.hub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 4px;
}

.hub-item {
  background: #0f1928;
  border: 1px solid #1a3a5c;
  border-radius: 8px;
  padding: 12px 14px;
  transition: all .35s ease;
  position: relative;
  overflow: hidden;
}
.hub-item.new-hub { border-color:#53d769; background:#0a1f0f; animation:hubPop .5s ease; }
.hub-item.removed { opacity:.4; border-color:#e94560; }
@keyframes hubPop { 0%{transform:scale(.95);opacity:0} 60%{transform:scale(1.03)} 100%{transform:scale(1);opacity:1} }
.hub-item .hub-name { font-size:13px; font-weight:600; color:#e0e0e0; }
.hub-item .hub-detail { font-size:11px; color:#8899aa; margin-top:3px; }
.hub-rank { position:absolute; top:8px; right:10px; font-size:20px; opacity:.5; }
.hub-coverage-bar { height:4px; border-radius:2px; margin-top:7px; background:#1a3a5c; overflow:hidden; }
.hub-coverage-fill { height:100%; border-radius:2px; background:linear-gradient(90deg,#53d769,#4fc3f7); transition:width .6s ease; }
```

- [ ] **Step 4: Regenerate and smoke-check layout**

```bash
cd "C:\Users\jimin\Desktop\1_BITAmin_16기\skybase-seoul-3D\.claude\worktrees\admiring-hugle-2d713e"
python 03_visualization/build_dashboard.py
```

Expected output ends with `Dashboard written: ...dashboard.html`. Visually verify:
- Hub cards appear in a grid row below the map, not in the right column.
- No large empty dark space under the map.
- Right side-panel shows only layer toggles + POI panel.

---

## Task 2 — H3 3-State Visibility Control (Leaflet, pre-MapLibre)

**Goal:** Add a 3-button toggle that controls H3 cell visibility: `전체 H3 표시` / `거점 관련 H3만 표시` / `H3 숨김`. Default is `거점 관련 H3만 표시`. Fix `kpi-avg-cs` to compute directly from `scores` (not from marker creation).

**Files:** Modify `03_visualization/build_dashboard.py` (CSS + JS changes).

- [ ] **Step 1: Add H3 visibility control HTML**

Inside the `.layer-panel` div, after the `formula-box` div and the `color-mode-select` block, add:

```html
<div style="margin-top:10px;">
  <label style="font-size:11px;color:#8899aa;">🔲 H3 셀 표시 모드</label>
  <div id="h3-vis-control" style="display:flex;gap:6px;margin-top:4px;">
    <button class="h3-vis-btn" data-mode="all"
      style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
             background:#0f1928;color:#8899aa;border:1px solid #1a3a5c;
             border-radius:6px;cursor:pointer;">전체 H3 표시</button>
    <button class="h3-vis-btn active" data-mode="hub"
      style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
             background:#0f3460;color:#4fc3f7;border:1px solid #4fc3f7;
             border-radius:6px;cursor:pointer;">거점 관련만</button>
    <button class="h3-vis-btn" data-mode="none"
      style="flex:1;padding:6px 4px;font-size:10px;font-family:'Noto Sans KR';
             background:#0f1928;color:#8899aa;border:1px solid #1a3a5c;
             border-radius:6px;cursor:pointer;">H3 숨김</button>
  </div>
</div>
```

- [ ] **Step 2: Add H3 visibility state variable and button handler in JS**

After the `let colorMode = 'score';` line, add:

```js
let h3VisMode = 'hub'; // 'all' | 'hub' | 'none'
let lastHubCoveredSet = new Set(); // cell indices covered by current hubs

document.querySelectorAll('.h3-vis-btn').forEach(btn => {
  btn.addEventListener('click', function() {
    h3VisMode = this.dataset.mode;
    document.querySelectorAll('.h3-vis-btn').forEach(b => {
      const on = b.dataset.mode === h3VisMode;
      b.style.background = on ? '#0f3460' : '#0f1928';
      b.style.color = on ? '#4fc3f7' : '#8899aa';
      b.style.borderColor = on ? '#4fc3f7' : '#1a3a5c';
    });
    // Re-render with current scores (stored on last update)
    if (window._lastScores) renderH3Layer(window._lastScores);
  });
});
```

- [ ] **Step 3: Refactor `buildHexLayer` into `renderH3Layer` that respects h3VisMode**

Replace the entire `buildHexLayer(scores)` function with:

```js
let hexMarkers = [];
function getHexColor(cell, score) {
  if (colorMode === 'score') return scoreToColor(score);
  const mode = COLOR_MODES[colorMode];
  if (!mode || !mode.field) return scoreToColor(score);
  if (mode.pop) return popToColor(cell[mode.field] || 0);
  return densityToColor(cell[mode.field] || 0, mode.max);
}

function renderH3Layer(scores) {
  hexMarkers.forEach(m => map.removeLayer(m));
  hexMarkers = [];

  if (h3VisMode === 'none') return;

  scores.forEach((sc, i) => {
    // 'hub' mode: only show cells covered by currently selected hubs
    if (h3VisMode === 'hub' && !lastHubCoveredSet.has(i)) return;

    const cell = GRID[i];
    const fillC = getHexColor(cell, sc);
    const m = L.circleMarker([cell.lat, cell.lon], {
      radius: 5, fillColor: fillC, fillOpacity: 0.7,
      color: fillC, weight: 0.5, opacity: 0.9
    });
    const storeSection = cell.c_food != null
      ? `<hr style="border-color:#334;margin:4px 0"><span style="color:#4fc3f7">음식 상권</span>: ${cell.c_food}개`
      : '';
    const popSection = cell.pop != null
      ? `<hr style="border-color:#334;margin:4px 0"><span style="color:#ff9800">추정 생활인구</span>: ${Math.round(cell.pop)}명<br>주간: ${Math.round(cell.pop_day)} | 저녁: ${Math.round(cell.pop_eve)} | 야간: ${Math.round(cell.pop_night)}<br>피크 시간: ${cell.peak_hour}시`
      : '';
    m.bindPopup(
      `<div style="font-family:'Noto Sans KR',sans-serif;font-size:12px;">` +
      `<b>${cell.dong}</b> (${cell.gu})<br>` +
      `종합: <b style="color:${scoreToColor(sc)}">${sc.toFixed(3)}</b><br>` +
      `공역: ${cell.sa} | 장애물: ${cell.so}<br>` +
      `소음: ${cell.sn} | 지형: ${cell.st} | 기상: ${cell.sw}<br>` +
      `긴급도: ${cell.urg} | 수요지수: ${cell.ddi}` +
      `${storeSection}${popSection}</div>`
    );
    m.addTo(map);
    hexMarkers.push(m);
  });
}
```

- [ ] **Step 4: Fix `kpi-avg-cs` and update `buildHubLayer` to populate `lastHubCoveredSet`**

At the top of `buildHubLayer(selFacIndices, scores)`, after clearing arrays, add:

```js
// Rebuild covered-cell set for H3 hub-mode filter
lastHubCoveredSet = new Set();
selFacIndices.forEach(fi => {
  COV[fi].forEach(ci => lastHubCoveredSet.add(ci));
});
```

- [ ] **Step 5: Fix `updateDashboard()` to use the new names and compute avg-cs from scores**

Replace the call `buildHexLayer(scores)` with:

```js
// Compute avg composite score directly (not from marker creation)
const avgCs = scores.reduce((s, v) => s + v, 0) / scores.length;
document.getElementById('kpi-avg-cs').textContent = avgCs.toFixed(3);

// Store for h3-vis-btn re-renders
window._lastScores = scores;
```

And replace the call `buildHexLayer(scores)` with `renderH3Layer(scores)` — but this call must happen **after** `buildHubLayer(selFacIndices, scores)` so `lastHubCoveredSet` is already populated when `renderH3Layer` runs.

Full updated `updateDashboard()`:
```js
function updateDashboard() {
  const active = getActiveLayers();
  const scores = GRID.map(cell => recalcScore(cell, active));

  // Avg composite KPI — computed directly, independent of H3 rendering
  const avgCs = scores.reduce((s, v) => s + v, 0) / scores.length;
  document.getElementById('kpi-avg-cs').textContent = avgCs.toFixed(3);
  window._lastScores = scores;

  const result = selectHubs(scores);
  const { hubs: selFacIndices, feasible, hotspots, uncovered } = result;

  // Hub layer first — populates lastHubCoveredSet
  buildHubLayer(selFacIndices, scores);

  // H3 layer after — uses lastHubCoveredSet for 'hub' mode
  renderH3Layer(scores);

  renderHubList(selFacIndices, scores, hotspots);

  document.getElementById('kpi-feasible').textContent = feasible.size.toLocaleString();
  document.getElementById('kpi-num-hubs').textContent = selFacIndices.length;
  const coveredHots = hotspots.size - (uncovered ? uncovered.size : 0);
  const covPct = hotspots.size > 0 ? (coveredHots / hotspots.size * 100).toFixed(1) : '0.0';
  document.getElementById('kpi-coverage').textContent = covPct + '%';

  const names = {sa:'공역',so:'장애물',sn:'소음',st:'지형',sw:'기상'};
  const parts = Object.entries(active).filter(([,v])=>v).map(([k])=>names[k]);
  document.getElementById('formula-display').textContent =
    parts.length ? parts.join(' × ') : '(선택 없음 — 모든 셀 점수 0)';
}
```

Also update the `color-mode-select` change handler to call `renderH3Layer` instead of `updateDashboard`:
```js
document.getElementById('color-mode-select').addEventListener('change', function() {
  colorMode = this.value;
  if (window._lastScores) renderH3Layer(window._lastScores);
});
```

- [ ] **Step 6: Regenerate and verify**

```bash
python 03_visualization/build_dashboard.py
```

Open `dashboard.html`. Verify:
- 3 H3 mode buttons visible in layer panel.
- Default is `거점 관련만` (highlighted blue).
- Switching to `H3 숨김` hides all H3 dots — only hubs, circles, lines, POIs visible.
- Switching to `전체 H3 표시` shows all 8,322 dots.
- `kpi-avg-cs` updates on layer toggle regardless of H3 mode.
- Hub cards appear in grid below the map.

- [ ] **Step 7: Commit**

```bash
git add 03_visualization/build_dashboard.py 03_visualization/dashboard.html
git commit -m "feat: fix layout + add H3 3-state visibility control"
```

---

## Task 3 — Generate 3D Buildings GeoJSON

**Goal:** Create `03_visualization/tableau_data/seoul_buildings_3d.geojson` — a filtered, height-cleaned, geometry-simplified subset of the 696 K building GPKG, suitable for MapLibre `fill-extrusion`.

**Files:** Create `03_visualization/build_buildings.py`.

- [ ] **Step 1: Create `build_buildings.py`**

```python
#!/usr/bin/env python3
"""
Pre-process processed/seoul_buildings.gpkg → tableau_data/seoul_buildings_3d.geojson
for MapLibre fill-extrusion.

Height cleaning rules (mirrors task spec):
  1. If HEIGHT is numeric and 2 ≤ HEIGHT ≤ 300 → use HEIGHT
  2. Else if GRND_FLR >= 1 → use GRND_FLR * 3
  3. Else → default 6 m
  Cap at 300 m.

Filter: keep only buildings where computed height_m >= 10 m.
Geometry: simplify with tolerance 0.00005 degrees (~5 m) and ensure validity.
"""
import json
from pathlib import Path
import geopandas as gpd
from shapely.validation import make_valid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GPKG = PROJECT_ROOT / "processed" / "seoul_buildings.gpkg"
OUT = Path(__file__).resolve().parent / "tableau_data" / "seoul_buildings_3d.geojson"
LAYER = "buildings_4326"
SIMPLIFY_TOL = 0.00005   # degrees, ≈ 5 m
MIN_HEIGHT_M = 10.0      # only buildings with height ≥ 10 m
MAX_HEIGHT_M = 300.0     # cap
SIMPLIFY_PRESERVE_TOPOLOGY = True


def compute_height(row):
    h = row["HEIGHT"]
    if h == h and h is not None:   # not NaN
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

    # Compute height_m
    gdf["height_m"] = gdf.apply(compute_height, axis=1)

    # Filter
    gdf = gdf[gdf["height_m"] >= MIN_HEIGHT_M].copy()
    print(f"  After height filter (≥{MIN_HEIGHT_M} m): {len(gdf):,} buildings")

    # Make valid + simplify
    print("  Simplifying geometries …")
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g).simplify(SIMPLIFY_TOL, preserve_topology=SIMPLIFY_PRESERVE_TOPOLOGY)
    )
    # Drop any that collapsed to non-polygon
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    print(f"  After simplify/filter: {len(gdf):,} buildings")

    # Keep only needed columns
    out_gdf = gdf[["height_m", "geometry"]].copy()

    # Write GeoJSON
    out_gdf.to_file(OUT, driver="GeoJSON")
    size_mb = OUT.stat().st_size / 1_048_576
    print(f"Written: {OUT}  ({size_mb:.1f} MB, {len(out_gdf):,} features)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

```bash
cd "C:\Users\jimin\Desktop\1_BITAmin_16기\skybase-seoul-3D\.claude\worktrees\admiring-hugle-2d713e"
python 03_visualization/build_buildings.py
```

Expected output (approximate):
```
Reading .../seoul_buildings.gpkg layer=buildings_4326 …
  Total: 696,712 buildings
  After height filter (≥10.0 m): ~150,000–200,000 buildings
  Simplifying geometries …
  After simplify/filter: ~140,000–190,000 buildings
Written: .../seoul_buildings_3d.geojson  (~10–30 MB, ...)
```

If output file > 40 MB: increase `MIN_HEIGHT_M` to 15 and re-run. Target is < 30 MB.

- [ ] **Step 3: Quick sanity check**

```bash
python -c "
import json
with open('03_visualization/tableau_data/seoul_buildings_3d.geojson') as f:
    d = json.load(f)
feats = d['features']
print(f'Features: {len(feats)}')
props = feats[0]['properties']
print(f'Properties: {list(props.keys())}')
heights = [f[\"properties\"][\"height_m\"] for f in feats]
print(f'Height range: {min(heights):.1f} – {max(heights):.1f} m')
"
```

- [ ] **Step 4: Commit**

```bash
git add 03_visualization/build_buildings.py 03_visualization/tableau_data/seoul_buildings_3d.geojson
git commit -m "feat: add 3D buildings GeoJSON generator"
```

---

## Task 4 — Migrate Map Engine to MapLibre GL JS

**Goal:** Replace Leaflet with MapLibre GL JS in `build_dashboard.py`. Preserve all existing behavior (layer toggles, hub selection, POI toggles, H3 3-state) while adding 3D pitch, right-click-drag pitch control, and a dark vector basemap.

**Files:** Modify `03_visualization/build_dashboard.py` — replace CDN links, CSS, and the entire map JavaScript section.

### 4a — CDN and map container CSS

- [ ] **Step 1: Replace Leaflet CDN links with MapLibre**

In `build_dashboard.py`, replace:
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```
with:
```html
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css"/>
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
```

- [ ] **Step 2: Update `#map` CSS**

MapLibre needs the map container to have explicit height and no `overflow:hidden` on a parent that conflicts. Change:
```css
.map-panel {{ background:#16213e; border-radius:12px; overflow:hidden; border:1px solid #0f3460; position:relative; }}
#map {{ height:600px; width:100%; }}
```
to:
```css
.map-panel {{ background:#16213e; border-radius:12px; border:1px solid #0f3460; position:relative; overflow:hidden; }}
#map {{ height:600px; width:100%; }}
.maplibregl-canvas {{ border-radius:11px; }}
```

### 4b — MapLibre map initialization

- [ ] **Step 3: Replace Leaflet `map` init with MapLibre**

Find and remove this block:
```js
const map = L.map('map', {{ preferCanvas: true }}).setView([37.5665, 126.9780], 11);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  maxZoom: 19, subdomains: 'abcd'
}}).addTo(map);
L.control.attribution({{prefix:false}}).addAttribution(...).addTo(map);
```

Replace with:
```js
const map = new maplibregl.Map({{
  container: 'map',
  style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  center: [126.9780, 37.5665],
  zoom: 11,
  pitch: 45,
  bearing: 0,
  antialias: true,
}});

// Right-click drag → pitch control
// Drag upward (–dy) = increase pitch (buildings more side-on)
// Drag downward (+dy) = decrease pitch (more top-down)
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
  map.setPitch(Math.max(0, Math.min(85, _rcDrag.pitch - dy * 0.35)));
}});
window.addEventListener('mouseup', e => {{ if (e.button === 2) _rcDrag = null; }});
map.getCanvas().addEventListener('contextmenu', e => e.preventDefault());

// Add navigation controls (zoom + compass)
map.addControl(new maplibregl.NavigationControl(), 'top-right');
```

### 4c — POI layers (MapLibre GeoJSON + circle layers)

- [ ] **Step 4: Replace Leaflet POI layer groups with MapLibre sources/layers**

Remove the entire POI LayerGroup block and POI toggle event listener. Replace with:

```js
// POI layers — created inside map.on('load', ...) block
const POI_CONFIG = {{
  park:       {{ color:'#ffffff', radius:5,  emoji:'🌳' }},
  commercial: {{ color:'#9c27b0', radius:6,  emoji:'🏪' }},
  medical:    {{ color:'#e040fb', radius:5,  emoji:'🏥' }},
  subway:     {{ color:'#7c4dff', radius:6,  emoji:'🚇' }},
  school:     {{ color:'#b39ddb', radius:5,  emoji:'🏫' }},
}};

// We build POI sources/layers inside map.on('load'). See Step 8.

// POI toggle buttons (same as before but uses setLayoutProperty)
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
```

### 4d — H3 source + layer

- [ ] **Step 5: Define H3 GeoJSON builder helper**

Add this helper function (used by `renderH3Layer`):

```js
function buildGridGeoJSON(scores, filterSet) {{
  // filterSet: Set of indices to include, or null for all
  const features = [];
  GRID.forEach((cell, i) => {{
    if (filterSet !== null && !filterSet.has(i)) return;
    features.push({{
      type: 'Feature',
      geometry: {{ type: 'Point', coordinates: [cell.lon, cell.lat] }},
      properties: {{
        score: scores[i],
        dong: cell.dong,
        gu: cell.gu,
        h3: cell.h3,
        urg: cell.urg,
        urgv: cell.urgv,
        ddi: cell.ddi,
        c_food: cell.c_food || 0,
        pop_idx: cell.pop_idx || 0,
        pop_day_idx: cell.pop_day_idx || 0,
        pop_eve_idx: cell.pop_eve_idx || 0,
        pop_night_idx: cell.pop_night_idx || 0,
      }}
    }});
  }});
  return {{ type: 'FeatureCollection', features }};
}}
```

- [ ] **Step 6: Replace Leaflet `renderH3Layer` with MapLibre source update**

Remove the Leaflet `hexMarkers` array and the old `renderH3Layer`. Replace with:

```js
function renderH3Layer(scores) {{
  if (!map._loaded) return;

  let filterSet = null;
  if (h3VisMode === 'none') {{
    map.setLayoutProperty('h3-cells', 'visibility', 'none');
    return;
  }}
  map.setLayoutProperty('h3-cells', 'visibility', 'visible');

  if (h3VisMode === 'hub') filterSet = lastHubCoveredSet;

  const geojson = buildGridGeoJSON(scores, filterSet);
  map.getSource('h3-source').setData(geojson);

  // Color paint depends on colorMode
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
    colorExpr = ['interpolate', ['linear'], ['get', field],
      0, '#1a1a2e', 0.5, '#0d47a1', 1, '#ffeb3b'
    ];
  }}
  map.setPaintProperty('h3-cells', 'circle-color', colorExpr);
}}
```

### 4e — Hub markers, service circles, route lines, target points

- [ ] **Step 7: Replace Leaflet `buildHubLayer` with MapLibre version**

Remove the old `buildHubLayer`. Add helper `makeCirclePolygon` and new `buildHubLayer`:

```js
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
    properties: {{ color, rank, lineColor: color }},
    geometry: {{ type: 'Polygon', coordinates: [coords] }} }};
}}

let hubMarkers = [];

function buildHubLayer(selFacIndices, scores) {{
  // Remove old hub markers
  hubMarkers.forEach(m => m.remove());
  hubMarkers = [];

  // Rebuild covered-cell set
  lastHubCoveredSet = new Set();
  selFacIndices.forEach(fi => COV[fi].forEach(ci => lastHubCoveredSet.add(ci)));

  const serviceFeatures = [];
  const routeFeatures   = [];
  const targetFeatures  = [];

  selFacIndices.forEach((fi, rank) => {{
    const fac   = FACS[fi];
    const color = PALETTE[rank % PALETTE.length];

    // Hub HTML marker
    const el = document.createElement('div');
    el.style.cssText = 'position:relative;width:44px;height:44px;cursor:pointer;';
    el.innerHTML = `
      <div style="position:absolute;inset:0;border-radius:50%;
        border:3px solid ${{color}};opacity:.45;
        animation:hubPulse 1.8s ease-in-out infinite;"></div>
      <div style="position:absolute;inset:6px;border-radius:50%;
        background:radial-gradient(circle,${{color}} 30%,${{color}}cc 100%);
        border:2.5px solid #fff;display:flex;align-items:center;
        justify-content:center;font-size:16px;">🚁</div>`;

    const cov    = COV[fi].filter(ci => scores[ci] > 0).length;
    const hotCov = COV[fi].filter(ci => scores[ci] > 0 && GRID[ci].urgv >= URG_THR).length;
    const popup  = new maplibregl.Popup({{ offset: 25 }}).setHTML(
      `<div style="font-family:'Noto Sans KR';font-size:12px;">` +
      `<b style="font-size:14px;color:${{color}};">#${{rank+1}} ${{fac.name}}</b><br>` +
      `시설: ${{fac.facility}} | 수용: ${{fac.capacity}}대<br>` +
      `적합셀 커버: <b>${{cov}}</b>셀 | 핫스팟: <b>${{hotCov}}</b>셀</div>`
    );
    const marker = new maplibregl.Marker({{ element: el, anchor: 'center' }})
      .setLngLat([fac.lon, fac.lat])
      .setPopup(popup)
      .addTo(map);
    hubMarkers.push(marker);

    // Service circle polygon
    serviceFeatures.push(makeCirclePolygon(fac.lat, fac.lon, 500, color, rank));

    // Route lines + target points (top-5 urgent cells)
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
          score: scores[ci], urg: GRID[ci].urg, ddi: GRID[ci].ddi
        }},
        geometry: {{ type: 'Point', coordinates: [GRID[ci].lon, GRID[ci].lat] }}
      }});
    }});
  }});

  map.getSource('service-circles').setData({{ type: 'FeatureCollection', features: serviceFeatures }});
  map.getSource('route-lines').setData({{ type: 'FeatureCollection', features: routeFeatures }});
  map.getSource('target-points').setData({{ type: 'FeatureCollection', features: targetFeatures }});
}}
```

### 4f — `map.on('load', ...)` block

- [ ] **Step 8: Add the `map.on('load', ...)` block that creates all sources + layers, then runs initial render**

This block replaces the old `updateDashboard()` initial call and the static POI group setup.

```js
let map_loaded = false;

map.on('load', () => {{
  map_loaded = true;

  // ── H3 source + circle layer ──────────────────────────────────
  map.addSource('h3-source', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'h3-cells',
    type: 'circle',
    source: 'h3-source',
    paint: {{
      'circle-radius': 5,
      'circle-color': '#4caf50',
      'circle-opacity': 0.7,
    }},
    layout: {{ visibility: 'visible' }}
  }});

  // ── Service circles ───────────────────────────────────────────
  map.addSource('service-circles', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'service-circles-fill',
    type: 'fill',
    source: 'service-circles',
    paint: {{
      'fill-color': ['get', 'color'],
      'fill-opacity': 0.08,
    }}
  }});
  map.addLayer({{
    id: 'service-circles-outline',
    type: 'line',
    source: 'service-circles',
    paint: {{
      'line-color': ['get', 'color'],
      'line-width': 2,
      'line-opacity': 0.8,
      'line-dasharray': [3, 2],
    }}
  }});

  // ── Route lines ───────────────────────────────────────────────
  map.addSource('route-lines', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'route-lines-layer',
    type: 'line',
    source: 'route-lines',
    paint: {{
      'line-color': ['get', 'color'],
      'line-width': 2,
      'line-opacity': 0.55,
      'line-dasharray': [4, 3],
    }}
  }});

  // ── Target points ─────────────────────────────────────────────
  map.addSource('target-points', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'target-points-layer',
    type: 'circle',
    source: 'target-points',
    paint: {{
      'circle-radius': 6,
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.9,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#ffffff',
    }}
  }});

  // Target point click popup
  map.on('click', 'target-points-layer', e => {{
    const p = e.features[0].properties;
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(
        `<div style="font-family:'Noto Sans KR';font-size:12px;">` +
        `<b>${{p.dong}}</b> (${{p.gu}})<br>` +
        `H3: <code>${{p.h3}}</code><br>` +
        `종합: <b>${{p.score?.toFixed(3)}}</b> | 긴급도: ${{p.urg}}<br>` +
        `수요지수: ${{p.ddi}}</div>`
      ).addTo(map);
  }});
  map.on('mouseenter', 'target-points-layer', () => map.getCanvas().style.cursor = 'pointer');
  map.on('mouseleave', 'target-points-layer', () => map.getCanvas().style.cursor = '');

  // ── POI sources + layers ──────────────────────────────────────
  Object.entries(POI_CONFIG).forEach(([cat, cfg]) => {{
    const features = (POI[cat] || []).map(p => ({{
      type: 'Feature',
      geometry: {{ type: 'Point', coordinates: [p.lon, p.lat] }},
      properties: {{ name: p.name || '' }}
    }}));
    map.addSource(`poi-${{cat}}`, {{
      type: 'geojson',
      data: {{ type: 'FeatureCollection', features }}
    }});
    map.addLayer({{
      id: `poi-${{cat}}`,
      type: 'circle',
      source: `poi-${{cat}}`,
      paint: {{
        'circle-radius': cfg.radius,
        'circle-color': cfg.color,
        'circle-opacity': 0.85,
        'circle-stroke-width': 1,
        'circle-stroke-color': cfg.color,
      }},
      layout: {{ visibility: 'none' }}
    }});
    // Click popup for POI
    map.on('click', `poi-${{cat}}`, e => {{
      const name = e.features[0].properties.name;
      new maplibregl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(`<div style="font-family:'Noto Sans KR';font-size:12px;">${{cfg.emoji}} ${{name || cat}}</div>`)
        .addTo(map);
    }});
  }});

  // ── Initial dashboard render ──────────────────────────────────
  updateDashboard();
}});
```

- [ ] **Step 9: Update `updateDashboard()` to guard against map not loaded**

At the top of `updateDashboard()`, add:
```js
if (!map_loaded) return;
```

- [ ] **Step 10: Regenerate, open, and verify MapLibre migration**

```bash
python 03_visualization/build_dashboard.py
```

Open `dashboard.html`. Verify:
- Map renders with CARTO dark vector basemap.
- Pitch 45° visible on load (buildings would lean if present).
- Right-click + drag upward increases pitch.
- Hub markers (🚁) visible with pulsing rings.
- Service circles (dashed outline) visible.
- Route lines (dashed) visible.
- Target points visible with popup on click.
- POI toggles show/hide circles.
- Layer toggles recompute hubs.
- H3 3-state buttons work.
- Plotly charts unchanged.

- [ ] **Step 11: Commit**

```bash
git add 03_visualization/build_dashboard.py 03_visualization/dashboard.html
git commit -m "feat: migrate map to MapLibre GL JS with 3D pitch and right-click drag"
```

---

## Task 5 — Add 3D Buildings (fill-extrusion)

**Goal:** Load `seoul_buildings_3d.geojson` via fetch and render as MapLibre `fill-extrusion` with dark blue-gray color scaled by height.

**Files:** Modify `03_visualization/build_dashboard.py` (JS only).

- [ ] **Step 1: Add buildings source + layer inside `map.on('load', ...)` after POI setup**

At the end of the `map.on('load', ...)` block (before `updateDashboard()`), add:

```js
// ── 3D Buildings ──────────────────────────────────────────────
map.addSource('buildings-3d', {{
  type: 'geojson',
  data: {{ type: 'FeatureCollection', features: [] }},  // populated by fetch
}});
map.addLayer({{
  id: 'buildings-3d-layer',
  type: 'fill-extrusion',
  source: 'buildings-3d',
  paint: {{
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'height_m'],
       0,   '#1a2a3a',
      30,   '#1e3a5f',
      80,   '#1e4976',
      150,  '#1a5276',
      300,  '#145374',
    ],
    'fill-extrusion-height':        ['get', 'height_m'],
    'fill-extrusion-base':          0,
    'fill-extrusion-opacity':       0.75,
    'fill-extrusion-vertical-gradient': true,
  }},
  minzoom: 12,  // only visible when zoomed in enough
}});

fetch('./tableau_data/seoul_buildings_3d.geojson')
  .then(r => r.json())
  .then(data => {{
    map.getSource('buildings-3d').setData(data);
    console.log('3D buildings loaded:', data.features.length, 'features');
  }})
  .catch(err => console.warn('Buildings load failed:', err));
```

- [ ] **Step 2: Regenerate and verify**

```bash
python 03_visualization/build_dashboard.py
```

Open `dashboard.html` from a local HTTP server (needed for fetch to work — CORS):

```bash
cd "C:\Users\jimin\Desktop\1_BITAmin_16기\skybase-seoul-3D\.claude\worktrees\admiring-hugle-2d713e\03_visualization"
python -m http.server 8080
```

Open `http://localhost:8080/dashboard.html`. Zoom in to zoom 13–15 over central Seoul. Verify:
- Buildings appear as dark blue-gray 3D extrusions above zoom 12.
- Taller buildings (30 F apartment blocks) are noticeably taller than 3 F buildings.
- Hub markers and route lines remain visible above buildings.

- [ ] **Step 3: Commit**

```bash
git add 03_visualization/build_dashboard.py 03_visualization/dashboard.html
git commit -m "feat: add 3D buildings fill-extrusion layer via MapLibre"
```

---

## Task 6 — Terrain / Hillshade (Secondary)

**Goal:** Add real terrain elevation to MapLibre using the free Terrarium tile service (AWS) which covers Seoul's mountains (Bukhansan, Dobongsan, Gwanaksan). No local DEM conversion needed.

**Files:** Modify `03_visualization/build_dashboard.py` (JS only).

- [ ] **Step 1: Add terrain source and `setTerrain` inside `map.on('load', ...)`**

After the 3D buildings block, add:

```js
// ── Terrain (Terrarium tiles, free, no key) ───────────────────
map.addSource('terrain-dem', {{
  type: 'raster-dem',
  tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{{z}}/{{x}}/{{y}}.png'],
  encoding: 'terrarium',
  tileSize: 256,
  maxzoom: 15,
  attribution: 'Terrain &copy; <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen/AWS</a>',
}});
map.setTerrain({{ source: 'terrain-dem', exaggeration: 1.5 }});

// Hillshade overlay layer
map.addLayer({{
  id: 'hillshade',
  type: 'hillshade',
  source: 'terrain-dem',
  paint: {{
    'hillshade-exaggeration': 0.5,
    'hillshade-shadow-color': '#0a0a1a',
    'hillshade-highlight-color': '#1e3a5f',
    'hillshade-accent-color': '#0f2a4a',
    'hillshade-illumination-anchor': 'map',
  }},
}}, 'h3-cells');  // insert below h3 cells
```

- [ ] **Step 2: Regenerate**

```bash
python 03_visualization/build_dashboard.py
```

- [ ] **Step 3: Serve and verify terrain**

Open `http://localhost:8080/dashboard.html` (with http.server still running). Set pitch to ~60° by right-click dragging upward. Pan to north Seoul (Bukhansan area: ~37.66°N, 126.99°E). Verify:
- Mountains visible as 3D bumps against the sky.
- Hillshade subtle, doesn't overwhelm the dark dashboard theme.
- Hub markers and routes unaffected.

If the Terrarium endpoint is unreachable in the test environment, check the browser console. The dashboard should still load and work without terrain — the `setTerrain` call fails gracefully.

- [ ] **Step 4: Commit**

```bash
git add 03_visualization/build_dashboard.py 03_visualization/dashboard.html
git commit -m "feat: add 3D terrain via Terrarium tiles with hillshade overlay"
```

---

## Task 7 — Final Verification and Visual Testing

**Goal:** Regenerate the complete dashboard, serve locally, run through all verification criteria.

**Files:** Run `build_dashboard.py`, open browser.

- [ ] **Step 1: Final regeneration**

```bash
python 03_visualization/build_dashboard.py
```

Expected output includes file size; verify the HTML is not excessively large (the GeoJSON is loaded separately now).

- [ ] **Step 2: Serve and open**

```bash
cd "C:\Users\jimin\Desktop\1_BITAmin_16기\skybase-seoul-3D\.claude\worktrees\admiring-hugle-2d713e\03_visualization"
python -m http.server 8080
```

Open `http://localhost:8080/dashboard.html` and check each item:

**Layout:**
- [ ] No large empty dark area under the map
- [ ] `최적 거점` panel is a full-width card grid **below** the map row
- [ ] Right side only has layer toggles + POI panel
- [ ] Hub cards display in a responsive grid (≥2 columns on 1400px width)

**H3 visibility:**
- [ ] Default state is `거점 관련만` (hub-related cells only visible)
- [ ] `전체 H3 표시` shows all 8,322 H3 dots
- [ ] `H3 숨김` shows only hubs, circles, route lines, target points, POIs
- [ ] `kpi-avg-cs` updates on every layer toggle regardless of H3 mode

**Map interactions:**
- [ ] Layer toggles recompute scores and re-select hubs
- [ ] Hub markers (🚁) visible with pulsing rings
- [ ] Service circles (dashed outline) visible
- [ ] Route lines to top-5 target cells visible
- [ ] Target point click shows popup with dong, gu, H3 id, score, urgency, demand
- [ ] POI toggles show/hide each category
- [ ] Right-click drag upward increases pitch (buildings more side-on)
- [ ] Right-click drag downward decreases pitch (more top-down)

**3D features:**
- [ ] Buildings visible as fill-extrusion when zoomed to ~13–15
- [ ] Taller buildings are taller in 3D
- [ ] Terrain visible as 3D hills when pitch ≥ 30°

**Charts:**
- [ ] Dong bar chart, hourly chart, radar, feasible % chart, mode table — all unchanged

- [ ] **Step 3: Final commit**

```bash
git add 03_visualization/build_dashboard.py 03_visualization/dashboard.html
git commit -m "chore: final regeneration after full 3D upgrade"
```

---

## Appendix: Environment Notes

- `tippecanoe` not available → PMTiles not used; buildings are plain GeoJSON loaded via fetch.
- `rio_cogeo` not available → terrain served via public Terrarium CDN (no local processing).
- GDAL CLI (`gdal_translate`, `gdalwarp`) not in PATH → same fallback as above.
- `rasterio` IS available → used in `build_buildings.py` only for DEM info; not needed for the chosen terrain approach.
- All local file paths in JavaScript use relative `./tableau_data/...` so the dashboard must be served by an HTTP server, not opened directly as a `file://` URL (required for fetch).
- If `file://` serving is needed, inline the buildings GeoJSON as a JS variable in `build_dashboard.py` and conditionally increase `MIN_HEIGHT_M` until the HTML stays < 50 MB.
