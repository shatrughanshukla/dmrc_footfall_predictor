# Volume 03 - Runtime Forecasting, Feature Engineering, and Model Training

**Revision:** 4405d167fc323f33be76e2c7f6614fd21cc574a8  
**Sources:** app/forecasting.py; pipeline/03_train_and_evaluate_forecaster.py; models/evaluation_metrics.json; metadata producer/consumer contracts.  
**Code excerpts:** the PDF appendix includes all functions in both Python modules and their module-level constants/import setup with original line numbers.

## 1. Two related but different flows

Training is an offline, heavy operation: read millions of synthetic rows, construct features and historical aggregates, fit baselines and a gradient-boosted tree model, evaluate, then serialize estimator and metadata. Runtime inference is a lightweight operation: a Flask process loads the serialized artifacts once, makes a one-row feature table for a chosen station/date/hour, asks the model for one prediction, then post-processes that result.

The large generated CSV is a training input. The running app does not read it. The app reads the estimator, metadata, cleaned station table, and small metrics file.

## 2. Runtime module initialization: app/forecasting.py:1-32

Imports: os/path utilities, joblib, NumPy, pandas, datetime, calendar helper and service-window predicate. BASE_DIR is computed relative to this file, then used to construct artifact paths. At import:

1. joblib.load deserializes model and metadata into process globals _MODEL and _META.
2. pandas reads stations_cleaned.csv and indexes rows by Station.
3. _METRICS starts as an empty dict; if the JSON path exists, json.load populates it.

These are startup side effects, not lazy per-request loads. Missing model/metadata or station CSV can prevent app startup. Metrics file is optional, so absent metrics yields empty saved metrics plus runtime provenance keys. joblib must be trusted and version-compatible; the code does not validate estimator feature count against metadata before serving.

## 3. get_station_info(station: str) -> dict

Purpose: adapt one station-directory row to the inference/API structure. Known station: split All_Lines on commas and strip whitespace, return primary line, bool interchange, and float coordinates if non-null. If All_Lines column is absent, fallback to [Line]. Unknown station: return "Unknown", no lines, false interchange and null coordinates.

Input is a station name string. Output dict fields are station, line, all_lines, is_interchange, latitude, longitude. It reads global _STATIONS_DF and does not mutate it.

**Illustrative return shape:**
    {"station":"Rajiv Chowk","line":"Blue Line","all_lines":["Blue Line","Yellow Line"],"is_interchange":true,"latitude":28.63,"longitude":77.22}
Coordinate values here are illustrative; use CSV for exact values.

**Edge:** duplicate station index rows can make .loc return a DataFrame instead of Series; the code expects one row. Unknown station fallback prevents lookup error, but later forecasting maps missing station index to 0, and optimizer can fail because all_lines is empty. It is safer for API routes to reject unknown names than to treat them as valid forecast identities.

## 4. predict_hourly_footfall(station: str, dt_obj: datetime, hour: int) -> int

This is the model inference core.

### Step-by-step construction

1. Hours below 5 or above 23 return 0 before any metadata lookup.
2. Get station information. Look up Station_Idx and Line_Idx in saved dictionaries; absent keys default to index 0. This keeps array/schema inputs finite but can silently map unknown categories to the first learned category.
3. Derive weekday via datetime.weekday() (Monday=0) and IsWeekend as 1 for Saturday/Sunday.
4. Encode cyclic time: sin/cos pairs for hour/24 and weekday/7. Pairs preserve wraparound similarity, e.g. Sunday and Monday are near neighbors on the weekly circle.
5. Read historical fallback features from metadata. Hist_Station_Mean falls back to global_mean. Hist_Hour_Day_Mean key is station-index + weekday + hour; missing key falls back to station mean.
6. Obtain month and call get_calendar_context(dt_obj.date()). HolidayType comes from that context; IsHoliday is true when holiday type is nonzero; IsWorkday comes from calendar context.
7. Get station typology from saved map, default RESIDENTIAL_SUBURB; map to integer typology index default 0. Get station-month historical mean, fallback to station mean.
8. Construct a dictionary of 23 named features. These include raw date parts; weekend/holiday/workday; event class; six trig values for hour/day/month; station/line/typology indexes; interchange flag and number of lines; three historical means.
9. Build a one-row pandas DataFrame with exactly the saved feature_cols order: [{name: values[name] for name in ...}]. That order is a training-serving schema contract.
10. _MODEL.predict(features)[0] extracts the first (only) prediction. Convert to float, round, then clamp below zero to zero; return integer.

**Output type:** int. **Side effects:** none beyond CPU/memory allocation. **Calls:** get_station_info, get_calendar_context, estimator predict. **Complexity:** feature calculation is O(1) relative to dataset size; model tree traversal depends on estimator size/depth. Building a DataFrame adds small allocation overhead.

### Worked feature example (symbolic values)

Suppose the user chooses a known station at Wednesday, 14 October 2026, hour 09. Then weekday=2, IsWeekend=0, month=10, and the date-derived day fields follow datetime. Hour cyclic values are sin(2*pi*9/24) and cos(2*pi*9/24). Historical values come from serialized maps using the selected station index. The values dict is reordered by metadata feature_cols before predict. The actual encoded station id and counts require reading this checkout's binary metadata and are not invented here.

### Risks and boundaries

- Direct hourly function knows only integer hours. The API service gate handles minute-level 23:30 closure.
- Unknown station gets station index zero and unknown line index zero; prediction may be numerically returned but semantically misidentified.
- Missing feature_cols entry causes KeyError before predict. A metadata feature name absent from values also causes KeyError.
- Training/inference category maps and model must be versioned together.
- Negative raw regressor output is clipped to zero after rounding.
- Calendar categories are static project scenarios, not measured event-response effects.

## 5. predict_footfall_with_minute_interpolation(...)

Signature: station, dt_obj, hour, minute -> integer estimate. First calls is_service_operating(hour, minute); closed times return 0. Otherwise it gets v0 at selected integer hour and v1 at min(23, hour+1), then computes v0 + (v1-v0)*(minute/60.0), rounds and clamps nonnegative.

At 09:15, weight is 15/60=.25: estimate is 0.75*v09 + 0.25*v10 before rounding. At 23:20, both v0 and v1 refer to 23:00 because next_hour is capped at 23, so interpolation remains the 23 estimate; at 23:31 the operating-hours gate returns zero. The algorithm assumes demand changes linearly between hourly model outputs. It creates smooth interpolation, not measured quarter-hour counts.

## 6. predict_station_full_day_profile(station, dt_obj) -> dict

Creates hours=list(range(5,24)), exactly 19 integer points. It loops over hours and appends model predictions plus corresponding training-history means. Labels format each as HH:00. np.argmax finds the first maximum index; labels[index] becomes peak_hour. sum(predicted_curve) becomes predicted_daily_total.

It then obtains station line list. For multiple lines, it imports get_interchange_line_split locally and reads a modeled share; for one line it creates 100% share. For each line, each hourly predicted value is multiplied by share and rounded. Return fields are labels, hours, predicted, historical, peak_hour, peak_footfall, daily_total, line_curves, is_interchange and all_lines.

**Why local import?** It avoids importing scheduling_optimizer at module top, but scheduling_optimizer itself loads static files at import. A function call on an interchange therefore imports it if it was not already loaded. The runtime module can tolerate this import because routes imports scheduling too.

**Verified naming caveat:** docstring says 24-hour profile, but the list has 19 buckets (05 through 23 inclusive). daily_total sums hourly estimates, not minute-level integration. The 23:00 modeled bucket is present even though the service window closes at 23:30; it should not be described as a full 60-minute count after close.

**Potential divide-by-zero risk:** unknown station fallback has all_lines=[]; is_interchange false but get_station_info returns line Unknown, so the function uses all_lines empty and creates no curves. The fallback expression in get() only applies if all_lines key is missing, not when it exists as an empty list.

## 7. get_model_evaluation_summary() -> dict

Returns a shallow dictionary expansion of _METRICS plus three runtime keys: synthetic-only basis, real_world_validation_available=False, feature_count from saved feature_cols, artifact_warning=None. Since keys after **_METRICS are written last, these constants override any same-named JSON entries. This method describes stored evaluation; it does not recompute metrics.

## 8. pipeline/03_train_and_evaluate_forecaster.py - module setup

The script imports joblib/NumPy/pandas and sklearn HistGradientBoostingRegressor, Ridge and metrics. BASE_DIR is inserted into sys.path so importing app.calendar_context works when the script is run directly. It defines synthetic input, small metadata inputs and three artifact outputs. SPLIT_DATE is the string 2026-10-01, compared with pandas datetime values.

Main guard means direct execution runs training; importing the module defines functions/constants without starting model training.

## 9. prepare_annual_data() - input to model matrix

### Read, enrich and encode

- Read synthetic CSV parsing Date into datetime; read cleaned station rows.
- Optionally load typology JSON. Missing file means all stations use the default residential category.
- Select Station, Is_Interchange, Num_Lines and drop duplicate combinations; left-merge into footfall rows. Left join preserves generated demand even if metadata is missing. Missing interchange/line count becomes false/1.
- Create fixed typology2idx dictionary and map station to category; missing type falls back to residential; unknown typology index becomes zero.
- Derive weekday, month, day-of-month, day-of-year, weekend.
- Build contexts once per unique date rather than once per row, then map holiday type, holiday flag, workday. This reduces repeated Python date-context calls.
- Add sin/cos cyclical encodings for hour, weekday and month.
- Sort unique station/line labels and map them to integer indices. These IDs are category labels, not magnitudes with ordinal meaning.

### Chronological split

train_mask is Date < SPLIT_DATE. train_df is a copy before split; test_df is all rows on/after split. Summary output prints actual min/max/count. This prevents future rows from contributing to the training fit, but holdout is still synthetic data generated by the same code recipe.

### Historical features and leakage controls

Global/station/station-weekday-hour/station-month means are first computed from all training dates. Those maps are used for future test rows and later runtime inference.

For training rows, the code separately constructs prior-only features:
- Sort training rows by date, station index, hour.
- Group by station/date and average hourly Footfall into Daily_Mean.
- For each station's dates, cumulative sum minus current Daily_Mean divided by prior date count yields mean over earlier station-days. Replacing zero count with NaN marks first history as unavailable.
- Repeat per station/month group for prior same-month historical mean.
- Merge these daily prior values back to hourly training rows with many-to-one validation.
- Group hourly training rows by station index, weekday, hour. cumcount is number of prior occurrences in that group; cumulative sum minus current target divided by that prior count forms the prior-only weekday-hour mean.
- Initial unavailable values are NaN; HistGradientBoostingRegressor accepts NaN natively.
- For holdout rows, fill historical features from all training dates only; unseen keys fall back to station mean, then global mean.

This avoids a training row using its own target or later date targets as its aggregate feature. It does not make the synthetic target realistic; it only improves the validity of the split within that synthetic scenario.

### Return contract and complexity

Returns train_df, test_df, feature_cols, metadata. Dataset operations are broadly O(N) to O(N log N) due groupings/sort/merge; memory is O(N) because copies and intermediate tables coexist. The generated dataset has 3,153,696 rows, so this offline step is memory-heavy relative to serving.

Metadata includes both-direction station/line mappings, typology maps, calendar maps, historical means, exact feature_cols and split_date. Training saves this metadata with the model so runtime can reproduce the feature contract.

## 10. compute_metrics(y_true, y_pred)

Calculates MAE, root mean squared error, R-squared and MAPE. MAPE uses only targets where y_true > 0, preventing divide-by-zero but changing its population: it excludes zero-demand targets. Returns rounded Python floats in a dictionary.

Edge: if there are no positive y_true values, np.mean of an empty vector returns NaN with a warning; function does not special-case it. MAE/RMSE/R2 also have undefined/degenerate cases for empty arrays or constant targets. Current metrics file reports a nonempty synthetic holdout.

## 11. train_and_evaluate_model()

1. Gets prepared split, schema and metadata.
2. Selects feature columns into X_train/X_test, targets into NumPy values.
3. Baseline 1 predicts per-row station historical mean; baseline 2 predicts station-weekday-hour history. These are feature-based naive comparisons.
4. Ridge(alpha=100) trains on X_train.fillna(0); predictions are clipped to nonnegative. Missing history is represented as zero only for Ridge.
5. HistGradientBoostingRegressor uses 250 iterations, learning rate 0.06, max_depth 9, min_samples_leaf 25, l2_regularization 0.05, seed 42. It trains with NaNs retained.
6. Evaluate held-out predictions through compute_metrics.
7. Create models directory if needed, save model then metadata with joblib.dump.
8. Assemble JSON report with row counts/date split, validation description, model comparison and feature names; dump to evaluation_metrics.json; return report.
9. Script main guard prints completion after direct invocation.

**Side effects:** writes model, metadata and metrics files; prints progress. If training fails after model dump but before metadata/report write, artifacts can become out of sync. A safer publication process writes to a temporary versioned directory and atomically swaps a matched artifact bundle.

## 12. Evaluation interpretation

The checked-in metrics record a 411,540-row chronological synthetic test set and model MAE 27.90, RMSE 54.82, R² 0.9947, MAPE 5.16% for HistGradientBoostingRegressor. Baselines have worse values. These figures describe fit to synthetic labels generated under authored rules. They do not establish accuracy on observed DMRC riders. The dataset is not independent of its generator recipe.

## 13. Interview questions and exercises

**Why save feature_cols inside metadata?** It defines the exact order used to build the inference DataFrame; column ordering/schema drift can break or corrupt predictions.

**How does the code avoid self-target leakage in training history?** For each training row, cumulative sum subtracts that row's own value, then divides by the number of earlier group observations. Data is sorted chronologically first.

**Why retain NaN history for HistGradientBoosting but fill with zero for Ridge?** This estimator handles missing values natively; the linear baseline's numeric design matrix needs a finite representation.

**Does the test split prove the model generalizes to Delhi ridership?** No; both train and test labels come from this repository's synthetic scenario process.

**Exercise:** Explain the first row in one station's daily group. Its prior station-day count is zero, replaced with NaN; therefore there is no historical station average available yet. HistGradientBoosting can consume this missing value. Add a test or assertion in a future pipeline that confirms the first historical value per station is missing and later values use only earlier dates.

**Proposed improvement:** save a manifest with source revision, Python/sklearn versions, input hashes, feature schema and training timestamp alongside artifacts; verify manifest at app startup. No such artifact manifest currently exists.

## Source map

| Function/block | Purpose | Main consumers |
|---|---|---|
| app/forecasting.py:15-32 | artifact paths and process-level loading | every inference call |
| app/forecasting.py:34-53 | station row adapter | forecast/routes/profile |
| app/forecasting.py:56-116 | 23-feature row and estimator prediction | routes/profile |
| app/forecasting.py:119-130 | minute interpolation + service gate | routes |
| app/forecasting.py:133-188 | 19-hour profile + line curves | dashboard/landing/result |
| app/forecasting.py:191-198 | saved evaluation/provenance response | routes |
| pipeline/03_train_and_evaluate_forecaster.py:48-194 | data prep/schema/history split | train entrypoint |
| pipeline/03_train_and_evaluate_forecaster.py:197-208 | score calculation | training |
| pipeline/03_train_and_evaluate_forecaster.py:211-297 | baseline/model/artifact lifecycle | offline pipeline |
