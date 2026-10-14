"""
DMRC Passenger Footfall Prediction & Train Scheduling Optimization Web Application.

Routes:
- /                   : Interactive transit management dashboard
- /get_footfall       : Synchronous result view (backward-compatible)
- /api/predict        : JSON endpoint for real-time forecasting & scheduling optimization
- /api/stations       : Station directory with line and interchange metadata
- /api/model_metrics  : Model validation metrics vs historical baselines
"""
import os
import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from flask import render_template, request, jsonify
import pandas as pd

from app import app
from app.travel_graph import build_graph, shortest_times_from
from app.forecasting import (
    get_station_info,
    predict_hourly_footfall,
    predict_footfall_with_minute_interpolation,
    predict_station_full_day_profile,
    get_model_evaluation_summary
)
from app.scheduling_optimizer import optimize_station_schedule
from app.calendar_context import get_calendar_context
from app.operating_hours import is_service_operating

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIONS_CLEANED_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'stations_cleaned.csv')
if not os.path.exists(STATIONS_CLEANED_PATH):
    STATIONS_CLEANED_PATH = os.path.join(BASE_DIR, 'csvFiles', 'DELHI_METRO_DATA.csv')

# Load cleaned stations metadata
stations_df = pd.read_csv(STATIONS_CLEANED_PATH)
stations_df['Station'] = stations_df['Station'].astype(str).str.rstrip('†‡*#¤').str.strip()
ALL_STATIONS = sorted(stations_df['Station'].unique().tolist())

# Build line-topology graph once at startup
travel_graph = build_graph(STATIONS_CLEANED_PATH)

# Network-wide apex benchmarks
BUSIEST_STATION = "Botanical Garden"
PEAK_HOUR = "09:00"


def _parse_datetime(date_str, time_str):
    """
    Safely parses date and time inputs into datetime object, hour, and minute.
    """
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    if not date_str:
        dt_date = today
    else:
        try:
            dt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Choose a valid date in YYYY-MM-DD format.")

    if not time_str:
        hour, minute = 9, 0
    else:
        try:
            parsed_time = datetime.strptime(time_str, "%H:%M").time()
            hour, minute = parsed_time.hour, parsed_time.minute
        except ValueError:
            raise ValueError("Choose a valid time in HH:MM format.")

    dt_obj = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute)
    return dt_obj, hour, minute


def _hour_band(profile, hour, minute=0):
    """Classify an hour relative to this station/date's predicted profile."""
    if not is_service_operating(hour, minute):
        return "Metro closed"
    values = sorted(profile)
    if not values:
        return "Unavailable"
    low = values[int((len(values) - 1) * 0.25)]
    high = values[int((len(values) - 1) * 0.75)]
    value = profile[hour - 5]
    if value >= high:
        return "Peak demand"
    if value <= low:
        return "Lower demand"
    return "Typical demand"


@app.route('/')
def landing():
    """Product landing page with a live, clearly labeled scenario preview."""
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    hero_station = 'Rajiv Chowk'
    hero_profile = predict_station_full_day_profile(
        hero_station,
        datetime(today.year, today.month, today.day, 9, 0)
    )
    return render_template(
        'landing.html',
        default_date=today.isoformat(),
        default_date_label=today.strftime('%A, %d %B %Y'),
        hero_station=hero_station,
        hero_profile=hero_profile,
        eval_metrics=get_model_evaluation_summary(),
    )


@app.route('/dashboard')
def index():
    # Build stations metadata dict for client-side search and line filtering
    stations_meta = {}
    for _, row in stations_df.iterrows():
        st = row['Station']
        all_lines = [l.strip() for l in str(row.get('All_Lines', row['Line'])).split(',')]
        stations_meta[st] = {
            "line": row['Line'],
            "all_lines": all_lines,
            "is_interchange": bool(row.get('Is_Interchange', len(all_lines) > 1)),
            "latitude": float(row['Latitude']) if pd.notna(row['Latitude']) else None,
            "longitude": float(row['Longitude']) if pd.notna(row['Longitude']) else None,
        }

    eval_metrics = get_model_evaluation_summary()

    return render_template(
        'index.html',
        stations=ALL_STATIONS,
        stations_meta=stations_meta,
        busiest_station=BUSIEST_STATION,
        peak_hour=PEAK_HOUR,
        eval_metrics=eval_metrics,
        default_date=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(),
        today_date=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(),
        default_time="09:00",
        default_station="Rajiv Chowk"
    )


@app.route('/get_footfall', methods=['POST'])
def get_footfall():
    station = request.form.get('station', 'Rajiv Chowk').strip().rstrip('†‡*#¤').strip()
    day_str = request.form.get('day', 'Monday')
    time_str = request.form.get('time', '09:00')
    date_str = request.form.get('date', '')
    selected_line = request.form.get('line', '')

    try:
        dt_obj, hour, minute = _parse_datetime(date_str, time_str)
    except ValueError as exc:
        return str(exc), 400
    day_name = dt_obj.strftime('%A')
    formatted_time = f"{hour:02d}:{minute:02d}"
    service_open = is_service_operating(hour, minute)
    calendar_context = get_calendar_context(dt_obj.date())
    calendar_context['service_open'] = service_open

    st_info = get_station_info(station)

    # 1. Machine learning footfall forecast
    time_footfall = predict_footfall_with_minute_interpolation(station, dt_obj, hour, minute) if service_open else 0
    hourly_footfall = predict_hourly_footfall(station, dt_obj, hour) if service_open else 0
    profile_24h = predict_station_full_day_profile(station, dt_obj)
    total_footfall = profile_24h['daily_total']

    # 2. Scheduling optimization
    schedule_res = optimize_station_schedule(
        station=station,
        primary_line=st_info['line'],
        all_lines=st_info['all_lines'],
        hour=hour,
        day_of_week=dt_obj.weekday(),
        total_footfall=hourly_footfall,
        is_workday=calendar_context['is_workday'],
        service_open=service_open
    )

    # If user selected a specific line, prioritize its recommendation for the headline cards
    primary_rec = schedule_res['primary_recommendation']
    if selected_line:
        for rec in schedule_res['line_recommendations']:
            if rec['line'].lower() == selected_line.lower():
                primary_rec = rec
                break

    # 3. Network travel times from topology to ALL stations
    try:
        times = shortest_times_from(travel_graph, station)
        station_line_map = dict(zip(stations_df['Station'], stations_df['Line']))
        travel_info = [
            {
                'End Station': dest,
                'Travel Time (minutes)': round(mins, 1),
                'Line': station_line_map.get(dest, 'Metro Network')
            }
            for dest, mins in sorted(times.items(), key=lambda kv: kv[1])
        ]
    except Exception:
        travel_info = []

    return render_template(
        'result.html',
        station=station,
        station_info=st_info,
        day=day_name,
        calendar_context=calendar_context,
        selected_hour_band=_hour_band(profile_24h['predicted'], hour, minute),
        date=dt_obj.strftime('%Y-%m-%d'),
        time=formatted_time,
        total_footfall=total_footfall,
        time_footfall=time_footfall,
        hourly_footfall=hourly_footfall,
        num_trains_needed=round(primary_rec['recommended_trains_per_hour'], 1),
        interval=primary_rec['recommended_headway_min'],
        existing_interval=primary_rec['existing_headway_min'],
        existing_trains=round(primary_rec['existing_trains_per_hour'], 1),
        capacity_utilization=primary_rec['capacity_utilization_pct'],
        crowding_badge=primary_rec['crowding_badge'],
        crowding_color=primary_rec['crowding_color'],
        avg_wait_time=primary_rec['avg_wait_time_rec_min'],
        service_open=service_open,
        explanation=primary_rec['explanation'],
        schedule_res=schedule_res,
        profile_24h=profile_24h,
        busiest_station=BUSIEST_STATION,
        peak_hour=PEAK_HOUR,
        travel_info=travel_info,
        eval_metrics=get_model_evaluation_summary()
    )


@app.route('/api/predict', methods=['GET', 'POST'])
def api_predict():
    """
    JSON API for dynamic frontend interaction without full page reloads.
    """
    data = request.get_json(silent=True) or request.args
    station = data.get('station', 'Rajiv Chowk').strip().rstrip('†‡*#¤').strip()
    date_str = data.get('date', '')
    time_str = data.get('time', '09:00')
    line_filter = data.get('line', '')

    try:
        dt_obj, hour, minute = _parse_datetime(date_str, time_str)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    calendar_context = get_calendar_context(dt_obj.date())
    service_open = is_service_operating(hour, minute)
    calendar_context['service_open'] = service_open
    st_info = get_station_info(station)

    # 1. Predictions
    time_footfall = predict_footfall_with_minute_interpolation(station, dt_obj, hour, minute) if service_open else 0
    hourly_footfall = predict_hourly_footfall(station, dt_obj, hour) if service_open else 0
    profile_24h = predict_station_full_day_profile(station, dt_obj)

    # 2. Scheduling Optimization
    schedule_res = optimize_station_schedule(
        station=station,
        primary_line=st_info['line'],
        all_lines=st_info['all_lines'],
        hour=hour,
        day_of_week=dt_obj.weekday(),
        total_footfall=hourly_footfall,
        is_workday=calendar_context['is_workday'],
        service_open=service_open
    )

    # Filter if requested
    filtered_rec = schedule_res['primary_recommendation']
    station_summary = not line_filter and schedule_res['is_interchange']
    if line_filter:
        for r in schedule_res['line_recommendations']:
            if r['line'].lower() == line_filter.lower():
                filtered_rec = r
                break
    elif station_summary:
        # The demand chart/KPI describe the whole interchange. Aggregate service
        # across every corridor too, so the headline never compares station-wide
        # passengers with just one line's trains or capacity.
        recommendations = schedule_res['line_recommendations']
        total_demand = schedule_res['total_station_footfall']
        recommended_capacity = sum(r['recommended_clearance_capacity'] for r in recommendations)
        existing_capacity = sum(r['existing_clearance_capacity'] for r in recommendations)
        utilization = round(total_demand / recommended_capacity * 100, 1) if recommended_capacity else 0.0
        if utilization > 105.0:
            risk, badge, color = 'CRITICAL_OVERCROWDING', 'Severe Crowd Alert', '#dc3545'
        elif utilization > 88.0:
            risk, badge, color = 'HIGH_CROWDING', 'High Demand', '#fd7e14'
        elif utilization > 65.0:
            risk, badge, color = 'MODERATE', 'Optimal Load', '#28a745'
        else:
            risk, badge, color = 'LOW', 'Comfortable Capacity', '#17a2b8'
        total_trains = lambda key: round(sum(r[key] for r in recommendations), 1)
        total_fleet = sum(r['fleet_size_available'] for r in recommendations)
        demand_weight = max(total_demand, 1)
        filtered_rec = {
            **schedule_res['primary_recommendation'],
            'line': 'All lines',
            'line_demand': total_demand,
            'is_station_summary': True,
            'line_count': len(recommendations),
            'recommended_headway_min': None,
            'existing_headway_min': None,
            'recommended_trains_per_hour': total_trains('recommended_trains_per_hour'),
            'existing_trains_per_hour': total_trains('existing_trains_per_hour'),
            'recommended_clearance_capacity': recommended_capacity,
            'existing_clearance_capacity': existing_capacity,
            'capacity_utilization_pct': utilization,
            'crowding_risk': risk,
            'crowding_badge': badge,
            'crowding_color': color,
            'avg_wait_time_rec_min': round(sum(r['avg_wait_time_rec_min'] * r['line_demand'] for r in recommendations) / demand_weight, 1),
            'trains_deployed_rec': sum(r['trains_deployed_rec'] for r in recommendations),
            'fleet_size_available': total_fleet,
            'explanation': (
                f"Combined estimate across {len(recommendations)} lines: {total_demand:,} passengers/hr. "
                f"The recommended schedules provide an estimated comfortable boarding capacity of "
                f"{recommended_capacity:,} passengers/hr ({utilization}% utilization). "
                "This is a model estimate based on configurable train-capacity assumptions, not a live passenger count."
            )
        }

    if not service_open:
        filtered_rec = {
            **filtered_rec,
            'line': 'All lines' if station_summary else filtered_rec['line'],
            'line_demand': 0,
            'recommended_headway_min': None,
            'existing_headway_min': None,
            'recommended_trains_per_hour': 0,
            'existing_trains_per_hour': 0,
            'recommended_clearance_capacity': 0,
            'existing_clearance_capacity': 0,
            'capacity_utilization_pct': None,
            'crowding_risk': 'SERVICE_CLOSED',
            'crowding_badge': 'Metro closed',
            'crowding_color': '#64748b',
            'avg_wait_time_rec_min': None,
            'trains_deployed_rec': 0,
            'status_action': 'SERVICE_CLOSED',
            'explanation': f"Metro service is closed at {hour:02d}:{minute:02d} (modeled operating window: 05:00-23:30). No trains are operating and modeled passenger demand is zero."
        }

    # 3. Dijkstra Travel Times to ALL stations
    times = shortest_times_from(travel_graph, station)
    station_line_map = dict(zip(stations_df['Station'], stations_df['Line']))
    travel_list = [
        {
            'destination': dest,
            'travel_time_min': round(mins, 1),
            'line': station_line_map.get(dest, 'Metro Network')
        }
        for dest, mins in sorted(times.items(), key=lambda kv: kv[1])
    ]

    calendar_context['hour_band'] = _hour_band(profile_24h['predicted'], hour, minute)
    calendar_context['selected_hour_demand'] = hourly_footfall
    calendar_context['daily_peak_hour'] = profile_24h['peak_hour']

    return jsonify({
        "status": "success",
        "station": station,
        "station_info": st_info,
        "datetime": {
            "date": dt_obj.strftime('%Y-%m-%d'),
            "day": dt_obj.strftime('%A'),
            "time": f"{hour:02d}:{minute:02d}",
            "hour": hour,
            "minute": minute,
            "is_peak": filtered_rec['is_peak'],
            "service_open": service_open
        },
        "calendar_context": calendar_context,
        "footfall": {
            "instant_interpolated": time_footfall,
            "hourly_demand": hourly_footfall,
            "daily_total": profile_24h['daily_total'],
            "station_peak_hour": profile_24h['peak_hour'],
            "station_peak_footfall": profile_24h['peak_footfall'],
        },
        "scheduling": {
            "headline": filtered_rec,
            "all_lines": schedule_res['line_recommendations'],
            "is_interchange": schedule_res['is_interchange']
        },
        "profile_24h": profile_24h,
        "travel_times": travel_list,
        "data_provenance": {
            "station_topology": "PROJECT_ROUTE_MAP_DATA_REQUIRES_SOURCE_VERIFICATION",
            "train_capacities": "CONFIGURABLE_PROJECT_ASSUMPTIONS_NOT_VERIFIED_DMRC_SPECIFICATIONS",
            "baseline_headways": "CONFIGURABLE_PROJECT_ASSUMPTIONS_NOT_VERIFIED_DMRC_TIMETABLES",
            "hourly_footfall_forecast": "MODEL_ESTIMATE_TRAINED_ON_SYNTHETIC_SIMULATION_NOT_OBSERVED_COUNTS",
            "interchange_demand_distribution": "SYNTHETIC_WEIGHTED_ESTIMATE_NOT_OBSERVED_LINE_SPLIT"
        }
    })


@app.route('/api/stations')
def api_stations():
    stations_data = []
    for _, row in stations_df.iterrows():
        st = row['Station']
        all_lines = [l.strip() for l in str(row.get('All_Lines', row['Line'])).split(',')]
        stations_data.append({
            "station": st,
            "line": row['Line'],
            "all_lines": all_lines,
            "is_interchange": bool(row.get('Is_Interchange', len(all_lines) > 1)),
            "latitude": float(row['Latitude']) if pd.notna(row['Latitude']) else None,
            "longitude": float(row['Longitude']) if pd.notna(row['Longitude']) else None,
        })
    return jsonify({"stations": stations_data})


@app.route('/api/model_metrics')
def api_model_metrics():
    return jsonify(get_model_evaluation_summary())
