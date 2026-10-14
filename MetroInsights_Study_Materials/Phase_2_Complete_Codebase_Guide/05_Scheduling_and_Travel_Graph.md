# Scheduling and Travel Graph

**Revision:** `4405d167fc323f33be76e2c7f6614fd21cc574a8` (`main`). This volume teaches a deterministic service scenario and a topology-weighted shortest-path estimate. The code does not dispatch real trains or receive live passenger counts.

## 1. Where these pieces fit

`app/scheduling_optimizer.py` loads two inputs when Python imports the module: the operations CSV (`data/cleaned/metro_line_operations.csv`) and, if it exists, the estimated interchange share JSON (`data/synthetic/line_distribution_model.json`). `routes.api_predict` sends forecast demand and selected date/hour facts to `optimize_station_schedule`. The optimizer returns line-level dictionaries for the JSON response. The operations rows are configurable project assumptions; their labels and comments do not establish that values are official or verified.

`app/network_topology.py` provides ordered station sequences and transfer definitions. `app/travel_graph.py` maps the topology names to canonical names in the station CSV, creates one graph node per `(station, line)`, connects consecutive stations, and adds weighted transfer edges. `routes.py` builds the graph at import and queries it for a selected origin. Both are estimates: edges use coordinate-derived straight-line distance divided by a fixed average speed, or a fixed fallback, rather than actual timetable and track geometry.

## 2. Scheduling: understand the units first

The optimizer compares **passenger demand per hour at the selected station** with a modeled **boarding clearance budget per arriving train**. It is not measuring all passengers already onboard, and its utilization denominator is not nominal train capacity multiplied by trains per hour. For a line, the core relationship is:

`clearance budget per train = comfort capacity * (1 - assumed through-load fraction)`

`clearance offered per hour = trains per hour * clearance budget per train`

`utilization = station line demand / clearance offered per hour * 100`

The through-load fractions (65% at peak, 40% off-peak) are hard-coded scenario assumptions. Thus the output should be described as a model-based station boarding capacity scenario, not actual occupancy. It does not simulate alighting, onboard loads between stations, passenger queues, train-by-train movement, or a live dispatch control system.

## 3. `is_peak_hour`

Signature: `is_peak_hour(hour: int, day_of_week: int, is_workday=None) -> bool` (`app/scheduling_optimizer.py:38-49`). `day_of_week` follows Python's weekday convention: Monday 0 through Sunday 6. If `is_workday` is explicitly supplied it overrides that weekday inference. A false workday immediately returns `False`; otherwise hours 8, 9, 10 and 17, 18, 19, 20 return true. The code uses whole integer hours, so 20:59 is represented as hour 20 and is peak; it does not model the half-hour cutoff in its docstring.

Example: `is_peak_hour(9, 2, True)` is true; `is_peak_hour(9, 2, False)` is false. The second result demonstrates the override. Invalid types are not validated; comparisons may raise `TypeError`.

**Interview:** Why accept both weekday and `is_workday`? The optional override lets the caller use the project's calendar/holiday classification rather than assuming every weekday is a workday. What is the limitation? The peak windows are coarse hour bins and do not encode exact minutes.

## 4. Line split helper and headway rounding

`get_interchange_line_split(station: str, all_lines: list) -> dict` (`52-64`) returns saved proportions when the station is a key in the loaded interchange model. Otherwise it evenly divides 1 by the count and rounds that share to four decimal places. Empty `all_lines` returns `{}`. It does not normalize a supplied JSON split or validate that its keys match `all_lines` or sum to one. This function affects how one station total becomes per-line modeled demand.

`round_to_practical_headway(headway_min, min_headway, max_headway) -> float` (`67-78`) first clamps a proposed headway into the physical/policy interval. It filters the `STANDARD_HEADWAYS` list to values inside those bounds and selects the valid value with smallest absolute distance from the clamped target. If no standard interval fits, it returns the clamped value rounded to two decimals. A tie resolves to the first item in list order because Python's `min` keeps the first equal key. The bounds are not independently validated; if minimum exceeds maximum, `max(min, min(target, max))` resolves to minimum.

Example: target 4.2 min, allowed 2.1-8.0 min. Valid choices include 4.0 and 4.5. Distances are 0.2 and 0.3, so result is 4.0. Smaller headway means more frequent trains: `60 / 4.0 = 15.0 trains/hour`.

## 5. `optimize_line_schedule` worked trace

Signature (`81-82`): `optimize_line_schedule(line, station_name, hour, day_of_week, line_demand, is_workday=None) -> dict`. The route passes an integer line-demand estimate and date context. A normal return is a dictionary consumed by the station optimizer and ultimately rendered to JSON/UI. The exact complete implementation is reproduced in Appendix A.

### Step-by-step calculation (illustrative, using the tracked Yellow Line assumptions)

Assume weekday 09:00, demand 1,000 riders/hour, and the Yellow Line CSV row: comfort capacity 1,920; nominal capacity 2,400; minimum signaling headway 2.1 minutes; maximum policy headway 8 minutes; peak baseline headway 2.3 minutes; fleet 64; turnaround 150 minutes.

1. Fleet limit: `floor(64 * 60 / 150) = floor(25.6) = 25 trains/hour`.
2. Signaling limit: `floor(60 / 2.1) = 28 trains/hour`; absolute maximum is `min(25, 28) = 25`.
3. Policy minimum frequency: `ceil(60 / 8) = 8 trains/hour`.
4. Peak baseline: 2.3 min, so existing frequency is `round(60 / 2.3, 1) = 26.1 trains/hour`.
5. Peak through-load is assumed 0.65. Clearance per train is `int(1,920 * (1 - .65)) = 672` riders.
6. Existing offered boarding clearance is `int(26.1 * 672) = 17,539` riders/hour. Demand 1,000 does not exceed this. Since 1,000 is not less than 45% of 17,539? 45% is about 7,893, yes it is less, but 09:00 is not in the energy-saving-hour allowlist, so it maintains baseline.
7. Frequency is then clamped to the fleet max 25, making raw headway `60/25 = 2.4`. The nearest allowed standard headway is 2.3 (distance .1) rather than 2.5 (.1 tie? Both are .1; list order selects 2.3), so recommendation becomes 2.3 and 26.1 trains/hour. **This reveals a constraint mismatch:** frequency is clamped before conversion to headway, then practical rounding can raise frequency above the clamp. For this data, the recommendation reports 26.1 while the calculated fleet maximum is 25. Treat this as a potential bug/risk, not a guarantee of feasible fleet use.
8. The returned utilization is demand divided by final clearance: `1000 / int(26.1*672) * 100`, about 5.7%. `trains_deployed_rec = min(64, ceil(150/2.3)) = 64`; the capped fleet count conceals that the unbounded cycle/headway requirement is 66 sets.

The arithmetic demonstrates why returned fields should be interpreted carefully: headway rounding and `trains_deployed_rec` currently do not guarantee that all reported values satisfy every configured constraint. The CSV and code do not prove the assumed capacities/fleet/headways are official.

### Control flow, edge cases, and risks

- An unknown line tries a case-insensitive substring match; if none match, it silently falls back to the first CSV index row. Empty CSV index would fail at `_OPS_DF.index[0]`.
- Demand-driven frequency is `line_demand / clearance_budget_per_train`. The `max(..., 250)` clearance floor prevents division by zero but means low-capacity assumptions could be masked.
- Action thresholds compare demand with current modeled clearance, and decrease service only at selected off-peak hours. `status_action` is chosen before frequency constraints, so action may say increase when the constrained recommendation cannot meet demand.
- Negative demand is not rejected. It can lower target frequency, while utilization becomes negative; this produces nonsensical output rather than an input error.
- Zero or invalid turnaround/headway values in CSV can cause division by zero or nonsensical bounds. Startup CSV loading only confirms parsing, not semantic validity.
- The function uses `nominal_cap` for total line capacity, but uses comfort capacity minus through-load for boarding clearance. These answer different questions.
- At 105% and 88% comparisons, strict `>` means exactly 105% is HIGH, exactly 88% is MODERATE, and exactly 65% is LOW.
- Wait time uses the textbook random-arrival approximation `headway / 2`; it assumes arrivals are uniform and ignores bunching and passenger schedules.

Time complexity is constant per line call apart from the small fixed headway list scan. Memory use is constant for the returned summary, excluding module-level pandas/JSON data.

## 6. `optimize_station_schedule`

Signature (`252-254`): `optimize_station_schedule(station, primary_line, all_lines, hour, day_of_week, total_footfall, is_workday=None, service_open=True) -> dict`.

If more than one line is listed, it calls the split helper. Otherwise it maps the full demand to `primary_line`. It loops over `all_lines`, rounds each share times station total, and calls the line optimizer. When `service_open` is false, it overwrites operating metrics with zero/`None`, sets `SERVICE_CLOSED`, and explains no trains operate. The final primary recommendation is actually the line with largest `line_demand`, not necessarily the supplied `primary_line`.

Risks: empty `all_lines` yields an empty recommendations list, then `max(...)` raises `ValueError`. Missing share keys use an equal split fallback, but the JSON split may sum to something other than 1, so rounded line demands need not add to station total. When closed, each line optimizer is first called with zero demand, then the resulting metrics are overwritten, doing unnecessary work. `total_station_footfall` is set to zero on closure. No board/alight or onboard state is modeled.

## 7. Network topology as data

`app/network_topology.py` is declarative data, not executable routing logic. Each `LINES[line]` list is an ordered sequence. The graph builder connects each adjacent pair and does not connect every possible pair on a line. `INTERCHANGES` lists station names and corresponding line keys; it is the explicit source for transfer edges. `INTERCHANGE_PENALTY_MIN = 5.0` applies to every listed transfer, regardless of the comment noting stations vary. `DEFAULT_SEGMENT_MIN = 2.5` is used when endpoint coordinates are absent/repeated or considered implausible.

`ALIASES` maps a normalized topology label to a canonical CSV spelling. Matching omissions mean stations/edges can disappear without a hard error. `INTERCHANGES` must agree with line membership and names; otherwise a graph node can represent a transfer line that has no adjacent track edge. The module docstring's source claims are not independently verified by the repository audit.

## 8. Graph construction details

`_normalize` removes a fixed set of footnote glyphs, strips/lowercases, normalizes dash variants, and removes commas/periods. It replaces only one occurrence of two consecutive spaces with one, rather than fully collapsing arbitrary whitespace. `_load_stations` reads CSV via `DictReader`, trims station and coordinate fields, converts non-empty coordinates to float, and indexes by normalized name; duplicate normalized names overwrite earlier rows.

`_is_placeholder_coord` returns true when a coordinate pair repeats for more than two station rows, or either coordinate is `None`. `_haversine_km` computes great-circle surface distance on a sphere with radius 6,371 km. The formula returns straight-line surface distance, not rail track length.

`_match_topology_to_canonical` builds a set of topology station names, tries normalized exact match, then the alias dictionary. Set iteration order is not guaranteed, but mapping results are key based so the final lookup is stable unless duplicate normalized names exist.

`build_graph(csv_path)` makes an adjacency dictionary. For each line, `zip(stops, stops[1:])` creates consecutive pairs. Missing name matches skip the edge. Valid coordinates yield `max((distance / 32 km/h) * 60, 1 minute)`; results above 8 minutes fall back to 2.5. Invalid/repeated coordinates also use 2.5. Every track edge is inserted in both directions, so the graph treats travel as symmetric. For each interchange, every pair among listed lines gets an edge weighted 5 minutes, also symmetric. The node tuple `(canonical_station, line)` preserves line identity; transfer cost is paid only when switching between such nodes.

Potential risks: coordinates are point-to-point rather than track distance; average speed is fixed; max-edge fallback can hide bad inputs; fallback values can distort routes; line/transfer names can mismatch; all transfers have one cost; `MAX_SEGMENT_MIN` and source geographic quality determine routing quality. Construction is linear in total listed station occurrences plus the small pairwise line count at each interchange; graph space is O(V+E), where V is station-line nodes and E is adjacency entries.

## 9. Dijkstra: `shortest_times_from`

Signature (`139-167`): `shortest_times_from(graph, station_name) -> dict[str, float]`. The start is multi-source: every graph node whose station matches starts at distance zero. This means a selected interchange starts on each of its lines with no transfer penalty, suitable for station-level travel-time estimates that begin at the station. A route that changes lines later pays the transfer edge weight.

The min-heap stores `(distance, node)`. Each loop pops the currently least-cost candidate; a `visited` set prevents repeated expansion. For each neighbor, candidate distance is `d + w`; if it improves the best-known distance, the code updates `dist` and pushes a fresh heap entry. Stale heap entries are naturally skipped after the node has been finalized. Finally, it collapses line-specific nodes to the minimum time per station and removes the origin.

### Hand-worked graph

Illustrative graph: start A on line X. A-X to B-X costs 3 minutes; B-X to C-X costs 4; B-X transfer to B-Y costs 5; B-Y to D-Y costs 2. Starting at A, heap progression is A(0) -> B-X(3) -> B-Y(8) and C-X(7) -> D-Y(10). Therefore shortest times: B=3, C=7, D=10. Going to D pays the 5-minute transfer. Dijkstra requires nonnegative weights; the builder creates positive weights. If the requested station is absent, `start_nodes` is empty, so the result is `{}` without an explicit not-found error.

Complexity is `O((V + E) log V)` using a binary heap and adjacency lists; each successful relaxation pushes at most an edge-scale number of heap entries, conventionally summarized as O(E log V). Space is O(V+E) including adjacency, distance, heap, and visited structures.

## 10. Interview questions and exercises

1. **Why use `(station, line)` nodes?** So the graph can distinguish being at one physical station on two line platforms and charge a transfer cost when moving between line identities.
2. **What makes Dijkstra valid here?** Edge weights are nonnegative travel minutes. A negative transfer/travel edge would invalidate the greedy finalization rule.
3. **Is `capacity_utilization_pct` onboard train occupancy?** No. It compares a station/hour demand estimate against modeled per-hour boarding clearance derived from comfort capacity and assumed through-load.
4. **Does the scheduler dispatch trains?** No. It returns a rule-based scenario recommendation; there is no train state, control system, or real-time data connection.
5. **How would you test headway constraints?** Unit tests for bounded inputs, exact standard intervals, tie behavior, no valid standard entries, and invariants after rounding (`min <= h <= max`, `60/h <= fleet/signal limit`). The last invariant currently exposes the rounding issue.

**Exercise:** For Rajiv Chowk, use the JSON split, a total of 10,000 modeled riders/hour, and `all_lines=["Blue Line", "Yellow Line"]`. Calculate the rounded demand sent to each line. Then describe how the algorithm chooses `primary_recommendation`.

**Solution:** Blue: `round(10000 * .5154) = 5154`; Yellow: `round(10000 * .4846) = 4846`; they sum to 10,000. It runs a line recommendation for each and selects the dictionary with greatest `line_demand`, so Blue Line is primary in this example. This selection is code behavior, not a statement about operational importance.

## 11. File connections and verification

- Caller: `app/routes.py` calls station optimization and shortest-time routing when assembling a prediction response.
- Upstream demand: runtime forecasting returns total station demand; line split config distributes it across lines.
- Upstream network: cleaned station CSV supplies coordinates/names; topology supplies adjacency and interchanges.
- Downstream: route JSON goes to `dashboard.js`; the schedule is displayed as a scenario, and travel times are shown in the destination table.
- Proposed improvements: validate CSV bounds on load; preserve constraints after rounding; distinguish boarding flow from onboard occupancy in labels; add uncertainty ranges; source and version operations assumptions; test disconnected/unknown stations; base travel time on published segment schedules/track paths and station-specific transfers.

## Appendix source blocks

The following appendix reproduces complete source files with original line numbers. It is intentionally consecutive: consult it alongside the explanations above to verify exact executable behavior.
