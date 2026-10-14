# Phase 2 Rebuild - Repository Audit and Coverage Plan

Audit date: 2026-10-14  
Repository: `dmrc_footfall_predictor`  
Documented revision: `4405d167fc323f33be76e2c7f6614fd21cc574a8` (`main`)  
Tracked files: 45  
Source/config/documentation text lines counted by `wc -l`: 6,316 (includes CSV/JSON rows; not a measure of code complexity).

## A. Existing Phase 2 material review

The existing Phase 2 file in this checkout is `output/pdf/MetroInsights_Phase_2_Codebase_Deep_Dive.pdf` (14 pages). There is no file named `MetroInsights_Phase_2_Complete_Codebase_Deep_Dive.pdf` in `output/pdf/` or the study-material directory. The existing 14-page PDF is a useful architecture and interview overview: it summarizes startup, API flow, pipeline, inference, scheduling, graph search, frontend, limitations, and exercises.

It does not satisfy the requested teaching depth. It has no complete function source excerpts; does not explain every source line/expression; does not give worked variable traces for the main algorithms; does not index every tracked file; and its frontend coverage is only a short function summary rather than the templates, JavaScript handlers/renderers, CSS assets, and legacy scripts. It is therefore treated as prior context, not source of truth. The new guide must follow the checkout at the revision above and label verified behavior, limitations, risks, unknowns, and proposals separately. A specific discrepancy found during the deeper source audit: the old guide says 23:30 is open, but app/operating_hours.py uses an exclusive end boundary (minute_of_day < 23*60+30), so exactly 23:30 is closed. The new lessons follow the code and flag the inconsistency.

## B. Verified repository boundaries

The 45-file tracked inventory is below. The generated `data/synthetic/dmrc_calibrated_footfall.csv` and `csvFiles/dmrc_footfall_data.csv` are ignored/untracked in the described deployment state; `venv/`, bytecode and caches are also excluded. The tracked model and metadata files are binary joblib artifacts. Their roles are verified from the training and loading code; this audit does not unpickle them as source code. Runtime loads them at module import. No database, automated test suite, test configuration, CI workflow, Dockerfile, or lockfile is tracked. Do not imply otherwise.

The codebase has six Python modules under `app/`, three numbered pipeline scripts, two older CSV-generator scripts, three templates, seven frontend JS/CSS files, two static image assets, source/derived CSV and JSON metadata, two documentation files, and small deployment/editor config. The detailed PDFs will give source lessons for meaningful executable code and block/group explanations for non-executable data, CSS and markup.

## C. Complete tracked-file inventory

### Entry, runtime, and configuration

| Exact path | Type / role | Symbols or important blocks | Inputs, outputs, dependencies, execution | Lesson depth |
|---|---|---|---|---|
| `run.py` | Python entrypoint | `if __name__ == '__main__'`, PORT/FLASK_DEBUG | Imports `app`; local development server; binds `0.0.0.0`; environment values control port/debug | Detailed |
| `app/__init__.py` | Flask package init | `app = Flask(__name__)`; routes import | Creates process app and imports route module to register decorated handlers | Detailed startup block |
| `Procfile` | Render/WSGI command | `web: gunicorn run:app` | Host launches Gunicorn module/callable target | Short but exact |
| `requirements.txt` | Python dependencies | pinned versions and minimums | Install-time dependency declaration; not a lockfile; SciPy has no direct app/pipeline import found | Short exact |
| `.gitignore` | Repository config | ignores `venv`, bytecode, generated large CSVs | Affects Git tracking, not runtime imports | Short exact |
| `.vscode/launch.json` | Editor config | debugpy launch config | Launches `run.py` with debug environment for local debugging | Short exact |
| `.vscode/settings.json` | Editor config | interpreter and terminal activation settings | Selects repository venv in VS Code | Short exact |

### Python runtime and algorithms

| Exact path | Type / role | Functions/constants | Inputs, outputs, dependencies, execution | Lesson depth |
|---|---|---|---|---|
| `app/routes.py` | Flask request handlers | `_parse_datetime`, `_hour_band`, `landing`, `index`, `get_footfall`, `api_predict`, `api_stations`, `api_model_metrics`; module globals `BASE_DIR`, station paths/data, `ALL_STATIONS`, defaults | Reads cleaned stations at import; calls calendar, operating-hours, forecasting, scheduling, travel graph; renders HTML/returns JSON | Deep, all functions and module initialization |
| `app/calendar_context.py` | Static date context | `_occasion`, `OCCASIONS`, `get_calendar_context` | Date -> weekend/workday/holiday/occasion dictionary; imported by forecasting and routes | Deep functions and catalog rules |
| `app/operating_hours.py` | Service window helper | `SERVICE_START_MINUTE`, `SERVICE_END_MINUTE`, `is_service_operating` | Hour/minute -> boolean using 05:00-23:30 project gate | Deep short function; boundary trace |
| `app/forecasting.py` | Model runtime | paths/globals `_MODEL`, `_META`, `_STATIONS_DF`, `_METRICS`; `get_station_info`, `predict_hourly_footfall`, `predict_footfall_with_minute_interpolation`, `predict_station_full_day_profile`, `get_model_evaluation_summary` | Loads model/metadata/CSV at import; request time inputs -> integer forecasts/profile/features consumed by routes and UI; depends on joblib/pandas/NumPy/calendar/operations | Deep, all functions and feature walkthrough |
| `app/scheduling_optimizer.py` | Rule-based service scenario | data-loading globals, `STANDARD_HEADWAYS`; `is_peak_hour`, `get_interchange_line_split`, `round_to_practical_headway`, `optimize_line_schedule`, `optimize_station_schedule` | Loads operations CSV and line-share JSON at import; line demand + calendar inputs -> headway/frequency/capacity narrative outputs; called from routes/forecast profiles | Deep, formulas and numerical trace |
| `app/network_topology.py` | Hand-authored network data | `LINES`, `INTERCHANGES`, `INTERCHANGE_PENALTY_MIN`, `DEFAULT_SEGMENT_MIN`, `ALIASES` | Ordered stop sequences/transfer alias definitions consumed by graph builder | Block/data lesson; important mapping examples |
| `app/travel_graph.py` | Graph construction/routing | `AVG_SPEED_KMH`, `MAX_SEGMENT_MIN`, `_STRIP_CHARS`; `_normalize`, `_load_stations`, `_is_placeholder_coord`, `_haversine_km`, `_match_topology_to_canonical`, `build_graph`, `shortest_times_from` | CSV + topology -> line-expanded weighted graph -> minimum estimated destination times; routes builds/queries at import/request | Deep, hand-worked Dijkstra |

### Offline pipelines and legacy generation

| Exact path | Type / role | Functions/constants | Inputs, outputs, execution | Lesson depth |
|---|---|---|---|---|
| `pipeline/01_audit_and_clean_data.py` | Current data preparation | path constants, `VERIFIED_COORDINATES`, `METRO_OPERATIONS`, `clean_stations`, `create_operations_dataset`, main guard | Raw station CSV and hand-authored metadata -> cleaned station CSV/legacy copies/operations CSV | Deep functions and assumptions provenance |
| `pipeline/02_generate_calibrated_dataset.py` | Current synthetic scenario generation | typology/factor/weight/day/hour constants; `build_line_distribution_model`, `compute_station_weights`, `generate_annual_footfall_dataset` | Clean station CSV -> line split JSON, typology JSON, large ignored CSV and legacy duplicate; fixed-seed NumPy generator | Deep all functions and sampling arithmetic |
| `pipeline/03_train_and_evaluate_forecaster.py` | Current model preparation/training | path constants, `SPLIT_DATE`; `prepare_annual_data`, `compute_metrics`, `train_and_evaluate_model`, main guard | Synthetic CSV + metadata -> model.joblib, metadata.joblib, evaluation_metrics.json | Deep all functions, features/leakage/metrics |
| `csvFilesGenerator/footfall.py` | Older/legacy generator | constants incl. `LINE_WEIGHT`, day/hour shapes; `load_stations`, `station_weights`, `generate`, main guard | Legacy CSV station input + topology import -> 12-week synthetic CSV; not the current numbered pipeline | Detailed comparison/short function lessons; don't confuse with current pipeline |
| `csvFilesGenerator/compartmentcapacity.py` | Older utility script | top-level `data` rows and CSV writer | Writes a legacy `metro_lines.csv` in current working directory; not current pipeline | Short exact block and side-effect note |
| `csvFilesGenerator/howtorun.txt` | Legacy run note | shell instructions | Documents old generator/app run steps | Short exact |

### HTML, JavaScript, CSS and media

| Exact path | Type / role | Important blocks/symbols | Inputs, outputs, dependencies | Lesson depth |
|---|---|---|---|---|
| `app/templates/landing.html` | Jinja landing page | page sections; theme bootstrap; JSON preview injection; JS/CSS refs | `hero_profile`; `landing.js`, `theme.js`; returns landing UI | Markup block walkthrough |
| `app/templates/index.html` | Jinja dashboard | station metadata injection, forecast form, controls, KPI/chart/table IDs, JS refs | `stations_meta`, default date/time; IDs contract with `dashboard.js` | Deep markup/API contract |
| `app/templates/result.html` | Legacy synchronous report | result data fields, inline search/chart JS, theme; static references | Variables supplied by `get_footfall`; inline Chart.js/search code | Deep all inline scripts + relevant markup |
| `app/static/js/dashboard.js` | Dashboard client | `METRO_LINE_COLORS`, `getLineColor`, DOMContentLoaded, `initControls`, `updateLineSelectOptions`, `fetchPrediction`, `renderDashboard`, `renderDemandChart`, `renderInterchangeBreakdown`, `renderTravelTimes`, `filterAndDisplayTravelTimes` | DOM/template data -> POST `/api/predict`, charts, KPI/table updates; async stale-request token | Deep all functions and asynchronous flow |
| `app/static/js/landing.js` | Landing preview animation/chart | `drawPreviewChart`, scroll/reveal initialization | `window.METROINSIGHTS_PREVIEW` -> SVG/chart-like preview and scroll-linked train | Deep function/event blocks |
| `app/static/js/theme.js` | Theme switching | icon tokens, theme application/toggle, chart color update | localStorage + DOM; updates Chart.js theme | Deep short file |
| `app/static/css/dashboard.css` | Core dashboard styles | design tokens, layout/cards/forms/KPIs/charts/tables/responsive rules | Imported by templates; style grouped dashboard components | Selector-group lesson; not every repeated declaration verbatim |
| `app/static/css/dashboard-polish.css` | Dashboard refinements | visual overrides and loading/responsive layout rules | Loaded after dashboard.css; cascade overrides base styles | Selector-group/cascade lesson |
| `app/static/css/landing.css` | Landing page styles | hero/platform/workflow/transparency, responsive and reduced-motion rules | Loaded only by landing page | Selector-group lesson |
| `app/static/css/metro-theme.css` | Shared theme tokens/toggle | light/dark custom properties, controls, responsive theme rules | Loaded by pages; `data-theme` toggled by JS | Token/cascade lesson |
| `app/static/animation.gif` | Static image asset | Animated GIF, 1920x668 | Repository-wide source search found no executable/template/CSS reference; tracked but currently unused asset. Binary is not line-addressable | Explain dimensions and lack of source consumer; no frame-by-frame PDF dump |
| `app/static/dmrc_logo.png` | Static image asset | RGBA PNG, 155x65 | Repository-wide source search found no executable/template/CSS reference; tracked but currently unused branding asset | Explain format/consumer |

### Data, model artifacts and documentation

| Exact path | Type / role | Important schema/content | Producers, consumers and limits | Lesson depth |
|---|---|---|---|---|
| `data/raw/DELHI_METRO_DATA.csv` | Tracked seed input | Station, Line, Latitude, Longitude (228 records per audit) | Pipeline 01 input; source/retrieval/license absent from repo | Schema/provenance |
| `data/raw/metro_lines.csv` | Tracked legacy seed | Line, coach count, compartment and total capacity | Legacy input; current operations assumptions are assembled in pipeline 01 | Schema/provenance |
| `csvFiles/DELHI_METRO_DATA.csv` | Tracked compatibility copy | Same station-directory schema | Legacy generator input; not canonical current pipeline input | Compare and explain |
| `csvFiles/metro_lines.csv` | Tracked compatibility data | Legacy capacity schema | Older capacity utility; current app uses `data/cleaned/metro_line_operations.csv` | Compare and explain |
| `data/cleaned/stations_cleaned.csv` | Tracked derived runtime data | Station, line, coordinates, interchange flag, all lines, line count | Pipeline 01 producer; routes/forecasting/travel graph consumers | Schema and transformations |
| `data/cleaned/metro_line_operations.csv` | Tracked scenario assumptions | 11 line rows; capacity/headway/fleet/turnaround/technology fields | Pipeline 01 produces; scheduling optimizer consumes; values unverified | Schema and formula trace |
| `data/cleaned/station_typologies.json` | Tracked classification map | Station -> project category | Pipeline 02 producer; training/runtime features consumer; authored/generated labels, not official | Short data lesson |
| `data/synthetic/line_distribution_model.json` | Tracked line-share config | Per interchange: lines/proportions/explanation/provenance text | Pipeline 02 producer; runtime scheduler and profile use; synthetic weights | Schema and share calculation |
| `models/footfall_forecaster.joblib` | Tracked binary estimator | Serialized sklearn regressor | Pipeline 03 producer; forecasting import-time consumer; don't explain binary as source | Artifact lifecycle/compatibility |
| `models/forecaster_metadata.joblib` | Tracked binary inference metadata | Feature names, indices, historical aggregates (as described by code) | Pipeline 03 producer; forecasting consumer | Artifact lifecycle; inspect safely, do not print binary |
| `models/evaluation_metrics.json` | Tracked evaluation report | train/test sizes, comparison metrics, feature names | Pipeline 03 producer; routes/forecasting metrics consumer; synthetic holdout only | Metrics interpretation |
| `read.md` | Project/deployment documentation | setup, feature and architecture claims | User-facing project notes; compare claims with implementation/audit | Short plus discrepancy notes |
| `DATA_AUDIT.md` | Data provenance/limitations report | data scope, source gaps, known limitations | Stage 1 verification reference; not executable | Explain claims and evidence boundaries |

## D. Final volume plan

The detailed-guide directory will contain persistent Markdown lessons plus numbered PDFs. The target PDF series is:

1. `00_Phase_2_Master_Index.pdf` - course map, all tracked files, file/function-to-volume/page index, limitations and use instructions.
2. `01_Startup_Routes_and_Request_Flow.pdf` - Flask startup, route registration, helpers, HTML routes and request lifecycle.
3. `02_API_Prediction_Deep_Walkthrough.pdf` - JSON prediction, supporting endpoints, request/response schema, connected client and scheduler contracts.
4. `03_Forecasting_and_Model_Training.pdf` - runtime feature construction/inference, data preparation, training, evaluation and artifacts.
5. `04_Calendar_Data_and_Synthetic_Generation.pdf` - operating hours, calendar context, cleaning, scenario inputs and synthetic generation.
6. `05_Scheduling_and_Travel_Graph.pdf` - headway/capacity scenario rules, topology, graph building and Dijkstra.
7. `06_Frontend_Templates_and_JavaScript.pdf` - full templates/JS sources and explanation of DOM, fetch, response rendering, chart and theme flows.
8. `07_Styles_Configuration_and_Legacy_Code.pdf` - CSS, deployment/configuration, documentation, static assets and legacy generator.
9. `08_End_to_End_Execution_Trace.pdf` - offline/runtime integration, representative request, failure paths, security and exercises.

PDF generation and visual review is complete for these nine outputs. The detailed index notes that CSS receives selector-group teaching rather than a sentence for every repeated declaration, and binary/untracked generated data is not printed as source.

## E. Coverage checklist (to update as lessons are written)

- [x] Existing Phase 2 PDF inspected; differences recorded.
- [x] Repository revision and tracked-file inventory enumerated.
- [x] Completed Stage 1 analysis and data audit read.
- [x] Runtime startup, route/function names, frontend handler names, pipeline function names inventoried.
- [x] Every tracked text source/config/template/script was opened or reproduced as text appendix; binary artifacts inspected by format/producer/consumer, not as source.
- [x] Runtime and pipeline function lessons, module initialization and UI handler/rendering lessons written in dependency order.
- [x] Consecutive source appendices generated from repository files with original line numbers; selected AST function excerpts use exact spans.
- [x] File/function-to-volume/page index populated after pagination in `00_Phase_2_Master_Index.pdf`.
- [x] All nine PDFs rendered and contact sheets/representative pages visually reviewed; PDF page counts and text extraction checked.
- [x] Cross-volume integration, exclusions and caveats recorded.

## F. Explicit exclusions

Excluded from line-by-line lessons: `.git` internals, local `venv/`, Python bytecode/cache, and generated ignored 130 MB training CSV copies. They are not tracked source. The large CSVs are explained by schema, generator, training consumer and serving-versus-retraining implications. The tracked `.joblib`, GIF and PNG binary assets are explained by format, producer/consumer, and runtime implications rather than treated as editable source text. All 45 tracked files are included in the inventory above.

## G. Final coverage notes

- The exact source excerpts are copied directly from revision `4405d167fc323f33be76e2c7f6614fd21cc574a8`. Python module appendices are complete consecutive source files where stated; V8 uses an exact AST span for `api_predict`.
- Explanations prioritize nontrivial execution and decisions. The four CSS files are reproduced completely but taught by selector/component groups and cascade behavior. HTML templates are reproduced completely with section/contract walkthroughs rather than prose commentary for every repeated tag/style attribute.
- The verified 23:30 exclusive service boundary and headway-rounding/fleet constraint interaction are documented as source behavior / potential risks.
- No application source was modified. Only study materials were created/updated. No automated tests were run or added; validation here means document/PDF/source consistency and visual output checks.

## H. Final PDF verification record

| Output | Pages | Extracted text words | Render status |
|---|---:|---:|---|
| `00_Phase_2_Master_Index.pdf` | 3 | 1,128 | Rendered; contents, maps and inventory inspected |
| `01_Startup_Routes_and_Request_Flow.pdf` | 7 | 3,006 | Rendered and inspected |
| `02_API_Prediction_Deep_Walkthrough.pdf` | 9 | 3,458 | Rendered and inspected |
| `03_Forecasting_and_Model_Training.pdf` | 11 | 4,802 | Rendered and inspected |
| `04_Calendar_Data_and_Synthetic_Generation.pdf` | 12 | 5,764 | Rendered and inspected after pagination repair |
| `05_Scheduling_and_Travel_Graph.pdf` | 12 | 6,488 | Rendered and inspected; source code is compact but legible at page scale |
| `06_Frontend_Templates_and_JavaScript.pdf` | 20 | 9,328 | Rendered and inspected |
| `07_Styles_Configuration_and_Legacy_Code.pdf` | 20 | 12,597 | Rendered and inspected |
| `08_End_to_End_Execution_Trace.pdf` | 7 | 2,578 | Rendered and inspected; API source span corrected to lines 235-398 |

All generated PDFs open via Poppler `pdfinfo`/`pdftotext`; each has nonempty text and a full PNG render. Representative source pages and all-volume contact sheets were checked for clipping, broken tables and missing glyphs. Printed source normalizes Unicode dash variants to ASCII hyphens and displays unsupported non-ASCII code symbols as explicit `\\u`/`\\U` escape notation, while keeping original repository line numbers. No code behavior was changed by this print-only normalization. No application tests were run or added.
