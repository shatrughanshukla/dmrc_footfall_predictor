import os
from flask import render_template, request
from app import app
import pandas as pd

# Load the CSV files
base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'csvFiles'))
metro_data = pd.read_csv(os.path.join(base_path, 'DELHI_METRO_DATA.csv'))
travel_times = pd.read_csv(os.path.join(base_path, 'dmrc_all_station_travel_times.csv'))
footfall_data = pd.read_csv(os.path.join(base_path, 'dmrc_footfall_data.csv'))
metro_lines = pd.read_csv(os.path.join(base_path, 'metro_lines.csv'))

# Ensure 'Day' column exists in footfall_data
if 'Day' not in footfall_data.columns:
    footfall_data['Date'] = pd.to_datetime(footfall_data['Date'])
    footfall_data['Day'] = footfall_data['Date'].dt.day_name()

@app.route('/')
def index():
    stations = metro_data['Station'].unique()
    return render_template('index.html', stations=stations)

@app.route('/get_footfall', methods=['POST'])
def get_footfall():
    station = request.form['station']
    day = request.form['day']
    time = request.form['time']

    # Filter footfall data for the selected station and day
    footfall = footfall_data[(footfall_data['Station'] == station) & 
                             (footfall_data['Day'] == day)]
    
    # Predict total footfall for the entire day
    total_footfall = footfall['Footfall'].sum()

    # Predict footfall at the specific time
    time_footfall = footfall[footfall['Time'] == time]['Footfall'].sum()

    line = metro_data[metro_data['Station'] == station]['Line'].values[0]
    capacity = metro_lines[metro_lines['Line'] == line]['Total Capacity'].values[0]
    num_trains_needed = total_footfall // capacity + 1

    # Calculate train interval
    if num_trains_needed > 0:
        interval = 1440 / num_trains_needed  # Calculate interval for a 24-hour day
    else:
        interval = "N/A"

    # Analyze busiest stations and peak hours
    busiest_station = footfall_data.groupby('Station')['Footfall'].sum().idxmax()
    peak_hour = footfall_data.groupby('Time')['Footfall'].sum().idxmax()

    # Analyze travel times
    travel_info = travel_times[travel_times['Start Station'] == station]

    return render_template('result.html', station=station, day=day, time=time,
                           total_footfall=total_footfall, time_footfall=time_footfall,
                           num_trains_needed=num_trains_needed, interval=interval,
                           busiest_station=busiest_station, peak_hour=peak_hour,
                           travel_info=travel_info.to_dict(orient='records'))