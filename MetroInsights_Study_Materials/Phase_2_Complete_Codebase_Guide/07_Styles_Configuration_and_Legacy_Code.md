# Styles, Configuration, and Legacy Code

**Revision:** `4405d167fc323f33be76e2c7f6614fd21cc574a8`. This volume covers the files that shape packaging, deployment, presentation, documentation and backward compatibility. Appendix A contains exact text source for all four CSS files, project-level configuration, and legacy generator code.

## 1. CSS loading and cascade

The dashboard template loads `dashboard.css`, then `metro-theme.css`, then `dashboard-polish.css`. Browser cascade considers origin, importance, specificity and source order; among otherwise equal declarations, later rules win. This means `dashboard-polish.css` is an override layer, not a separate component runtime. `result.html` uses the same three stylesheets. `landing.html` uses landing styling and the shared theme styles.

### `dashboard.css` (427 lines)

The base dashboard stylesheet defines shared color/spacing tokens, body/font defaults, header/navigation, cards, forms and controls, badges, KPI grid, charts, tables, explanation blocks, loading/status states, and responsive breakpoints. Read selectors as contracts with HTML class names: for example `.dashboard-container` sets the main content width, `.card` supplies panel surfaces/borders/shadows, `.kpi-grid` lays out key metrics, and `.chart-container` gives Chart.js a sizing context. CSS variables let later theme rules replace surface/text/border colors without duplicating every component selector.

Responsive `@media` blocks change grid/column behavior at narrower widths. If a dashboard element overflows on mobile, inspect both the base layout declaration and later breakpoint override. CSS does not decide demand, API state or schedule values.

### `metro-theme.css` (121 lines)

This stylesheet defines light/dark custom properties keyed by `data-theme` on the root element, then applies them to surfaces, text, borders, controls, charts and theme-toggle affordances. The JavaScript writes `document.documentElement.dataset.theme`; CSS reacts to that attribute. Theme keys should be consumed through `var(--token)` for consistent switching. Hard-coded colors in templates/JS may not follow the theme and are potential consistency issues.

### `dashboard-polish.css` (306 lines)

This file refines visual hierarchy, spacing, desktop widths, station summary, filters, tables and responsive behavior after base rules. Since it loads later, same-specificity overrides take precedence. When a declaration appears ineffective, inspect computed styles and selector specificity rather than assuming the browser ignored it. The file is not a component framework: its rules rely on the actual HTML selectors.

### `landing.css` (121 lines)

Landing-only sections include hero layout, preview chart, feature cards, workflow, transparency content, and scroll-linked metro illustration. Class names also serve as hooks for `landing.js`; the `.scroll-track`, `.scroll-train` and `.scroll-track-progress` elements are positioned/animated from scroll progress. Reveal classes coordinate initial hidden/visible states with `IntersectionObserver`. A `prefers-reduced-motion` rule should keep the content available without requiring animation. The JS additionally honors reduced motion for train travel.

## 2. Runtime and deployment configuration

### `run.py` and `Procfile`

`run.py` imports the Flask app and, only when run as the main script, reads `PORT` (default 5000), derives debug mode from a small accepted set of strings, and starts Flask on `0.0.0.0`. The Render `Procfile` says `web: gunicorn run:app`: Gunicorn imports module `run` and serves the exported WSGI object named `app`. In production, the `if __name__ == '__main__'` development-server block is not the serving mechanism.

Importing `run` imports `app`, routes, forecasting and graph dependencies. Module-level model/CSV loads therefore occur during worker startup; a missing incompatible model or required cleaned data can prevent service startup. `requirements.txt` declares Python packages but is not a lockfile. It uses a mix of exact pins and lower bounds; a future compatible version may be installed for minimum-bound entries. SciPy is declared but repository source imports were not found. `gunicorn` was appended without a version pin.

### `.gitignore`

It excludes `venv/`, Python bytecode/cache and the two generated, large training-data CSV paths. This controls Git tracking only. It does not delete local files and does not prevent pipeline scripts from writing those paths. Runtime inference loads the saved joblib model/metadata and station CSV; training pipeline 03 reads `data/synthetic/dmrc_calibrated_footfall.csv`. A deployment that needs only serving does not necessarily need the large training CSV, but retraining needs it or a way to regenerate it.

### `requirements.txt`

One requirement per line describes installed dependencies. Flask/Jinja/Werkzeug serve HTTP/templates; pandas/NumPy handle tables and arrays; scikit-learn supplies estimator classes; joblib serializes them; python-dateutil/date helpers serve date calculations; Gunicorn runs WSGI. Compatibility risk: joblib pickle-like artifacts depend on compatible Python/library versions and trusted artifacts. There is no lockfile, container image, or CI environment tracked.

### `.vscode/launch.json` and `.vscode/settings.json`

These are editor conveniences, not app settings. The launch profile runs `run.py` in VS Code's integrated terminal with `FLASK_DEBUG=1`, Jinja debugging and debugpy. The settings choose `${workspaceFolder}/venv/bin/python` and terminal activation. Render does not read these editor files.

## 3. Documentation and data provenance

`read.md` describes user setup and project usage; treat implementation and a fresh code audit as authoritative where prose conflicts. `DATA_AUDIT.md` records data provenance/limits. The raw station file is the seed for cleaning; operations CSV contains scenario assumptions; line split JSON contains estimates; generated training CSVs are ignored; model binaries are produced by pipeline 03; metrics JSON records synthetic holdout evaluation. These are different data roles and should not be conflated.

Missing from tracked files: no automated test directory/configuration, no CI workflow, no Dockerfile, no database schema/migration, and no dependency lockfile. Do not present any as project features. Lack of tests does not prove behavior is correct; it means regressions need manual checks unless tests are added.

## 4. Legacy generators

`csvFilesGenerator/footfall.py` is an older generator, not the numbered production pipeline. It reads the compatibility station CSV, calculates station weights from hard-coded line and hub weights, produces 12 weeks of hourly values using seeded Poisson sampling, and writes the ignored legacy CSV. It differs from pipeline 02 in timespan, model factors and metadata outputs. The shared output filename can mislead operators; verify which script generated a CSV before describing it.

`csvFilesGenerator/compartmentcapacity.py` defines a small table of line/coach/capacity values and writes `metro_lines.csv` in the current working directory. Its output location depends on where the shell runs it, unlike pipeline paths anchored to `BASE_DIR`. It is a legacy utility and does not feed the current scheduler, which reads `data/cleaned/metro_line_operations.csv`.

`csvFilesGenerator/howtorun.txt` is a human run note. It is not executable configuration. Its final command lacks a newline between `python run.py` and the next prompt in the tracked text; this is a documentation formatting issue, not Python syntax.

## 5. Static assets and generated artifacts

`app/static/animation.gif` and `app/static/dmrc_logo.png` are tracked image files, not line-addressable source. Repository search found no template/CSS/JS references to these two assets at the documented revision, so they appear unused by the current UI. (An untracked external consumer cannot be ruled out.) The `.joblib` model and metadata are binary serialized artifacts; pipeline 03 produces them and `app/forecasting.py` loads them. `evaluation_metrics.json` is text and is read for the evaluation endpoint/display. Model files should only be loaded from trusted project-controlled sources.

## 6. Reliability, security and targeted improvements

- Check every module-level file read and model load in a clean deployment image; import-time exceptions can block all routes.
- Validate operations data (positive headways, capacities, fleet, turnaround) before calculations.
- Pin a tested dependency set and ensure model artifacts were created with compatible versions.
- Replace dynamic `innerHTML` in browser renderers with DOM nodes plus `textContent` for station/line/search strings.
- Add route tests for malformed JSON, unknown station, invalid time/date, missing model files, closed service and graph failures.
- Add offline pipeline tests with tiny fixture data; verify deterministic seed behavior and output schema.
- Clarify that “estimated”/“synthetic” values are scenario outputs rather than live counts or observed ridership.

## Appendix

Complete text sources follow with original line numbers for CSS, deployment/editor config, dependency files, docs, and legacy utilities. Image/model/data binaries are catalogued by path, format, producer/consumer and limitations in the Master Index rather than printed as text.
