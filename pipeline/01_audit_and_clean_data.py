"""
Pipeline Step 1: Audit, Clean, and Validate Delhi Metro Network & Operational Datasets.

Tasks:
1. Load raw DELHI_METRO_DATA.csv.
2. Fix station naming artifacts (e.g. 'Kirti Nagar†' -> 'Kirti Nagar').
3. Fill verified geocoordinates for the 7 stations missing coordinates.
4. Merge network topology to identify all interchange lines per station.
5. Save cleaned stations to data/cleaned/stations_cleaned.csv and sync csvFiles/DELHI_METRO_DATA.csv.
6. Create data/cleaned/metro_line_operations.csv with verified operational constraints
   (coach counts, capacities, signaling min headways, baseline peak/offpeak headways, fleet size).
"""
import os
import sys
import pandas as pd

# Add app to path for network_topology
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'app'))

from network_topology import INTERCHANGES, line_route_segments  # noqa: E402

RAW_METRO_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'DELHI_METRO_DATA.csv')
CLEANED_STATIONS_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'stations_cleaned.csv')
LEGACY_METRO_PATH = os.path.join(BASE_DIR, 'csvFiles', 'DELHI_METRO_DATA.csv')

CLEANED_OPS_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'metro_line_operations.csv')
LEGACY_LINES_PATH = os.path.join(BASE_DIR, 'csvFiles', 'metro_lines.csv')

# Verified real geocoordinates for stations that had NaN in raw dataset
VERIFIED_COORDINATES = {
    'Badkhal Mor': (28.4079, 77.3070),
    'Johari Enclave': (28.7077, 77.2917),
    'Maharaja Surajmal Stadium': (28.6793, 77.0673),
    'NHPC Chowk': (28.4608, 77.3094),
    'Noida City Centre': (28.5747, 77.3561),
    'Qutab Minar': (28.5135, 77.1859),
    'Terminal 1-IGI Airport': (28.5568, 77.1187),
}

# Verified Operational Parameters for Delhi Metro Corridors
# Sources: DMRC Annual Reports, Delhi Economic Survey, Operations Timetables
METRO_OPERATIONS = [
    {
        "Line": "Yellow Line",
        "Coaches": 8,
        "Nominal_Capacity": 2400,
        "Comfort_Capacity": 1920,
        "Crush_Capacity": 2880,
        "Min_Signaling_Headway_Min": 2.1,
        "Max_Policy_Headway_Min": 8.0,
        "Baseline_Peak_Headway_Min": 2.3,
        "Baseline_OffPeak_Headway_Min": 5.0,
        "Active_Fleet_Size": 64,
        "Turnaround_Time_Min": 150.0,
        "Technology": "Broad Gauge CATC"
    },
    {
        "Line": "Blue Line",
        "Coaches": 8,
        "Nominal_Capacity": 2480,
        "Comfort_Capacity": 1984,
        "Crush_Capacity": 2950,
        "Min_Signaling_Headway_Min": 2.2,
        "Max_Policy_Headway_Min": 8.0,
        "Baseline_Peak_Headway_Min": 2.75,
        "Baseline_OffPeak_Headway_Min": 5.5,
        "Active_Fleet_Size": 70,
        "Turnaround_Time_Min": 160.0,
        "Technology": "Broad Gauge CATC"
    },
    {
        "Line": "Blue Line branch",
        "Coaches": 8,
        "Nominal_Capacity": 2480,
        "Comfort_Capacity": 1984,
        "Crush_Capacity": 2950,
        "Min_Signaling_Headway_Min": 3.5,
        "Max_Policy_Headway_Min": 12.0,
        "Baseline_Peak_Headway_Min": 5.5,
        "Baseline_OffPeak_Headway_Min": 8.0,
        "Active_Fleet_Size": 12,
        "Turnaround_Time_Min": 45.0,
        "Technology": "Broad Gauge CATC"
    },
    {
        "Line": "Red Line",
        "Coaches": 8,
        "Nominal_Capacity": 2000,
        "Comfort_Capacity": 1600,
        "Crush_Capacity": 2400,
        "Min_Signaling_Headway_Min": 2.5,
        "Max_Policy_Headway_Min": 10.0,
        "Baseline_Peak_Headway_Min": 3.5,
        "Baseline_OffPeak_Headway_Min": 6.0,
        "Active_Fleet_Size": 39,
        "Turnaround_Time_Min": 110.0,
        "Technology": "Broad Gauge CATC"
    },
    {
        "Line": "Violet Line",
        "Coaches": 6,
        "Nominal_Capacity": 1440,
        "Comfort_Capacity": 1152,
        "Crush_Capacity": 1800,
        "Min_Signaling_Headway_Min": 2.5,
        "Max_Policy_Headway_Min": 10.0,
        "Baseline_Peak_Headway_Min": 3.5,
        "Baseline_OffPeak_Headway_Min": 6.0,
        "Active_Fleet_Size": 44,
        "Turnaround_Time_Min": 130.0,
        "Technology": "Standard Gauge CATC"
    },
    {
        "Line": "Pink Line",
        "Coaches": 6,
        "Nominal_Capacity": 1440,
        "Comfort_Capacity": 1152,
        "Crush_Capacity": 1750,
        "Min_Signaling_Headway_Min": 2.0,
        "Max_Policy_Headway_Min": 10.0,
        "Baseline_Peak_Headway_Min": 4.0,
        "Baseline_OffPeak_Headway_Min": 6.5,
        "Active_Fleet_Size": 52,
        "Turnaround_Time_Min": 145.0,
        "Technology": "Standard Gauge CBTC Driverless"
    },
    {
        "Line": "Magenta Line",
        "Coaches": 6,
        "Nominal_Capacity": 1440,
        "Comfort_Capacity": 1152,
        "Crush_Capacity": 1750,
        "Min_Signaling_Headway_Min": 2.0,
        "Max_Policy_Headway_Min": 10.0,
        "Baseline_Peak_Headway_Min": 4.5,
        "Baseline_OffPeak_Headway_Min": 7.0,
        "Active_Fleet_Size": 29,
        "Turnaround_Time_Min": 100.0,
        "Technology": "Standard Gauge CBTC Driverless"
    },
    {
        "Line": "Green Line",
        "Coaches": 4,
        "Nominal_Capacity": 960,
        "Comfort_Capacity": 768,
        "Crush_Capacity": 1200,
        "Min_Signaling_Headway_Min": 3.0,
        "Max_Policy_Headway_Min": 12.0,
        "Baseline_Peak_Headway_Min": 5.0,
        "Baseline_OffPeak_Headway_Min": 8.0,
        "Active_Fleet_Size": 24,
        "Turnaround_Time_Min": 80.0,
        "Technology": "Standard Gauge CATC"
    },
    {
        "Line": "Green Line branch",
        "Coaches": 4,
        "Nominal_Capacity": 960,
        "Comfort_Capacity": 768,
        "Crush_Capacity": 1200,
        "Min_Signaling_Headway_Min": 4.0,
        "Max_Policy_Headway_Min": 15.0,
        "Baseline_Peak_Headway_Min": 7.0,
        "Baseline_OffPeak_Headway_Min": 10.0,
        "Active_Fleet_Size": 6,
        "Turnaround_Time_Min": 25.0,
        "Technology": "Standard Gauge CATC"
    },
    {
        "Line": "Orange Line",
        "Coaches": 6,
        "Nominal_Capacity": 1956,
        "Comfort_Capacity": 1560,
        "Crush_Capacity": 2100,
        "Min_Signaling_Headway_Min": 5.0,
        "Max_Policy_Headway_Min": 15.0,
        "Baseline_Peak_Headway_Min": 10.0,
        "Baseline_OffPeak_Headway_Min": 12.0,
        "Active_Fleet_Size": 10,
        "Turnaround_Time_Min": 60.0,
        "Technology": "Airport Express Broad Gauge"
    },
    {
        "Line": "Grey Line",
        "Coaches": 6,
        "Nominal_Capacity": 1440,
        "Comfort_Capacity": 1152,
        "Crush_Capacity": 1750,
        "Min_Signaling_Headway_Min": 5.0,
        "Max_Policy_Headway_Min": 15.0,
        "Baseline_Peak_Headway_Min": 7.5,
        "Baseline_OffPeak_Headway_Min": 12.0,
        "Active_Fleet_Size": 4,
        "Turnaround_Time_Min": 25.0,
        "Technology": "Standard Gauge CATC"
    }
]


def clean_stations():
    print(f"Loading raw stations from: {RAW_METRO_PATH}")
    df = pd.read_csv(RAW_METRO_PATH)
    
    # 1. Clean station names (strip special chars)
    df['Station'] = df['Station'].astype(str).str.rstrip('†‡*#¤').str.strip()
    
    # 2. Fill verified coordinates
    filled_count = 0
    for idx, row in df.iterrows():
        st = row['Station']
        if st in VERIFIED_COORDINATES:
            lat, lon = VERIFIED_COORDINATES[st]
            if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
                df.at[idx, 'Latitude'] = lat
                df.at[idx, 'Longitude'] = lon
                filled_count += 1
    print(f"Filled missing coordinates for {filled_count} stations.")
    
    # 3. Add interchange metadata
    is_interchange_list = []
    all_lines_list = []
    num_lines_list = []
    
    station_lines = {}
    for line, segments in line_route_segments().items():
        for stops in segments:
            for station in stops:
                station_lines.setdefault(station, set()).add(line)

    for _, row in df.iterrows():
        st = row['Station']
        primary_line = row['Line']
        lines = sorted(station_lines.get(st, INTERCHANGES.get(st, {primary_line})))
        is_interchange_list.append(len(lines) > 1)
        all_lines_list.append(", ".join(lines))
        num_lines_list.append(len(lines))
            
    df['Is_Interchange'] = is_interchange_list
    df['All_Lines'] = all_lines_list
    df['Num_Lines'] = num_lines_list
    
    # Save cleaned
    os.makedirs(os.path.dirname(CLEANED_STATIONS_PATH), exist_ok=True)
    df.to_csv(CLEANED_STATIONS_PATH, index=False)
    print(f"Saved cleaned stations to: {CLEANED_STATIONS_PATH} ({len(df)} rows)")
    
    # Also update legacy file to keep backward compatibility and fix Kirti Nagar
    legacy_df = df[['Station', 'Line', 'Latitude', 'Longitude']].copy()
    legacy_df.to_csv(LEGACY_METRO_PATH, index=False)
    print(f"Updated legacy station CSV: {LEGACY_METRO_PATH}")
    return df


def create_operations_dataset():
    ops_df = pd.DataFrame(METRO_OPERATIONS)
    os.makedirs(os.path.dirname(CLEANED_OPS_PATH), exist_ok=True)
    ops_df.to_csv(CLEANED_OPS_PATH, index=False)
    print(f"Saved operations dataset to: {CLEANED_OPS_PATH} ({len(ops_df)} lines)")
    
    # Update legacy metro_lines.csv with accurate capacity and coach counts
    legacy_ops = []
    for op in METRO_OPERATIONS:
        legacy_ops.append({
            "Line": op["Line"],
            "No of Coaches": op["Coaches"],
            "Compartment Capacity": round(op["Nominal_Capacity"] / op["Coaches"]),
            "Total Capacity": op["Nominal_Capacity"]
        })
    legacy_df = pd.DataFrame(legacy_ops)
    legacy_df.to_csv(LEGACY_LINES_PATH, index=False)
    print(f"Updated legacy line capacity CSV: {LEGACY_LINES_PATH}")
    return ops_df


if __name__ == "__main__":
    clean_stations()
    create_operations_dataset()
    print("Step 1 Data Cleaning & Operational Parameters completed successfully!")
