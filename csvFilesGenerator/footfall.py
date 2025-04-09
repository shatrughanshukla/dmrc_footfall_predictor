import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

print("Current Working Directory:", os.getcwd())
metro_data_path = '/home/shatrughan-shukla/Desktop/CODEEE/DELHI_METRO_DATA.csv'
travel_times_path = '/home/shatrughan-shukla/Desktop/CODEEE/dmrc_all_station_travel_times.csv'

metro_data = pd.read_csv(metro_data_path)
travel_times = pd.read_csv(travel_times_path)
start_time = datetime.strptime("05:30", "%H:%M")
end_time = datetime.strptime("23:30", "%H:%M")
total_minutes = int((end_time - start_time).total_seconds() / 60)
time_slots = {
    "early_morning": (datetime.strptime("05:30", "%H:%M"), datetime.strptime("07:59", "%H:%M")),
    "morning_peak": (datetime.strptime("08:00", "%H:%M"), datetime.strptime("11:00", "%H:%M")),
    "midday": (datetime.strptime("11:01", "%H:%M"), datetime.strptime("16:59", "%H:%M")),
    "evening_peak": (datetime.strptime("17:00", "%H:%M"), datetime.strptime("20:00", "%H:%M")),
    "late_evening": (datetime.strptime("20:01", "%H:%M"), datetime.strptime("23:30", "%H:%M"))
}

busiest_stations = ["AIIMS", "Kashmere Gate", "Rajeev Chowk", "Rajouri Garden"]

def get_time_slot(time):
    for slot, (start, end) in time_slots.items():
        if start <= time <= end:
            return slot
    return None
def generate_footfall(station, time):
    time_slot = get_time_slot(time)
    
    if station in busiest_stations:
        if time_slot == "morning_peak" or time_slot == "evening_peak":
            return random.randint(100, 150)
        elif time_slot == "early_morning" or time_slot == "late_evening":
            return random.randint(13, 50)
        else:
            return random.randint(50, 100)
    else:
        if time_slot == "morning_peak" or time_slot == "evening_peak":
            return random.randint(50, 100)
        elif time_slot == "early_morning" or time_slot == "late_evening":
            return random.randint(13, 30)
        else:
            return random.randint(30, 70)

dates = pd.date_range(start="2025-01-01", periods=7)
footfall_data = []

for date in dates:
    for station, line in zip(metro_data["Station"], metro_data["Line"]):
        current_time = start_time
        while current_time <= end_time:
            footfall = generate_footfall(station, current_time)
            footfall_data.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Time": current_time.strftime("%H:%M"),
                "Station": station,
                "Line": line,
                "Footfall": footfall
            })
            current_time += timedelta(minutes=1)

footfall_df = pd.DataFrame(footfall_data)
footfall_df.to_csv('/home/shatrughan-shukla/Desktop/CODEEE/dmrc_footfall_data.csv', index=False)

print("Footfall data generated and saved to 'dmrc_footfall_data.csv'")