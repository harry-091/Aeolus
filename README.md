# POLARNAV (SIH26059)
### Autonomous Antarctic AI Maritime Navigation Decision Support & Risk Mitigation System

<div align="center">

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-000000.svg?style=for-the-badge&logo=vercel&logoColor=white)](https://frontend-pearl-nine-74.vercel.app/)
[![Backend API](https://img.shields.io/badge/Backend%20API-Render-46E3B7.svg?style=for-the-badge&logo=render&logoColor=white)](https://sih-2026-059.onrender.com)
[![Interactive Docs](https://img.shields.io/badge/Swagger%20Docs-FastAPI-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://sih-2026-059.onrender.com/docs)
[![Database](https://img.shields.io/badge/Database-Supabase%20Postgres-3ECF8E.svg?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)

[![SIH](https://img.shields.io/badge/Smart%20India%20Hackathon-PS%20SIH26059-blue.svg)](https://sih.gov.in)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2F%20Uvicorn-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%2F%20TypeScript-61DAFB.svg)](https://react.dev)
[![MapLibre](https://img.shields.io/badge/GIS-MapLibre%20GL-blueviolet.svg)](https://maplibre.org)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Standards](https://img.shields.io/badge/Standards-IMO%20Polar%20Code%20%2F%20POLARIS-orange.svg)](https://www.imo.org)

</div>

---

## 1. Project Overview

**PolarNav** is a production-grade, AI-enabled maritime decision support and risk mitigation system engineered specifically for polar research and resupply vessels transiting the extreme, dynamic waters of Antarctica.

Navigating the Southern Ocean presents unforgiving operational challenges: multi-year pack ice, drifting tabular icebergs, extreme katabatic gales, and severe satellite communications latency. PolarNav fuses multi-spectral Earth observation satellites (Sentinel-1 SAR, AMSR2), hydrodynamic ocean models (Copernicus GLO12), and atmospheric reanalysis (ERA5) with physics-informed machine learning to deliver:

1. **Dynamic Conformal Polar Routing**: Time-dependent A* pathfinding on South Polar Stereographic projection (`EPSG:3031`) avoiding landmasses, shallow shoals, and dense ice.
2. **0–48h Iceberg Kinematic Drift Forecasting**: Dead-reckoning trajectory models trained on 522 historical iceberg tracks from BYU/NIC to predict Closest Point of Approach (CPA) and collision risk.
3. **IMO POLARIS Compliance**: Automated Risk Index Outcome (RIO) calculation conforming to IMO Resolution MSC.385(94) and MSC.1/Circ.1519.
4. **Natural-Language AI Copilot**: Grounded maritime advisory powered by Google Gemini with sub-2s response latency and deterministic offline fallback.

---

## 2. SIH Problem Statement (SIH26059)

* **Problem ID**: SIH26059
* **Title**: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System
* **Challenge**: Polar research vessels (such as India's *R/V Sagar Nidhi*, Germany's *FS Polarstern*, or Australia's *R/V Aurora Australis*) frequently encounter closing ice leads, drifting bergs, and sudden storm surges. Traditional marine radar has a line-of-sight range limited to 12–18 nautical miles, forcing captains into reactive, multi-thousand-kilometer detours or hazardous ice besetments.
* **Solution**: PolarNav provides proactive, long-horizon corridor optimization, cutting voyage distances by up to **65.5%**, saving days of fuel and transit time while maintaining zero grounding or ice-breach safety violations.

---

## 3. Core Implemented Features

* **3-Corridor Pareto Optimization**: Computes three distinct operational trajectories per voyage:
  * **Route B (Balanced / Optimal)**: Best trade-off between fuel economy, transit time, and safety margins.
  * **Route C (Safest Ice Margin)**: Maximum standoff distance from heavy pack ice and iceberg clusters.
  * **Route A (Direct / Baseline)**: Minimal distance geodesic track for benchmark comparison.
* **Sentinel-1A SAR Radar Obstacle Ingestion**: Processes 10m C-Band radar scenes using CFAR target detection to identify embedded icebergs and navigable fracture leads through clouds and polar night.
* **Interactive What-If Simulation Engine**: Allows ship navigators to test hypothetical storm surges, sea-ice expansion (+15%), or iceberg displacements and instantly inspect route impacts.
* **Autonomous Emergency Diversion**: Single-click tactical rerouting around sudden calving events with complete fuel, time, and waypoint differential metrics.
* **Ground-Truth Benchmark Mode**: Quantitative statistical comparison against real historical Antarctic research voyages (e.g. Australian Antarctic Division *R/V Aurora Australis* 2015/16).
* **Iridium Low-Bandwidth Mode**: Single-toggle operational HUD that strips heavy raster tiles and streams compact vector GeoJSON for bandwidth-constrained satellite terminals ($<2.4\text{ kbps}$).

---

## 4. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        1. FRONTEND USER INTERFACE                      │
│      React 19 • TypeScript • Vite • Tailwind CSS • MapLibre GL         │
│  - Tactical ECDIS PolarMap (EPSG:3031)   - Pareto Route Optimization   │
│  - Realtime Vessel Telemetry HUD         - Interactive Copilot Drawer  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP REST / WebSocket / GeoJSON
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        2. BACKEND API & ROUTING                        │
│          FastAPI • Uvicorn • SQLAlchemy 2.0 • Python 3.11+             │
│  - Conformal A* Pathfinding Engine       - Emergency Diversion Service │
│  - IMO POLARIS RIO Safety Engine         - PostgreSQL / Supabase State │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┴────────────────────────────┐
       ▼                                                         ▼
┌──────────────────────────────┐        ┌────────────────────────────────┐
│   3. MACHINE LEARNING        │        │   4. ENVIRONMENTAL DATA FEEDS  │
│ - Sea Ice RF Predictor       │        │ - Sentinel-1 SAR Dual-Pol GRD  │
│   (R² = 0.8861, MAE = 0.0401)│        │ - NOAA/NSIDC CDR Sea Ice Grid  │
│ - Iceberg Drift Kinematics   │        │ - Copernicus GLO12 Currents    │
│   (0.61 km median error)     │        │ - ECMWF ERA5 Reanalysis Waves  │
│ - Sentinel-1 SAR CFAR Model  │        │ - GEBCO 2023 Bathymetric Grid  │
│   (98.47% accuracy)          │        │ - COMNAP 112 Antarctic Bases   │
└──────────────────────────────┘        └────────────────────────────────┘
```

---

## 5. Folder Structure

```text
POLARNAV/
├── README.md                      # Primary documentation entry point (this file)
├── LICENSE                        # MIT Open Source License
├── .gitignore                     # Git hygiene & sensitive file exclusion
├── .env.example                   # Master environment variable template
├── requirements.txt               # Backend Python production dependencies
├── start.bat                      # One-click Windows launch script
├── start.sh                       # One-click Linux/macOS launch script
│
├── frontend/ (or SIH26059/frontend/) # Production React 19 web application
│   ├── src/
│   │   ├── components/            # Reusable UI components & MapLibre PolarMap
│   │   ├── pages/platform/        # Tactical navigation, telemetry, routes, alerts
│   │   ├── context/               # FleetContext single source of truth
│   │   └── services/              # Axios REST API client
│   └── package.json               # Frontend dependencies & npm build scripts
│
├── backend/                       # FastAPI server & Antarctic routing engines
│   ├── app/                       # Server entrypoint (server.py), DB schema, routers
│   ├── data/                      # Raw and processed NetCDF, CSV, and cache data
│   │   ├── raw/                   # NOAA, NSIDC, Copernicus, and BYU/NIC source files
│   │   ├── processed/             # Gridded risk surfaces, forecasts, verification
│   │   └── cache/                 # Fast response cache for Sentinel-1 radar scenes
│   ├── models/                    # Serialized .joblib ML weights & feature configs
│   ├── realtime/                  # Ingestion workers, telemetry, and spatial state
│   ├── services/                  # AIS simulation & Gemini AI Copilot orchestration
│   ├── src/                       # Core algorithms (navigation, risk, sea_ice, iceberg)
│   └── tests/                     # Automated pytest test suite (259 tests across 24 suites)
│
├── data/                          # Shared repository dataset catalog & verification
│   ├── README.md                  # Comprehensive dataset provenance & schema guide
│   └── processed/verification/    # AAD 2015/16 research voyage backtest benchmark
│
├── scripts/                       # Developer automation & maintenance utilities
│   ├── setup/                     # Environment bootstrapping tools
│   ├── development/               # Headless browser screenshot generator
│   └── maintenance/               # Health check and data validation routines
│
└── docs/                          # In-depth technical documentation
    ├── ARCHITECTURE.md            # Detailed system design & cost manifold formula
    ├── DEBUGGING.md               # Beginner-friendly step-by-step troubleshooting guide
    ├── DATA_SOURCES.md            # Environmental datasets & satellite provenance
    ├── ML.md                      # Machine learning architectures & validation metrics
    ├── API.md                     # Comprehensive REST API reference & schemas
    ├── DEPLOYMENT.md              # Cloud deployment guide (Vercel & Render)
    ├── NAVIGATION.md              # EPSG:3031 polar navigation mathematics
    ├── SIH_DEMO.md                # Step-by-step judge demonstration script
    └── assets/screenshots/        # High-resolution production UI screenshots
```

---

## 6. Installation

### Prerequisites
* **Python**: `3.11` or higher (Python 3.11, 3.12, 3.13, 3.14 tested and supported)
* **Node.js**: `v20.x` or higher
* **Package Managers**: `pip` and `npm`

### Step 1: Clone Repository & Setup Virtual Environment
```powershell
git clone https://github.com/your-org/polarnav.git
cd polarnav

# Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Linux/macOS: source venv/bin/activate
```

### Step 2: Install Backend Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Install Frontend Dependencies
```powershell
cd SIH26059\frontend
npm install
cd ..\..
```

---

## 7. Environment Variables

Create `.env` in the repository root by copying `.env.example`:

```powershell
copy .env.example .env
```

| Variable Name | Purpose | Required? | Default / Example | Where to Obtain |
| :--- | :--- | :--- | :--- | :--- |
| `PORT` | Backend server port | Optional | `8000` | Local environment |
| `HOST` | Backend bind host | Optional | `0.0.0.0` | Local environment |
| `CORS_ORIGINS` | Permitted web origins | Optional | `*` | Frontend deployment URL |
| `GEMINI_API_KEY` | Powers AI Navigation Copilot | Optional | `""` (Uses local deterministic fallback) | [Google AI Studio](https://aistudio.google.com/) |
| `DATABASE_URL` | PostgreSQL persistence | Optional | `""` (Falls back to local file pipeline) | [Supabase](https://supabase.com) |
| `VITE_API_URL` | Frontend $\to$ Backend URL | Required for Web | `http://localhost:8000` | Local or Render API host |
| `VITE_MAPTILER_API_KEY` | Vector map basemap | Optional | Preconfigured fallback | [MapTiler Cloud](https://cloud.maptiler.com/) |

*Note: PolarNav works 100% out of the box without external API keys thanks to built-in local deterministic fallbacks!*

---

## 8. Running the Application

### One-Click Launch
* **Windows**: Double-click [`start.bat`](file:///d:/SIH/start.bat)
* **Linux / macOS**: Run `chmod +x start.sh && ./start.sh`

### Manual Execution

#### Terminal 1 — Backend (FastAPI)
```powershell
# Set Python path to repository root and backend
$env:PYTHONPATH="D:\SIH;D:\SIH\backend;D:\SIH\backend\src"

python -m uvicorn backend.app.server:app --host 0.0.0.0 --port 8000 --reload
```
*Backend API available at: `http://localhost:8000`*
*Interactive OpenAPI Docs at: `http://localhost:8000/docs`*

#### Terminal 2 — Frontend (Vite / React 19)
```powershell
cd SIH26059\frontend
npm run dev
```
*Frontend UI available at: `http://localhost:3000`*

---

## 9. Testing & Quality Assurance

PolarNav includes a multi-tier automated test suite:

```powershell
# 1. Run Complete Pytest Suite (259 tests across 24 test suites)
python -m pytest backend/tests -v

# 2. Run Adversarial Edge-Case Evaluation Suite
python backend/test_judge_adversarial.py

# 3. Run API Security & Input Injection Suite
python backend/test_judge_api_security.py

# 4. Run Master 5-Phase End-to-End System Validation
python backend/final_system_validation.py

# 5. Run Offline Historical Voyage Backtest (R/V Aurora Australis)
python backend/run_offline_backtest.py

# 6. Frontend Type-Check & Production Build
cd SIH26059\frontend
npm run build
npm run lint
```

---

## 10. Data Sources (Taxonomy)

PolarNav strictly separates data into three transparent operational regimes:

1. **LIVE DATA**:
   * **Sentinel-1 SAR**: ESA Copernicus radar passes downloaded every 1–3 days.
   * **Open-Meteo Marine / ECMWF ERA5**: Live wind velocity and significant wave heights (with transparent 1.5s timeout local fallback).
   * **Copernicus Marine (GLO12)**: Live ocean current vectors and sea surface temperatures.
2. **STATIC DATASETS**:
   * **GEBCO 2023 / NOAA ETOPO**: 15 arc-second bathymetry used for under-keel safety clearance ($>500\text{m}$).
   * **COMNAP Facilities Catalog**: Geo-referenced database of 112 Antarctic research stations and emergency shelters.
   * **BYU/NIC Iceberg Database**: 522 historical iceberg track records spanning 1978 to the present.
3. **SIMULATION & BENCHMARK DATA**:
   * **What-If Simulation Engine**: Parameterized scenario perturbations (e.g., +25 km iceberg drift, +15% ice compression).
   * **AAD 2015/16 Benchmark**: Ground-truth AIS trajectory of *R/V Aurora Australis* used for empirical comparative validation.

---

## 11. Machine Learning Pipeline

```text
Earth Observation Satellite Data (NetCDF / GeoJSON / CSV)
  │
  ▼
Feature Preprocessing (Lagged SIC, Coriolis/Wind vectors, CFAR peak detector)
  │
  ▼
Trained Models (RandomForest / Gradient Boosting in backend/models/)
  │
  ▼
Fast Deterministic Runtime Inference (<50ms per step)
  │
  ▼
Dynamic Injection into Navigation Cost Manifold & RIO Calculator
```

*For in-depth mathematical architectures, see [docs/ML.md](file:///d:/SIH/docs/ML.md).*

---

## 12. Navigation & Polar Routing Logic

1. **Conformal Polar Stereographic Projection (`EPSG:3031`)**: Paths are calculated directly on conformal stereographic coordinates centered on $-90^\circ\text{S}$, eliminating polar distortion.
2. **7-Factor Cost Surface**: Evaluates distance, sea ice concentration, iceberg proximity, ocean current drift, wave resistance, bathymetric clearance, and fuel burn.
3. **Hard Boundary Safety Checks**:
   * Continental landmass avoidance via `shapely.prepared` polygon containment.
   * Mandatory depth barrier: water depth must exceed $\text{vessel draft} + 2.0\text{m}$.
4. **Antimeridian ($180^\circ / -180^\circ$) Handling**: Routes that cross the date line are automatically split into valid `MultiLineString` segments.
5. **IMO POLARIS Scoring**: Computes the Risk Index Outcome ($\text{RIO} = \sum C_i \times RIV_i$). Routes are only certified when $\text{RIO} \ge 0$.

---

## 13. Troubleshooting

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **Frontend fails to start** | Missing `node_modules` | Run `npm install` inside `SIH26059/frontend`. |
| **Backend returns 500 on startup** | `PYTHONPATH` not configured | Set `$env:PYTHONPATH="D:\SIH;D:\SIH\backend;D:\SIH\backend\src"`. |
| **Map canvas is blank / dark** | Network blocked to tile server | PolarNav automatically falls back to offline dark matter canvas; check console. |
| **Route calculation takes >5s** | External weather API timeout | The system auto-falls back to local ERA5 NetCDF reanalysis in 1.5s; check backend log. |
| **AI Copilot returns deterministic text** | `GEMINI_API_KEY` missing | This is expected behavior! The offline deterministic copilot provides safe fallback guidance. |

*For complete step-by-step diagnostic workflows, refer to [docs/DEBUGGING.md](file:///d:/SIH/docs/DEBUGGING.md).*

---

## 14. Development Guidelines

Where to make changes in the codebase:
* **UI & Visual Components**: Edit [`frontend/src/components/`](file:///d:/SIH/SIH26059/frontend/src/components/) and [`frontend/src/pages/`](file:///d:/SIH/SIH26059/frontend/src/pages/).
* **Map Display & Layers**: Edit [`PolarMap.tsx`](file:///d:/SIH/SIH26059/frontend/src/components/map/PolarMap.tsx).
* **API Endpoints & REST Routes**: Edit [`backend/app/server.py`](file:///d:/SIH/backend/app/server.py).
* **Routing Mathematics & Cost Weights**: Edit [`backend/src/optimization/cost_function.py`](file:///d:/SIH/backend/src/optimization/cost_function.py) and [`polar_routing_engine.py`](file:///d:/SIH/backend/src/optimization/polar_routing_engine.py).
* **ML Model Training & Features**: Edit [`backend/src/sea_ice/`](file:///d:/SIH/backend/src/sea_ice/) and [`backend/src/iceberg/`](file:///d:/SIH/backend/src/iceberg/).
* **External Weather / Satellite Feeds**: Edit [`backend/src/data/`](file:///d:/SIH/backend/src/data/).
* **Environment Configuration**: Edit [`.env.example`](file:///d:/SIH/.env.example) and local `.env`.
# Aeolus
