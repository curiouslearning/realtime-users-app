from flask import Flask, jsonify, render_template
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.cloud import secretmanager
import json
from time import sleep
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from google.api_core.exceptions import ResourceExhausted
from flask_caching import Cache


# Initialize Flask app
app = Flask(__name__)

# Set up caching (in this case, we're using simple in-memory caching)
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 120 # Cache timeout in seconds

cache = Cache(app)

# Load static coordinates once at startup
with open('country_coordinates.json') as f:
    country_data = json.load(f)["ref_country_codes"]

# Create a lookup dictionary for countries
country_coordinates = {entry["country"]: (entry["latitude"], entry["longitude"]) for entry in country_data}

def get_gcp_credentials():
    client = secretmanager.SecretManagerServiceClient()
    name = "projects/405806232197/secrets/service_account_json/versions/latest"
    response = client.access_secret_version(name=name)
    key = response.payload.data.decode("UTF-8")
    service_account_info = json.loads(key)
    gcp_credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/analytics.readonly"
        ]
    )
    return gcp_credentials

@app.route('/')
def index():
    """
    Serve the HTML globe page.
    """
    return render_template('world_map.html')


@app.route('/globe')
def split_view():
    """
    Serve the HTML split view page with two iframes.
    """
    return render_template('globe.html')


@app.route('/world_map')
def map_colored():
    """
    Serve the world_map.html page.
    """
    return render_template('world_map.html')


@app.route('/realtime', methods=['GET'])
@cache.cached(timeout=120)  # Cache the API data
def get_realtime_data():
    retries = 3
    while retries > 0:

        try:
            credentials = get_gcp_credentials()
            client = BetaAnalyticsDataClient(credentials=credentials)
            property_id = "159643920"
            request = {
                "property": f"properties/{property_id}",
                "dimensions": [{"name": "country"}],
                "metrics": [{"name": "activeUsers"}],
                "minute_ranges": [
                    {
                        "start_minutes_ago": 29,
                        "end_minutes_ago": 0
                    }
                ]
            }
            print("Calling client.run_realtime_report")
            response = client.run_realtime_report(request=request)

            response_data = []
            for row in response.rows:
                country = row.dimension_values[0].value
                active_users = row.metric_values[0].value

                # Get coordinates from the dictionary based on the country name
                coords = country_coordinates.get(country)
                if coords:
                    lat, lon = coords
                else:
                    print(f"Coordinates not found for {country}")
                    lat, lon = None, None  # Set to None if coordinates are not available

                response_data.append({
                    'country': country,
                    'active_users': active_users,
                    'latitude': lat,
                    'longitude': lon
                })

            return jsonify(response_data)
        except ResourceExhausted as e:
            retries -= 1
            print(f"Quota exhausted, retrying in 60 seconds... ({3 - retries} of 3 retries)")
            time.sleep(60)  # Wait for 1 minute before retrying
    return jsonify({"error": "Quota exhausted. Please try again later."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)