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
import requests

# Initialize Flask app
app = Flask(__name__)

# Set up caching (in this case, we're using simple in-memory caching)
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # Cache timeout in seconds (5 minutes)

cache = Cache(app)


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


def get_coordinates(city, country):
    """
    Fetch latitude and longitude using the Google Geocoding API.
    """
    api_key = "AIzaSyDeBC6RCnaUPoi2ch_dXrOln03mW9FWw5E"  
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': f"{city}, {country}",
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            print(f"Geocoding failed for {city}, {country}: {data['status']}")
    except requests.exceptions.RequestException as e:
        print(f"Error during Google Geocoding API request: {str(e)}")
    
    return None, None


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
@cache.cached(timeout=300)  # Cache the API data for 5 minutes
def get_realtime_data():
    retries = 3
    while retries > 0:
        try:
            credentials = get_gcp_credentials()
            client = BetaAnalyticsDataClient(credentials=credentials)
            property_id = "159643920"
            request = {
                "property": f"properties/{property_id}",
                "dimensions": [{"name": "country"}, {"name": "city"}],
                "metrics": [{"name": "activeUsers"}],
                "minute_ranges": [
                    {
                        "start_minutes_ago": 29,
                        "end_minutes_ago": 0
                    }
                ]
            }
            print ("Calling geocoding API")
            response = client.run_realtime_report(request=request)
            response_data = []
            for row in response.rows:
                country = row.dimension_values[0].value
                city = row.dimension_values[1].value
                active_users = row.metric_values[0].value

                # Check if the coordinates are already cached
                cache_key = f"{city},{country}"
                cached_coords = cache.get(cache_key)

                if cached_coords:
                    lat, lon = cached_coords
                else:
                    lat, lon = get_coordinates(city, country)
                    if lat and lon:
                        # Store the coordinates in the cache for future use
                        cache.set(cache_key, (lat, lon))

                response_data.append({
                    'country': country,
                    'city': city,
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
