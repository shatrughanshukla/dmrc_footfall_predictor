# Volume 04 - Calendar Rules, Station Cleaning, and Synthetic Data

**Revision:** 4405d167fc323f33be76e2c7f6614fd21cc574a8  
**Sources:** app/calendar_context.py, app/operating_hours.py, pipeline/01_audit_and_clean_data.py, pipeline/02_generate_calibrated_dataset.py, data/raw and data/cleaned CSV/JSON.  
**Code appendix:** complete Python source modules and exact original line numbers.

## 1. Provenance labels before algorithms

The repository contains station/line seed tables, generated labels, hand-authored configuration and serialized model files. It does not contain observed station-by-hour ridership, AFC entry/exit counts, OD data or a current verified train schedule.

**VERIFIED IMPLEMENTATION:** pipeline scripts read/write the described files and use the constants described below.  
**NOT VERIFIED:** the data audit says raw source/retrieval/license details and row-level citations for operational parameters are absent. A code comment or JSON field saying “verified” does not independently verify that fact. Treat throughput weights, station typologies, hourly shapes, line splits, event multipliers and operating values as project assumptions until sourced.

## 2. app/operating_hours.py

Module constants convert clock boundaries to minutes from midnight: start=5*60=300 (05:00); end=23*60+30=1410 (23:30). is_service_operating(hour, minute=0) converts inputs to integers, calculates hour*60+minute and returns start <= minute_of_day < end.

The start is inclusive; end is exclusive. Examples: 04:59 false, 05:00 true, 23:29 true, 23:30 false under the exact code. Note that project audit text has described the modeled window as through 23:30; the implementation's half-open interval means the instant 23:30 itself is excluded. This is a source/documentation discrepancy to preserve in the guide.

The helper accepts integer-like values; it does not validate hour in 0..23 or minute in 0..59. Inputs such as hour=24, minute=-30 can map to a legal-looking minute total; callers should validate a real clock representation. API parser normally supplies valid parts.

Complexity O(1), no side effects. Imported by forecasting and routes; it is the central boundary rule for selected-time forecasting.

## 3. app/calendar_context.py

### Module data

Imports Python date. _occasion(name, category, *, public_holiday=False, source="") returns a dictionary with name/category/source, public-holiday flag and integer holiday_type. The category-to-id mapping is NATIONAL=1, FESTIVAL=2, PEAK_FESTIVAL=3, SHOPPING_PEAK=4, LEISURE_PEAK=4. Unknown category causes KeyError; call sites use known literal categories.

OCCASIONS maps explicit dates from 2025 through 2033 to event records. Source labels distinguish the synthetic 2025 project calendar, a named GNCTD 2026 notice, and future festival dates whose office closure is unconfirmed. These labels are data values, not an external source verifier.

The annual loop for year 2025 through 2035 inserts fixed dates with setdefault. setdefault keeps explicit entries from earlier dictionary literals instead of overwriting them. Republic Day, Independence Day, Gandhi Jayanti and Christmas become public-holiday events in this loop. Existing explicit rows retain their own labels/category.

### get_calendar_context(day: date) -> dict

1. Fetch exact date event with OCCASIONS.get(day); missing key yields None.
2. weekend = weekday >=5 (Python Saturday=5, Sunday=6).
3. public_holiday is true only when an event exists and its flag is true.
4. workday = not weekend and not public_holiday. A weekday festival with closure unconfirmed remains workday.
5. day_status prioritizes weekend, then public holiday, then listed-but-unconfirmed weekday event, then ordinary workday.
6. Return ISO date, weekday name, weekend/workday/public-holiday booleans, status, optional event name/category/source, category id or zero, and coverage note.

**Important:** “occasion present” and “public holiday” are different booleans. The generator may apply a festival category multiplier while retaining weekday work profile. Calendar rules are static and do not query a live holiday calendar.

**Complexity:** O(1) average dictionary lookup. Input must be datetime.date; passing a string will not find a key and then fail at .weekday().

**Exercise:** For a Saturday that is also a listed holiday, day_status returns Weekend because that branch is first, but is_public_holiday may still be true.

## 4. pipeline/01_audit_and_clean_data.py

### Module setup and assumptions

Imports os/sys/pandas; calculates BASE_DIR; inserts app directory into sys.path; imports INTERCHANGES and LINES from network_topology. It uses raw CSV and writes cleaned CSV plus legacy copies.

VERIFIED_COORDINATES is a seven-station dictionary of (latitude, longitude) tuples. The code names them verified; the audit cannot trace their external source per row. METRO_OPERATIONS is a literal list of 11 dictionaries, each a row with line name, coaches, nominal/comfort/crush capacities, minimum signal headway, maximum policy headway, baseline peak/offpeak headways, fleet, turnaround and technology. These are inputs to a what-if model, not dynamically downloaded DMRC rules.

### clean_stations() -> pandas.DataFrame

1. Read data/raw/DELHI_METRO_DATA.csv.
2. Convert Station to string, remove trailing marker characters, trim outer whitespace. rstrip removes matching characters only at the end.
3. Iterate rows. If a station appears in VERIFIED_COORDINATES and either coordinate is NA, assign both coordinates from the hard-coded pair and increment the count. If one coordinate exists but the other is absent, both are overwritten.
4. For each station, look up authored INTERCHANGES. Interchange: sort line names, make comma-separated All_Lines, set true and count lines. Otherwise set false, use primary Line only, count=1.
5. Attach Is_Interchange, All_Lines, Num_Lines columns.
6. Create output directory, write cleaned CSV without index.
7. Write a four-column legacy projection Station/Line/Latitude/Longitude, discarding added interchange fields.
8. Return the cleaned DataFrame.

The row loops are O(S); pandas I/O and string conversion are also O(S). Required columns are assumed; missing columns raise. There is no full schema validation or duplicate-station conflict resolution.

### create_operations_dataset() -> DataFrame

Build DataFrame from METRO_OPERATIONS; create directory; write the cleaned operations CSV. Then construct a reduced legacy table. Compartment Capacity is round(Nominal_Capacity / Coaches); Total Capacity is nominal capacity. Write legacy CSV and return full operations table.

This derives per-coach capacity and reduces columns; it does not validate values against a live feed. If Coaches were zero, division would fail, but literal rows have positive coach counts.

The main guard runs cleaning then operations generation. Importing this script alone does not run either routine.

## 5. pipeline/02_generate_calibrated_dataset.py - assumptions

Imports os/sys/json/date/timedelta, NumPy and pandas. BASE_DIR is inserted into sys.path with app directory so it can import topology/calendar modules. Paths identify cleaned stations, typologies JSON, line-share JSON, canonical generated CSV and legacy duplicate. NUM_WEEKS=104, start=2025-01-06, weekday network target=3,200,000. The target is an authored scenario benchmark, not a station count measured in the repository.

Assumption tables:
- STATION_TYPOLOGIES hard-codes selected stations; absent names default to RESIDENTIAL_SUBURB.
- Holiday factors include date-specific 2025 values; later dates use category multipliers.
- Monthly factors use one scalar per month.
- LINE_THROUGHPUT_WEIGHT and DEFAULT_LINE_WEIGHT set relative route weights.
- NAMED_HUB_WEIGHT boosts selected stations.
- DAY_TYPE maps weekday number to profile and system multiplier.
- HOUR_SHAPE gives unnormalized hourly weights. Code normalizes by each profile's sum.

These are a simulation recipe, not empirical observations.

## 6. build_line_distribution_model() -> dict

Creates a model with metadata, then loops through topology INTERCHANGES. For each line it gets throughput weight or fallback, reads route length as number of stops in LINES, and calculates weight = line_weight * (1 + 0.01 * route_length). It sums weights; computes each rounded proportion to four decimals; then computes residual = 1.0 - rounded sum and adds it to the first proportions key. This attempts to make the saved shares sum exactly to one. It stores sorted line names, proportions and an explanation; creates parent directory, writes JSON, prints path and returns model.

Complexity is proportional to total line references across interchanges. Empty line lists would make total weight zero and first-key access fail; topology is expected to be nonempty. Explanation percentages use int(p*100), so displayed whole percentages may not sum to 100 even if stored proportions do.

A normalized split is still not an observed passenger transfer split.

## 7. compute_station_weights(df_stations) -> dict

Iterates rows; reads station and primary line. Base weight is the line throughput weight or fallback. If station appears in INTERCHANGES, multiply by 1 + .75*(number of connected lines - 1). Then multiply by optional named-hub weight. Store under station key.

This assumes station appears once in df_stations. Duplicate station rows overwrite the same dict key. The numeric weight is not a passenger count.

## 8. generate_annual_footfall_dataset(seed=42) -> DataFrame

### Setup and calendar loop

Read cleaned stations; compute station weights and total weight. Build station-to-typology map, default residential; write typologies JSON. Create NumPy Generator with default_rng(seed); initialize rows list.

Same seed plus same code, inputs and draw order produces repeatable pseudo-random samples. It does not make the assumed rates realistic.

Nested loops iterate 104 weeks, seven days each, then stations and hourly buckets. For each date, choose day type and calendar context. A weekday with confirmed public holiday uses Sunday hourly shape; otherwise use profile from day type. Sum shape weights. Retrieve month factor. If holiday_type >0, select exact 2025 date factor if available, else category factor, else 1.0. Compute daily system total = 3,200,000 * day multiplier * month factor * holiday factor.

A festival occasion can have holiday_type>0 while is_public_holiday is false; that affects category factor but does not switch off weekday-shaped hours.

### Station and hour loops

For each station:
- Read station, primary line, typology.
- Base station share = station_weight / total_network_weight.
- Confirmed holiday: commercial office share *= .55, shopping/leisure *= 1.45, transit gateway *= 1.25.
- Else, weekend: commercial office *= .70, shopping/leisure *= 1.35.
- Expected station daily = daily system total * adjusted share.
- For each hour, start from hour shape weight. Shopping/leisure hours 16-20 multiply 1.20. Commercial office weekday work hours 8,9,17,18 multiply 1.15 when not an occasion.
- Expected hourly = station daily * adjusted hour weight / original shape_total.
- Draw Poisson(max(expected_hourly,1.0)), cast to int and append (ISO date, hour, station, line, footfall).

### Worked arithmetic (illustrative)

If scenario daily total is 3,200,000, a station base share is .01, a holiday typology factor is 1.25, and hour weight/shape_total is .10, the pre-sampling mean is 3,200,000*.01*1.25*.10=4,000. This is arithmetic illustration, not verified station/hour demand.

### Subtle modeling effects verified from the code

1. Typology share factors are applied after base shares are normalized and are not renormalized. Adjusted station shares may no longer sum to one, so total expected system entries can shift.
2. Hour-specific factors are applied after shape_total was computed from unadjusted weights. Adjusted hourly weights can sum above the daily allocation.
3. max(expected_hourly,1.0) gives every bucket at least a Poisson rate of one.
4. A station row writes its primary Line only. It does not create separate demand rows per interchange line; line splitting happens in separate weighted JSON.
5. Canonical synthetic CSV and legacy duplicate are both written; generated CSV is not required for normal serving.

### Outputs and computational cost

DataFrame columns: Date, Hour, Station, Line, Footfall. Writes canonical and legacy CSVs, returns DataFrame. Expected row count is 104*7*228*19 = 3,153,696, assuming exactly 228 station rows. Time/memory are O(weeks*days*stations*hours). The list and DataFrame coexist, making generation memory-heavy. A local CSV can be roughly 130 MB. Pipeline 03 reads it; app runtime inference does not.

The main guard first builds line split JSON, then generates annual footfall and prints completion. Failure can leave partial outputs updated.

## 9. Data files and consumers

| Path | Role |
|---|---|
| data/raw/DELHI_METRO_DATA.csv | seed station/line/coordinates; pipeline 01 reads |
| data/raw/metro_lines.csv | legacy capacity seed; no direct runtime consumer established |
| data/cleaned/stations_cleaned.csv | station lookup, graph coordinate and interchange input |
| data/cleaned/metro_line_operations.csv | schedule assumptions |
| data/cleaned/station_typologies.json | pipeline 03 and runtime feature map |
| data/synthetic/line_distribution_model.json | pipeline 02 output; runtime profile/scheduler consumes |
| data/synthetic/dmrc_calibrated_footfall.csv | ignored generated training input; pipeline 03 reads, app does not |
| csvFiles/dmrc_footfall_data.csv | ignored legacy generated duplicate, not app inference input |

## 10. Interview questions and exercises

**What does calibrated mean here?** Code scales scenarios to an authored network total and authored shapes/weights. Without station-level observed labels, it does not mean calibrated against station counts.

**Why Poisson?** It produces nonnegative integer draws with a rate-driven mean. Real transit data may be overdispersed and temporally correlated.

**Why can a fixed seed still produce changed rows?** Input order, random draw order, factors and library behavior affect generated outputs.

**What breaks if cleaned station rows duplicate?** Weight dict entries can overwrite; generated rows may duplicate; graph and model indexing may disagree.

**Exercise:** 104*7*228*19=3,153,696 generated station-hour records, assuming the cleaned station input contains 228 rows.

**Exercise:** apply .55 office and 1.45 shopping multipliers to two normalized shares and show why they need not still sum to one. This explains the network-total shift.

**Proposed improvement:** immutable raw inputs, source citations/retrieval dates, unique station/schema validation, post-factor total reporting, and an output manifest with seed and factor version. These recommendations are not implemented.

## Source connections

Pipeline 01 creates station/operations files; pipeline 02 consumes cleaned stations and topology/calendar assumptions; pipeline 03 consumes synthetic CSV/metadata; runtime forecasting consumes typology and saved model metadata; scheduling reads operations/line splits; travel graph reads station coordinates and topology.
