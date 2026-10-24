# Phase 9 | Final Interview Bible & Cheat Sheet

*High-signal revision for the day before an interview.*

> FastAPI Edition | Repository-grounded study material | Snapshot: 2026-10-24

## 5-minute project review
MetroInsights is a FastAPI planning prototype. It accepts a station/date/time; constructs 23 features; predicts hourly demand with HistGradientBoostingRegressor; creates 19 hourly points from 05:00 to 23:00; includes calendar context and a closed-hours gate; estimates service frequency using clearance, headway, fleet and signaling assumptions; and computes topology-based travel times with a line-expanded graph and Dijkstra. It has 243 station records and 11 project-defined route keys. Synthetic data has 3,361,176 rows. Chronological synthetic holdout: 438,615 rows, split at 2026-10-01. HGBR metrics: MAE 26.58, RMSE 51.10, R² 0.9946, MAPE 5.18%. These are not observed-ridership metrics.

## 30-second pitch
“MetroInsights is a FastAPI transit-planning prototype that turns station, date, and time selections into hourly demand scenarios. It uses a 23-feature scikit-learn regressor trained on synthetic data, applies configurable train-capacity and headway assumptions, and estimates network travel times with a line-aware Dijkstra graph. I built the API, data/model pipeline, service-planning logic, and dashboard. The key caveat is that neither the demand labels nor several operating parameters are verified live DMRC data.”

## Architecture in one line
Browser -> FastAPI/Uvicorn -> routes -> forecasting + calendar + operating hours + scheduler + graph -> CSV/JSON/joblib artifacts -> HTML/JSON.

## Files to remember
- `run.py`: ASGI entry point.
- `app/__init__.py`: app/static setup.
- `app/routes.py`: endpoints and orchestration.
- `app/forecasting.py`: artifact load, features, prediction/profile.
- `app/scheduling_optimizer.py`: headway/capacity heuristic.
- `app/travel_graph.py`: mapping, edge construction, Dijkstra.
- `app/network_topology.py`: ordered line stops, aliases, interchanges, weights.
- `app/calendar_context.py`, `app/operating_hours.py`: time context/gating.
- `pipeline/03_train_and_evaluate_forecaster.py`: features, split, baselines, model.

## Mapping concept in 60 seconds
The cleaned station table supplies canonical labels. The topology file supplies ordered station names along each route. Normalization/aliases translate topology labels into canonical station names. The graph creates a distinct node for each station-line pair, adds weighted edges between adjacent stops, and adds transfer edges between line nodes at an interchange. Dijkstra sums nonnegative edge times and finds the minimum route. Results are estimates because coordinates, fixed speed, fallback segment time, and single transfer penalty simplify operations.

## Numbers and caveats
- 243 station rows: project cleaned table; not a verified official unique station count.
- 11 line/branch route keys: project topology grouping.
- 19 modeled hourly points, 05:00-23:00.
- 3,361,176 synthetic training records.
- 438,615 chronological synthetic holdout rows.
- HGBR: MAE 26.58, RMSE 51.10, R² 0.9946, MAPE 5.18% on generated targets.
- Never call R² “accuracy”; never claim actual DMRC passenger-count validation.
- Travel destinations exclude the origin; count varies with graph coverage and selected source.

## 100 rapid-fire questions with compact answers
1. What is it? A station/date/time scenario planning prototype.
2. User? Transit planner/analyst.
3. Live data? No.
4. Backend? FastAPI.
5. Server? Uvicorn.
6. UI? Jinja, JS, CSS.
7. ML library? scikit-learn.
8. Data tools? Pandas and NumPy.
9. Model? HistGradientBoostingRegressor.
10. Feature count? 23.
11. Target? Synthetic hourly passenger demand.
12. Validation? Chronological out-of-time synthetic holdout.
13. Split? 2026-10-01.
14. Holdout rows? 438,615.
15. Total rows? 3,361,176.
16. MAE? 26.58 passengers/hour.
17. RMSE? 51.10 passengers/hour.
18. R²? 0.9946.
19. Is R² accuracy? No.
20. Why synthetic caveat? Labels are generated, not observed.
21. Baselines? Historical means and Ridge.
22. Best baseline MAE? Ridge 53.67.
23. Historical baseline MAE? 60.25.
24. Why chronological split? Simulates later-date prediction.
25. Leakage risk? Future or same-time targets in features.
26. Cyclic feature? Sine/cosine period representation.
27. Why two values? Preserve phase/quadrant.
28. Historical feature source? Training-period aggregates.
29. Does model train on API call? No.
30. Artifact format? Joblib.
31. Joblib trust? Load only trusted artifacts.
32. Route graph package? Custom adjacency graph.
33. Graph algorithm? Dijkstra.
34. Dijkstra allows negative weights? No.
35. Edge weights? Estimated minutes.
36. Node? `(station,line)`.
37. Why expanded? Explicit transfer states/cost.
38. Interchange cost? Project-wide 5-minute assumption.
39. Segment fallback? 2.5 minutes.
40. Coordinate speed? 32 km/h assumption.
41. Haversine? Great-circle distance formula.
42. Route times official? No, estimates.
43. Normalization purpose? Match variants of station labels.
44. Alias purpose? Resolve known unmatched labels.
45. Unmatched station behavior? Edge can be skipped.
46. Improvement? Mapping audit and stable IDs.
47. Why multi-source start? Begin on any source station line-state.
48. Output includes origin? No.
49. Complexity? O((V+E) log V).
50. Why adjacency list? Efficient sparse graph traversal.
51. API predict methods? GET query and POST JSON.
52. Invalid date response? 400.
53. Unknown station? Validation needs improvement.
54. Pydantic body? Not currently used for predict contract.
55. OpenAPI docs? `/api/docs`.
56. HTML engine? Jinja2.
57. Static assets? Starlette StaticFiles.
58. Async means faster ML? No.
59. Threadpool purpose? Keep sync work off event loop.
60. GIL? Can limit Python CPU threading.
61. Closed hours? Return zero/closed status.
62. Profile slots? 19.
63. Minute estimate? Linear interpolation.
64. Is interpolation trained? No.
65. Peak badge source? Demand quantiles/profile.
66. Capacity utilization? Demand/clearance capacity.
67. Occupancy? Not measured.
68. Clearance? Space available for boarders after through-load assumption.
69. Headway? Minutes between trains.
70. Trains/hour relation? 60 divided by headway.
71. Fleet constraint? Fleet size and turnaround.
72. Signaling constraint? Minimum safe headway assumption.
73. Through-load? Assumed already-onboard share.
74. Interchange demand? Configured synthetic split.
75. Real train count? No.
76. DB? None currently.
77. Static inputs? CSV/JSON.
78. Why no DB? Read-only prototype inputs.
79. When DB? Observations/concurrency/mutations.
80. Startup loading? Eager module imports.
81. Startup risk? Missing artifacts abort import.
82. Worker memory? Each worker loads own copies.
83. First optimization? Profile then batch 19 predictions.
84. Caching target? Static graph/source routes.
85. Retraining at startup? No.
86. Queue present? No.
87. Authentication? No.
88. Rate limiting? Not in app code.
89. Privacy data? Currently synthetic.
90. Main model risk? Synthetic-to-real domain gap.
91. Main routing risk? Incomplete/incorrect mapping.
92. Main scheduler risk? Unverified assumptions.
93. Testing priority? Unit/contract/smoke tests.
94. Health endpoints? Add readiness/liveness.
95. Monitoring? Add latency/error/model version.
96. Next data step? Obtain quality observed counts.
97. Next model step? Time-based real validation/calibration.
98. Next API step? Typed request schema/validation.
99. Next topology step? Verified stable IDs/GTFS.
100. Final honesty point? Prototype, estimates, synthetic evidence.

## 50 difficult questions with concise answers
1. Why is holdout high? Generated patterns may be smooth and learnable.
2. How prove external validity? Independent observed time split and error analysis.
3. Why HGBR vs XGBoost? Existing sklearn stack; compare options empirically.
4. Why not normalize? Trees generally don't require scaling.
5. Are integer categories ordinal? They can imply order; compare categorical/one-hot.
6. Why use MAPE? Intuitive relative error; zero labels excluded, so caveat.
7. Why is R² not accuracy? It is explained variance metric for regression.
8. Could chronological split still leak? Yes, feature availability and generated rule leakage need audit.
9. Why is historical baseline weak? Depends on synthetic history and sparse station-hour patterns.
10. What if a category is unseen? Mapping/default behavior must be explicit.
11. What is concept drift? Relationship between features and target changes over time.
12. How monitor drift? Input/target distribution and delayed error metrics.
13. What if holiday calendar wrong? Context features distort scenarios; version calendar.
14. What if training and serving schema diverge? Contract tests/metadata versioning.
15. Why feature order? Estimator expects trained column schema.
16. What does batch inference improve? Fewer DataFrame/model calls and overhead.
17. Why not async predict? sklearn is synchronous CPU work.
18. Why threadpool not process? Simple nonblocking integration; process costs higher.
19. When separate service? Independent model scaling/resource isolation is needed.
20. What if worker OOM? Reduce workers/cache, quantify model copy, scale memory.
21. How deploy artifact safely? Version/hash, trusted build, compatibility manifest.
22. Is joblib safe from untrusted file? No, pickle-based loading is unsafe.
23. Why Dijkstra not BFS? Weighted edges are not equal.
24. Why not Bellman-Ford? No negative edges; heap Dijkstra is simpler/faster.
25. Why line states? Transfer is a distinct action with cost.
26. Is starting transfer free? Multi-source origins imply yes at source; document assumption.
27. Could Dijkstra support time-dependent edges? Not standard static costs; use time-dependent routing methods.
28. Why bidirectional edges? Simplifies prototype; actual directed operation may differ.
29. How detect mapping issues? Compare topology set to canonical map and assert coverage.
30. What causes silent reachability loss? Failed name mapping or omitted route segment.
31. Why Haversine imperfect? Track geometry differs from straight line.
32. Why max segment threshold? Catch obvious bad coordinate distances.
33. Could threshold hide real long segments? Inspect official distances and thresholds.
34. Why fallback duration? Keep edges traversable without reliable coordinates.
35. Why constant transfer penalty weak? Stations differ in walking/vertical transfer time.
36. What is clearance utilization? Demand relative to residual boarding offer per hour.
37. Why peak still comfortable? Forecast low or modeled capacity high.
38. Are capacity values official? Treat as project assumptions pending verification.
39. Does schedule optimize fleet globally? No, heuristic per line/station/hour.
40. Is wait estimate realistic? Headway/2 assumes random passenger arrivals and regular service.
41. What is largest business risk? Misrepresenting estimates as operational truth.
42. What protects input boundary? Basic parsing; typed/range/station validation needed.
43. What about request flooding? Edge rate limits and concurrency controls.
44. How avoid exposing internals? Stable error messages; sanitized logs.
45. Why no DB transaction? No mutable relational workflow today.
46. How add real data? Provenance schema, validation, aggregation, privacy controls.
47. How handle missing observations? Distinguish missing from zero; impute or flag.
48. How test closed hours? Parameterized boundary tests around 05:00/23:30.
49. How test graph? Tiny hand-computable graph plus integration station coverage.
50. What would you not claim? Real-world accuracy, live occupancy, official timetable recommendation.

## Final 1-page checklist
[ ] Say prototype and synthetic data before metrics. [ ] Name 243 station records, not official total. [ ] Explain API flow. [ ] Explain features/model and chronological split. [ ] Explain mapping and line-expanded graph. [ ] Explain Dijkstra nonnegative weights. [ ] Distinguish capacity clearance from occupancy. [ ] State no live count/auth/database. [ ] Acknowledge runtime smoke verification status. [ ] Propose real data, tests, provenance and calibration.
## How to use this series
Read Phase 1 first, then Phase 2 while opening the source files. Use Phases 3, 5, 6, and 7 to deepen technical understanding; rehearse with Phases 4 and 8; revise with Phase 9. The editable Markdown beside each PDF is the source of truth for corrections.

## Evidence and honesty rules
MetroInsights is a planning prototype. Its demand targets and holdout are synthetic. Model metrics describe agreement with generated scenario labels, not real passenger counts or operational DMRC accuracy. Network topology, coordinates, capacities, headways, service frequency, and interchange splits are project data or configurable assumptions unless separately verified. Say “estimated” and explain the assumptions. Do not describe this as a live passenger-count, train occupancy, or production DMRC system.

## Verified snapshot used in this edition
The cleaned station table contains 243 station records. The topology graph's destination count depends on the selected source and excludes the source itself; 242 destinations can be returned when all other modeled stations are connected. Do not say 226 or 228 without checking the current data. The project defines 11 route keys, including branch keys. The synthetic training series uses 243 stations x 728 dates x 19 hourly slots (05:00-23:00), or 3,361,176 rows. A chronological holdout begins 2026-10-01 and has 438,615 rows. The recorded HistGradientBoostingRegressor scores are MAE 26.58, RMSE 51.10, R2 0.9946, and MAPE 5.18%; Ridge MAE is 53.67 and historical station/day/hour mean MAE is 60.25. These are synthetic-only evaluation results.

## Current stack and constraints
FastAPI + Uvicorn, Starlette/Jinja2, server-rendered HTML with JavaScript/CSS, Pandas, NumPy, scikit-learn, joblib, CSV/JSON, and a custom adjacency graph with heapq Dijkstra. No relational database, live ridership feed, authentication, or distributed job queue is present. The generated multi-million-row CSV is a training input; runtime inference loads compact serialized model/metadata plus station and operations inputs, rather than reading every training row on each request. Runtime startup imports routes and eagerly loads artifacts/builds the graph, so missing files can prevent startup. The current FastAPI migration has passed static compilation and diff checks in prior work, but an actual runtime smoke test was not possible in the offline environment; verify locally before claiming deployment verification.

