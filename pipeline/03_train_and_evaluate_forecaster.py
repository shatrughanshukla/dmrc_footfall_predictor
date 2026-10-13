"""
Pipeline Step 3: Train & Chronologically Evaluate Advanced Footfall Forecaster.

Features:
1. Ingests a 104-week synthetic scenario dataset (2025-01 to 2027-01).
2. Advanced Feature Engineering:
   - Calendar & Holiday: hour/date cycles, weekends, workdays, known occasions, and event classes.
   - Cyclical Trigonometric Encodings: Hour (sin/cos), DayOfWeek (sin/cos), Month (sin/cos).
   - Station Typology: Commercial/Office, Intermodal Gateway, University, Shopping/Leisure, Residential.
   - Station Centrality: Line, Is_Interchange, Num_Lines.
   - Historical Aggregates (strictly computed on Training split to prevent any data leakage):
     * Hist_Station_Mean
     * Hist_Hour_Day_Mean
     * Hist_Station_Month_Mean
3. Chronological Out-of-Time Split:
   - Train through 2026-09-30; test from 2026-10-01 onward, including Dussehra/Diwali.
4. Evaluates:
   - Baseline 1: Overall Station Mean
   - Baseline 2: Historical (Station, DayOfWeek, Hour) Mean
   - Baseline 3: Linear Ridge Regression
   - Production Model: Tuned HistGradientBoostingRegressor
5. Saves model artifacts, metadata, and evaluation report to models/.
"""
import os
import sys
import json
import joblib
from datetime import date
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from app.calendar_context import get_calendar_context

FOOTFALL_DATA_PATH = os.path.join(BASE_DIR, 'data', 'synthetic', 'dmrc_calibrated_footfall.csv')
STATIONS_CLEANED_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'stations_cleaned.csv')
TYPOLOGY_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'station_typologies.json')
MODEL_OUT_PATH = os.path.join(BASE_DIR, 'models', 'footfall_forecaster.joblib')
METADATA_OUT_PATH = os.path.join(BASE_DIR, 'models', 'forecaster_metadata.joblib')
METRICS_OUT_PATH = os.path.join(BASE_DIR, 'models', 'evaluation_metrics.json')

SPLIT_DATE = '2026-10-01'  # Hold out the future festival quarter and year end


def prepare_annual_data():
    print(f"Loading 104-week footfall dataset from: {FOOTFALL_DATA_PATH}")
    df = pd.read_csv(FOOTFALL_DATA_PATH, parse_dates=['Date'])
    stations_df = pd.read_csv(STATIONS_CLEANED_PATH)
    
    # Load typologies
    typology_dict = {}
    if os.path.exists(TYPOLOGY_PATH):
        with open(TYPOLOGY_PATH, 'r', encoding='utf-8') as f:
            typology_dict = json.load(f)
            
    # Merge station attributes
    station_meta = stations_df[['Station', 'Is_Interchange', 'Num_Lines']].drop_duplicates()
    df = df.merge(station_meta, on='Station', how='left')
    df['Is_Interchange'] = df['Is_Interchange'].fillna(False).astype(int)
    df['Num_Lines'] = df['Num_Lines'].fillna(1).astype(int)
    
    # Station Typology encoding
    typologies_unique = ["RESIDENTIAL_SUBURB", "COMMERCIAL_OFFICE", "TRANSIT_GATEWAY", "UNIVERSITY_CAMPUS", "SHOPPING_LEISURE"]
    typology2idx = {t: i for i, t in enumerate(typologies_unique)}
    df['Typology'] = df['Station'].map(lambda s: typology_dict.get(s, "RESIDENTIAL_SUBURB"))
    df['Typology_Idx'] = df['Typology'].map(typology2idx).fillna(0).astype(int)
    
    # Calendar & Holiday features
    df['DayOfWeek'] = df['Date'].dt.weekday
    df['Month'] = df['Date'].dt.month
    df['DayOfMonth'] = df['Date'].dt.day
    df['DayOfYear'] = df['Date'].dt.dayofyear
    df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
    
    # Holiday indicators
    date_strs = df['Date'].dt.strftime('%Y-%m-%d')
    contexts = {
        d: get_calendar_context(pd.Timestamp(d).date())
        for d in date_strs.unique()
    }
    holiday_map = {d: ctx['holiday_type'] for d, ctx in contexts.items()}
    public_holiday_map = {d: ctx['is_public_holiday'] for d, ctx in contexts.items()}
    df['HolidayType'] = date_strs.map(holiday_map).fillna(0).astype(int)
    df['IsHoliday'] = (df['HolidayType'] > 0).astype(int)
    df['IsWorkday'] = (
        (df['DayOfWeek'] < 5) & ~date_strs.map(public_holiday_map).fillna(False)
    ).astype(int)
    
    # Cyclical trigonometric encodings
    df['Hour_Sin'] = np.sin(2 * np.pi * df['Hour'] / 24.0)
    df['Hour_Cos'] = np.cos(2 * np.pi * df['Hour'] / 24.0)
    df['Day_Sin'] = np.sin(2 * np.pi * df['DayOfWeek'] / 7.0)
    df['Day_Cos'] = np.cos(2 * np.pi * df['DayOfWeek'] / 7.0)
    df['Month_Sin'] = np.sin(2 * np.pi * df['Month'] / 12.0)
    df['Month_Cos'] = np.cos(2 * np.pi * df['Month'] / 12.0)
    
    # Station & Line Categoricals
    stations_unique = sorted(df['Station'].unique().tolist())
    lines_unique = sorted(df['Line'].unique().tolist())
    
    station2idx = {s: i for i, s in enumerate(stations_unique)}
    line2idx = {l: i for i, l in enumerate(lines_unique)}
    
    df['Station_Idx'] = df['Station'].map(station2idx)
    df['Line_Idx'] = df['Line'].map(line2idx)
    
    # Chronological Out-of-Time Split
    train_mask = df['Date'] < SPLIT_DATE
    train_df = df[train_mask].copy()
    test_df = df[~train_mask].copy()
    
    print(f"Chronological Out-of-Time Split:")
    print(f"  Training set (before split): {train_df['Date'].min().strftime('%Y-%m-%d')} to {train_df['Date'].max().strftime('%Y-%m-%d')} ({len(train_df):,} rows)")
    print(f"  Future holdout:              {test_df['Date'].min().strftime('%Y-%m-%d')} to {test_df['Date'].max().strftime('%Y-%m-%d')} ({len(test_df):,} rows)")
    
    # Final training-period aggregates are used for forecasts after the split.
    # Training rows use prior-date-only aggregates below, preventing a row's
    # own target (or later training dates) from leaking into its features.
    global_mean = train_df['Footfall'].mean()
    hist_station_mean = train_df.groupby('Station_Idx')['Footfall'].mean().to_dict()
    hist_hour_day_mean = train_df.groupby(['Station_Idx', 'DayOfWeek', 'Hour'])['Footfall'].mean().to_dict()
    hist_station_month_mean = train_df.groupby(['Station_Idx', 'Month'])['Footfall'].mean().to_dict()

    # Daily station summaries let station and station-month means use only
    # completed earlier dates, with no same-day information in a forecast.
    train_df = train_df.sort_values(['Date', 'Station_Idx', 'Hour']).copy()
    daily = (train_df.groupby(['Station_Idx', 'Date'], as_index=False, sort=True)
             .agg(Daily_Mean=('Footfall', 'mean')))
    daily['Month'] = pd.to_datetime(daily['Date']).dt.month
    station_group = daily.groupby('Station_Idx', sort=False)['Daily_Mean']
    daily['Hist_Station_Mean'] = (
        (station_group.cumsum() - daily['Daily_Mean']) /
        station_group.cumcount().replace(0, np.nan)
    )
    month_group = daily.groupby(['Station_Idx', 'Month'], sort=False)['Daily_Mean']
    daily['Hist_Station_Month_Mean'] = (
        (month_group.cumsum() - daily['Daily_Mean']) /
        month_group.cumcount().replace(0, np.nan)
    )
    train_df = train_df.merge(
        daily[['Station_Idx', 'Date', 'Hist_Station_Mean', 'Hist_Station_Month_Mean']],
        on=['Station_Idx', 'Date'], how='left', validate='many_to_one'
    )

    hour_day_keys = ['Station_Idx', 'DayOfWeek', 'Hour']
    hour_day_group = train_df.groupby(hour_day_keys, sort=False)['Footfall']
    prior_hour_day_count = hour_day_group.cumcount()
    train_df['Hist_Hour_Day_Mean'] = (
        (hour_day_group.cumsum() - train_df['Footfall']) /
        prior_hour_day_count.replace(0, np.nan)
    )

    # Use all training dates only for test rows and live inference.
    test_df['Hist_Station_Mean'] = test_df['Station_Idx'].map(hist_station_mean)
    test_df['Hist_Hour_Day_Mean'] = [
        hist_hour_day_mean.get((station, day, hour), hist_station_mean.get(station, global_mean))
        for station, day, hour in zip(test_df['Station_Idx'], test_df['DayOfWeek'], test_df['Hour'])
    ]
    test_df['Hist_Station_Month_Mean'] = [
        hist_station_month_mean.get((station, month), hist_station_mean.get(station, global_mean))
        for station, month in zip(test_df['Station_Idx'], test_df['Month'])
    ]
    # Initial history is genuinely unavailable for early training rows.
    # HistGradientBoostingRegressor handles missing history values natively.
    
    feature_cols = [
        'Hour', 'DayOfWeek', 'Month', 'DayOfMonth', 'DayOfYear',
        'IsWeekend', 'IsHoliday', 'IsWorkday', 'HolidayType',
        'Hour_Sin', 'Hour_Cos', 'Day_Sin', 'Day_Cos', 'Month_Sin', 'Month_Cos',
        'Station_Idx', 'Line_Idx', 'Typology_Idx', 'Is_Interchange', 'Num_Lines',
        'Hist_Station_Mean', 'Hist_Hour_Day_Mean', 'Hist_Station_Month_Mean'
    ]
    
    metadata = {
        'station2idx': station2idx,
        'idx2station': {i: s for s, i in station2idx.items()},
        'line2idx': line2idx,
        'idx2line': {i: l for l, i in line2idx.items()},
        'typology2idx': typology2idx,
        'typology_dict': typology_dict,
        'delhi_holidays': {k: ctx['occasion'] for k, ctx in contexts.items() if ctx['occasion']},
        'holiday_type_by_date': holiday_map,
        'hist_station_mean': hist_station_mean,
        'hist_hour_day_mean': {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in hist_hour_day_mean.items()},
        'hist_station_month_mean': {f"{k[0]}_{k[1]}": v for k, v in hist_station_month_mean.items()},
        'global_mean': global_mean,
        'feature_cols': feature_cols,
        'split_date': SPLIT_DATE
    }
    
    return train_df, test_df, feature_cols, metadata


def compute_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    non_zero = y_true > 0
    mape = np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100.0
    return {
        'MAE': round(float(mae), 2),
        'RMSE': round(float(rmse), 2),
        'R2': round(float(r2), 4),
        'MAPE_%': round(float(mape), 2)
    }


def train_and_evaluate_model():
    train_df, test_df, feature_cols, metadata = prepare_annual_data()
    
    X_train = train_df[feature_cols]
    y_train = train_df['Footfall'].values
    
    X_test = test_df[feature_cols]
    y_test = test_df['Footfall'].values
    
    print("\n--- Evaluating Baseline 1: Station Overall Mean ---")
    b1_pred = test_df['Hist_Station_Mean'].values
    m_b1 = compute_metrics(y_test, b1_pred)
    print(f"  Station Mean Baseline: {m_b1}")
    
    print("\n--- Evaluating Baseline 2: Historical (Station, Day, Hour) Mean ---")
    b2_pred = test_df['Hist_Hour_Day_Mean'].values
    m_b2 = compute_metrics(y_test, b2_pred)
    print(f"  Station-Day-Hour Mean Baseline: {m_b2}")
    
    print("\n--- Evaluating Baseline 3: Ridge Regression ---")
    ridge = Ridge(alpha=100.0)
    ridge.fit(X_train.fillna(0), y_train)
    ridge_pred = np.clip(ridge.predict(X_test), 0, None)
    m_ridge = compute_metrics(y_test, ridge_pred)
    print(f"  Ridge Regression: {m_ridge}")
    
    print("\n--- Training Production Model: Tuned HistGradientBoostingRegressor ---")
    model = HistGradientBoostingRegressor(
        max_iter=250,
        learning_rate=0.06,
        max_depth=9,
        min_samples_leaf=25,
        l2_regularization=0.05,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    ml_pred = np.clip(model.predict(X_test), 0, None)
    m_ml = compute_metrics(y_test, ml_pred)
    print(f"  Tuned HistGradientBoostingRegressor: {m_ml}")
    
    # Save model and metadata
    os.makedirs(os.path.dirname(MODEL_OUT_PATH), exist_ok=True)
    joblib.dump(model, MODEL_OUT_PATH)
    joblib.dump(metadata, METADATA_OUT_PATH)
    print(f"\nModel saved to: {MODEL_OUT_PATH}")
    print(f"Metadata saved to: {METADATA_OUT_PATH}")
    
    # Save comprehensive metrics report
    report = {
        "evaluation_dataset": {
            "name": "Delhi Metro Synthetic Scenario Test Split",
            "total_records": len(train_df) + len(test_df),
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "split_date": SPLIT_DATE,
            "validation_method": "Chronological Out-of-Time Validation (future festival quarter; prior-date history features)"
        },
        "model_comparison": {
            "baseline_station_mean": {
                "name": "Station Overall Mean Baseline",
                "metrics": m_b1
            },
            "baseline_historical_hour_day": {
                "name": "Historical (Station, DayOfWeek, Hour) Mean Baseline",
                "metrics": m_b2
            },
            "baseline_ridge_regression": {
                "name": "Ridge Regression Baseline",
                "metrics": m_ridge
            },
            "hist_gradient_boosting": {
                "name": "Tuned HistGradientBoostingRegressor (Production ML)",
                "metrics": m_ml
            }
        },
        "feature_importance_features": feature_cols
    }
    
    with open(METRICS_OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"Metrics report saved to: {METRICS_OUT_PATH}")
    return report


if __name__ == "__main__":
    train_and_evaluate_model()
    print("Step 3 Advanced Model Training & Evaluation completed successfully!")
