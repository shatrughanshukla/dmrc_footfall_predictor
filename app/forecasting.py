"""
Passenger Footfall Forecasting Inference Engine.

Wraps the trained machine learning model (HistGradientBoostingRegressor) and
historical baseline models to provide real-time hourly and 24-hour profile predictions.
"""
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from app.calendar_context import get_calendar_context

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'footfall_forecaster.joblib')
METADATA_PATH = os.path.join(BASE_DIR, 'models', 'forecaster_metadata.joblib')
STATIONS_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'stations_cleaned.csv')
EVAL_METRICS_PATH = os.path.join(BASE_DIR, 'models', 'evaluation_metrics.json')

# Load model and metadata
_MODEL = joblib.load(MODEL_PATH)
_META = joblib.load(METADATA_PATH)
_STATIONS_DF = pd.read_csv(STATIONS_PATH).set_index('Station')

# Evaluation metrics
_METRICS = {}
if os.path.exists(EVAL_METRICS_PATH):
    import json
    with open(EVAL_METRICS_PATH, 'r', encoding='utf-8') as f:
        _METRICS = json.load(f)


def get_station_info(station: str) -> dict:
    if station not in _STATIONS_DF.index:
        return {
            "station": station,
            "line": "Unknown",
            "all_lines": [],
            "is_interchange": False,
            "latitude": None,
            "longitude": None
        }
    row = _STATIONS_DF.loc[station]
    all_lines = [l.strip() for l in str(row['All_Lines']).split(',')] if 'All_Lines' in row else [row['Line']]
    return {
        "station": station,
        "line": row['Line'],
        "all_lines": all_lines,
        "is_interchange": bool(row['Is_Interchange']),
        "latitude": float(row['Latitude']) if pd.notna(row['Latitude']) else None,
        "longitude": float(row['Longitude']) if pd.notna(row['Longitude']) else None,
    }


def predict_hourly_footfall(station: str, dt_obj: datetime, hour: int) -> int:
    """
    Predicts footfall for a given station, date, and hour using the trained ML model.
    """
    info = get_station_info(station)
    st_idx = _META['station2idx'].get(station, 0)
    line_idx = _META['line2idx'].get(info['line'], 0)
    
    day_of_week = dt_obj.weekday()
    is_weekend = 1 if day_of_week >= 5 else 0
    
    hour_sin = np.sin(2 * np.pi * hour / 24.0)
    hour_cos = np.cos(2 * np.pi * hour / 24.0)
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    
    # Historical features
    hist_st_mean = _META['hist_station_mean'].get(st_idx, _META['global_mean'])
    hist_key = f"{st_idx}_{day_of_week}_{hour}"
    hist_hd_mean = _META['hist_hour_day_mean'].get(hist_key, hist_st_mean)

    month = dt_obj.month
    date_context = get_calendar_context(dt_obj.date())
    holiday_type = date_context['holiday_type']
    typology = _META.get('typology_dict', {}).get(station, 'RESIDENTIAL_SUBURB')
    typology_idx = _META.get('typology2idx', {}).get(typology, 0)
    station_month_key = f"{st_idx}_{month}"
    station_month_mean = _META.get('hist_station_month_mean', {}).get(station_month_key, hist_st_mean)
    values = {
        'Hour': hour,
        'DayOfWeek': day_of_week,
        'Month': month,
        'DayOfMonth': dt_obj.day,
        'DayOfYear': dt_obj.timetuple().tm_yday,
        'IsWeekend': is_weekend,
        'IsHoliday': int(bool(holiday_type)),
        'IsWorkday': int(date_context['is_workday']),
        'HolidayType': holiday_type,
        'Hour_Sin': hour_sin,
        'Hour_Cos': hour_cos,
        'Day_Sin': day_sin,
        'Day_Cos': day_cos,
        'Month_Sin': np.sin(2 * np.pi * month / 12.0),
        'Month_Cos': np.cos(2 * np.pi * month / 12.0),
        'Station_Idx': st_idx,
        'Line_Idx': line_idx,
        'Typology_Idx': typology_idx,
        'Is_Interchange': 1 if info['is_interchange'] else 0,
        'Num_Lines': len(info['all_lines']),
        'Hist_Station_Mean': hist_st_mean,
        'Hist_Hour_Day_Mean': hist_hd_mean,
        'Hist_Station_Month_Mean': station_month_mean,
    }
    # Match the loaded model's schema so inference stays aligned with the
    # persisted training metadata when the feature set changes.
    features = pd.DataFrame([{name: values[name] for name in _META['feature_cols']}])
    
    pred = _MODEL.predict(features)[0]
    return max(0, round(float(pred)))


def predict_footfall_with_minute_interpolation(station: str, dt_obj: datetime, hour: int, minute: int) -> int:
    """
    Interpolates smoothly across the hour based on the minute.
    """
    v0 = predict_hourly_footfall(station, dt_obj, hour)
    next_hour = min(23, hour + 1)
    v1 = predict_hourly_footfall(station, dt_obj, next_hour)
    
    interpolated = v0 + (v1 - v0) * (minute / 60.0)
    return max(0, round(interpolated))


def predict_station_full_day_profile(station: str, dt_obj: datetime) -> dict:
    """
    Generates 24-hour demand profile for charts (05:00 to 23:00).
    """
    hours = list(range(5, 24))
    predicted_curve = []
    historical_curve = []
    
    st_idx = _META['station2idx'].get(station, 0)
    day_of_week = dt_obj.weekday()
    
    for h in hours:
        # ML prediction
        pred_val = predict_hourly_footfall(station, dt_obj, h)
        predicted_curve.append(pred_val)
        
        # Historical baseline mean
        hist_key = f"{st_idx}_{day_of_week}_{h}"
        hist_val = round(_META['hist_hour_day_mean'].get(hist_key, _META['hist_station_mean'].get(st_idx, 0)))
        historical_curve.append(hist_val)
        
    labels = [f"{h:02d}:00" for h in hours]
    
    # Identify peak demand periods
    max_idx = int(np.argmax(predicted_curve))
    peak_hour = labels[max_idx]
    peak_footfall = predicted_curve[max_idx]
    
    # Daily sum
    predicted_daily_total = sum(predicted_curve)
    
    # Calculate line-wise 24-hour demand curves
    info = get_station_info(station)
    all_lines = info.get('all_lines', [info['line']])
    is_interchange = len(all_lines) > 1
    
    from app.scheduling_optimizer import get_interchange_line_split
    line_splits = get_interchange_line_split(station, all_lines) if is_interchange else {info['line']: 1.0}
    
    line_curves = {}
    for l in all_lines:
        share = line_splits.get(l, 1.0 / len(all_lines))
        line_curves[l] = [round(val * share) for val in predicted_curve]
    
    return {
        "labels": labels,
        "hours": hours,
        "predicted": predicted_curve,
        "historical": historical_curve,
        "peak_hour": peak_hour,
        "peak_footfall": peak_footfall,
        "daily_total": predicted_daily_total,
        "line_curves": line_curves,
        "is_interchange": is_interchange,
        "all_lines": all_lines
    }


def get_model_evaluation_summary() -> dict:
    return {
        **_METRICS,
        "data_basis": "SYNTHETIC_SIMULATION_ONLY",
        "real_world_validation_available": False,
        "feature_count": len(_META['feature_cols']),
        "artifact_warning": None,
    }
