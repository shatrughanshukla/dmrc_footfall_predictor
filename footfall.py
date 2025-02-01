# import pandas as pd
# import numpy as np
# import random

# # Load the station and travel time datasets
# stations_df = pd.read_csv('DELHI_METRO_DATA.csv')
# travel_times_df = pd.read_csv('dmrc_travel_times.csv')

# # Define metro operation timings
# start_time = pd.to_datetime("05:30 AM", format="%I:%M %p")
# end_time = pd.to_datetime("11:30 PM", format="%I:%M %p")

# # Generate all minutes in the metro operation timings
# operation_minutes = pd.date_range(start=start_time, end=end_time, freq='1min').time

# # Define days of the week and footfall multipliers for weekends vs weekdays
# days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
# weekday_multiplier = 1.0
# weekend_multiplier = 0.6  # Lower footfall on weekends

# # Initialize a list to store the footfall data
# footfall_data = []

# # Total daily footfall range (between 5,00,000 and 35,00,000)
# total_daily_footfall_range = (500000, 3500000)

# # Assign each station a share of total footfall based on random weights
# stations = stations_df['Station'].unique()
# station_weights = np.random.dirichlet(np.ones(len(stations)), size=1).flatten()

# # Generate footfall data for each station, day, and minute
# for day in days_of_week:
#     is_weekend = day in ['Saturday', 'Sunday']
#     multiplier = weekend_multiplier if is_weekend else weekday_multiplier

#     # Randomly determine total daily footfall within the range
#     total_daily_footfall = random.randint(*total_daily_footfall_range)

#     for station, weight in zip(stations, station_weights):
#         station_daily_footfall = int(total_daily_footfall * weight * multiplier)

#         # Distribute footfall over all minutes in the day
#         minute_footfall = np.random.randint(13, 201, size=len(operation_minutes))
#         minute_footfall = (minute_footfall / minute_footfall.sum()) * station_daily_footfall
#         minute_footfall = minute_footfall.astype(int)  # Ensure integer values

#         for minute, footfall in zip(operation_minutes, minute_footfall):
#             footfall_data.append({
#                 "Day": day,
#                 "Station": station,
#                 "Time": minute,
#                 "Footfall": footfall
#             })

# # Convert the footfall data into a DataFrame
# footfall_df = pd.DataFrame(footfall_data)

# # Verify total daily footfall is within range
# for day in days_of_week:
#     total_footfall = footfall_df[footfall_df['Day'] == day]['Footfall'].sum()
#     print(f"{day} - Total Footfall: {total_footfall}")

# # Save to a CSV file
# output_file = 'metro_footfall_data.csv'
# footfall_df.to_csv(output_file, index=False)
# print(f"Footfall data created and saved to {output_file}!")


# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


# import os
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# import random

# # Print the current working directory
# print("Current Working Directory:", os.getcwd())

# # Load the data from the CSV files
# metro_data_path = '/home/shatrughan-shukla/Desktop/CODEEE/DELHI_METRO_DATA.csv'
# travel_times_path = '/home/shatrughan-shukla/Desktop/CODEEE/dmrc_all_station_travel_times.csv'

# metro_data = pd.read_csv(metro_data_path)
# travel_times = pd.read_csv(travel_times_path)

# # Define metro operation timings and footfall range
# start_time = datetime.strptime("05:30", "%H:%M")
# end_time = datetime.strptime("23:30", "%H:%M")
# total_minutes = int((end_time - start_time).total_seconds() / 60)

# # Define peak hours
# peak_hours = [
#     (datetime.strptime("08:00", "%H:%M"), datetime.strptime("11:00", "%H:%M")),
#     (datetime.strptime("17:00", "%H:%M"), datetime.strptime("20:00", "%H:%M"))
# ]

# # Define busiest stations
# busiest_stations = ["AIIMS", "Kashmere Gate", "Rajeev Chowk", "Rajouri Garden"]

# # Define footfall ranges
# footfall_min = 13
# footfall_max = 200

# # Function to check if a given time is within peak hours
# def is_peak_hour(time):
#     return any(start <= time <= end for start, end in peak_hours)

# # Function to generate footfall for a given minute
# def generate_footfall(station, time):
#     if station in busiest_stations:
#         if is_peak_hour(time):
#             return random.randint(150, footfall_max)
#         else:
#             return random.randint(100, 150)
#     else:
#         if is_peak_hour(time):
#             return random.randint(50, 100)
#         else:
#             return random.randint(footfall_min, 50)

# # Generate the footfall data for 7 days
# dates = pd.date_range(start="2025-01-01", periods=7)
# footfall_data = []

# for date in dates:
#     for station, line in zip(metro_data["Station"], metro_data["Line"]):
#         current_time = start_time
#         while current_time <= end_time:
#             footfall = generate_footfall(station, current_time)
#             footfall_data.append({
#                 "Date": date.strftime("%Y-%m-%d"),
#                 "Time": current_time.strftime("%H:%M"),
#                 "Station": station,
#                 "Line": line,
#                 "Footfall": footfall
#             })
#             current_time += timedelta(minutes=1)

# # Convert to DataFrame
# footfall_df = pd.DataFrame(footfall_data)

# # Save to CSV
# footfall_df.to_csv('/home/shatrughan-shukla/Desktop/CODEEE/dmrc_footfall_data.csv', index=False)

# print("Footfall data generated and saved to 'dmrc_footfall_data.csv'")

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Print the current working directory
print("Current Working Directory:", os.getcwd())

# Load the data from the CSV files
metro_data_path = '/home/shatrughan-shukla/Desktop/CODEEE/DELHI_METRO_DATA.csv'
travel_times_path = '/home/shatrughan-shukla/Desktop/CODEEE/dmrc_all_station_travel_times.csv'

metro_data = pd.read_csv(metro_data_path)
travel_times = pd.read_csv(travel_times_path)

# Define metro operation timings
start_time = datetime.strptime("05:30", "%H:%M")
end_time = datetime.strptime("23:30", "%H:%M")
total_minutes = int((end_time - start_time).total_seconds() / 60)

# Define time slots
time_slots = {
    "early_morning": (datetime.strptime("05:30", "%H:%M"), datetime.strptime("07:59", "%H:%M")),
    "morning_peak": (datetime.strptime("08:00", "%H:%M"), datetime.strptime("11:00", "%H:%M")),
    "midday": (datetime.strptime("11:01", "%H:%M"), datetime.strptime("16:59", "%H:%M")),
    "evening_peak": (datetime.strptime("17:00", "%H:%M"), datetime.strptime("20:00", "%H:%M")),
    "late_evening": (datetime.strptime("20:01", "%H:%M"), datetime.strptime("23:30", "%H:%M"))
}

# Define busiest stations
busiest_stations = ["AIIMS", "Kashmere Gate", "Rajeev Chowk", "Rajouri Garden"]

# Function to determine the time slot for a given time
def get_time_slot(time):
    for slot, (start, end) in time_slots.items():
        if start <= time <= end:
            return slot
    return None

# Function to generate footfall for a given minute
def generate_footfall(station, time):
    time_slot = get_time_slot(time)
    
    if station in busiest_stations:
        if time_slot == "morning_peak" or time_slot == "evening_peak":
            return random.randint(100, 150)
        elif time_slot == "early_morning" or time_slot == "late_evening":
            return random.randint(13, 50)
        else:  # midday
            return random.randint(50, 100)
    else:
        if time_slot == "morning_peak" or time_slot == "evening_peak":
            return random.randint(50, 100)
        elif time_slot == "early_morning" or time_slot == "late_evening":
            return random.randint(13, 30)
        else:  # midday
            return random.randint(30, 70)

# Generate the footfall data for 7 days
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

# Convert to DataFrame
footfall_df = pd.DataFrame(footfall_data)

# Save to CSV
footfall_df.to_csv('/home/shatrughan-shukla/Desktop/CODEEE/dmrc_footfall_data.csv', index=False)

print("Footfall data generated and saved to 'dmrc_footfall_data.csv'")