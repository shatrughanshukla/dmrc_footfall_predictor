import os
from flask import render_template, request
from app import app
import pandas as pd

base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'csvFiles'))
metro_data = pd.read_csv(
    os.path.join(base_path, 'DELHI_METRO_DATA.csv'),
    dtype={'Station': 'category', 'Line': 'category'}
)
travel_times = pd.read_csv(
    os.path.join(base_path, 'dmrc_all_station_travel_times.csv'),
    dtype={'Start Station': 'category', 'End Station': 'category',
           'Start Line': 'category', 'End Line': 'category',
           'Travel Time (minutes)': 'int32'}
)
# dmrc_footfall_data.csv has ~1.7M rows. Loading it with pandas' default
# dtypes uses 400MB+ of RAM (each repeated Station/Time string becomes its
# own Python object), which is enough to crash low-memory hosts (e.g. Render
# free tier's 512MB). category dtype + int32 cuts that to ~30MB.
footfall_data = pd.read_csv(
    os.path.join(base_path, 'dmrc_footfall_data.csv'),
    dtype={'Station': 'category', 'Line': 'category', 'Time': 'category', 'Footfall': 'int32'},
    parse_dates=['Date']
)
metro_lines = pd.read_csv(os.path.join(base_path, 'metro_lines.csv'))

if 'Day' not in footfall_data.columns:
    footfall_data['Day'] = footfall_data['Date'].dt.day_name().astype('category')

# These only depend on the full dataset, not on the request, so compute them
# once at startup instead of on every request.
BUSIEST_STATION = footfall_data.groupby('Station', observed=True)['Footfall'].sum().idxmax()
PEAK_HOUR = footfall_data.groupby('Time', observed=True)['Footfall'].sum().idxmax()

@app.route('/')
def index():
    stations = metro_data['Station'].unique()
    return render_template('index.html', stations=stations)

@app.route('/get_footfall', methods=['POST'])
def get_footfall():
    station = request.form['station']
    day = request.form['day']
    time = request.form['time']

    footfall = footfall_data[(footfall_data['Station'] == station) & 
                             (footfall_data['Day'] == day)]
    
    total_footfall = footfall['Footfall'].sum()
    time_footfall = footfall[footfall['Time'] == time]['Footfall'].sum()

    line = metro_data[metro_data['Station'] == station]['Line'].values[0]
    capacity = metro_lines[metro_lines['Line'] == line]['Total Capacity'].values[0]
    num_trains_needed = total_footfall // capacity + 1

    if num_trains_needed > 0:
        interval = 1440 / num_trains_needed
    else:
        interval = "N/A"

    travel_info = travel_times[travel_times['Start Station'] == station]

    return render_template('result.html', station=station, day=day, time=time,
                           total_footfall=total_footfall, time_footfall=time_footfall,
                           num_trains_needed=num_trains_needed, interval=interval,
                           busiest_station=BUSIEST_STATION, peak_hour=PEAK_HOUR,
                           travel_info=travel_info.to_dict(orient='records'))
