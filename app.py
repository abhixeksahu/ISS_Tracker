# app.py
import streamlit as st
import pandas as pd
import requests
from skyfield.api import load, EarthSatellite, Topos
from datetime import datetime, timedelta

# ----------------- Configuration & Styling -----------------
# Set the layout and title for the browser tab
st.set_page_config(
    page_title="ISS Real-Time Tracker",
    page_icon="🛰️",
    layout="wide"
)

# Hide the default Streamlit branding
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# ----------------- Core Functions (from your notebook) -----------------
@st.cache_data(ttl=3600) # Cache the TLE data for 1 hour
def fetch_tle():
    """Fetches the latest ISS TLE data from CelesTrak."""
    tle_url = 'https://celestrak.org/NORAD/elements/gp.php?NAME=ISS%20(ZARYA)&FORMAT=TLE'
    try:
        response = requests.get(tle_url, timeout=10)
        response.raise_for_status()
        tle_data = response.text.strip().split('\r\n')
        return tle_data[0], tle_data[1], tle_data[2]
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching TLE data: {e}")
        return None, None, None

def calculate_passes(iss, ts, latitude, longitude):
    """Calculates upcoming ISS passes for a location."""
    observer_location = Topos(latitude_degrees=latitude, longitude_degrees=longitude)
    t0 = ts.now()
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=5)) # Search 5 days

    times, events = iss.find_events(observer_location, t0, t1, altitude_degrees=10.0)
    
    pass_data = []
    for i in range(0, len(events) - 2, 3):
        if not (events[i]==0 and events[i+1]==1 and events[i+2]==2):
             continue
        
        rise_time = times[i]
        culminate_time = times[i+1]
        set_time = times[i+2]
        alt, az, _ = (iss - observer_location).at(culminate_time).altaz()
        duration = (set_time - rise_time) * 24 * 60

        pass_data.append({
            "Rise Time (UTC)": rise_time.utc_strftime('%Y-%m-%d %H:%M'),
            "Max Altitude": f"{alt.degrees:.1f}°",
            "Direction": f"{az.degrees:.1f}°",
            "Duration (min)": f"{duration:.1f}",
        })
    return pd.DataFrame(pass_data)


# ----------------- Main App Logic -----------------
# Title of the dashboard
st.title("ISS Real-Time Tracker & Pass Predictor")

# Fetch data and create Skyfield objects
iss_name, iss_l1, iss_l2 = fetch_tle()
if not all([iss_name, iss_l1, iss_l2]):
    st.stop() # Stop the app if TLE fetch fails

ts = load.timescale()
iss = EarthSatellite(iss_l1, iss_l2, iss_name, ts)

# --- Real-Time Tracker Section ---
st.header("Live Location")

# Get current ISS position
geocentric = iss.at(ts.now())
subpoint = geocentric.subpoint()
lat, lon = subpoint.latitude.degrees, subpoint.longitude.degrees
alt_km = subpoint.elevation.km

# Display current location data in columns
col1, col2, col3 = st.columns(3)
col1.metric("Latitude", f"{lat:.4f}°")
col2.metric("Longitude", f"{lon:.4f}°")
col3.metric("Altitude", f"{alt_km:.2f} km")

# Create a DataFrame for the map marker
map_data = pd.DataFrame({'lat': [lat], 'lon': [lon]})
st.map(map_data, zoom=2)
st.caption("Map automatically updates based on the latest position from TLE data.")


# --- Pass Predictor Section ---
st.header(" Pass Predictor")

# Prepare location data
locations_data = {
    'City': ['Rourkela', 'New Delhi', 'Mumbai', 'London', 'New York', 'Tokyo', 'Sydney'],
    'Latitude': [22.2604, 28.6139, 19.0760, 51.5072, 40.7128, 35.6895, -33.8688],
    'Longitude': [84.8536, 77.2090, 72.8777, -0.1276, -74.0060, 139.6917, 151.2093]
}
locations_df = pd.DataFrame(locations_data).set_index('City')

# Create a dropdown for city selection
selected_city = st.selectbox(
    "Select a city to predict visible passes:",
    locations_df.index,
    index=0 # Default to Rourkela
)

# Get coordinates for the selected city
selected_lat = locations_df.loc[selected_city]['Latitude']
selected_lon = locations_df.loc[selected_city]['Longitude']

# Calculate and display passes
pass_df = calculate_passes(iss, ts, selected_lat, selected_lon)

if not pass_df.empty:
    st.dataframe(pass_df, use_container_width=True)
else:
    st.info(f"No visible ISS passes found for {selected_city} in the next 5 days.")