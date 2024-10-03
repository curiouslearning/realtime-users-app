from flask import Flask, jsonify, render_template
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.cloud import secretmanager
import json
from time import sleep
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from google.api_core.exceptions import ResourceExhausted
from geopy.geocoders import OpenCage

app = Flask(__name__)

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
    api_key = "fc14231c09b94f1494d254d6ad3efacf"  # Replace with your actual API key
    geolocator =  OpenCage(api_key)
    try:
        location = geolocator.geocode(f"{city}, {country}", timeout=10)
        if location:
            return location.latitude, location.longitude
    except GeocoderTimedOut:
        print(f"Geocoding timed out for {city}, {country}")
    except GeocoderServiceError as e:
        print(f"Geocoding error: {str(e)}")
    
    return None, None


@app.route('/')
def index():
    """
    Serve the HTML map page.
    """
    return render_template('globe.html')

@app.route('/realtime', methods=['GET'])


def get_realtime_data():
    retries = 3
    while retries > 0:
        try:
            credentials = get_gcp_credentials()
            client = BetaAnalyticsDataClient(credentials=credentials)
            property_id = "175820453"
            request = {
                "property": f"properties/{property_id}",
                "dimensions": [{"name": "country"}, {"name": "city"}],
                "metrics": [{"name": "activeUsers"}]
            }
            response = client.run_realtime_report(request=request)
            response_data = []
            for row in response.rows:
                country = row.dimension_values[0].value
                city = row.dimension_values[1].value
                active_users = row.metric_values[0].value
                lat, lon = get_coordinates(city, country)
                response_data.append({
                    'country': country,
                    'city': city,
                    'active_users': active_users,
                    'latitude': lat,
                    'longitude': lon
                })

            return response_data
        except ResourceExhausted as e:
            retries -= 1
            print(f"Quota exhausted, retrying in 60 seconds... ({3 - retries} of 3 retries)")
            time.sleep(60)  # Wait for 1 minute before retrying
    return {"error": "Quota exhausted. Please try again later."}


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
