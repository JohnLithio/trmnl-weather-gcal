# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TRMNL Private Plugin for Google Calendar + Weather. A FastAPI backend that serves calendar events and weather data to a TRMNL e-ink display device. Uses Google OAuth for calendar access and Open-Meteo for weather (free, no API key).

## Common Commands

```bash
# Development
uv sync                                    # Install dependencies
uv run uvicorn app.main:app --reload       # Run locally on port 8000

# Deployment to Cloud Run (replace PROJECT_ID and REGION)
docker build --platform linux/amd64 -t REGION-docker.pkg.dev/PROJECT_ID/REPO/app:latest .
docker push REGION-docker.pkg.dev/PROJECT_ID/REPO/app:latest
gcloud run deploy SERVICE_NAME --image REGION-docker.pkg.dev/PROJECT_ID/REPO/app:latest --region REGION
```

## Deployment Notes

**Backend changes** (anything in `app/`): Requires Docker build + push + gcloud deploy.

**markup.liquid**: This file is NOT deployed. It's a Liquid template that gets copy/pasted directly into the TRMNL dashboard UI by the user. Changes to markup.liquid only require updating it in the TRMNL Private Plugin settings.

## Architecture

- **app/main.py** - FastAPI routes: `/setup` (OAuth UI), `/oauth/callback`, `/api/events` (main data endpoint)
- **app/calendar.py** - Google Calendar API integration, fetches 365 days of events from multiple calendars
- **app/oauth.py** - Google OAuth 2.0 flow with refresh token handling
- **app/storage.py** - Token persistence: local file for dev, GCP Secret Manager for production (triggered by GCP_PROJECT env var)
- **app/weather.py** - Open-Meteo API for weather + air quality data
- **app/config.py** - Environment variable loading

## API Response Structure

`GET /api/events` returns JSON with:
- `events[]` - Calendar events with date_formatted, summary, start_time, end_time, all_day
- `weather.current` - temp, feels_like, humidity, condition (from weather_code)
- `weather.today` - high, low, sunrise, sunset, max_uv, max_aqi
- `weather.hourly[]` - 24-hour forecast with temp, precip_chance, wind_speed, wind_dir, uv, aqi, icon
- `weather.daily[]` - 7-day forecast with high, low, precip_chance

## Key Behaviors

- Weather failures return `weather: null` and don't break the calendar data
- Timezone handling: Server runs in UTC (Cloud Run), but uses `TIMEZONE` env var for all formatting
- Hourly forecast filters to "next 24 hours" based on current time in configured timezone
- Events sorted by date, then all-day events first, then by start time
