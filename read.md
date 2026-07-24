# DMRC Footfall Predictor

A Flask web app that predicts station-wise footfall on the Delhi Metro (DMRC) network and estimates the train frequency needed to handle that crowd.

Select a station, day, and time — the app returns:
- Total and time-slot footfall for that station/day
- Estimated number of trains needed based on line capacity
- Suggested train interval
- The busiest station and peak hour across the network
- Travel time info to connected stations

## Tech Stack

- **Backend**: Python, Flask
- **Data processing**: pandas
- **Frontend**: HTML/CSS (server-rendered templates)
- **Production server**: Gunicorn

## Project Structure

```
dmrc_footfall_predictor/
├── app/
│   ├── __init__.py          # Flask app initialization
│   ├── routes.py            # Route handlers and prediction logic
│   ├── templates/
│   │   ├── index.html       # Station/day/time selection form
│   │   └── result.html      # Prediction results page
│   └── static/               # Logo and animation assets
├── csvFiles/
│   ├── DELHI_METRO_DATA.csv               # Station -> line mapping with coordinates
│   ├── dmrc_footfall_data.csv             # Historical footfall by station/day/time
│   ├── dmrc_all_station_travel_times.csv  # Travel time between station pairs
│   └── metro_lines.csv                    # Line capacity and coach info
├── csvFilesGenerator/         # Scripts used to originally generate the CSV datasets
├── run.py                    # App entry point
├── requirements.txt
└── Procfile                  # Start command for deployment (Render/Railway)
```

## Running Locally

1. Clone the repo and move into it:
   ```bash
   git clone <your-repo-url>
   cd dmrc_footfall_predictor
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the app:
   ```bash
   python run.py
   ```

4. Open `http://localhost:5000` in your browser.

## Deployment

This project is set up to deploy on **Render** or **Railway** using the included `Procfile` and `requirements.txt`.

Quick Render steps:
1. Push this repo to GitHub.
2. Create a new **Web Service** on [Render](https://render.com), connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn run:app`

## Data

Footfall figures are historical/simulated data (see `csvFilesGenerator/` for how the datasets were built) used for demonstration and prediction purposes, not live DMRC ridership data.
