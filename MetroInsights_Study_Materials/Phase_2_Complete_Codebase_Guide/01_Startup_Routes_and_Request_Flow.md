# Volume 01 - Startup, Flask Registration, and Page Routes

**Source revision:** `4405d167fc323f33be76e2c7f6614fd21cc574a8`  
**Files:** `run.py`, `app/__init__.py`, and `app/routes.py` lines 1-233.  
**Code excerpt policy:** the PDF builder inserts the full, consecutive source ranges from this exact checkout, with original line numbers. The teaching notes below explain these blocks; no source code is silently rewritten.

## 1. What runs first?

### `run.py` - local entry point (lines 1-6)

The file imports `os` and the package-level `app`. When executed as a script, it reads `PORT` (default 5000) and `FLASK_DEBUG` (default false), then calls Flask's development server with host `0.0.0.0`. The `if __name__ == '__main__'` guard means this body runs for `python run.py`, but not when Gunicorn imports the module.

- `os.environ.get('PORT', 5000)` returns a string environment value if present, so `int(...)` converts it for the server argument. A non-numeric `PORT` raises `ValueError` before the server starts.
- Debug is enabled only for exact strings `'1'`, `'true'`, or `'True'`. Values such as `'TRUE'` are false.
- `0.0.0.0` listens on all container interfaces. It is needed for a hosted process to be reachable through the platform's network proxy; it is not the public URL.
- **Verified distinction:** local `python run.py` enters the `app.run(...)` code. The `Procfile` instead asks Gunicorn to import `run:app`; the `__main__` body does not run in that import path.

### `app/__init__.py` - app construction and route registration (lines 1-5)

`app = Flask(__name__)` creates one Flask instance. `__name__` tells Flask which package/module roots to use for resources. The subsequent `from app import routes` executes `routes.py`; importing `app` has already assigned the `app` object, so the routes module can import that same object and apply `@app.route(...)` decorators. Importing routes is the registration side effect: Flask records each URL/method and its handler on the app.

This is not an application factory: the module creates a single global app at import time. That is simple for this small service, but makes startup tightly coupled to files read by imported modules and complicates tests that need isolated app configurations.

### Gunicorn path

`Procfile` contains `web: gunicorn run:app`. Gunicorn imports module `run`, finds the global `app`, then serves requests using its WSGI interface. `run.py` imports `app`, triggering the same module initialization and route registration. It does not call `app.run()` in this mode.

## 2. Route-module imports and module-level initialization

### `app/routes.py` lines 1-47

This module is both HTTP layer and composition root for one application process. Its imports fall into groups:

- Standard library: `os`, `json`, `datetime/date`, `ZoneInfo`.
- Flask: `render_template`, `request`, `jsonify`.
- Data table loading: pandas.
- Application modules: Flask app, topology graph functions, forecasting functions, schedule optimizer, calendar context, service-window predicate.

At import time it computes `BASE_DIR` by taking the absolute current source-file path and moving up two directories. `STATIONS_CLEANED_PATH` points to `data/cleaned/stations_cleaned.csv`; if that path does not exist, it switches to legacy `csvFiles/DELHI_METRO_DATA.csv`. It then reads the selected CSV into `stations_df`, strips source marker characters from station names, creates a sorted unique station-name list, and builds `travel_graph` once.

Important consequences:

1. CSV parsing and graph construction occur during import/startup, not inside every page route.
2. A missing required CSV, malformed schema, or error in graph building may stop process startup.
3. The fallback only checks whether the cleaned file exists. It does not prove the legacy CSV has every column the rest of the module expects.
4. `stations_df` is a module-global DataFrame shared by all requests in this process. The handlers read it but do not intentionally mutate it after initialization.
5. `BUSIEST_STATION = "Botanical Garden"` and `PEAK_HOUR = "09:00"` are fixed display/example defaults. They are not dynamically computed network-wide benchmarks in this module.

### Dependency chain / circular-import question

`app/__init__.py` defines `app` before importing `routes`. `routes.py` then executes `from app import app`, which retrieves the already-defined symbol from the partially initialized package. This import order works as written. If someone moved the routes import above app construction, the expected symbol would not yet exist.

## 3. `_parse_datetime(date_str, time_str)`

**Signature:** `_parse_datetime(date_str, time_str)`  
**Input:** date/time strings or false-like empty values. Types are not annotated.  
**Output:** `(dt_obj, hour, minute)`, where `dt_obj` is a naive `datetime` and hour/minute are integers.  
**Raises:** `ValueError` with user-facing text on malformed nonempty date or time.

Execution order:

1. Capture today's date using `datetime.now(ZoneInfo('Asia/Kolkata')).date()`. The clock is read in Delhi's time zone, avoiding the host's local zone for the default date.
2. If the date string is empty, use today. Otherwise parse exactly `%Y-%m-%d`. `datetime.strptime` rejects impossible dates such as `2026-02-30`; the `except ValueError` replaces its implementation-specific message with a stable prompt.
3. If the time string is empty, choose 09:00. Otherwise parse `%H:%M`; it expects a 24-hour hour-and-minute representation and rejects malformed values.
4. Construct `datetime(year, month, day, hour, minute)`. This object is naive: it contains no timezone information even though the default date used an aware clock. Downstream code treats its date/hour as local Delhi scenario fields.
5. Return the datetime and its already-parsed hour/minute separately for convenience.

**Illustrative trace:** date `2026-10-14`, time `09:15` produces `datetime(2026, 10, 14, 9, 15)`, `9`, `15`. Empty date/time uses the current Kolkata/Delhi calendar date and 09:00. A valid but closed time such as `02:02` is parsed normally; closure is a separate service-window decision.

**Risks:** no future-date restriction is enforced here; no station validation is done here; values of the wrong type may fail before the caught `ValueError` (for example, `strptime` expects text). The API handler's broadness around malformed JSON types is discussed in Volume 02.

## 4. `_hour_band(profile, hour, minute=0)`

It labels selected time as closed, unavailable, peak, lower or typical based on a station/date's predicted hourly profile.

1. Call `is_service_operating(hour, minute)` first. A closed time returns before profile indexing.
2. Sort the profile values into a new list. Empty profile returns `Unavailable`.
3. Select low/high values at integer positions `int((n-1)*.25)` and `int((n-1)*.75)`. This is an index-based quartile approximation, not an interpolated statistical percentile.
4. Index `profile[hour - 5]`, relying on a profile whose first item corresponds to hour 05. If hour is outside 05-23 while service is marked open due a bad service rule/input, indexing could fail; with the current window it does not happen for valid values.
5. Values at/above `high` are Peak demand; values at/below `low` are Lower demand; the rest are Typical demand. If all values are equal, `high == low`, so the first condition wins and every value is classified Peak.

Complexity is O(n log n) time because sorting dominates, O(n) additional list space. A selection algorithm could find quartile order statistics without sorting all values, but n=19 makes this negligible.

## 5. `landing()` - GET `/`

The decorator registers a GET endpoint. The handler obtains today's Delhi date, fixes the sample station to Rajiv Chowk, computes a full-day scenario at 09:00, and passes labels/profile/metrics to `landing.html`. The template can render a sample visualization without a user request. The resulting profile is generated by the same inference helper used by the dashboard; it is a model estimate on synthetic-trained data, not observed ridership.

**Inputs:** no route parameters. **Output:** rendered HTML response. **Calls:** `predict_station_full_day_profile`, `get_model_evaluation_summary`, `render_template`. A startup/model error would already have happened when imports loaded artifacts.

## 6. `index()` - GET `/dashboard`

This handler converts the module-level pandas table into `stations_meta`, a dictionary keyed by station name. For each DataFrame row:

- `iterrows()` yields an index and a Series; `_` discards the index.
- It reads canonical station name and uses `row.get('All_Lines', row['Line'])` as a fallback. The value is converted to string, comma-split, and whitespace-trimmed into a list.
- It builds metadata: primary line, all lines, interchange boolean (using explicit column if available, else infer from multiple lines), and coordinates converted to floats only if pandas says they are not missing.

It then gets stored evaluation summary and renders `index.html` with station list, metadata, constants, current Delhi date, fixed default time 09:00 and Rajiv Chowk station. `default_date` and `today_date` call the clock separately, so at midnight they could theoretically disagree by one day; a single captured date would be more consistent.

**Output contract:** template receives `stations`, `stations_meta`, `busiest_station`, `peak_hour`, `eval_metrics`, `default_date`, `today_date`, `default_time`, `default_station`. In `index.html`, `stations_meta` is serialized to `window.STATIONS_META`, which `dashboard.js` uses to filter line choices.

**Complexity:** O(S) iteration plus sorting O(S log S) at module initialization for `ALL_STATIONS`; each dashboard request rebuilds a dictionary for S station rows. With 228 rows this is small, though metadata could be built once.

## 7. `get_footfall()` - legacy POST `/get_footfall`

This synchronous result route accepts an HTML form. It reads station/day/time/date/line from `request.form`, strips station marker characters, parses the datetime, derives weekday/service/calendar context, and then calls forecast and schedule functions. It computes the full daily profile even when the selected time is closed; selected-time and hourly demand are set to zero when closed. It calls the station optimizer with explicit `service_open` and chooses the selected line's recommendation for headline fields if a matching one exists. If line doesn't match, the primary recommendation remains selected.

Travel estimates come from `shortest_times_from(travel_graph, station)`, are associated with the station's first line from `stations_df`, and are sorted by minutes. Here the travel-time block has a broad `except Exception` that converts any error into an empty list. This preserves page rendering but hides the exception cause unless separately logged; contrast with `/api/predict`, whose graph call is not inside this catch.

Finally `render_template('result.html', ...)` passes numerous flattened headline values plus nested `schedule_res`, `profile_24h`, travel info, and provenance metrics. The template is the consumer contract; mismatched key names can fail rendering or display blanks.

**Important implementation boundary:** this route is not the asynchronous dashboard API. It produces a complete page response after form submit. The modern dashboard uses `/api/predict` and browser-side rendering. `day_str` is read but never used; actual weekday is calculated from parsed date. This is dead/legacy form input.

## 8. Source-to-flow map for Volume 01

| Caller / trigger | Function | Calls / data | Next stage |
|---|---|---|---|
| `python run.py` | `run.py` main guard | imports global `app`, reads env | Flask development server |
| Gunicorn `run:app` | module import | `app/__init__.py` -> routes import | WSGI request handling |
| `GET /` | `landing()` | profile inference, evaluation summary | Jinja `landing.html` |
| `GET /dashboard` | `index()` | global station DataFrame, metrics | Jinja `index.html`, then JS |
| `POST /get_footfall` | `get_footfall()` | parser, calendar, forecast, schedule, graph | Jinja `result.html` |

## 9. Interview questions and answers

**Why does importing `app` register routes?** `app/__init__.py` imports `routes`; evaluating each decorated function applies its `@app.route` decorator, registering the handler.

**Why is the graph built once?** Topology and station metadata are static during a process, so building once avoids repeated CSV reads/graph creation. Trade-off: changes to files require process restart; startup failures happen earlier.

**Is `dt_obj` timezone-aware?** No. The current Delhi date default is obtained from an aware `ZoneInfo` clock, but the constructed scenario `datetime` has no `tzinfo`.

**Does `_hour_band` compute a standard percentile?** No. It sorts and selects two discrete array positions. For small profile length 19, this is a simple quartile-style threshold.

**How would you test parser boundaries?** Check empty defaults, valid leap date, impossible date, malformed format, `00:00`, `23:59`, and wrong-type values at API boundary. Keep parser behavior separate from whether the time is an operating hour.

## 10. Modification exercise and solution

**Exercise:** Make `index()` read the Delhi date once so `default_date` and `today_date` cannot differ at midnight.

**Solution:** At the start of the handler, set `today = datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()`, then pass `today` for both template fields. This preserves the existing template contract while removing two clock reads. Add a focused test with a patched clock that would cross midnight between calls; no such test currently exists in the repository.

## Current coverage status

This lesson covers startup and synchronous route code. It does not yet explain `/api/predict`; that request orchestration receives its own source-ordered lesson because it is the central runtime path.
