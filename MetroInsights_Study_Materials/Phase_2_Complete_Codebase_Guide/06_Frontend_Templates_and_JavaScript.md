# Frontend Templates and JavaScript

**Source revision:** `4405d167fc323f33be76e2c7f6614fd21cc574a8`. This volume follows the browser code in dependency order: Flask injects initial values into Jinja templates; the dashboard script reads template IDs, posts a scenario, and renders response fields; the landing page has a separate preview script; the theme script updates the document and any Chart.js charts.

## 1. Browser architecture and contracts

The dashboard is server-rendered HTML plus client-side updates. `app/templates/index.html` receives `stations_meta`, `default_date`, `today_date`, and `default_time`. Jinja's `tojson` serializes station metadata into `window.STATIONS_META`. The form controls have stable `id` values consumed by `dashboard.js`. On `DOMContentLoaded`, the script registers listeners and immediately calls `/api/predict`. A successful response replaces displayed values and chart/table contents.

The browser does not run the ML model. Flask handles prediction and returns JSON; the browser formats and visualizes the returned values. Chart.js 4.4.1 is loaded from jsDelivr. If that CDN is unavailable, KPI rendering can still happen but chart creation raises and its local `try/catch` logs the chart failure.

Important contracts:

| Template or API contract | Used by |
|---|---|
| `window.STATIONS_META[station]` has `all_lines` | `updateLineSelectOptions` |
| `station`, `date`, `time`, `line` JSON keys | `/api/predict` request body |
| `data.status`, `data.datetime`, `data.footfall`, `data.scheduling`, `data.profile_24h`, `data.travel_times` | `fetchPrediction` and renderers |
| HTML IDs such as `dispFootfall`, `demandChartCanvas`, `lineBreakdownTableBody`, `travelTimesTableBody` | DOM write targets |
| `line_curves`, `labels`, `predicted`, `historical` arrays | Chart renderers |

If any template ID is renamed without updating JavaScript, the corresponding feature quietly fails or returns early. Optional chaining is used in some selectors but not everywhere; `fetchPrediction` directly reads the four controls, so missing elements cause a rejected async call.

## 2. `dashboard.js` module state and startup

`METRO_LINE_COLORS` is a browser-side display map. It includes an `Aqua Line` color even though this project topology/operations data may not support that line; a color entry alone does not create a route. `getLineColor` tries substring matches case-insensitively and returns a blue fallback. Because it returns the first matching entry, overlapping names can match whichever key appears earliest.

`demandChart`, `lineChart`, `currentData`, `currentTravelTimes`, and `predictionRequestId` are module-scoped mutable values shared by functions. They track Chart.js instances, latest response data, table data, and asynchronous request ordering. The `DOMContentLoaded` callback calls `initControls()` and then fetches the default selection.

### `initControls()` (`dashboard.js:41-130`)

This function queries controls by ID, prevents native form navigation, and registers handlers. Station changes update the line options before fetching. Slider `input` writes the hour into the time field and visible label, then immediately fetches. Time field `change` copies its hour component into the slider, then fetches. Date change clears preset-button visual state. Line selection triggers a request. Search input only filters the already-loaded destination array; it does not call the server.

Preset button behavior: it starts from the browser's current date at noon, then repeatedly advances a day until a weekday/Saturday/Sunday condition is met. `getDay()` uses Sunday=0, unlike Python weekday numbering. Date serialization uses local date components and zero-pads month/day. `Today` does not move the date. The selected preset is marked active and a new prediction is requested. Date calculation uses browser local timezone; the app has no explicit timezone conversion here.

Potential interaction issue: every slider `input` can issue a request, not only on release. Request IDs stop stale responses from replacing newer results, but old HTTP requests are not aborted, so rapid dragging still consumes server work. The handler assumes `selectedTimeLabel` exists. `parseInt` truncates minutes from a time such as `09:45` to hour 9 only for slider sync, while the time input itself remains `09:45`.

### `updateLineSelectOptions()` (`132-152`)

It reads current station and `window.STATIONS_META`. It resets the line dropdown to an all-lines option, then appends one `<option>` per station line. Using `document.createElement` plus `.textContent` is safer than concatenating line names into HTML. It toggles the group. It does not restore the previously selected line after rebuilding, so station change returns to station overview. If required elements/metadata are absent it returns without feedback.

## 3. `fetchPrediction()` async walkthrough (`154-201`)

The exact function is in Appendix A. Each call increments `predictionRequestId` and captures its own ID. It reads control values, shows a loader/status, and sends a JSON POST with `Content-Type: application/json`. `await fetch` pauses this async function while other browser work proceeds; `await res.json()` parses the body. The function does not check `res.ok`, so an HTTP error with JSON body follows the same `data.status` logic; a non-JSON error becomes a caught parse exception.

Before rendering, it compares the captured ID with the latest global ID. If another request started after it, the older response returns early. This is stale-response protection, not cancellation. A success updates `currentData`, calls `renderDashboard`, adds the ready CSS class, clears form status, and schedules chart resize on the next animation frame. A non-success shows the server's `message` or a fallback. `catch` logs details to the developer console but shows a generic network error. `finally` hides the loader only if this is still the newest request, preventing an old request from hiding the new request's spinner.

Example: request A gets id 4. User changes time before A finishes, request B gets id 5. If A resolves, `4 !== 5`, so it returns without drawing; B owns the visible state. Both requests still reached the server.

## 4. `renderDashboard(data)` response-to-UI mapping (`203-313`)

It first requires `data.scheduling`. It destructures common response sections and reads `scheduling.headline`. It chooses a demand value from finite `headline.line_demand` or falls back to total `footfall.hourly_demand`. If a line filter is selected, the headline can be a line-level result. Text is inserted using `textContent` for station names, explanatory strings, calendar labels, and KPI values, which avoids interpreting those values as HTML.

The function derives a human date label by constructing noon in the browser from the response date. Noon avoids many midnight/DST date shifts, but uses local browser timezone. It uses service closure state from `datetime.service_open === false`; closed scenario labels suppress regular demand, utilization, waits and trains.

KPI mapping:

- Footfall uses selected line demand if finite; instant interpolation is scaled by selected-line share. This is display arithmetic, not a separate line-specific model call.
- Headway shows `Varies` for station summary and a number for one line.
- Trains/hour likewise displays combined schedule values for summaries or one-line value.
- Utilization context reads recommended clearance capacity and labels scope as all lines or selected line.
- Wait and fleet text come from the schedule headline.
- Explanation goes to `textContent`.

Each major rendering group has its own `try/catch`, so a chart/table problem need not prevent later sections. Failures only go to console; the user may see a blank/stale section with no visible error state. `currentData` is set before renderer calls. Selected-line chart series use the corresponding line curve; the historical profile is multiplied by a share inferred from current hourly demand. This assumes the current share is suitable for every hour, though line demand shares may vary by time.

## 5. Chart rendering: `renderDemandChart(profile,currentHour)` (`315-405`)

It exits without canvas/profile, reads labels and numeric arrays with empty-array defaults, and creates arrays of point radius/background so the chosen hour is highlighted red and larger. It configures predicted demand and synthetic training-period baseline datasets; if multiple line curves exist, it adds dashed line-specific datasets colored through `getLineColor`.

Before replacement it destroys the previous chart instance. This avoids duplicate canvas listeners/resources. `new Chart(ctx, {type:'line', data, options})` makes a responsive line chart with custom legend, tooltip, zero-based y-axis and operating-hour x-axis. `tension: .35` visually smooths segments; it does not mean the model itself interpolated those points. A Chart.js rendering curve may visually imply intermediate values not present in the discrete data.

Risk: the selected-hour styling checks `profile.hours[i] === currentHour`; if types differ (string vs number), no point will be highlighted. CDN/version/runtime errors are handled by `renderDashboard`'s chart-level catch.

## 6. Breakdown and destination renderers

### `renderInterchangeBreakdown(scheduling)` (`407-489`)

The section is deliberately shown for both interchange and single-line stations. It updates title/description, clears `<tbody>`, then builds rows from `scheduling.all_lines`. It makes arrays for doughnut-chart labels, demands, and colors. `status_action === 'SERVICE_CLOSED'` changes several cells to “Closed” or em dash. The `toLocaleString()` calls make demand easier to read. It then destroys/replaces the doughnut chart and gets a border color from CSS custom property `--surface` so the slices blend with the theme.

Data safety risk: the row is constructed with `tr.innerHTML` and interpolates `l.line`, `l.crowding_color`, and numeric fields from the server. Those values are currently derived from project data/model logic, but `innerHTML` is an HTML injection sink if a future untrusted value can reach them. Safer improvement: construct cells and assign `.textContent`; validate colors against an allowlist. Chart arrays use values as chart data; malformed response values may break Chart.js.

### `renderTravelTimes(times)` (`491-496`)

When an array is supplied, it replaces module state, then delegates display to the filter function. When undefined, it preserves the old state and rerenders current data.

### `filterAndDisplayTravelTimes()` (`498-544`)

It reads table/search/count elements, lowercases and trims the query, and filters destination and line names using substring inclusion. It supports both current API key names (`destination`, `line`, `travel_time_min`) and legacy CSV-like names (`End Station`, `Line`, `Travel Time (minutes)`). It updates filtered count, empties the table, and renders either a no-results row or destination rows.

The function also uses `innerHTML` with interpolated destination, line, and query values. This creates an injection risk if those fields become attacker-controlled. The no-results message embeds user search text. Use DOM-created elements and text nodes to render safely. The `??` operator for minutes means zero is preserved, unlike `||`. Search has O(n) time per keystroke over destination count and O(k) DOM construction for k matches; no debounce is used.

## 7. Landing page script: `landing.js`

An immediately invoked function expression `(function(){...}())` keeps helpers and `profile` private instead of creating globals. `drawPreviewChart` reads `window.METROINSIGHTS_PREVIEW`, normalizes a profile into SVG points using min/max, sets polyline/area geometry and marks index 4 as a 09:00 sample. The fixed index assumes labels are ordered and index 4 is the selected hour; it is sample presentation logic rather than dynamically matched time.

`initScrollMetro` computes document scroll progress between 0 and 1, moves a decorative train along a rail, and grows a progress line. It disables travel when `prefers-reduced-motion: reduce` is set. It attaches passive scroll and resize listeners. `initReveals` uses `IntersectionObserver` to add `is-visible` when content enters the viewport, or immediately reveals all items if unsupported/reduced motion. Once revealed, each item is unobserved. `initMobileNavigation` toggles `hidden`, text glyph, accessible label and `aria-expanded`; clicking a menu link closes it. DOMContentLoaded initializes all four behaviors.

## 8. Theme script: `theme.js`

It is another private IIFE. `applyTheme` restricts theme to `dark` or `light`, writes `documentElement.dataset.theme` (CSS uses it as a selector), and tries to persist `metroflow-theme` in localStorage. Storage failure is caught so current-page theme still works. For each theme button it updates label/title/ARIA and inserts a known static SVG icon. If Chart.js is loaded, it updates chart defaults and existing chart scale text/grid/legend colors, then calls `chart.update('none')` to redraw without animation. On DOM ready it applies the template's theme (already initialized from localStorage inline to avoid flash), then toggles when a button is clicked.

## 9. Templates and their roles

### `app/templates/index.html` (234 lines)

Dashboard shell: head loads core CSS, shared theme CSS, then polish overrides, plus Chart.js. The order matters: later styles can override earlier selectors. It serializes `stations_meta` to JS, builds station/date/time/line controls, and supplies IDs consumed by `dashboard.js`. `defer` on theme JS delays execution until parse completion; dashboard.js is a normal script at the bottom, so its event listener is registered after the document markup exists. The KPI section has initial placeholder content which is replaced by the first API response. Canvas/table-body nodes are renderer targets. Accessibility includes labels, `aria-live`, status role, and search labels.

The HTML form action points to `/get_footfall`, but dashboard.js prevents submit and uses `/api/predict`. Without JS, the form does not provide the same interactive prediction route behavior unless native submission is otherwise triggered; inspect this distinction when debugging progressive enhancement.

### `app/templates/landing.html` (106 lines)

Marketing/overview page. Jinja adds server-generated `hero_profile` to `window.METROINSIGHTS_PREVIEW` using `tojson | safe`, then loads `landing.js` and `theme.js` deferred. `tojson` is the important serialization step: it produces JavaScript-compatible JSON and escapes sensitive characters for embedding. The page's static SVG/chart markup is a target for `drawPreviewChart`; scroll-train elements match the landing CSS/JS selectors.

### `app/templates/result.html` (298 lines)

Legacy synchronous result report rendered by `/get_footfall`. Its fields (`station`, `station_info`, `day`, `date`, `time`, `calendar_context`, `crowding_color`, `crowding_badge`, `explanation`, `hourly_footfall`, `time_footfall`, schedule, `profile_24h`, `travel_info`, etc.) are supplied by route code. Jinja conditions separate interchange/single-line labels and open/closed service display. Inline JS filters destination rows and creates a Chart.js demand chart. Its client-side search hides rows and updates count; it searches station and line text. Most Jinja variable output is escaped by default; the profile uses `tojson | safe`, so safe serialization is expected. Inline style values are built from mapped values; dynamic CSS data should remain validated.

The result page duplicates some dashboard visualization behavior. The dashboard API workflow and this legacy result template are two entry paths; the latter is not the same DOM or response rendering path as dashboard.js.

## 10. Debugging and test ideas

1. In DevTools Network, confirm POST `/api/predict`, JSON request keys, status and response fields before debugging rendering.
2. In Console, inspect Chart.js failures separately from fetch failures.
3. Compare response `scheduling.headline` with displayed KPI values to isolate backend vs DOM mapping.
4. Verify every template ID used in JS exists exactly once on the relevant page.
5. Test out-of-order requests with delayed responses to ensure stale response protection works.
6. Test malicious-looking station/search text with DOM text rendering after replacing `innerHTML` sinks.
7. Browser tests should cover date presets at month/year boundaries, time values with minutes, empty search results, closed service, one-line vs interchange, dark mode after charts exist, and reduced-motion behavior.

No browser test framework or automated tests are tracked. These are proposed tests, not existing coverage.

## Appendix source blocks

Complete HTML and JavaScript sources are appended with original line numbers. Excerpts are consecutive within each file, so you can follow the code directly in the checkout. CSS is covered in the next volume by selector groups and cascade order; it is kept separate to preserve readable source code.
