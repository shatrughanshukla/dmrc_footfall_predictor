import pandas as pd
import math
from itertools import permutations

# Load the dataset
stations_df = pd.read_csv('DELHI_METRO_DATA.csv')

# Inspect the first few rows
print("Initial Dataset Preview:")
print(stations_df.head())

# Ensure the dataset has necessary columns
required_columns = ['Station', 'Line', 'Latitude', 'Longitude']
assert all(col in stations_df.columns for col in required_columns), "Dataset must contain Station, Line, Latitude, Longitude."

# Sort stations by Line, then by Latitude, and Longitude
stations_df = stations_df.sort_values(by=['Line', 'Latitude', 'Longitude']).reset_index(drop=True)

# Inspect sorted data
print("Sorted Dataset Preview:")
print(stations_df.head())

# Function to calculate distance using the Haversine formula
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c  # Distance in km

# Example: Calculate distance between two stations
example_distance = haversine(28.7041, 77.1025, 28.5355, 77.3910)  # Example latitudes/longitudes
print(f"Example Distance: {example_distance:.2f} km")

# List to store travel time data
travel_times = []

# Create permutations for all station pairs
station_pairs = permutations(stations_df.index, 2)

# Calculate travel time for every station pair
for start_idx, end_idx in station_pairs:
    start_station = stations_df.iloc[start_idx]
    end_station = stations_df.iloc[end_idx]
    
    # Validate coordinates
    if pd.notna(start_station['Latitude']) and pd.notna(start_station['Longitude']) \
            and pd.notna(end_station['Latitude']) and pd.notna(end_station['Longitude']):
        # Calculate distance
        distance_km = haversine(start_station['Latitude'], start_station['Longitude'],
                                end_station['Latitude'], end_station['Longitude'])
        
        # Check for valid distance
        if distance_km > 0:
            # Estimate travel time (average speed: 40 km/h, stop time: 30 seconds)
            travel_time = round((distance_km / 40) * 60 + 0.5)  # Time in minutes
            
            # Add data to the list
            travel_times.append({
                "Start Station": start_station['Station'],
                "End Station": end_station['Station'],
                "Start Line": start_station['Line'],
                "End Line": end_station['Line'],
                "Travel Time (minutes)": travel_time
            })
        else:
            print(f"Skipping zero-distance stations: {start_station['Station']} -> {end_station['Station']}")
    else:
        print(f"Invalid coordinates for stations: {start_station['Station']} or {end_station['Station']}")

# Convert to DataFrame
travel_times_df = pd.DataFrame(travel_times)

# Preview travel time dataset
print("Travel Time Dataset Preview:")
print(travel_times_df.head())

# Save the dataset to a CSV file
output_file = 'dmrc_all_station_travel_times.csv'
travel_times_df.to_csv(output_file, index=False)

print(f"Travel time dataset created and saved as {output_file}!")
