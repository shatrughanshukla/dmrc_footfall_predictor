# Volume 02 - The /api/predict Request, Line Allocation, and JSON Contract

**Source revision:** 4405d167fc323f33be76e2c7f6614fd21cc574a8  
**Primary source:** app/routes.py:234-420; connected caller app/static/js/dashboard.js:154-201; connected callee app/scheduling_optimizer.py:252-306. Complete source excerpts for the whole API route and both small endpoints are inserted in the PDF appendix from this revision.

## 1. The request contract

The endpoint is registered by @app.route('/api/predict', methods=['GET', 'POST']). The primary dashboard sends a POST with Content-Type: application/json and a JSON body shaped like:

    {"station":"Rajiv Chowk","date":"2026-10-14","time":"09:00","line":""}

The endpoint also supports GET query parameters. It returns a JSON object with status, station metadata, date/time and calendar context, selected-time and hourly demand, the full profile, scheduling headline/all-line outputs, travel estimates, and provenance strings. Date/time parse errors return HTTP 400 with {status: "error", message: ...}. Other unexpected errors are not caught at the endpoint and may become HTTP 500 responses.

## 2. Start of api_predict() - select input and parse time (source lines 234-253)

1. The decorator binds both GET and POST to this function. The function docstring describes dynamic frontend use but does not restrict method.
2. request.get_json(silent=True) asks Flask to parse JSON; silent=True suppresses parse errors by returning None. or request.args selects query parameters if JSON is absent or false-like. Thus an empty JSON object also falls back to query args.
3. data.get(...) uses defaults for station, date, time, and line. station is assumed to be a string because .strip() and .rstrip() are called immediately. The code removes trailing footnote symbols then whitespace. date_str, time_str, line_filter are not type-checked.
4. _parse_datetime produces local scenario date/hour/minute. Only ValueError from this block is caught and converted into JSON plus 400. Attribute/type errors caused by malformed JSON shapes or non-string values are not caught here.
5. Calendar context is computed from the parsed date. service_open is checked with both hour and minute, then stored into that mutable context dictionary. Station metadata is looked up even for a closed time.

**Verified risk:** this route has no allowlist check for station names before scheduling. get_station_info() returns a fallback with empty all_lines for unknown station names; optimize_station_schedule() then builds no line recommendations and calls max() on an empty list. That raises ValueError and is not caught by /api/predict. Validate station against ALL_STATIONS before forecasting/scheduling to return a useful 400 instead.

## 3. Forecast section (source lines 254-258)

Three distinct quantities are prepared:

- time_footfall: minute-interpolated selected-time estimate, only if the service gate is open; else literal integer zero.
- hourly_footfall: model estimate for the selected whole hour, also zero when closed.
- profile_24h: the 19-point daily profile from 05:00 through 23:00, calculated regardless of selected-time closure.

The variable name profile_24h is historical shorthand. It is not 24 observations: the implementation has 19 hourly labels. Therefore a selected time of 02:02 should have zero selected-time demand and closed service while the same response can still carry a daytime chart. The chart is not a prediction that trains run at 02:02.

The forecasting helper includes its own service check in minute interpolation, but the route performs a service check before calling it. This is redundant defensive gating for selected-time count; direct hourly prediction itself only returns zero outside hours 05-23, not at 23:30 boundary by minute. Route-level gate is what handles 23:31 as closed.

## 4. Station/line scheduling (source lines 259-270)

The API passes:

- station and primary line from cleaned station lookup;
- every line listed for that station;
- selected hour and Python weekday number (Monday=0 through Sunday=6);
- total_footfall=hourly_footfall (the whole-hour station demand, not the minute-interpolated figure);
- workday and service-open flags.

optimize_station_schedule() splits total demand over line shares at interchanges, calculates per-line recommendations, and returns an object containing line_recommendations, primary_recommendation (the highest-demand line), is_interchange, and total station demand. It performs closed-service overrides inside the optimizer too. The route then handles headline display/aggregation.

## 5. Choose the headline: selected line vs station overview (source lines 271-324)

Initially filtered_rec points to the optimizer's primary recommendation. station_summary is true only if there is no line filter and the schedule says this is an interchange.

If line_filter is truthy, the route loops over line recommendations, comparing lowercase line names. A match replaces filtered_rec; if there is no match, the previous primary line remains silently. **Potential UX risk:** invalid line names are not reported, so the response can look like a line-specific selection while actually showing the primary line. Validate membership and return 400 or include a warning.

If it is an unfiltered interchange, the API constructs an aggregate headline:

- total_demand uses optimizer station total.
- recommended_capacity and existing_capacity sum per-line estimated clearance capacity. This combines corridor capacities for the station overview.
- utilization = total_demand / recommended_capacity * 100, with zero if capacity is false-like.
- Badge thresholds are strict > comparisons: above 105 critical; above 88 high; above 65 moderate; otherwise low. So exactly 65 is labeled low; exactly 88 is moderate; exactly 105 is high.
- Trains/hour add line frequencies together. Combined headway is deliberately None, because parallel/interchange lines do not have one meaningful shared headway.
- Average wait is a demand-weighted average: sum(wait_i * demand_i) / max(total_demand, 1). The denominator floor prevents division by zero. If total demand is zero but line waiting values were nonzero, this floor would not make it a mathematically weighted average; closed handling follows later.
- fleet_size_available sums line fleet sizes. The displayed deployed count sums each line recommendation’s deployed fleet estimate.
- The narrative uses comma-grouped values and labels the capacity estimate; it explicitly says the value is not a live passenger count.

**Illustrative calculation only:** suppose the lines' hourly demands were 4,000 and 3,000 and their recommended clearance capacities were 12,000 and 8,000. Combined utilization is (7,000 / 20,000) * 100 = 35%. This is not an actual request result; it only demonstrates the formula.

## 6. Closed-service override (source lines 326-345)

After all other headline decisions, if the selected minute is closed, the route makes a shallow dictionary copy ({**filtered_rec, ...}) and overwrites service-dependent values. This preserves other keys such as is_peak and any fields not explicitly replaced, while setting line demand, trains/hour and capacity to zero; headways and wait to None; utilization to None; risk to SERVICE_CLOSED; badge to Metro closed; and a closure explanation.

This is why the frontend can show N/A utilization instead of zero percent: no operating capacity denominator exists when no trains are running. It also ensures that station summary and line-focus headline both show closed state. schedule_res['line_recommendations'] remains available to the table and is independently closed-overridden inside optimize_station_schedule().

## 7. Travel graph integration (source lines 347-357)

The endpoint asks shortest_times_from(travel_graph, station) for a dictionary of destination station -> estimated minutes. It maps each destination to a line using dict(zip(stations_df['Station'], stations_df['Line'])); if no line is mapped, it emits Metro Network. It sorts by minutes and builds objects {destination, travel_time_min, line} with time rounded to one decimal place.

Unlike the legacy HTML route, this graph call is not wrapped in a try/except. An unexpected graph exception will abort the request. The output is a shortest-time estimate, not path steps or a timetable journey, and it does not depend on selected clock time/service-open flag.

## 8. Calendar enrichment and response body (source lines 359-398)

The API adds hour_band, selected whole-hour demand, and daily peak hour to the calendar dictionary, then returns jsonify(...):

- status is "success" on this path.
- station and station_info expose canonical request key and metadata.
- datetime serializes date/day/time/hour/minute plus optimizer peak flag and service-open boolean.
- calendar_context includes weekday/workday/occasion/source plus UI helper fields.
- footfall distinguishes selected-minute interpolation, selected-hour demand, daily total, and daily peak.
- scheduling exposes headline, line-level schedules and interchange boolean.
- profile_24h carries chart series/labels/line curves.
- travel_times is sorted destination data.
- data_provenance explicitly marks topology, capacities, headways, footfall and line share as project estimates or assumptions.

**Why types matter:** a client may treat capacity_utilization_pct as a number when open and null when closed; headways are numbers when applicable and null for all-line/closed headlines; the frontend must branch instead of blindly appending % or m.

## 9. api_stations() and api_model_metrics() (lines 401-420)

api_stations() repeats much of the metadata serialization used by index(): iterate rows, split All_Lines, convert nullable coordinates to float-or-null, and return {stations: [...]}. It is a compact discovery endpoint; the current dashboard also receives stations_meta embedded in the template, so this endpoint is not the only way the browser obtains station metadata.

api_model_metrics() simply returns get_model_evaluation_summary() as JSON. It exposes saved metrics and provenance labels; it does not run training or compute new scores on a request.

## 10. End-to-end request trace with illustrative values

Input: Rajiv Chowk, 2026-10-14, 09:15, no selected line.

1. Browser serializes the controls into JSON. Request ID increments before fetch.
2. Flask parses date/time; dt_obj is a naive 09:15 local scenario, and weekday is Wednesday (2).
3. Calendar helper supplies workday/occasion context; service helper returns true for 09:15.
4. Inference produces model estimates at 09:00 and 10:00; minute interpolation is p09 + (p10-p09)*(15/60) then rounded and clamped nonnegative. The example gives the formula, not repository-verified passenger values.
5. The line schedule call receives selected-hour demand, not the 09:15 interpolated number.
6. Since Rajiv Chowk is an interchange and no line is selected, line recommendations are aggregated. Each line's estimated clearance capacity is summed; utilization is station demand divided by that sum.
7. The graph provides sorted route-time estimates.
8. The route builds JSON. Browser checks request sequence, stores newest successful payload and renders dashboard fields/charts/tables.

## 11. API failure behavior and proposed improvements

### VERIFIED IMPLEMENTATION

- Date/time ValueError becomes 400 JSON.
- Service closure does not reject the request; it returns a closed state and zero selected demand.
- Graph errors are uncaught in JSON API, unlike /get_footfall.
- Endpoint does not check line-filter membership.

### POTENTIAL BUG OR RISK

- Wrong JSON types can raise AttributeError/TypeError at .strip() or later; body fields are not schema-validated.
- Unknown station can reach empty-line optimizer and fail at max(line_recommendations, ...).
- Unknown line silently leaves primary recommendation selected.
- API response mixes null, numeric values and strings in dependent fields; clients must honor service status.
- Recomputing graph shortest paths per request may become costly if topology expands; currently small graph and no cache.

### PROPOSED IMPROVEMENT

Validate JSON/query input into a schema before business logic; validate station and line against loaded metadata; use one error response shape; log server errors; decide whether travel-time output should remain available when closed; add boundary tests around service-hour edges and aggregate thresholds. Do not describe these improvements as already implemented.

## 12. Interview questions with follow-ups

**Why calculate hourly and minute demand separately?** The model is trained on hourly examples. Minute interpolation is a presentation estimate between neighboring hourly outputs; schedule decisions currently use the selected whole-hour count.

**Why is the selected-line KPI not the entire station?** The chosen line's recommendation replaces the primary headline; for line-specific display the frontend scales selected-time estimate using the line/hour demand share. All-lines interchange view aggregates capacity/frequency separately.

**Why set closed utilization to null instead of zero?** Zero utilization could incorrectly imply available service capacity with no passengers. null indicates the ratio is not meaningful when capacity is zero/not operating.

**What does “no collision” mean in this API?** Nothing: the app has no train positions or movement simulation. Scheduling is a headway/capacity scenario, not collision avoidance.

**How would you debug a 500 for an unknown station?** Reproduce API input, follow get_station_info fallback to empty lines, inspect optimize_station_schedule loop and subsequent max(line_recommendations, ...), then add request-boundary station validation and a regression test.

## 13. Modification exercise and solution

**Exercise:** Ensure an unknown station returns a structured 400 before schedule evaluation.

**Solution outline:** After reading and normalizing station, check station in stations_df['Station'].values or a precomputed set. If false, return jsonify({"status":"error","message":"Unknown station."}), 400. Prefer a precomputed set at module initialization to avoid scanning the column each request. Add tests for missing station default, valid station, unknown string, and non-string station input. The repository currently contains no automated test suite, so these would be proposed tests, not existing tests.

## Source connections

| Stage | Exact location | Produces/consumes |
|---|---|---|
| Browser request | app/static/js/dashboard.js:154-201 | JSON request values and returned response |
| Input/route orchestration | app/routes.py:234-398 | Full response contract |
| Calendar/service gate | app/calendar_context.py:85-111; app/operating_hours.py:7-10 | Date context and open/closed flag |
| Feature prediction/profile | app/forecasting.py:56-189 | selected estimates and 19-point profile |
| Line schedule | app/scheduling_optimizer.py:252-306 and per-line helper | headline and line schedule records |
| Graph travel estimates | app/travel_graph.py:139-167 | destination times |
| Browser rendering | app/static/js/dashboard.js:203-544 | KPIs, charts, line rows and travel table |
