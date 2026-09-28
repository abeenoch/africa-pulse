# Africa Pulse — Live African Urban Intelligence Platform
#
# Acquires public data for four African cities, preserves raw evidence with
# checksums, loads it into a ClickHouse warehouse (`raw.*`, `urbanpulse.*`),
# builds analytical marts, asserts data quality, and serves them through a
# Streamlit dashboard. Airflow schedules the four-stage pipeline daily.
#
# Brief alignment: this README is the operator entry point. Detailed
# contracts live in docs/: architecture, warehouse model, metric catalogue,
# source register, decision log, lineage, and the runbook.

## What it does

| Layer | Implementation | Tables / output |
|---|---|---|
| Acquisition | `ingestion/` — one module per source, `config/cities.yaml` portfolio | `data/raw/**` JSON envelopes + SHA-256 |
| Raw sync | `ingestion/load_raw_to_clickhouse.py` | `raw.*` (7 source tables) |
| Facts | `warehouse/transform.py::transform_facts` | 6 facts in `urbanpulse.*` |
| Marts | `warehouse/transform.py::transform_marts` | 4 marts in `urbanpulse.*` |
| Quality gates | `tests/test_data_quality.py` (6 suites) | stdout + exit code |
| Observability | `ingestion/common/observability.py` | `urbanpulse.ingestion_log` |
| Serving | `dashboard/app.py` (Streamlit, 6 pages) | `http://localhost:8501` |
| Scheduling | `airflow/dags/africa_pulse_pipeline.py` (`@daily`, retries 2) | Airflow UI `:8080` |

## Cities

Lagos (NG), Abuja (NG), Port Harcourt (NG), Accra (GH) — see
`config/cities.yaml`. Adding a city = one YAML entry; no warehouse redesign.

## Entry points

| Task | Command |
|---|---|
| Full pipeline, end to end | `python scripts/run_pipeline.py` |
| Skip live acquisition (rebuild from evidence) | `python scripts/run_pipeline.py --skip-ingestion` |
| Dashboard | `streamlit run dashboard/app.py` |
| Dashboard regression harness | `python scripts/validate_dashboard.py` |
| Quality suite only | `python tests/test_data_quality.py` |
| Raw table counts | `python scripts/raw_counts.py` |
| Warehouse connectivity probe | `python scripts/test_connection.py` |
| Scheduled production runs | Airflow UI → unpause `africa_pulse_pipeline` |

## Setup

```powershell
Copy-Item .env.example .env   # fill in ClickHouse Cloud credentials
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/run_pipeline.py
streamlit run dashboard/app.py
```

Airflow:

```powershell
Copy-Item .env .env.airflow          # then set AIRFLOW__CORE__FERNET_KEY
docker compose --profile airflow run --rm airflow-init
docker compose --profile airflow up -d airflow-scheduler airflow-webserver
# Airflow UI: http://localhost:8080 — enable africa_pulse_pipeline
```

## Warehouse access

The warehouse is hosted on **ClickHouse Cloud**, so it is accessible remotely
— no local database container is required to read it. Any environment with
the repository and credentials can reach it:

* Connection details (`CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`,
  `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`) are read from `.env` — copy
  `.env.example` and fill it in. `.env` is git-ignored and never pushed.
* Verify access with `python scripts/test_connection.py`, which prints the
  server version and confirms the `raw.*` tables.
* The dashboard (`streamlit run dashboard/app.py`) and the quality suite
  (`python tests/test_data_quality.py`) query the same warehouse directly.
* ClickHouse Cloud restricts ingress by IP, so a new source address must be
  allowlisted under **Service → Network Access** in the ClickHouse Cloud
  console before it can connect.

## Freshness SLA & Operational Contract

* Every fetcher outcome and every pipeline stage writes a row to
  `urbanpulse.ingestion_log` with `status` in
  (`success`, `duplicate`, `error`).
* "Current" means a `success`/`duplicate` row **within the last 36 hours**.
  Older than that, the dashboard's Provenance page raises a red **STALE**
  banner; any `error` inside the window raises amber.
* `tests/test_data_quality.py::test_ingestion_log_fresh` enforces the same
  contract in CI — a stale warehouse fails the build.

## Deliberate Design Constraints & Limitations

* **No arbitrary historical backfill**  Sources are polled
  with fixed windows (Open-Meteo past 7d + forecast 3d, GDELT 24h, FX latest
  daily snapshot, World Bank latest 10 years, OSM current snapshot). History
  grows only by running daily. Nothing is synthesised to fill gaps.
* **Latest-date rows can contain forecast weather.** The Open-Meteo window
  extends ~3 days into the future, so the newest marts row may be dated after
  the ingestion day.
* **FX has one observation.** Until a second daily run lands, the 24h change
  column is NULL and the Economic page shows "Baseline — no prior day".
* **Mobility has no time series.** OSM is a single snapshot; only rainfall
  varies. The Mobility page states this in its limitation callout.


## Repository Architecture Map

| Path | Concern |
|---|---|
| `ingestion/` | Source acquisition, one module per source |
| `ingestion/common/` | HTTP client (retry/backoff), raw-evidence store, observability writer |
| `config/cities.yaml` | City portfolio, non-secret configuration |
| `warehouse/ddl/` | Authoritative ClickHouse schema (`00_raw`, `01_dimensions`, `02_facts`, `03_marts`) |
| `warehouse/transform.py` | Raw → facts → marts (native ClickHouse SQL) |
| `tests/` | Data-quality assertion suite (6 suites) |
| `dashboard/` | Streamlit serving layer + `scripts/validate_dashboard.py` harness |
| `airflow/` | Scheduler: DAG, service image, Airflow-only requirements |
| `scripts/` | `run_pipeline.py` orchestrator + ops probes |
| `docs/` | Decision log, source register, progress log, runbook, architecture, warehouse model, metric catalogue |


