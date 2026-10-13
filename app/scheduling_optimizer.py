"""
DMRC Realistic Train Frequency and Scheduling Optimization Engine.

Provides transit-grade operational headway and frequency optimization based on:
1. Predicted passenger demand over time.
2. Verified line train passenger capacity (nominal, comfort 80%, crush 120%).
3. Baseline scheduled train frequency and headways (DMRC official peak vs off-peak timetables).
4. Minimum safe train separation (CATC/CBTC signaling safety headway limit).
5. Maximum policy headway (service frequency upper bound).
6. Active line fleet availability and turnaround cycle times.
7. Passenger waiting times and platform clearance limits.
8. Explainable operational recommendations.
"""
import os
import json
import math
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPS_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'metro_line_operations.csv')
LINE_MODEL_PATH = os.path.join(BASE_DIR, 'data', 'synthetic', 'line_distribution_model.json')

# Load operational parameters and line models at module import
_OPS_DF = pd.read_csv(OPS_PATH).set_index('Line')
if os.path.exists(LINE_MODEL_PATH):
    with open(LINE_MODEL_PATH, 'r', encoding='utf-8') as f:
        _LINE_DIST_MODEL = json.load(f)
else:
    _LINE_DIST_MODEL = {"interchanges": {}}

# Practical headway dispatch intervals (minutes) common in metro operations
STANDARD_HEADWAYS = [
    2.0, 2.15, 2.3, 2.5, 2.75, 3.0, 3.25, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0,
    6.5, 7.0, 7.5, 8.0, 9.0, 10.0, 12.0, 15.0
]


def is_peak_hour(hour: int, day_of_week: int, is_workday=None) -> bool:
    """
    Returns True if the hour falls into Delhi Metro peak rush hours on a weekday.
    Weekday morning peak: 08:00 - 11:00 (hours 8, 9, 10)
    Weekday evening peak: 17:00 - 20:30 (hours 17, 18, 19, 20)
    Saturdays/Sundays are treated as off-peak.
    """
    if is_workday is None:
        is_workday = day_of_week < 5
    if not is_workday:
        return False
    return (8 <= hour <= 10) or (17 <= hour <= 20)


def get_interchange_line_split(station: str, all_lines: list) -> dict:
    """
    Returns {line: proportion} for an interchange station.
    """
    interchanges = _LINE_DIST_MODEL.get("interchanges", {})
    if station in interchanges:
        return interchanges[station].get("proportions", {})
    
    # Fallback equal distribution
    if all_lines:
        share = round(1.0 / len(all_lines), 4)
        return {l: share for l in all_lines}
    return {}


def round_to_practical_headway(headway_min: float, min_headway: float, max_headway: float) -> float:
    """
    Rounds a continuous optimal headway to the closest practical metro dispatch interval,
    strictly obeying signaling minimum and policy maximum bounds.
    """
    bounded = max(min_headway, min(headway_min, max_headway))
    valid_headways = [h for h in STANDARD_HEADWAYS if min_headway <= h <= max_headway]
    if not valid_headways:
        return round(bounded, 2)
    # Find closest standard interval
    closest = min(valid_headways, key=lambda x: abs(x - bounded))
    return round(closest, 2)


def optimize_line_schedule(line: str, station_name: str, hour: int, day_of_week: int,
                           line_demand: int, is_workday=None) -> dict:
    """
    Optimizes train scheduling for a specific line at a given station and hour.
    """
    if line not in _OPS_DF.index:
        # Default fallback if line key has slight naming variant
        line_match = [idx for idx in _OPS_DF.index if line.lower() in idx.lower()]
        line = line_match[0] if line_match else _OPS_DF.index[0]
        
    ops = _OPS_DF.loc[line]
    nominal_cap = int(ops['Nominal_Capacity'])
    comfort_cap = int(ops['Comfort_Capacity'])
    min_signal_headway = float(ops['Min_Signaling_Headway_Min'])
    max_policy_headway = float(ops['Max_Policy_Headway_Min'])
    fleet_size = int(ops['Active_Fleet_Size'])
    turnaround_min = float(ops['Turnaround_Time_Min'])
    
    # Maximum frequency physically supported by rolling stock fleet and turnaround time
    # Max trains per hour = Fleet / (Turnaround / 60)
    fleet_max_freq = math.floor((fleet_size * 60.0) / turnaround_min)
    signaling_max_freq = math.floor(60.0 / min_signal_headway)
    abs_max_freq = min(signaling_max_freq, fleet_max_freq)
    abs_min_freq = math.ceil(60.0 / max_policy_headway)
    
    peak = is_peak_hour(hour, day_of_week, is_workday)
    
    # Baseline scheduled headway from official DMRC operations
    if hour in [5, 6, 22, 23]:
        # Taper hours (early morning or late night)
        existing_headway = min(max_policy_headway, float(ops['Baseline_OffPeak_Headway_Min']) * 1.3)
    elif peak:
        existing_headway = float(ops['Baseline_Peak_Headway_Min'])
    else:
        existing_headway = float(ops['Baseline_OffPeak_Headway_Min'])
        
    existing_freq = round(60.0 / existing_headway, 1)
    
    # Transit Boarding Clearance Budget per Train:
    # During peak, trains arrive with ~65% through load, leaving 35% comfort capacity for boarding.
    # During off-peak, trains arrive with ~40% through load, leaving 60% comfort capacity for boarding.
    through_load_factor = 0.65 if peak else 0.40
    clearance_budget_per_train = max(int(comfort_cap * (1.0 - through_load_factor)), 250)
    
    # Existing offered clearance capacity for boarding at this station
    existing_clearance_capacity = int(existing_freq * clearance_budget_per_train)
    existing_line_capacity = int(existing_freq * nominal_cap)
    
    # Demand-driven frequency required to comfortably clear passenger boarding
    required_freq_for_demand = line_demand / clearance_budget_per_train
    
    # Baseline provides network connectivity across the entire line.
    # Recommended frequency must respect corridor baseline, but scale up if demand surges.
    if line_demand > existing_clearance_capacity:
        target_freq = required_freq_for_demand
        status_action = "INCREASE_FREQUENCY"
    elif line_demand < (existing_clearance_capacity * 0.45) and not peak and hour in [5, 6, 13, 14, 22, 23]:
        # Demand is light enough that frequency can be safely relaxed for energy efficiency
        target_freq = max(abs_min_freq, required_freq_for_demand * 1.1)
        status_action = "DECREASE_FREQUENCY"
    else:
        target_freq = existing_freq
        status_action = "MAINTAIN_SCHEDULE"
        
    # Clamping against physical signaling and fleet constraints
    constrained_freq = max(abs_min_freq, min(target_freq, abs_max_freq))
    raw_headway = 60.0 / constrained_freq
    
    # Round to realistic practical dispatch headway
    rec_headway = round_to_practical_headway(raw_headway, min_signal_headway, max_policy_headway)
    rec_freq = round(60.0 / rec_headway, 1)
    
    # Recomputed metrics with final recommended headway
    rec_clearance_capacity = int(rec_freq * clearance_budget_per_train)
    rec_total_line_capacity = int(rec_freq * nominal_cap)
    capacity_shortfall = rec_clearance_capacity - line_demand
    
    # Capacity Utilization (%)
    if rec_clearance_capacity > 0:
        utilization_pct = round((line_demand / rec_clearance_capacity) * 100.0, 1)
    else:
        utilization_pct = 0.0
        
    # Crowding & Platform Risk Assessment
    if utilization_pct > 105.0:
        crowding_risk = "CRITICAL_OVERCROWDING"
        crowding_badge = "Severe Crowd Alert"
        crowding_color = "#dc3545"  # Red
    elif utilization_pct > 88.0:
        crowding_risk = "HIGH_CROWDING"
        crowding_badge = "High Demand"
        crowding_color = "#fd7e14"  # Orange
    elif utilization_pct > 65.0:
        crowding_risk = "MODERATE"
        crowding_badge = "Optimal Load"
        crowding_color = "#28a745"  # Green
    else:
        crowding_risk = "LOW"
        crowding_badge = "Comfortable Capacity"
        crowding_color = "#17a2b8"  # Teal
        
    # Average Passenger Wait Time: E[W] = Headway / 2
    avg_wait_time_existing = round(existing_headway / 2.0, 1)
    avg_wait_time_rec = round(rec_headway / 2.0, 1)
    
    # Required active train sets deployed on corridor for this headway
    # Trains needed = Turnaround / Headway
    trains_deployed_rec = min(fleet_size, math.ceil(turnaround_min / rec_headway))
    
    # Construct transparent explainable narrative
    explanation_parts = []
    if status_action == "INCREASE_FREQUENCY":
        explanation_parts.append(
            f"Passenger demand on {line} at {station_name} ({line_demand:,} riders/hr) exceeds "
            f"baseline clearance capacity ({existing_clearance_capacity:,} riders/hr). "
            f"Recommended increasing service from {existing_freq:.1f} to {rec_freq:.1f} trains/hr "
            f"(headway reduced from {existing_headway:.1f}m to {rec_headway:.1f}m)."
        )
    elif status_action == "DECREASE_FREQUENCY":
        explanation_parts.append(
            f"Passenger demand is light ({line_demand:,} riders/hr). "
            f"Recommended moderating service from {existing_freq:.1f} to {rec_freq:.1f} trains/hr "
            f"(headway relaxed from {existing_headway:.1f}m to {rec_headway:.1f}m) to conserve energy "
            f"while safely respecting the {max_policy_headway:.1f}m policy maximum."
        )
    else:
        explanation_parts.append(
            f"Existing baseline timetable ({existing_freq:.1f} trains/hr, {existing_headway:.1f}m headway) "
            f"comfortably handles the projected demand ({line_demand:,} riders/hr) at {utilization_pct}% capacity utilization."
        )
        
    if rec_headway <= min_signal_headway + 0.05:
        explanation_parts.append(
            f"⚠️ Service frequency is operating at or near the absolute signaling safety limit ({min_signal_headway:.1f} min)."
        )
    if capacity_shortfall < 0:
        explanation_parts.append(
            f"⚠️ Capacity shortfall of {abs(capacity_shortfall):,} passengers/hr detected due to signaling throughput limit. "
            f"Station crowd management marshals recommended."
        )
        
    explanation = " ".join(explanation_parts)
    
    return {
        "line": line,
        "is_peak": peak,
        "line_demand": line_demand,
        "existing_headway_min": existing_headway,
        "existing_trains_per_hour": existing_freq,
        "existing_clearance_capacity": existing_clearance_capacity,
        "existing_line_capacity": existing_line_capacity,
        "recommended_headway_min": rec_headway,
        "recommended_trains_per_hour": rec_freq,
        "recommended_clearance_capacity": rec_clearance_capacity,
        "recommended_total_line_capacity": rec_total_line_capacity,
        "capacity_shortfall_surplus": capacity_shortfall,
        "capacity_utilization_pct": utilization_pct,
        "avg_wait_time_existing_min": avg_wait_time_existing,
        "avg_wait_time_rec_min": avg_wait_time_rec,
        "trains_deployed_rec": trains_deployed_rec,
        "fleet_size_available": fleet_size,
        "min_signaling_headway_min": min_signal_headway,
        "max_policy_headway_min": max_policy_headway,
        "crowding_risk": crowding_risk,
        "crowding_badge": crowding_badge,
        "crowding_color": crowding_color,
        "status_action": status_action,
        "explanation": explanation
    }


def optimize_station_schedule(station: str, primary_line: str, all_lines: list,
                              hour: int, day_of_week: int, total_footfall: int,
                              is_workday=None) -> dict:
    """
    Evaluates demand and scheduling for the entire station, including line-wise breakdowns
    for interchange stations.
    """
    is_interchange = len(all_lines) > 1
    line_splits = get_interchange_line_split(station, all_lines) if is_interchange else {primary_line: 1.0}
    
    line_recommendations = []
    for line in all_lines:
        share = line_splits.get(line, 1.0 / len(all_lines))
        line_demand = round(total_footfall * share)
        line_rec = optimize_line_schedule(
            line, station, hour, day_of_week, line_demand, is_workday=is_workday
        )
        line_rec["demand_share_pct"] = round(share * 100.0, 1)
        line_recommendations.append(line_rec)
        
    # Aggregate summary (using primary line or highest-demand line)
    primary_rec = max(line_recommendations, key=lambda r: r['line_demand'])
    
    return {
        "station": station,
        "is_interchange": is_interchange,
        "total_station_footfall": total_footfall,
        "all_lines": all_lines,
        "primary_line": primary_rec["line"],
        "line_distribution_metadata": _LINE_DIST_MODEL.get("metadata", {}),
        "line_recommendations": line_recommendations,
        "primary_recommendation": primary_rec
    }
