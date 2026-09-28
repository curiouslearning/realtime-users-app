# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A small Flask app that shows real-time active users (last 30 minutes) from a Google Analytics 4 property, plotted by country on a Leaflet world map or a Three.js globe. There is no build step, test suite, or linter.

## Commands

```bash
pip install -r requirements.txt
python main.py                          # dev server on http://0.0.0.0:5000 (debug=True)
gunicorn -b 0.0.0.0:8080 main:app       # production-style (gunicorn is in requirements.txt)
```

To run locally you need Google Cloud Application Default Credentials (`gcloud auth application-default login`) with access to Secret Manager in GCP project `405806232197`. Without them, `/realtime` fails, but the HTML pages still render.

## Architecture

- **`main.py`**: the whole backend.
  - `/realtime` calls `get_gcp_credentials()` on every request. That function pulls a service-account JSON from Secret Manager (`service_account_json` secret), then calls GA4 `run_realtime_report` on property `159643920` with dimension `country` and metric `activeUsers`.
  - Responses are cached in memory for 120s (`flask_caching` SimpleCache). The cache is per process, so each gunicorn worker keeps its own copy.
  - On `ResourceExhausted` (GA quota) the handler sleeps 60s and retries up to 3 times, which blocks the request.
  - Response shape: `[{country, active_users (string), latitude, longitude}]`. Lat/lon are `None` when the country is not in the lookup.
- **`country_coordinates.json`**: a static lookup from country name to lat/lon (under the key `ref_country_codes`), loaded once at startup. It replaced live geopy geocoding; `geopy` is still imported but only for its exception types. Keys must exactly match GA4's `country` dimension strings. When the log prints "Coordinates not found for X", add or rename an entry here (see the "add Eswatini" commit).
- **Routes and templates**:
  - `/` and `/world_map` serve `world_map.html`: Leaflet plus chroma.js, with country shapes fetched at runtime from a GitHub-hosted geojson.
  - `/globe` serves `globe.html`: Three.js r128 with the texture `static/images/ear0xuu2.jpg`.
  - `split_view.html` iframes both pages but no route currently serves it. (The `/globe` handler's function is named `split_view`, which is misleading.)
  - Both pages poll `/realtime` every 60s. All JS libraries load from CDNs.

## Deployment caveats

The `Dockerfile` looks stale. It `git clone`s a different repo (`curiouslearning/realtime-users-app`) instead of copying local sources, has a stray space in `WORKDIR`, and its `CMD` (`python3 run main.py --server.port=8080`) is not a valid way to start this app. Check with the user how the app is actually deployed before relying on it or "fixing" it.
