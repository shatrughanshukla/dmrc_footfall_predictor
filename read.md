# Delhi Metro Passenger Demand Forecasting & Train Scheduling Optimization System

A simulation and dashboard prototype covering **243 unique station records** and **11 project-defined corridors**, including operational extensions through 2026. DMRC's published 271 line-station count includes shared interchange stations on more than one line; this project stores each physical station once. It does not currently contain observed DMRC station-by-hour passenger data, verified operational schedules, or verified rolling-stock constraints. See [DATA_AUDIT.md](DATA_AUDIT.md) before interpreting any forecast or recommendation.

Rather than displaying arbitrary passenger counts or naive formulas, this system:
1. **Demonstrates station-wise demand prediction** using a Gradient Boosted Tree model trained on generated synthetic demand. Its reported scores measure agreement with that synthetic generator only, not actual DMRC footfall.
2. **Estimates line-wise passenger demand** across intersecting corridors at interchange hubs (e.g., Yellow vs. Blue Line at Rajiv Chowk).
3. **Simulates frequency and headway recommendations** using configurable project assumptions for capacities, headways, turnaround, and fleet. These values are not verified DMRC standards.
4. **Delivers explainable recommendations**, providing operations controllers with transparent reasoning behind headway adjustments, capacity utilization, and platform crowding risks.
5. **Labels forecasts and line splits as synthetic estimates**, while documenting that the present operational inputs still need source verification.

---

## Architecture & Core Features

### 1. Station-Wise Simulated Demand Forecasting
* Hourly footfall predictions across all 19 operating hours (05:00 to 23:00) with smooth minute interpolation.
* Distinct modeling of weekday bimodal commute peaks (morning rush 08:00–11:00, evening rush 17:00–20:30) vs. weekend leisure curves.
* Uses code-authored demand weights and curves. These values are not verified against station-level observed DMRC ridership; do not use them as actual counts.

### 2. Interchange Line-Wise Demand Breakdown
* For the modeled multi-line interchange hubs, estimates passenger distribution based on corridor passenger throughput, train rake capacity, and network centrality.
* Prominently tagged as `[ESTIMATED LINE DEMAND]` to maintain absolute operational transparency.

### 3. Realistic Train Frequency & Headway Optimization
* Computes required passenger clearance frequency based on train comfort capacity (80% load factor) and through-load factors.
* **Minimum Signaling Separation**: Clamped to CATC/CBTC safety limits ($h_{\min} = 2.0$–$2.5$ min). The system will never recommend unrealistic intervals under this safety limit.
* **Maximum Policy Headway**: Clamped to service policy limits ($h_{\max} = 8.0$–$12.0$ min off-peak) to prevent passengers waiting unrealistic durations.
* **Fleet Constraint**: Limits dispatch frequency to what the line's active rolling stock and round-trip turnaround time physically support.
* **Dispatch Practical Intervals**: Rounds headways to real operational dispatch steps (e.g., 2.3 min, 2.5 min, 2.75 min, 3.0 min, 3.5 min, 5.0 min, etc.).

### 4. Network Topology & Dijkstra Route Graph
* Line-expanded network topology graph with station-and-line nodes and modeled interchanges.
* Dijkstra multi-source shortest path calculation accounting for inter-station track travel and platform transfer penalties.

### 5. Interactive Transit Operations Dashboard
* Station selector with line indicators and interchange badges.
* Date picker defaults to today's date in Delhi, permits today and future dates, and has dynamic weekday/Saturday/Sunday shortcuts. The dashboard reports weekday/workday/holiday status, listed occasion, selected-hour demand band, and that station's predicted daily peak hour.
* Real-time interactive hour slider (05:00 to 23:00) with dynamic live updates via JSON API.
* Dynamic operating-hours demand curve (ML estimate vs. synthetic training-period baseline).
* Interchange demand distribution chart and corridor performance table.
* Real-time KPI cards: Demand, Recommended Headway, Trains/Hour, Capacity Utilization (%), and Average Passenger Wait Time.

---

## Data Provenance & Integrity Standards

| Provenance | Meaning | Assets |
| :--- | :--- | :--- |
| 🟡 **Unverified project inputs** | Hand-authored route and operations tables. | Station topology and `metro_line_operations.csv`; requires external source verification. |
| 🟠 **Model estimate on synthetic data** | ML output learned from the project's generated dataset. | Forecaster; not validated against actual passenger counts. |
| 🔵 **Synthetic simulation** | Generated demand scenarios, separate from observed data. | `dmrc_calibrated_footfall.csv` (728 days × 19 hours × 243 stations = 3,361,176 records). |

---

## Synthetic Holdout Metrics

The active model, metadata, and evaluation report have been regenerated together from the 728-day synthetic dataset (2025-01-06 through 2027-01-03). The 23-feature `HistGradientBoostingRegressor` achieved MAE 26.58 passengers/hour, RMSE 51.10 passengers/hour, and R² 0.9946 on the chronological holdout beginning 2026-10-01 (438,615 rows). This is a holdout against generated scenarios, not real passenger counts, and should not be interpreted as real-world accuracy. Holiday/occasion impacts are assumed scenario effects until measured from observed data. See `DATA_AUDIT.md` and `models/evaluation_metrics.json` for limitations and baseline comparisons.

---

## Project Structure

```
dmrc_footfall_predictor/
├── data/
│   ├── raw/                              # Preserved original source files
│   │   ├── DELHI_METRO_DATA.csv
│   │   └── metro_lines.csv
│   ├── cleaned/                          # Derived; not independently verified
│   │   ├── stations_cleaned.csv          # Station and topology inputs
│   │   └── metro_line_operations.csv     # Project assumptions for operations
│   └── synthetic/                        # Simulated scenarios and estimates
│       ├── dmrc_calibrated_footfall.csv  # 728-day synthetic hourly demand
│       └── line_distribution_model.json  # Interchange line split weights
├── pipeline/
│   ├── 01_audit_and_clean_data.py        # Cleans stations and establishes ops parameters
│   ├── 02_generate_calibrated_dataset.py # Generates calibrated dataset & line split model
│   └── 03_train_and_evaluate_forecaster.py # ML training & chronological evaluation
├── models/
│   ├── footfall_forecaster.joblib        # Serialized trained ML model
│   ├── forecaster_metadata.joblib        # Encoders, historical means, features
│   └── evaluation_metrics.json           # Validation metrics comparison report
├── app/
│   ├── __init__.py                       # Flask application factory
│   ├── routes.py                         # Web routes & REST API endpoints
│   ├── forecasting.py                    # Real-time ML inference & 24h curves
│   ├── scheduling_optimizer.py          # Transit frequency & headway optimizer
│   ├── network_topology.py               # Line sequences & interchange definitions
│   ├── travel_graph.py                   # Dijkstra shortest-time routing graph
│   ├── templates/
│   │   ├── landing.html                  # Product landing page and forecast preview
│   │   ├── index.html                    # Modern interactive dispatcher dashboard
│   │   └── result.html                   # Synchronous report view
│   └── static/
│       ├── css/landing.css               # Responsive landing page and metro motifs
│       ├── css/metro-theme.css            # Shared light/dark design tokens
│       ├── css/dashboard.css             # Transit operations styling
│       ├── js/landing.js                  # Scroll-linked train and reveal behavior
│       ├── js/theme.js                    # Light/dark theme toggle
│       ├── js/dashboard.js               # Dynamic Chart.js and API client
│       └── dmrc_logo.png
├── csvFiles/                             # Synced legacy files for backward compatibility
├── run.py                                # Application entry point
├── requirements.txt                      # Dependencies (Flask, scikit-learn, pandas, etc.)
└── Procfile                              # Gunicorn deployment configuration
```

See `DATA_AUDIT.md` for source discovery, schema/count audit, current data gaps, and use limitations.

---

## Running Locally

1. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run data pipeline** (optional, pre-generated models and cleaned data are included):
   ```bash
   python pipeline/01_audit_and_clean_data.py
   python pipeline/02_generate_calibrated_dataset.py
   python pipeline/03_train_and_evaluate_forecaster.py
   ```

3. **Start the web application**:
   ```bash
   python run.py
   ```

4. **Open the landing page**:
   Navigate to `http://localhost:5000`, then choose **Open forecasting workspace** to use the dashboard at `/dashboard`.

---

## Deployment

The application is fully compatible with **Render**, **Railway**, or containerized production hosting via the included `Procfile`:
```
web: gunicorn run:app
```
