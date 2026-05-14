# 배송 분석 탭 Premium Analytics 리디자인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `index.html`의 `#tab-analysis` 탭을 GitHub/Bloomberg 스타일 Premium Analytics 테마로 재구성한다. 데이터·JS 로직은 그대로 유지.

**Architecture:** CSS 변수 블록 교체 → KPI HTML 구조 재편(2행 레이블) → 카드 제목 래퍼 추가 → 정적/동적 텍스트 띄어쓰기 수정. 모두 `03_visualization/index.html` 단일 파일 내 타겟 Edit.

**Tech Stack:** HTML, CSS (CSS Variables), Chart.js (기존 그대로), vanilla JS

---

## 파일 변경 맵

| 파일 | 변경 위치 | 내용 |
|---|---|---|
| `03_visualization/index.html` | lines 128–137 | `:root` CSS 변수 교체 |
| `03_visualization/index.html` | lines 139–203 | 컴포넌트 CSS 교체 (`.kpi`, `.card`, `.control` 등) |
| `03_visualization/index.html` | lines 376–384 | KPI HTML: 2행 구조로 재편 + `--accent` 추가 |
| `03_visualization/index.html` | line 388 | `드론 vs 오토바이` → `드론 대 오토바이` + card-header 래퍼 |
| `03_visualization/index.html` | line 401 | 시간대별 카드 card-header 래퍼 + 텍스트 수정 |
| `03_visualization/index.html` | lines 404–427 | 탄소·기후 카드 card-header 래퍼 |
| `03_visualization/index.html` | line 450 | 상세 테이블 `<th>` 띄어쓰기 수정 |
| `03_visualization/index.html` | line 1191 | Chart.js 레이블 `드론 절약시간` → `드론 절약 시간` |

---

## Task 1: CSS 변수 블록 교체

**Files:**
- Modify: `03_visualization/index.html:128-137`

- [ ] **Step 1: CSS 변수를 Premium Analytics 팔레트로 교체**

현재 (lines 128–137):
```css
    :root {
      --bg: #0b1020;
      --panel: #171d35;
      --text: #edf4ff;
      --muted: #aab7d4;
      --blue: #7ec8ff;
      --green: #8fbc6b;
      --orange: #ff8b5c;
      --red: #ff5b72;
    }
```

교체 후:
```css
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --border: #21262d;
      --border-subtle: #161b22;
      --text: #e6edf3;
      --muted: #8b949e;
      --blue: #58a6ff;
      --green: #3fb950;
      --orange: #f0883e;
      --red: #f85149;
      --purple: #bc8cff;
    }
```

- [ ] **Step 2: 브라우저에서 탭 전환 후 배경색이 `#0d1117`로 변경됐는지 확인**

---

## Task 2: 컴포넌트 CSS 교체

**Files:**
- Modify: `03_visualization/index.html:139-203`

- [ ] **Step 1: `#tab-analysis` 기준 컴포넌트 CSS를 Premium Analytics 스타일로 전면 교체**

현재 block (lines 139–203) 전체를 아래로 교체:

```css
    * { box-sizing: border-box; }
    #tab-analysis { margin: 0; background: var(--bg); color: var(--text); font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif; }
    .wrap { max-width: 1600px; margin: 0 auto; padding: 28px 32px 48px; }

    /* Header */
    .header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 28px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }
    .title h1 { font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; line-height: 1.2; }
    .title p { color: var(--muted); font-size: 13px; margin-top: 6px; }

    /* Filter controls */
    .control { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; }
    .control-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
    .control label { display: block; color: var(--blue); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
    select { width: 100%; padding: 9px 12px; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; font-size: 13px; font-family: inherit; outline: none; }
    select:focus { border-color: var(--blue); }
    select option { background: var(--panel); color: var(--text); }

    /* KPI row labels */
    .kpi-row-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin: 20px 0 10px; display: flex; align-items: center; gap: 8px; }
    .kpi-row-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }

    /* KPI cards */
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 8px; }
    .kpi { background: var(--panel); border: 1px solid var(--border); border-top: 3px solid var(--accent, var(--blue)); border-radius: 0 0 8px 8px; padding: 16px 18px 14px; }
    .kpi .label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 10px; }
    .kpi .value { font-size: 28px; font-weight: 700; color: var(--text); letter-spacing: -0.03em; line-height: 1; }
    .kpi .sub { font-size: 11px; color: var(--muted); margin-top: 8px; }

    /* Cards */
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
    .grid .wide { grid-column: 1 / -1; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    .card-header { padding: 14px 20px 0; }
    .card-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); padding-bottom: 12px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }
    .card-title::before { content: ''; width: 3px; height: 14px; background: var(--accent, var(--blue)); border-radius: 2px; flex-shrink: 0; }
    .card-body { padding: 16px 20px; }
    .chart { width: 100%; height: 350px; }
    .chart.tall { height: 390px; }
    .chart.radar-compact { height: 390px; }

    /* Comparison */
    .comparison-inner { display: grid; grid-template-columns: 0.9fr 1.1fr; gap: 16px; align-items: start; }
    .comparison-radar { min-height: 100%; display: flex; align-items: center; }
    .comparison-radar .chart { flex: 1; }
    .comparison-table { overflow: auto; }

    /* Carbon */
    .carbon-grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 16px; margin-top: 16px; }
    .carbon-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 0; }
    .carbon-metric { border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; background: var(--bg); }
    .carbon-metric .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em; }
    .carbon-metric .value { margin-top: 7px; font-size: 20px; font-weight: 700; color: var(--green); letter-spacing: -0.02em; }
    .formula { margin: 10px 0 0; padding: 10px 14px; border-radius: 0 4px 4px 0; background: var(--bg); color: var(--muted); font-size: 12px; line-height: 1.65; border-left: 2px solid var(--border); }
    .source-list { margin: 10px 0 0; padding-left: 16px; color: var(--muted); font-size: 12px; line-height: 1.6; }
    .source-list a { color: var(--blue); text-decoration: none; }

    /* Weather */
    .weather-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 16px; }
    .weather-grid .wide { grid-column: 1 / -1; }
    .weather-kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 14px 0; }
    .weather-kpi { border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; background: var(--bg); }
    .weather-kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em; }
    .weather-kpi .value { margin-top: 7px; font-size: 18px; font-weight: 700; color: var(--purple); }
    .weather-note { color: var(--muted); font-size: 12px; line-height: 1.55; margin: 10px 0 0; }

    /* Tables */
    .table-card { margin-top: 16px; overflow: hidden; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; padding: 10px 12px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--panel); white-space: nowrap; }
    td { padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); color: var(--text); }
    tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
    tr:hover td { background: rgba(88,166,255,0.06); }
    .badge { display: inline-block; padding: 2px 8px; background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid rgba(248,81,73,0.3); border-radius: 4px; font-size: 11px; font-weight: 700; }
    .badge.ok { background: rgba(63,185,80,0.15); color: var(--green); border-color: rgba(63,185,80,0.3); }
    .detail-wrap { max-height: 420px; overflow: auto; border-radius: 6px; }
    .detail-note { color: var(--muted); font-size: 12px; line-height: 1.55; margin: 10px 0 0; }
    .empty { color: var(--muted); padding: 24px 4px; }
    .footer { color: var(--muted); font-size: 12px; margin-top: 18px; }

    @media (max-width: 1100px) {
      .header { flex-direction: column; }
      .control { width: 100%; }
      .control-grid { grid-template-columns: 1fr; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
      .grid { grid-template-columns: 1fr; }
      .grid .wide { grid-column: auto; }
      .carbon-grid { grid-template-columns: 1fr; }
      .carbon-metrics { grid-template-columns: 1fr; }
      .comparison-inner { grid-template-columns: 1fr; }
      .weather-grid { grid-template-columns: 1fr; }
      .weather-kpis { grid-template-columns: 1fr; }
    }
```

- [ ] **Step 2: 브라우저에서 카드 배경이 `#161b22`, 상단 포인트 바가 표시되는지 확인**

---

## Task 3: KPI HTML 재편 (2행 구조)

**Files:**
- Modify: `03_visualization/index.html:376-385`

- [ ] **Step 1: 8개 KPI를 시간 4개 + 비용 4개 두 행으로 분리하고 `--accent` 색상 추가**

현재 (lines 376–385):
```html
    <div class="kpis">
      <div class="kpi"><div class="label">평균 드론 배송시간</div><div class="value" id="kpiDroneTime">-</div><div class="sub">직선 비행 경로 기준</div></div>
      <div class="kpi"><div class="label">평균 오토바이 배송시간</div><div class="value" id="kpiMotoTime">-</div><div class="sub">실측 도로 이동 기준</div></div>
      <div class="kpi"><div class="label">드론 평균 절약시간</div><div class="value" id="kpiTimeSaved">-</div><div class="sub">오토바이 대비 시간 차이</div></div>
      <div class="kpi"><div class="label">드론이 더 빠른 비율</div><div class="value" id="kpiFastRatio">-</div><div class="sub" id="kpiScope1">선택 조건 기준</div></div>
      <div class="kpi"><div class="label">평균 드론 배송비</div><div class="value" id="kpiDroneCost">-</div><div class="sub">드론 운항 비용 기준</div></div>
      <div class="kpi"><div class="label">평균 오토바이 배송비</div><div class="value" id="kpiMotoCost">-</div><div class="sub">지상 배송 비용 기준</div></div>
      <div class="kpi"><div class="label">드론 평균 절약비용</div><div class="value" id="kpiCostSaved">-</div><div class="sub">오토바이 대비 비용 차이</div></div>
      <div class="kpi"><div class="label">드론이 더 저렴한 비율</div><div class="value" id="kpiCheapRatio">-</div><div class="sub" id="kpiScope2">선택 조건 기준</div></div>
    </div>
```

교체 후:
```html
    <div class="kpi-row-label">배송 시간 지표</div>
    <div class="kpis">
      <div class="kpi" style="--accent:#58a6ff"><div class="label">평균 드론 배송 시간</div><div class="value" id="kpiDroneTime">-</div><div class="sub">직선 비행 경로 기준</div></div>
      <div class="kpi" style="--accent:#8b949e"><div class="label">평균 오토바이 배송 시간</div><div class="value" id="kpiMotoTime">-</div><div class="sub">실측 도로 이동 기준</div></div>
      <div class="kpi" style="--accent:#3fb950"><div class="label">드론 평균 절약 시간</div><div class="value" id="kpiTimeSaved">-</div><div class="sub">오토바이 대비 시간 차이</div></div>
      <div class="kpi" style="--accent:#79c0ff"><div class="label">드론이 더 빠른 비율</div><div class="value" id="kpiFastRatio">-</div><div class="sub" id="kpiScope1">선택 조건 기준</div></div>
    </div>
    <div class="kpi-row-label">배송 비용 지표</div>
    <div class="kpis" style="margin-bottom:24px;">
      <div class="kpi" style="--accent:#f0883e"><div class="label">평균 드론 배송비</div><div class="value" id="kpiDroneCost">-</div><div class="sub">드론 운항 비용 기준</div></div>
      <div class="kpi" style="--accent:#8b949e"><div class="label">평균 오토바이 배송비</div><div class="value" id="kpiMotoCost">-</div><div class="sub">지상 배송 비용 기준</div></div>
      <div class="kpi" style="--accent:#3fb950"><div class="label">드론 평균 절약 비용</div><div class="value" id="kpiCostSaved">-</div><div class="sub">오토바이 대비 비용 차이</div></div>
      <div class="kpi" style="--accent:#f0883e"><div class="label">드론이 더 저렴한 비율</div><div class="value" id="kpiCheapRatio">-</div><div class="sub" id="kpiScope2">선택 조건 기준</div></div>
    </div>
```

- [ ] **Step 2: 8개 KPI id (`kpiDroneTime` 등)가 그대로 유지되어 JS가 정상 동작하는지 확인**

---

## Task 4: 카드 제목에 card-header 래퍼 추가

**Files:**
- Modify: `03_visualization/index.html:387-427`

- [ ] **Step 1: 비교 카드 `<h3>` → `card-header` + `card-title` + `card-body` 구조로 교체**

현재 (lines 387–398):
```html
    <div class="card table-card">
      <h3>드론 vs 오토바이</h3>
      <div class="comparison-inner">
        <div class="comparison-radar"><div id="radar" class="chart radar-compact"></div></div>
        <div class="comparison-table">
          <table>
            <thead><tr><th>지표</th><th>오토바이</th><th>드론</th><th>드론 우위</th></tr></thead>
            <tbody id="summaryTable"></tbody>
          </table>
        </div>
      </div>
    </div>
```

교체 후:
```html
    <div class="card table-card" style="--accent:#58a6ff">
      <div class="card-header"><div class="card-title">드론 대 오토바이 비교</div></div>
      <div class="card-body">
        <div class="comparison-inner">
          <div class="comparison-radar"><div id="radar" class="chart radar-compact"></div></div>
          <div class="comparison-table">
            <table>
              <thead><tr><th>지표</th><th>오토바이</th><th>드론</th><th>드론 우위</th></tr></thead>
              <tbody id="summaryTable"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
```

- [ ] **Step 2: 시간대별 카드 래퍼 교체**

현재 (lines 400–402):
```html
    <div class="grid">
      <div class="card wide"><h3>시간대별 속도・배송시간 변화</h3><div id="timePattern" class="chart"></div></div>
    </div>
```

교체 후:
```html
    <div class="grid">
      <div class="card wide" style="--accent:#79c0ff">
        <div class="card-header"><div class="card-title">시간대별 속도·배송 시간 변화</div></div>
        <div class="card-body"><div id="timePattern" class="chart"></div></div>
      </div>
    </div>
```

- [ ] **Step 3: 탄소 비교 카드 래퍼 교체**

현재 (lines 404–413):
```html
    <div class="carbon-grid">
      <div class="card">
        <h3>탄소 배출량 비교</h3>
        <div class="carbon-metrics">
          <div class="carbon-metric"><div class="label">선택 조건 평균 감축률</div><div class="value" id="carbonReduction">-</div></div>
          <div class="carbon-metric"><div class="label">드론 건당 배출량</div><div class="value" id="carbonDroneTrip">-</div></div>
          <div class="carbon-metric"><div class="label">오토바이 건당 배출량</div><div class="value" id="carbonMotoTrip">-</div></div>
        </div>
        <div id="carbonChart" class="chart"></div>
      </div>
```

교체 후:
```html
    <div class="carbon-grid">
      <div class="card" style="--accent:#3fb950">
        <div class="card-header"><div class="card-title">탄소 배출량 비교</div></div>
        <div class="card-body">
          <div class="carbon-metrics">
            <div class="carbon-metric"><div class="label">선택 조건 평균 감축률</div><div class="value" id="carbonReduction">-</div></div>
            <div class="carbon-metric"><div class="label">드론 건당 배출량</div><div class="value" id="carbonDroneTrip">-</div></div>
            <div class="carbon-metric"><div class="label">오토바이 건당 배출량</div><div class="value" id="carbonMotoTrip">-</div></div>
          </div>
          <div id="carbonChart" class="chart"></div>
        </div>
      </div>
```

- [ ] **Step 4: 탄소 계산 카드 래퍼 교체**

현재 (lines 414–427):
```html
      <div class="card">
        <h3>탄소 배출량 계산</h3>
        <table>
          <thead><tr><th>항목</th><th>적용값</th></tr></thead>
          <tbody id="carbonFactorTable"></tbody>
        </table>
        <div class="formula" id="carbonFormula"></div>
        <ul class="source-list">
          <li>전력배출계수: 온실가스종합정보센터, 2024년 승인 국가 온실가스 배출계수_전력배출계수</li>
          <li>휘발유 발열량·배출계수: 환경부 환경정보공개제도 등록 가이드라인 2024</li>
          <li>드론 전력소비량: Rodrigues et al., iScience 2022, 실측 기반 소형 배송 드론 연구</li>
        </ul>
      </div>
    </div>
```

교체 후:
```html
      <div class="card" style="--accent:#3fb950">
        <div class="card-header"><div class="card-title">탄소 배출량 계산 근거</div></div>
        <div class="card-body">
          <table>
            <thead><tr><th>항목</th><th>적용값</th></tr></thead>
            <tbody id="carbonFactorTable"></tbody>
          </table>
          <div class="formula" id="carbonFormula"></div>
          <ul class="source-list">
            <li>전력 배출 계수: 온실가스 종합 정보 센터, 2024년 승인 국가 온실가스 배출 계수 — 전력 배출 계수</li>
            <li>휘발유 발열량·배출 계수: 환경부 환경 정보 공개 제도 등록 가이드라인 2024</li>
            <li>드론 전력 소비량: Rodrigues et al., iScience 2022, 실측 기반 소형 배송 드론 연구</li>
          </ul>
        </div>
      </div>
    </div>
```

- [ ] **Step 5: 기후 민감도 카드 래퍼 교체**

현재 (lines 429–442):
```html
    <div class="weather-grid">
      <div class="card wide">
        <h3>월별 드론 기후 민감도</h3>
        <div class="weather-kpis">
          <div class="weather-kpi"><div class="label">운항 가능</div><div class="value" id="weatherAvailableKpi">-</div></div>
          <div class="weather-kpi"><div class="label">제한 운항</div><div class="value" id="weatherRestrictedKpi">-</div></div>
          <div class="weather-kpi"><div class="label">운항 불가</div><div class="value" id="weatherUnavailableKpi">-</div></div>
          <div class="weather-kpi"><div class="label">평균 풍속</div><div class="value" id="weatherWindKpi">-</div></div>
          <div class="weather-kpi"><div class="label">강수 시간 비율</div><div class="value" id="weatherRainyKpi">-</div></div>
        </div>
        <div id="weatherStatusChart" class="chart"></div>
        <div class="weather-note">기상 운항 판정 기준: 풍속 6m/s 이하이며 강수 0mm이면 가능, 풍속 8m/s 이하 또는 강수 0.5mm 이하의 경계 조건은 제한, 그 외는 불가로 집계합니다.</div>
      </div>
    </div>
```

교체 후:
```html
    <div class="weather-grid">
      <div class="card wide" style="--accent:#bc8cff">
        <div class="card-header"><div class="card-title">월별 드론 기후 민감도</div></div>
        <div class="card-body">
          <div class="weather-kpis">
            <div class="weather-kpi"><div class="label">운항 가능</div><div class="value" id="weatherAvailableKpi">-</div></div>
            <div class="weather-kpi"><div class="label">제한 운항</div><div class="value" id="weatherRestrictedKpi">-</div></div>
            <div class="weather-kpi"><div class="label">운항 불가</div><div class="value" id="weatherUnavailableKpi">-</div></div>
            <div class="weather-kpi"><div class="label">평균 풍속</div><div class="value" id="weatherWindKpi">-</div></div>
            <div class="weather-kpi"><div class="label">강수 시간 비율</div><div class="value" id="weatherRainyKpi">-</div></div>
          </div>
          <div id="weatherStatusChart" class="chart"></div>
          <div class="weather-note">기상 운항 판정 기준: 풍속 6m/s 이하이며 강수 0mm이면 가능, 풍속 8m/s 이하 또는 강수 0.5mm 이하의 경계 조건은 제한, 그 외는 불가로 집계합니다.</div>
        </div>
      </div>
    </div>
```

- [ ] **Step 6: 구별 상세 카드 래퍼 교체**

현재 (lines 444–458):
```html
    <div class="card table-card">
      <h3>구별 상세 분석 결과</h3>
      <div class="detail-wrap">
        <table>
          <thead>
            <tr>
              <th>자치구</th><th>운항 가능률</th><th>조건부 운항률</th><th>운항 불가율</th><th>절약시간</th><th>절약비용</th><th>드론시간</th><th>오토바이시간</th><th>드론비용</th><th>오토바이비용</th><th>빠른비율</th><th>저렴비율</th><th>경로수</th>
            </tr>
          </thead>
          <tbody id="detailTable"></tbody>
        </table>
```

교체 후:
```html
    <div class="card table-card" style="--accent:#58a6ff">
      <div class="card-header"><div class="card-title">자치구별 상세 분석</div></div>
      <div class="card-body">
      <div class="detail-wrap">
        <table>
          <thead>
            <tr>
              <th>자치구</th><th>운항 가능률</th><th>조건부 운항률</th><th>운항 불가율</th><th>절약 시간</th><th>절약 비용</th><th>드론 시간</th><th>오토바이 시간</th><th>드론 비용</th><th>오토바이 비용</th><th>빠른 비율</th><th>저렴 비율</th><th>경로 수</th>
            </tr>
          </thead>
          <tbody id="detailTable"></tbody>
        </table>
```

---

## Task 5: 상세 카드 닫는 태그 + footer 래퍼 확인

**Files:**
- Modify: `03_visualization/index.html:454-459`

- [ ] **Step 1: 구별 상세 카드 닫는 태그 수정 (`card-body` 닫기 추가)**

현재 (lines 454–459):
```html
        </table>
      </div>
      <div class="detail-note">기상 운항 판정 기준: ...</div>
    </div>

  </div>
```

교체 후:
```html
        </table>
      </div>
      <div class="detail-note">기상 운항 판정 기준: 풍속 6m/s 이하이며 강수 0mm이면 가능, 풍속 8m/s 이하 또는 강수 0.5mm 이하의 경계 조건은 제한, 그 외는 불가로 집계합니다.</div>
      </div>
    </div>

  </div>
```

---

## Task 6: JS 차트 레이블 텍스트 수정

**Files:**
- Modify: `03_visualization/index.html:1191`

- [ ] **Step 1: Chart.js 레이블 띄어쓰기 수정**

현재 (line 1191):
```javascript
    { type: "scatter", mode: "lines+markers", x: pattern.x, y: pattern.avg_time_saved, name: "드론 절약시간",
```

교체 후:
```javascript
    { type: "scatter", mode: "lines+markers", x: pattern.x, y: pattern.avg_time_saved, name: "드론 절약 시간",
```

---

## Task 7: git 커밋

**Files:**
- `03_visualization/index.html`

- [ ] **Step 1: 변경 확인**

```bash
git diff --stat 03_visualization/index.html
```

Expected: `1 file changed, N insertions(+), N deletions(-)`

- [ ] **Step 2: 커밋**

```bash
git add 03_visualization/index.html
git commit -m "feat(analysis-tab): Premium Analytics 테마 적용 및 한국어 띄어쓰기 수정"
```

---

## 자체 검토

- **스펙 커버리지:** ✅ CSS 변수 교체 (Task 1-2), KPI 2행 구조 (Task 3), 카드 제목 래퍼 (Task 4), 띄어쓰기 수정 (Task 4·6), `#tab-optimization` 미변경 (CSS 범위가 `#tab-analysis` 안쪽)
- **Placeholder 없음:** 모든 `old_string` / `new_string`에 실제 코드 포함
- **타입 일관성:** `card-header`, `card-title`, `card-body`가 Task 2 CSS와 Task 4 HTML에서 동일하게 사용됨
- **`--accent` CSS 변수:** `:root`에 없고 각 `.card` 인라인 `style`로 전달 → `var(--accent, var(--blue))` fallback으로 안전
