# SkyBase Seoul

서울시 드론 배송 거점 최적 입지 분석 프로젝트입니다. 공공데이터, H3 격자, 지형 제약, 배송 수요, 공공시설 후보지를 결합해 드론 배송 허브 후보지를 선정하고, 드론과 오토바이 배송의 시간, 비용, 탄소 배출 차이를 시각화합니다.

최종 제출 버전은 [`skybase-seoul-v3`](./skybase-seoul-v3)에 있습니다.

## Project Overview

SkyBase Seoul은 서울 전역을 대상으로 드론 배송 거점 입지를 평가하는 의사결정 지원 시스템입니다. 분석 파이프라인은 행정동 경계, 건물, 경사도, 생활인구, 상권, 공영주차장 및 공공시설 데이터를 전처리한 뒤 후보 허브를 선정하고 배송 경로를 산출합니다. 결과는 웹 대시보드에서 지도, 지표, 시간대별 패턴, 탄소 절감 효과로 확인할 수 있습니다.

## Key Features

- 서울시 행정동 및 H3 격자 기반 수요 분석
- 경사도, 건물, 제한 구역 등 드론 운용 제약 반영
- 공영주차장 중심의 드론 허브 후보지 평가
- 후보 허브별 커버리지와 배송 경로 산출
- 드론 배송과 오토바이 배송의 시간, 비용, 탄소 배출 비교
- Mapbox GL JS와 Plotly 기반 인터랙티브 대시보드

## Repository Structure

```text
skybase-seoul-v3/
├── 01_preprocessing/     # 데이터 정제 및 H3 기반 집계 노트북/스크립트
├── 02_analysis/          # 제약 레이어, 후보지 최적화, 배송 경로 분석
├── 03_visualization/     # 최종 HTML 대시보드와 시각화 데이터
├── processed/            # 분석 및 대시보드 입력용 가공 데이터
└── docs/                 # 대시보드 기획 및 개선 문서
```

## Dashboard

최종 대시보드는 아래 파일에서 확인할 수 있습니다.

- [`skybase-seoul-v3/03_visualization/index.html`](./skybase-seoul-v3/03_visualization/index.html)
- [`skybase-seoul-v3/03_visualization/drone_analysis_dashboard.html`](./skybase-seoul-v3/03_visualization/drone_analysis_dashboard.html)

브라우저에서 HTML 파일을 직접 열면 대시보드를 볼 수 있습니다. 일부 브라우저 환경에서 로컬 파일 접근이 제한되면 간단한 정적 서버를 실행한 뒤 접속하세요.

```bash
cd skybase-seoul-v3/03_visualization
python -m http.server 8000
```

접속 주소:

```text
http://localhost:8000/index.html
```

## Pipeline

1. `01_preprocessing`에서 원천 데이터를 서울 범위로 정리하고 H3 격자 단위로 집계합니다.
2. `02_analysis`에서 드론 운용 제약, 후보 허브 점수, 배송 경로를 계산합니다.
3. `03_visualization`에서 처리된 결과를 웹 대시보드용 데이터와 HTML로 구성합니다.

## Main Data Outputs

- `processed/final_hubs.gpkg`: 최종 드론 허브 후보지
- `processed/drone_routes.gpkg`: 후보 허브와 배송 수요지 간 드론 경로
- `processed/delivery_routes_summary.csv`: 배송 경로 요약 테이블
- `processed/hub_delivery_stats.csv`: 허브별 배송 통계
- `03_visualization/dashboard_data/`: 대시보드 로딩용 CSV/GeoJSON/JS 데이터

## Tech Stack

- Python, Jupyter Notebook
- pandas, GeoPandas, Shapely, H3
- Mapbox GL JS
- Plotly.js
- HTML, CSS, JavaScript

## Notes

원천 데이터(`00_data/`)는 용량과 배포 제한을 고려해 Git 추적 대상에서 제외했습니다. GitHub에는 최종 분석 산출물과 대시보드 실행에 필요한 가공 데이터만 포함합니다.
