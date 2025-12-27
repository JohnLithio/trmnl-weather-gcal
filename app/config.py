import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/oauth/callback")

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

# Calendar configuration
CALENDAR_IDS = [
    cal_id.strip()
    for cal_id in os.getenv("CALENDAR_IDS", "primary").split(",")
    if cal_id.strip()
]
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Storage
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
TOKEN_FILE = DATA_DIR / "google_token.json"

# API Security
API_SECRET = os.getenv("API_SECRET", "")

# Weather configuration (Open-Meteo)
# Coordinates must be set in .env for weather to work
WEATHER_LAT = float(os.getenv("WEATHER_LAT", "0"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "0"))
