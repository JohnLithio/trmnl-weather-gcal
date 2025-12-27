# TRMNL Google Calendar + Weather Plugin

A TRMNL Private Plugin that displays your Google Calendar events and weather forecast on your e-ink display.

## Features

- Fetches events from multiple Google Calendars
- Shows events for the next 365 days (vs 30 days in the built-in plugin)
- Real-time weather with hourly/daily forecasts (Open-Meteo API - free, no key required)
- Air quality index and UV index
- Simple SVG weather icons optimized for e-ink
- Returns JSON data for TRMNL's Liquid templates

## Prerequisites

- [Google Cloud](https://cloud.google.com/) account
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- [Docker](https://docs.docker.com/get-docker/) installed (for local builds)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager (for local development)
- A [TRMNL](https://usetrmnl.com/) device

## Deployment Guide

### Step 1: Create GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., `trmnl-calendar`)
3. Note your **Project ID** (you'll need it later)

### Step 2: Enable Required APIs

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable calendar-json.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** user type
3. Fill in app name (e.g., "TRMNL Calendar")
4. Add your email as a test user
5. Add scope: `https://www.googleapis.com/auth/calendar.readonly`

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Choose **Web application**
4. Add authorized redirect URI: `https://placeholder.com/oauth/callback`
   - (You'll update this after getting your Cloud Run URL)
5. Save the **Client ID** and **Client Secret**

### Step 5: Create Artifact Registry Repository

```bash
gcloud artifacts repositories create trmnl-calendar \
  --repository-format=docker \
  --location=us-central1
```

### Step 6: Build and Push Docker Image

```bash
# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build the image
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest
```

### Step 7: Create Secret for Token Storage

```bash
# Create the secret
gcloud secrets create trmnl-google-token --replication-policy=automatic

# Get your project number
gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"

# Grant Cloud Run service account access (replace PROJECT_NUMBER)
gcloud secrets add-iam-policy-binding trmnl-google-token \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding trmnl-google-token \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretVersionAdder"
```

### Step 8: Deploy to Cloud Run

```bash
# Find your coordinates at https://www.latlong.net/

gcloud run deploy trmnl-calendar \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLIENT_ID=YOUR_CLIENT_ID" \
  --set-env-vars "GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET" \
  --set-env-vars "GOOGLE_REDIRECT_URI=https://CLOUD_RUN_URL/oauth/callback" \
  --set-env-vars "GCP_PROJECT=YOUR_PROJECT_ID" \
  --set-env-vars "TIMEZONE=America/New_York" \
  --set-env-vars "WEATHER_LAT=40.7128" \
  --set-env-vars "WEATHER_LON=-74.0060"
```

Note the **Service URL** from the output (e.g., `https://trmnl-calendar-abc123-uc.a.run.app`)

### Step 9: Update OAuth Redirect URI

1. Go back to **APIs & Services → Credentials**
2. Edit your OAuth client
3. Update the redirect URI to: `https://YOUR_CLOUD_RUN_URL/oauth/callback`
4. Redeploy with the correct redirect URI:

```bash
gcloud run deploy trmnl-calendar \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest \
  --region us-central1 \
  --update-env-vars "GOOGLE_REDIRECT_URI=https://YOUR_CLOUD_RUN_URL/oauth/callback"
```

### Step 10: Connect Google Calendar

1. Visit `https://YOUR_CLOUD_RUN_URL/setup`
2. Click **Connect Google Calendar**
3. Authorize access to your calendar
4. You should see "Connected" status

### Step 11: Create TRMNL Private Plugin

1. In TRMNL, go to **Plugins → Private Plugin → New**
2. Set **Strategy**: Polling
3. Set **Polling URL**: `https://YOUR_CLOUD_RUN_URL/api/events`
4. Set refresh interval (e.g., 15 minutes)
5. Copy contents of `markup.liquid` into the **Markup Editor**
6. Save and add to your playlist

## Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/trmnl-calendar.git
cd trmnl-calendar

# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your Google OAuth credentials and coordinates

# Run the server
uv run uvicorn app.main:app --reload
```

Visit `http://localhost:8000/setup` to connect your Google account.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLIENT_ID` | OAuth client ID from GCP | Yes |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret from GCP | Yes |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | Yes |
| `TIMEZONE` | IANA timezone (e.g., `America/New_York`) | Yes |
| `WEATHER_LAT` | Latitude for weather data | Yes |
| `WEATHER_LON` | Longitude for weather data | Yes |
| `GCP_PROJECT` | GCP project ID (enables Secret Manager) | For Cloud Run |
| `CALENDAR_IDS` | Comma-separated calendar IDs | No (default: `primary`) |
| `API_SECRET` | Bearer token for API auth | No |

## API Response

`GET /api/events` returns:

```json
{
  "generated_at": "2025-12-26T10:30:00-05:00",
  "timezone": "America/New_York",
  "event_count": 15,
  "events": [
    {
      "id": "abc123",
      "date": "2025-12-26",
      "date_formatted": "Thu Dec 26",
      "summary": "Team Meeting",
      "start_time": "10:00 AM",
      "end_time": "11:00 AM",
      "all_day": false,
      "location": "Conference Room A",
      "calendar_id": "primary"
    }
  ],
  "weather": {
    "current": {
      "temp": 32,
      "feels_like": 28,
      "humidity": 65,
      "condition": "Partly Cloudy"
    },
    "today": {
      "high": 38,
      "low": 25,
      "sunrise": "7:15 AM",
      "sunset": "4:45 PM",
      "max_uv": 2.5,
      "max_aqi": 45
    },
    "hourly": [
      {
        "hour": "1 PM",
        "temp": 35,
        "precip_chance": 10,
        "wind_speed": 12,
        "wind_dir": "NW",
        "uv": 2,
        "aqi": 42,
        "icon": "<svg>...</svg>"
      }
    ],
    "daily": [
      {
        "date": "Fri Dec 27",
        "high": 40,
        "low": 28,
        "precip_chance": 15
      }
    ]
  }
}
```

## Updating

To deploy updates after making changes:

```bash
# Rebuild and push
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest

# Deploy new revision
gcloud run deploy trmnl-calendar \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/trmnl-calendar/app:latest \
  --region us-central1
```

**Note:** Changes to `markup.liquid` don't require redeployment—just update it in the TRMNL dashboard.

## License

MIT
