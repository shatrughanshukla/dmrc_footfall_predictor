"""
Rebuilds dmrc_footfall_data.csv as an actually-structured model instead of
uniform random noise. What was wrong with the original (see git history):

  1. Only 7 calendar dates were ever generated (one per weekday) -- so
     "footfall for a Monday" was one arbitrary random draw, not an average
     of anything.
  2. generate_footfall() only knew two things: is this one of 4 hardcoded
     station names, and which of 5 time-of-day buckets are we in. Every
     other station and every weekday were treated identically.
  3. Nothing was calibrated to any real number -- the totals could have
     been anything and looked the same.

This version instead:
  - Generates 12 full weeks (84 days), so every weekday has 12 independent
    samples the app can average over instead of trusting one draw.
  - Gives every station a demand *weight* derived from real structure: how
    many lines it interchanges between (from network_topology.py) and which
    line it's on (DMRC's busiest lines carry more riders than its quietest
    ones). A handful of stations that are well-known to be disproportionately
    busy even among interchanges (Rajiv Chowk, Kashmere Gate, New Delhi) get
    a documented extra boost on top of that.
  - Distinguishes weekday / Saturday / Sunday ridership levels and uses a
    different hour-of-day shape for weekday commute traffic vs. weekend
    leisure traffic.
  - Calibrates the whole network to Delhi Metro's own published average
    daily ridership (~2.76 million/day, per Wikipedia's "List of Delhi Metro
    stations" citing Hindustan Times) rather than an arbitrary range, and
    generates at HOURLY granularity (not per-minute) -- per-minute precision
    on synthetic data was fake precision; a station's ridership doesn't
    actually vary minute to minute, an operations planner thinks in hours.
  - Uses numpy's Poisson distribution for the per-station-hour draw, so
    variance scales naturally with the expected count instead of being an
    arbitrary randint() range.

Run: python3 footfall.py   (writes ../csvFiles/dmrc_footfall_data.csv)
"""
import os
import csv
from datetime import date, timedelta

import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
from network_topology import INTERCHANGES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
METRO_DATA_PATH = os.path.join(HERE, '..', 'csvFiles', 'DELHI_METRO_DATA.csv')
OUTPUT_PATH = os.path.join(HERE, '..', 'csvFiles', 'dmrc_footfall_data.csv')

NUM_WEEKS = 12
START_DATE = date(2025, 1, 6)  # a Monday -- keeps full weeks aligned
SYSTEM_DAILY_RIDERSHIP_WEEKDAY = 2_760_000  # DMRC's published average, sourced above

# Relative demand per line -- approximate, illustrative ordering based on
# each line's well-known role in the network (Blue/Yellow are the oldest,
# longest, most central lines; Grey/Airport Express are the network's
# lightest-used). NOT DMRC's actual published per-line ridership breakdown,
# which isn't public at this granularity -- documented here as an assumption,
# not a fact.
LINE_WEIGHT = {
    "Blue Line": 1.30, "Blue Line branch": 0.95,
    "Yellow Line": 1.25,
    "Violet Line": 1.10,
    "Pink Line": 1.05,
    "Red Line": 1.00,
    "Magenta Line": 0.90,
    "Green Line": 0.80, "Green Line branch": 0.70,
    "Grey Line": 0.40,
    "Orange Line": 0.50,  # Airport Express -- famously runs well under capacity
}
DEFAULT_LINE_WEIGHT = 0.85

# A small number of stations are known (from DMRC's own press coverage) to be
# disproportionately busier than even a typical interchange -- documented
# multiplier, not derived from data we have.
NAMED_HUB_BOOST = {
    "Rajiv Chowk": 1.6,
    "Kashmere Gate": 1.4,
    "New Delhi": 1.3,
}

# Day-type multiplier relative to a weekday, and which hourly shape to use.
DAY_TYPE = {
    0: ("weekday", 1.00), 1: ("weekday", 1.00), 2: ("weekday", 1.00),
    3: ("weekday", 1.00), 4: ("weekday", 1.00),
    5: ("saturday", 0.85),
    6: ("sunday", 0.60),
}

# Fraction of that day-type's ridership occurring in each operating hour
# (05:30-23:30). Bimodal commute peaks on weekdays; flatter, later, and
# lighter on weekends. Normalized in code, so these don't need to sum to 1.
HOUR_SHAPE = {
    "weekday": {5: 1, 6: 2.5, 7: 4.5, 8: 7.5, 9: 8.5, 10: 7, 11: 5.5, 12: 5,
                13: 5, 14: 5, 15: 5, 16: 5.5, 17: 7.5, 18: 9, 19: 8, 20: 6,
                21: 4, 22: 2.5, 23: 1},
    "saturday": {5: 0.5, 6: 1.5, 7: 2.5, 8: 4, 9: 5.5, 10: 6.5, 11: 7, 12: 7.5,
                 13: 7.5, 14: 7.5, 15: 7, 16: 6.5, 17: 6, 18: 5.5, 19: 5,
                 20: 4, 21: 2.5, 22: 1.5, 23: 1},
    "sunday": {5: 0.5, 6: 1, 7: 2, 8: 3, 9: 4.5, 10: 6, 11: 7, 12: 7.5,
               13: 7.5, 14: 7.5, 15: 7, 16: 6.5, 17: 6, 18: 5.5, 19: 5,
               20: 3.5, 21: 2, 22: 1, 23: 0.5},
}


def load_stations(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append((row["Station"].strip().rstrip("†‡*#¤").strip(), row["Line"].strip()))
    return rows


def station_weights(stations):
    """Returns {(station, line): weight}, not yet normalized."""
    weights = {}
    for station, line in stations:
        w = LINE_WEIGHT.get(line, DEFAULT_LINE_WEIGHT)
        n_lines = len(INTERCHANGES.get(station, {line}))
        if n_lines > 1:
            w *= 1 + 0.8 * (n_lines - 1)
        w *= NAMED_HUB_BOOST.get(station, 1.0)
        weights[(station, line)] = w
    return weights


def generate(num_weeks=NUM_WEEKS, seed=42):
    rng = np.random.default_rng(seed)
    stations = load_stations(METRO_DATA_PATH)
    weights = station_weights(stations)
    total_weight = sum(weights.values())

    rows = []
    for week in range(num_weeks):
        for day_offset in range(7):
            d = START_DATE + timedelta(weeks=week, days=day_offset)
            day_type, day_multiplier = DAY_TYPE[d.weekday()]
            shape = HOUR_SHAPE[day_type]
            shape_total = sum(shape.values())
            daily_system_total = SYSTEM_DAILY_RIDERSHIP_WEEKDAY * day_multiplier

            for (station, line), w in weights.items():
                station_share = w / total_weight
                station_daily_total = daily_system_total * station_share
                for hour, hour_w in shape.items():
                    expected = station_daily_total * (hour_w / shape_total)
                    footfall = int(rng.poisson(max(expected, 0.1)))
                    rows.append((d.isoformat(), hour, station, line, footfall))
    return rows


if __name__ == "__main__":
    rows = generate()
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Hour", "Station", "Line", "Footfall"])
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} rows to {OUTPUT_PATH}")
    print(f"Spans {NUM_WEEKS} weeks starting {START_DATE.isoformat()} "
          f"({NUM_WEEKS} samples per weekday for averaging)")
