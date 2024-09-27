from google.cloud import secretmanager
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
import json

def get_gcp_credentials():
    # Get credentials from Google Secret Manager
    client = secretmanager.SecretManagerServiceClient()

    # Retrieve the secret that holds the service account key
    name = "projects/405806232197/secrets/service_account_json/versions/latest"
    response = client.access_secret_version(name=name)
    key = response.payload.data.decode("UTF-8")

    # Use the key to load service account credentials
    service_account_info = json.loads(key)
    gcp_credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/analytics.readonly"
        ]
    )

    return gcp_credentials

# Fetch credentials
credentials = get_gcp_credentials()

# Initialize the GA4 API client
client = BetaAnalyticsDataClient(credentials=credentials)

# GA4 Property ID
property_id = "175820453"

# Create the Real-Time Report Request
request = {
    "property": f"properties/{property_id}",
    "dimensions": [{"name": "country"}, {"name": "city"}],
    "metrics": [{"name": "activeUsers"}]
}

# Fetch the real-time data from GA4
response = client.run_realtime_report(request=request)

# Print the response to check the output
print(response)
