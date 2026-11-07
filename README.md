# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick the safest route. It compares three route options using the forecast weather at the time the truck will reach each part of the road, applies the risk and load-weight rules, and recommends the best route.

**Live demo:** _add your hosted URL here_ · **Walkthrough:** _add your Loom link here_

## Features

- **3 route options** from OSRM. When OSRM returns fewer alternatives, extra routes are found through detour waypoints on either side of the trip.
- **Weather checkpoints every 10, 25 or 50 miles.** Each checkpoint has an ETA based on OSRM's per-segment travel times, and its weather is the forecast for that hour.
- **Risk scoring** for wind, rain and snow, with the load-weight rules applied.
- **Recommendation** ranked by No Travel miles, Severe miles, High miles, average risk, then travel time, with a plain-language reason.
- **Map** showing all routes, risk-coloured segments for the selected route, checkpoint tooltips (ETA, weather, why it's risky) and route labels.
- **Corridor heatmap** with a 0–48 hour slider and play button. You can switch between overall risk, wind, rain and snow, and a truck marker shows where the selected route puts you at that hour.

## How it works

```
origin/destination ──► Photon geocoding
                   ──► OSRM routes (+ detours) ──► checkpoints every N mi with ETAs
                                                 ──► Open-Meteo hourly forecast at each ETA
                                                 ──► risk per checkpoint ──► miles per level
                                                 ──► rank routes ──► recommendation
corridor grid around routes ──► Open-Meteo 48 h ──► heatmap scores per hour
```

### Risk rules

| Condition | Low      | Moderate  | High      | Severe    | No Travel |
|-----------|----------|-----------|-----------|-----------|-----------|
| Wind      | <25 mph  | 25–34     | 35–44     | 45–54     | ≥55 mph   |
| Rain      | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow      | <0.5 in/hr  | 0.5–1.0   | 1.0–2.0   | 2.0–3.0   | >3.0  |

Load rules: 45–54 mph with more than 30,000 lb → No Travel; 35–44 mph with more than 40,000 lb → Severe. A checkpoint's risk is the worst of its wind, rain and snow levels. When a value sits on a shared boundary (for example rain of exactly 0.25), it goes to the higher level. The rules are in [risk.py](backend/routing/services/risk.py) and covered by boundary tests.

### Miles per risk level

Each checkpoint covers the part of the road that is closer to it than to the next checkpoint. A route's Severe/High miles are the sum of those stretches, and its **average risk** is the mile-weighted mean on a 0 (Low) to 4 (No Travel) scale.

### Recommendation

Routes are compared in this order ([recommendation.py](backend/routing/services/recommendation.py)):

0. Fewest **No Travel** miles. These are worse than Severe, so they are checked first.
1. Fewest **Severe** miles
2. Fewest **High** miles
3. Lowest **average risk**
4. Shortest **travel time**

Tiny differences count as ties (0.5 mi, 0.05 average risk, 1 minute). This keeps a route that is 0.01 safer on average from beating one that is three hours faster. If even the best route has Severe or No Travel miles, the app warns the driver to consider delaying departure.

### Heatmap

The backend builds an evenly spaced grid covering a band around all three routes (capped at 350 points) and returns a score for every point and hour from departure to +48 h. The frontend draws it with a custom Leaflet canvas layer ([heatLayer.js](frontend/src/lib/heatLayer.js)):

- Overlapping points keep the **maximum** value instead of adding up, so many low-risk points never turn into a fake hotspot.
- Each frame is drawn at half resolution into a reused canvas and coloured with a lookup table, which takes a few milliseconds. That keeps dragging the slider and the play animation smooth.
- All 49 hours are fetched once, so moving the slider never makes a network request.
- The layer animates with map zoom and is drawn with padding, so panning doesn't reveal gaps.

## Third-party services (all free, no API keys)

| Purpose   | Service |
|-----------|---------|
| Routing   | [OSRM](https://project-osrm.org/) public server |
| Geocoding | [Photon](https://photon.komoot.io/) (OpenStreetMap data) |
| Weather   | [Open-Meteo](https://open-meteo.com/) hourly forecast |
| Basemap   | Esri World Light Gray |

Forecasts are cached for 30 minutes and geocoding results for 24 hours. Nearby checkpoints share one forecast (about a 3.5-mile grid), which is finer than the weather model's resolution.

## Running locally

Requirements: Python 3.11+ and Node 18+.

```bash
# Backend (http://127.0.0.1:8000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver

# Frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

Run the tests:

```bash
cd backend && python manage.py test routing
```

## API

| Method | Path | Body / query | Returns |
|--------|------|--------------|---------|
| GET  | `/api/geocode?q=Denver` | | Up to 5 place suggestions |
| POST | `/api/plan` | `origin`, `destination` (text or `{label, lat, lon}`), `departure` (ISO 8601), `load_lb`, `interval_mi` (10/25/50) | Routes, checkpoints, risk summary, recommendation, heatmap grid |
| POST | `/api/heatmap` | `points`, `start`, `load_lb` | Hourly wind/rain/snow scores for 0–48 h |
| GET  | `/api/health` | | `{"status": "ok"}` |

## Deployment

The Dockerfile builds the React app and serves it from Django using WhiteNoise, so the whole app runs as one service.

**Render:** create a new Blueprint from this repo. It uses [render.yaml](render.yaml) and generates the secret key for you.

**Any Docker host:**

```bash
docker build -t truck-routing .
docker run -p 8000:8000 -e DJANGO_SECRET_KEY=change-me -e DJANGO_ALLOWED_HOSTS=your.domain truck-routing
```

Environment variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` (only needed if the frontend is hosted separately, together with `VITE_API_URL` at build time), `TRUCK_DURATION_FACTOR` (default 1.1), and `OSRM_URL`, `PHOTON_URL`, `OPEN_METEO_URL` to point at other instances.

## Assumptions and limitations

- OSRM's public server uses a **car** profile. Durations are multiplied by 1.1 to approximate truck speeds, and truck-specific restrictions (height, weight, hazmat) are not modelled.
- ETAs assume continuous driving. Rest breaks required by hours-of-service rules are not added.
- Wind uses the sustained 10 m wind speed. Gusts are shown in tooltips but not scored.
- Rain is rain plus showers. Snow is the snowfall rate in inches per hour.
- Departure must be within the next 7 days, and the trip must finish within the 15-day forecast range.
- The public OSRM, Photon and Open-Meteo servers are rate-limited. For production use, self-host them or use paid plans.

## Project structure

```
backend/
  config/                 Django settings and URLs
  routing/
    services/
      routing.py          OSRM routes and detour alternatives
      sampling.py         checkpoints and ETAs along a route
      weather.py          Open-Meteo client, caching, interpolation
      risk.py             risk thresholds, load rules, heatmap scores
      recommendation.py   route ranking and explanation
      planner.py          builds the full trip plan
      heatmap.py          corridor grid and 48 h scores
      geo.py              distance, bearing, resampling, simplification
    tests/                unit and API tests
frontend/
  src/
    components/           form, route cards, checkpoint table, map, heatmap controls
    lib/heatLayer.js      canvas heatmap layer
```
