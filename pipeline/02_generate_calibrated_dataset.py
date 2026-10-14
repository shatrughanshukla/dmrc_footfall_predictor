"""
Pipeline Step 2: Annual Calibrated Footfall Dataset & Line Distribution Generation.

Features:
1. Expands dataset to a two-year synthetic scenario period:
   - 104 weeks (728 days, 2025-01-06 to 2027-01-03)
   - 19 operating hours (05:00 to 23:00) across the cleaned station roster
2. Simulates assumed Delhi transit patterns:
   - Calendar holidays & festivals (Republic Day, Holi, Independence Day,
     Raksha Bandhan peak, Diwali, Chhath, Christmas, New Year).
   - Monthly seasonal variations (winter smog/GRAP transit drives, hot summer AC shifts,
     monsoon rain traffic gridlock shifts).
   - Station functional typologies (Commercial/Office, Intermodal Gateways, Universities,
     Shopping/Leisure, Residential Suburbs).
3. Scenario-scaled to project-authored network ridership benchmarks (not observed station counts):
   - System average daily station entries: ~3.2M passengers/day.
   - Apex hubs: Botanical Garden (~275,000/day), Kashmere Gate (~260,000/day), Rajiv Chowk (~215,000/day).
4. Persists interchange line demand split model to data/synthetic/line_distribution_model.json.
"""
import os
import sys
import json
from datetime import date, timedelta
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'app'))

from network_topology import INTERCHANGES, LINES  # noqa: E402
from calendar_context import get_calendar_context  # noqa: E402

STATIONS_CLEANED_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'stations_cleaned.csv')
TYPOLOGY_PATH = os.path.join(BASE_DIR, 'data', 'cleaned', 'station_typologies.json')
LINE_DIST_MODEL_PATH = os.path.join(BASE_DIR, 'data', 'synthetic', 'line_distribution_model.json')
OUTPUT_SYNTHETIC_PATH = os.path.join(BASE_DIR, 'data', 'synthetic', 'dmrc_calibrated_footfall.csv')
LEGACY_OUTPUT_PATH = os.path.join(BASE_DIR, 'csvFiles', 'dmrc_footfall_data.csv')

NUM_WEEKS = 104
START_DATE = date(2025, 1, 6)  # Monday
SYSTEM_DAILY_ENTRIES_WEEKDAY = 3_200_000

# Station Functional Typologies
STATION_TYPOLOGIES = {
    # Commercial & Corporate Office Hubs
    "Barakhambha Road": "COMMERCIAL_OFFICE",
    "Rajiv Chowk": "COMMERCIAL_OFFICE",
    "Udyog Bhawan": "COMMERCIAL_OFFICE",
    "Central Secretariat": "COMMERCIAL_OFFICE",
    "ITO": "COMMERCIAL_OFFICE",
    "Nehru Place": "COMMERCIAL_OFFICE",
    "Bhikaji Cama Place": "COMMERCIAL_OFFICE",
    "Noida Sector 16": "COMMERCIAL_OFFICE",
    "Noida Sector 62": "COMMERCIAL_OFFICE",
    "Noida Electronic City": "COMMERCIAL_OFFICE",
    "Millennium City Centre Gurugram": "COMMERCIAL_OFFICE",
    "IFFCO Chowk": "COMMERCIAL_OFFICE",
    "MG Road": "COMMERCIAL_OFFICE",
    "Okhla NSIC": "COMMERCIAL_OFFICE",
    "Mohan Estate": "COMMERCIAL_OFFICE",
    "Jasola Apollo": "COMMERCIAL_OFFICE",
    "Delhi Gate": "COMMERCIAL_OFFICE",
    "Janpath": "COMMERCIAL_OFFICE",
    "Patel Chowk": "COMMERCIAL_OFFICE",

    # Intermodal Transit Gateways
    "New Delhi": "TRANSIT_GATEWAY",
    "Kashmere Gate": "TRANSIT_GATEWAY",
    "Anand Vihar ISBT": "TRANSIT_GATEWAY",
    "Hazrat Nizamuddin": "TRANSIT_GATEWAY",
    "Delhi Aerocity": "TRANSIT_GATEWAY",
    "Indira Gandhi International Airport": "TRANSIT_GATEWAY",
    "Dhaula Kuan": "TRANSIT_GATEWAY",
    "Dwarka Sector 21": "TRANSIT_GATEWAY",

    # University & College Campus Hubs
    "Vishwa Vidyalaya": "UNIVERSITY_CAMPUS",
    "GTB Nagar": "UNIVERSITY_CAMPUS",
    "Model Town": "UNIVERSITY_CAMPUS",
    "Durgabai Deshmukh South Campus": "UNIVERSITY_CAMPUS",
    "Jamia Millia Islamia": "UNIVERSITY_CAMPUS",
    "Hauz Khas": "UNIVERSITY_CAMPUS",

    # Major Retail, Bazaar & Leisure Hubs
    "Chandni Chowk": "SHOPPING_LEISURE",
    "Sarojini Nagar": "SHOPPING_LEISURE",
    "Lajpat Nagar": "SHOPPING_LEISURE",
    "INA": "SHOPPING_LEISURE",
    "Karol Bagh": "SHOPPING_LEISURE",
    "Akshardham": "SHOPPING_LEISURE",
    "Kalkaji Mandir": "SHOPPING_LEISURE",
    "Qutab Minar": "SHOPPING_LEISURE",
    "Noida Sector 18": "SHOPPING_LEISURE",
    "Botanical Garden": "SHOPPING_LEISURE",
}

# Exact factors preserve the original 2025 synthetic scenarios. For other
# years, category multipliers are explicit simulation assumptions only.
SYNTHETIC_HOLIDAY_FACTORS_2025 = {
    date(2025, 1, 26): 0.88, date(2025, 3, 14): 0.75,
    date(2025, 3, 31): 0.85, date(2025, 8, 9): 1.25,
    date(2025, 8, 15): 0.90, date(2025, 10, 2): 0.88,
    date(2025, 10, 20): 1.15, date(2025, 10, 22): 0.70,
    date(2025, 10, 23): 1.20, date(2025, 10, 27): 1.10,
    date(2025, 12, 25): 1.08, date(2025, 12, 31): 1.12,
}
SYNTHETIC_CATEGORY_FACTORS = {
    "NATIONAL": 0.90, "FESTIVAL": 0.90, "PEAK_FESTIVAL": 1.20,
    "SHOPPING_PEAK": 1.15, "LEISURE_PEAK": 1.08,
}

# Monthly Seasonal Factors in Delhi NCR
MONTHLY_FACTORS = {
    1: 1.02,   # Jan: Republic Day shopping, pleasant winter
    2: 1.04,   # Feb: Peak pleasant weather
    3: 1.03,   # Mar: Spring festivals
    4: 0.97,   # Apr: School exams, early summer
    5: 0.98,   # May: Extreme heat (AC metro shift vs road)
    6: 0.95,   # Jun: School summer vacations
    7: 1.06,   # Jul: Monsoon start, road gridlock shifts riders to metro
    8: 1.10,   # Aug: Peak monsoon + Raksha Bandhan
    9: 1.04,   # Sep: Autumn start
    10: 1.12,  # Oct: Navratri, Dussehra, Diwali shopping rush
    11: 1.14,  # Nov: GRAP winter pollution transit drives + Bhai Dooj (Network Peak Month)
    12: 1.06,  # Dec: Winter tourism & holidays
}

# Line relative volume weightings
LINE_THROUGHPUT_WEIGHT = {
    "Yellow Line": 1.40,
    "Blue Line": 1.35,
    "Blue Line branch": 0.90,
    "Violet Line": 1.05,
    "Pink Line": 1.10,
    "Red Line": 1.00,
    "Magenta Line": 0.95,
    "Green Line": 0.75,
    "Green Line branch": 0.60,
    "Orange Line": 0.45,
    "Grey Line": 0.35,
}
DEFAULT_LINE_WEIGHT = 0.85

NAMED_HUB_WEIGHT = {
    "Botanical Garden": 3.6,   # DMRC #1 (~275,000/day)
    "Kashmere Gate": 3.4,      # DMRC #2 (~260,000/day)
    "Rajiv Chowk": 2.8,        # DMRC #3 (~215,000/day)
    "New Delhi": 1.9,
    "Anand Vihar ISBT": 1.8,
    "Hauz Khas": 1.6,
    "Central Secretariat": 1.5,
    "Janakpuri West": 1.5,
    "Millennium City Centre Gurugram": 1.4,
    "Chandni Chowk": 1.3,
    "Noida Sector 18": 1.3,
}

DAY_TYPE = {
    0: ("weekday", 1.00),
    1: ("weekday", 1.00),
    2: ("weekday", 1.00),
    3: ("weekday", 1.00),
    4: ("weekday", 1.00),
    5: ("saturday", 0.85),
    6: ("sunday", 0.62),
}

HOUR_SHAPE = {
    "weekday": {
        5: 1.0, 6: 2.4, 7: 4.8, 8: 8.2, 9: 9.8, 10: 7.6,
        11: 5.4, 12: 4.8, 13: 4.6, 14: 4.6, 15: 5.0, 16: 5.8,
        17: 8.0, 18: 9.6, 19: 8.8, 20: 6.2, 21: 4.2, 22: 2.4, 23: 1.0
    },
    "saturday": {
        5: 0.6, 6: 1.6, 7: 2.8, 8: 4.2, 9: 6.0, 10: 7.0,
        11: 7.4, 12: 7.8, 13: 7.8, 14: 7.6, 15: 7.2, 16: 6.8,
        17: 6.4, 18: 6.0, 19: 5.4, 20: 4.4, 21: 3.2, 22: 1.8, 23: 1.0
    },
    "sunday": {
        5: 0.5, 6: 1.2, 7: 2.0, 8: 3.2, 9: 4.8, 10: 6.2,
        11: 7.2, 12: 7.8, 13: 7.8, 14: 7.6, 15: 7.2, 16: 6.8,
        17: 6.5, 18: 6.0, 19: 5.2, 20: 4.0, 21: 2.8, 22: 1.6, 23: 0.8
    },
}


def build_line_distribution_model():
    model = {
        "metadata": {
            "title": "Delhi Metro Interchange Line Demand Split Model",
            "provenance": "ESTIMATED_MODEL",
            "description": "Estimates passenger demand distribution across intersecting lines at interchange stations using corridor capacity, ridership volume weighting, and network centrality.",
            "disclaimer": "This is an operational estimate model based on corridor throughput ratios."
        },
        "interchanges": {}
    }
    for station, lines in INTERCHANGES.items():
        weights = {}
        for line in lines:
            line_w = LINE_THROUGHPUT_WEIGHT.get(line, DEFAULT_LINE_WEIGHT)
            route_len = len(LINES.get(line, []))
            weight = line_w * (1.0 + 0.01 * route_len)
            weights[line] = weight
            
        total_w = sum(weights.values())
        proportions = {line: round(w / total_w, 4) for line, w in weights.items()}
        diff = 1.0 - sum(proportions.values())
        first_line = list(proportions.keys())[0]
        proportions[first_line] = round(proportions[first_line] + diff, 4)
        
        model["interchanges"][station] = {
            "lines": sorted(list(lines)),
            "proportions": proportions,
            "explanation": f"Demand distributed across {len(lines)} lines: " +
                           ", ".join([f"{l}: {int(p*100)}%" for l, p in proportions.items()])
        }
        
    os.makedirs(os.path.dirname(LINE_DIST_MODEL_PATH), exist_ok=True)
    with open(LINE_DIST_MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)
    print(f"Saved line distribution model to: {LINE_DIST_MODEL_PATH}")
    return model


def compute_station_weights(df_stations):
    weights = {}
    for _, row in df_stations.iterrows():
        st = row['Station']
        line = row['Line']
        base_w = LINE_THROUGHPUT_WEIGHT.get(line, DEFAULT_LINE_WEIGHT)
        if st in INTERCHANGES:
            n_lines = len(INTERCHANGES[st])
            base_w *= (1.0 + 0.75 * (n_lines - 1))
        base_w *= NAMED_HUB_WEIGHT.get(st, 1.0)
        weights[st] = base_w
    return weights


def generate_annual_footfall_dataset(seed=42):
    df_stations = pd.read_csv(STATIONS_CLEANED_PATH)
    weights = compute_station_weights(df_stations)
    total_network_weight = sum(weights.values())
    
    # Save station typologies mapping
    typology_dict = {}
    for st in df_stations['Station']:
        typology_dict[st] = STATION_TYPOLOGIES.get(st, "RESIDENTIAL_SUBURB")
    with open(TYPOLOGY_PATH, 'w', encoding='utf-8') as f:
        json.dump(typology_dict, f, indent=2)
    print(f"Saved station typologies to: {TYPOLOGY_PATH}")

    rng = np.random.default_rng(seed)
    rows = []
    
    print(f"Generating 104-week (728 days) scenario dataset for {len(df_stations)} stations...")
    
    for week in range(NUM_WEEKS):
        for day_offset in range(7):
            d = START_DATE + timedelta(weeks=week, days=day_offset)
            day_type, day_mult = DAY_TYPE[d.weekday()]
            calendar = get_calendar_context(d)
            # A confirmed public holiday gets a non-office day curve. A listed
            # festival without confirmed closure retains the weekday work curve.
            if d.weekday() < 5 and calendar['is_public_holiday']:
                shape = HOUR_SHAPE['sunday']
            else:
                shape = HOUR_SHAPE[day_type]
            shape_total = sum(shape.values())
            
            # Apply Monthly Seasonality
            month_factor = MONTHLY_FACTORS.get(d.month, 1.0)
            
            # Apply Holiday Factors
            has_occasion = calendar['holiday_type'] > 0
            category = calendar['occasion_category']
            holiday_factor = SYNTHETIC_HOLIDAY_FACTORS_2025.get(
                d, SYNTHETIC_CATEGORY_FACTORS.get(category, 1.0)
            ) if has_occasion else 1.0
            is_holiday = int(has_occasion)
            
            daily_system_total = SYSTEM_DAILY_ENTRIES_WEEKDAY * day_mult * month_factor * holiday_factor
            
            for _, row in df_stations.iterrows():
                st = row['Station']
                line = row['Line']
                typology = typology_dict[st]
                
                # Apply Typology Specific Adjustments
                st_share = weights[st] / total_network_weight
                if calendar['is_public_holiday']:
                    if typology == "COMMERCIAL_OFFICE":
                        st_share *= 0.55  # Offices shut
                    elif typology == "SHOPPING_LEISURE":
                        st_share *= 1.45  # Malls & markets surge
                    elif typology == "TRANSIT_GATEWAY":
                        st_share *= 1.25  # Intercity transit rush
                elif d.weekday() >= 5:  # Weekend
                    if typology == "COMMERCIAL_OFFICE":
                        st_share *= 0.70
                    elif typology == "SHOPPING_LEISURE":
                        st_share *= 1.35
                        
                st_daily_expected = daily_system_total * st_share
                
                for hour, hour_w in shape.items():
                    # Hour shaping adjustments for typology
                    hw = hour_w
                    if typology == "SHOPPING_LEISURE" and hour in [16, 17, 18, 19, 20]:
                        hw *= 1.20
                    elif typology == "COMMERCIAL_OFFICE" and hour in [8, 9, 17, 18] and not is_holiday and d.weekday() < 5:
                        hw *= 1.15
                        
                    expected_hourly = st_daily_expected * (hw / shape_total)
                    footfall = int(rng.poisson(max(expected_hourly, 1.0)))
                    rows.append((d.isoformat(), hour, st, line, footfall))
                    
    df_out = pd.DataFrame(rows, columns=["Date", "Hour", "Station", "Line", "Footfall"])
    
    # Save to synthetic directory
    os.makedirs(os.path.dirname(OUTPUT_SYNTHETIC_PATH), exist_ok=True)
    df_out.to_csv(OUTPUT_SYNTHETIC_PATH, index=False)
    print(f"Wrote {len(df_out):,} explicitly synthetic rows to {OUTPUT_SYNTHETIC_PATH}")
    
    # Sync legacy path
    df_out.to_csv(LEGACY_OUTPUT_PATH, index=False)
    print(f"Synced legacy path at {LEGACY_OUTPUT_PATH}")
    
    return df_out


if __name__ == "__main__":
    build_line_distribution_model()
    generate_annual_footfall_dataset()
    print("Step 2 Annual Dataset Generation completed successfully!")
