# End-to-End Execution Trace

**Documented checkout:** `4405d167fc323f33be76e2c7f6614fd21cc574a8` on `main`. This volume links previously explained functions into full journeys and names what runs once at startup, per HTTP request, and offline. Values in the worked walk-through are labeled illustrative unless directly fixed by code/data.

## 1. Three execution timelines

### A. Offline data/model build

1. `pipeline/01_audit_and_clean_data.py` reads `data/raw/DELHI_METRO_DATA.csv`, cleans/normalizes station rows, applies hand-authored corrections and writes `data/cleaned/stations_cleaned.csv`, compatibility copies and operations settings. This step does **not** establish external provenance for each manually authored coordinate/operating assumption.
2. `pipeline/02_generate_calibrated_dataset.py` reads cleaned stations, writes typology and interchange split JSON, generates two years of synthetic station/hour rows using a fixed random seed, and writes large CSVs. Those two CSV paths are ignored by Git. The generator uses stochastic Poisson sampling around configured expectations; reproducible seed gives repeatability for same software/input order, not evidence of observed ridership.
3. `pipeline/03_train_and_evaluate_forecaster.py` reads the synthetic CSV and metadata, prepares temporal/calendar/station features, separates a date holdout at `SPLIT_DATE`, trains the configured estimator and Ridge baseline, computes metrics, and serializes model/metadata/metrics files.
4. Runtime `app/forecasting.py` loads the saved model and metadata. Production inference does not automatically rerun pipelines or retrain. Changing the generated data alone does not alter predictions until the model is retrained and serialized artifacts are replaced.

Data contract chain: raw station directory -> cleaned station directory -> generated scenario records -> training feature matrix/target -> sklearn model + metadata -> runtime model-ready row -> predicted demand.

## 2. Startup and import-time state

1. Render executes the `Procfile` command `gunicorn run:app`; Gunicorn imports `run.py` and finds `app`.
2. `run.py` imports `app` package. `app/__init__.py` constructs Flask and imports `app.routes` so decorators register endpoints.
3. `routes.py` reads cleaned station data (with a fallback path), derives station lists/defaults, imports forecasting and scheduling helpers, and builds the travel graph from station CSV plus topology.
4. Importing forecasting loads `.joblib` model/metadata and station CSV, and optionally evaluation metrics. Importing the optimizer loads operations CSV and line-share JSON.

Consequences: one missing/corrupt required file or incompatible serialized estimator may fail worker import before serving requests. Multiple workers repeat their own in-memory loads. A local virtualenv is excluded from deployment; requirements must install compatible dependencies. There is no database connection/persistent store in the tracked app path.

## 3. `/api/predict` request walkthrough

### Browser sends

`dashboard.js:fetchPrediction` reads `station`, `date`, `time`, and selected `line` controls and sends a JSON POST. The backend also accepts query args as fallback when parsed JSON is empty. The browser assigns each request an increasing ID; an older response is ignored if a newer request exists.

### Route parsing and context

`routes.api_predict` defaults station to Rajiv Chowk and time to 09:00, trims station and removes footnote glyphs, then calls `_parse_datetime`. Only `ValueError` is caught here and returned as JSON status error with HTTP 400. It computes calendar context and asks `is_service_operating(hour, minute)`. It obtains station metadata before prediction.

### Prediction branch

If service is open, it calls minute interpolation and hourly prediction. If closed, both selected-time demand values become zero without invoking those two functions. It always builds `profile_24h`; that profile iterates operating hours 05 through 23. The minute interpolation blends current-hour and next-hour predictions linearly according to `minute / 60`; the model only predicts hourly anchors.

### Schedule branch

The route calls `optimize_station_schedule` with station, primary line, all lines, hour, Python weekday index, hourly footfall, calendar workday flag, and service flag. For interchange station with no line filter, it constructs a station-wide headline by summing each line's boarding-clearance capacity and train counts, then calculates combined utilization. A chosen line uses that line's recommendation. If a nonempty line filter does not match any line, the current code silently leaves the previous default recommendation selected; it does not return a validation error.

Closed-service processing overrides the headline to zero demand, no headway, no capacity, N/A utilization/wait, no trains, and a closed badge. The per-line recommendation list is also produced by the optimizer with closed status. This is a display/model gate, not proof no passenger can be on trains at that instant; the app treats all modeled demand as zero outside its configured operating window.

### Routing and response

The route runs multi-source Dijkstra from every line-node of the origin and converts the station-keyed result to a sorted array of destination, rounded minutes and one line label from the station CSV's primary `Line` column. The travel time is a topology-weight estimate, not a departure-time timetable prediction. The `station_line_map` does not necessarily represent every destination interchange line.

It appends selected hour-band/peak context and returns JSON fields: status, station, station_info, datetime, calendar_context, footfall, scheduling (headline/all lines/interchange flag), profile_24h, travel_times, and explicit `data_provenance` disclaimers. Browser renderers map these values into visible text, chart series, doughnut breakdown and filterable destinations.

## 4. Worked request example (illustrative)

Request: `POST /api/predict` body `{station: "Rajiv Chowk", date: "2026-10-14", time: "09:00", line: ""}`. This demonstrates control/data flow; predicted numeric ridership is not claimed here.

1. Browser request ID increments; JSON request goes to Flask.
2. `_parse_datetime` creates a Python datetime, hour 9 and minute 0. Calendar context marks date facts based on current static calendar code. Operating gate evaluates 09:00 as open.
3. `get_station_info` returns interchange metadata and both line names.
4. Forecasting produces hourly and minute values, plus a 19-point 05:00-23:00 profile. The profile's maximum index determines peak hour.
5. Scheduling distributes station hourly demand according to stored share proportions (or equal fallback), then runs one line schedule per line. Since line filter is empty and this is an interchange, API creates a combined headline. `recommended_clearance_capacity` is sum of line-level hourly boarding clearance; utilization is station demand divided by this sum.
6. Dijkstra starts from Rajiv Chowk's Blue and Yellow nodes, explores adjacent line edges and interchange links, then keeps minimum arrival value per station.
7. JSON response arrives. If this is still latest request ID, frontend sets text values, selects line/all-line curve as applicable, draws Chart.js charts, fills line table and destination list.

To debug a mismatch, compare in this order: request payload -> route JSON -> `scheduling.headline` -> DOM field. That locates whether an error originates in control state, backend calculation, serialization, or rendering.

## 5. Error paths and reliability boundaries

| Failure/input | Current observed behavior | Practical effect |
|---|---|---|
| Bad date/time parse | Route returns JSON error + 400 | Browser shows server message in status element |
| Unknown station | `get_station_info` returns unknown metadata; graph route can yield empty travel result; forecaster uses index fallback for feature encoding | Demand may look like another station's encoded baseline; station selection is not explicitly rejected in this API path |
| JSON parse/network failure | Browser catch logs and shows generic service error | Existing dashboard content can remain visible/stale |
| HTTP non-2xx with valid JSON | Browser does not inspect `res.ok`; examines JSON status | Usually shows API message if error payload follows contract |
| HTTP error with HTML body | `res.json()` throws; generic catch path | Backend HTML error details are not shown to user |
| Missing startup artifact | Import-time file/model load can fail | Worker may not boot; no runtime recovery path shown |
| Graph edge mismatch/disconnected nodes | Dijkstra returns only reachable graph destinations, or `{}` when no source node | UI count can be lower than station inventory; no route-level warning is added |
| Empty station `all_lines` | Scheduler later does `max` on empty recommendation list | Request may fail unless upstream station metadata prevents it |

The API lacks an explicit schema validator for station/time/line values. There is no automated test suite tracked. These are verified source observations; proposed mitigations are not implemented in this revision.

## 6. Security and data-quality crosscutting notes

- Dashboard renderers use `textContent` for many text fields, but use `innerHTML` for dynamic line rows and destination rows; treat those as injection sinks if upstream text becomes untrusted.
- `tojson` protects template embedding for station metadata and landing profiles; avoid replacing it with string interpolation.
- `.joblib` is a Python pickle-like trusted artifact format; do not load files from an untrusted upload/source.
- CSV values are parsed as numbers but operation assumption validation is not comprehensive.
- Synthetic model holdout evaluation checks prediction consistency against synthetic generated targets, not real measured DMRC footfall. Explain this distinction in interviews.
- The deployment ignores generated 130 MB CSVs. Current serving loads serialized model/metadata and smaller runtime CSVs; retraining pipeline needs generated CSV or a regeneration step. Deployment build does not run the training pipeline automatically.

## 7. Interview narrative with technical precision

“MetroInsights is a Flask application that serves station-level demand estimates from a scikit-learn model trained on generated synthetic scenarios. A browser posts station/date/time/line selections to an API. The backend applies date and service-window context, runs hourly inference and minute interpolation, distributes interchange demand across lines, and produces a rule-based frequency/capacity scenario. A separate topology-aware weighted graph estimates shortest station-to-station travel times. The frontend updates KPIs, charts and tables without a full-page reload. Its principal limits are synthetic rather than observed training targets, configurable rather than verified operating assumptions, simplified boarding-capacity calculations, and estimated rather than timetable-derived travel time.”

The statement is intentionally explicit about what is and is not live. Avoid calling the service “real-time ridership prediction” unless the data source and deployment are changed to support that claim.

## 8. Integrated exercises

1. Trace a closed-hour request and list which forecast calls are skipped, which profile calls still occur, and which response keys represent zero or `None`.
2. Alter a station line dropdown in DevTools and predict how demand, chart historical baseline, headline utilization and recommendation fields change.
3. Explain why a destination time can be present without a direct track edge: Dijkstra may pass through multiple line nodes and transfer edges.
4. Propose a contract test that checks JSON keys and a frontend test that verifies `dispUtilization` reflects the headline.
5. Audit a generated response's provenance labels and state exactly which claims are synthetic, configurable or project route-map data.

**Solutions:** (1) `service_open` false makes selected minute/hourly demand zero, but full-day profile still makes hourly model calls for 05-23; optimizer still constructs closed line recommendation records, then the API overrides headline; keys include `service_open:false`, demand 0, capacity 0, utilization/wait `None`, headways `None`. (2) Only if a station supports the selected line does the option appear. A selected line sets headline to that line, uses line curve, and scales historical values using the selected-line/current total share; schedule values are line-level. (3) The graph's path is a sequence of weighted adjacent track edges plus transfer penalties. (4) Assert status success and expected response schema with fixture inputs; in browser, mock JSON and check text content. (5) Read `data_provenance` and do not elevate those labels to external verification.
