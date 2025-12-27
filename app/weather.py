"""Weather data fetching from Open-Meteo API."""

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import TIMEZONE, WEATHER_LAT, WEATHER_LON


class WeatherError(Exception):
    """Exception raised for weather API errors."""

    pass


# Open-Meteo API endpoints
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def _degrees_to_compass(degrees: float) -> str:
    """Convert wind direction in degrees to compass direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(degrees / 22.5) % 16
    return directions[index]


def _format_time(iso_time: str) -> str:
    """Format ISO time string to 12-hour format (e.g., '7:15 AM')."""
    dt = datetime.fromisoformat(iso_time)
    return dt.strftime("%-I:%M %p")


def _format_hour(iso_time: str) -> str:
    """Format ISO time string to hour (e.g., '1 PM')."""
    dt = datetime.fromisoformat(iso_time)
    return dt.strftime("%-I %p")


def _format_date(iso_date: str) -> str:
    """Format ISO date string to readable format (e.g., 'Fri Dec 27')."""
    dt = datetime.fromisoformat(iso_date)
    return dt.strftime("%a %b %-d")


def _weather_code_to_icon(code: int) -> str:
    """Convert WMO weather code to simple SVG icon for e-ink display."""
    # Simple black SVG icons optimized for e-ink (16x16)
    sun = '<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="4" fill="#000"/><g stroke="#000" stroke-width="1.5"><line x1="8" y1="1" x2="8" y2="3"/><line x1="8" y1="13" x2="8" y2="15"/><line x1="1" y1="8" x2="3" y2="8"/><line x1="13" y1="8" x2="15" y2="8"/><line x1="3" y1="3" x2="4.5" y2="4.5"/><line x1="11.5" y1="11.5" x2="13" y2="13"/><line x1="3" y1="13" x2="4.5" y2="11.5"/><line x1="11.5" y1="4.5" x2="13" y2="3"/></g></svg>'
    cloud = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 12a3 3 0 0 1-.1-6A4 4 0 0 1 11.9 5a2.5 2.5 0 0 1 .1 5H4z" fill="#000"/></svg>'
    part_cloud = '<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="6" cy="6" r="3" fill="#000"/><g stroke="#000" stroke-width="1"><line x1="6" y1="1" x2="6" y2="2"/><line x1="1" y1="6" x2="2" y2="6"/><line x1="2.5" y1="2.5" x2="3.2" y2="3.2"/><line x1="9.5" y1="2.5" x2="8.8" y2="3.2"/></g><path d="M5 13a2.5 2.5 0 0 1-.1-5A3.5 3.5 0 0 1 11.4 7 2 2 0 0 1 11.5 11H5z" fill="#000"/></svg>'
    rain = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 8a2.5 2.5 0 0 1-.1-5A3.5 3.5 0 0 1 10.4 2 2 2 0 0 1 10.5 6H4z" fill="#000"/><g stroke="#000" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="10" x2="3" y2="14"/><line x1="8" y1="10" x2="7" y2="14"/><line x1="12" y1="10" x2="11" y2="14"/></g></svg>'
    snow = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 7a2.5 2.5 0 0 1-.1-5A3.5 3.5 0 0 1 10.4 1 2 2 0 0 1 10.5 5H4z" fill="#000"/><g fill="#000"><circle cx="4" cy="10" r="1"/><circle cx="8" cy="11" r="1"/><circle cx="12" cy="10" r="1"/><circle cx="6" cy="14" r="1"/><circle cx="10" cy="14" r="1"/></g></svg>'
    storm = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 7a2.5 2.5 0 0 1-.1-5A3.5 3.5 0 0 1 10.4 1 2 2 0 0 1 10.5 5H4z" fill="#000"/><polygon points="9,8 6,12 8,12 7,16 11,11 9,11 10,8" fill="#000"/></svg>'
    fog = '<svg width="16" height="16" viewBox="0 0 16 16"><g stroke="#000" stroke-width="2" stroke-linecap="round"><line x1="2" y1="6" x2="14" y2="6"/><line x1="2" y1="10" x2="14" y2="10"/><line x1="4" y1="14" x2="12" y2="14"/></g></svg>'

    icons = {
        0: sun,           # Clear
        1: sun,           # Mostly clear
        2: part_cloud,    # Partly cloudy
        3: cloud,         # Overcast
        45: fog,          # Foggy
        48: fog,          # Icy fog
        51: rain,         # Light drizzle
        53: rain,         # Drizzle
        55: rain,         # Heavy drizzle
        56: rain,         # Freezing drizzle
        57: rain,         # Heavy freezing drizzle
        61: rain,         # Light rain
        63: rain,         # Rain
        65: rain,         # Heavy rain
        66: rain,         # Freezing rain
        67: rain,         # Heavy freezing rain
        71: snow,         # Light snow
        73: snow,         # Snow
        75: snow,         # Heavy snow
        77: snow,         # Snow grains
        80: rain,         # Light showers
        81: rain,         # Showers
        82: rain,         # Heavy showers
        85: snow,         # Light snow showers
        86: snow,         # Heavy snow showers
        95: storm,        # Thunderstorm
        96: storm,        # Thunderstorm with hail
        99: storm,        # Heavy thunderstorm with hail
    }
    return icons.get(code, cloud)


def _weather_code_to_condition(code: int) -> str:
    """Convert WMO weather code to human-readable condition."""
    conditions = {
        0: "Clear",
        1: "Mostly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Icy Fog",
        51: "Light Drizzle",
        53: "Drizzle",
        55: "Heavy Drizzle",
        56: "Freezing Drizzle",
        57: "Heavy Freezing Drizzle",
        61: "Light Rain",
        63: "Rain",
        65: "Heavy Rain",
        66: "Freezing Rain",
        67: "Heavy Freezing Rain",
        71: "Light Snow",
        73: "Snow",
        75: "Heavy Snow",
        77: "Snow Grains",
        80: "Light Showers",
        81: "Showers",
        82: "Heavy Showers",
        85: "Light Snow Showers",
        86: "Heavy Snow Showers",
        95: "Thunderstorm",
        96: "Thunderstorm with Hail",
        99: "Heavy Thunderstorm with Hail",
    }
    return conditions.get(code, "Unknown")


async def get_weather_data() -> dict:
    """
    Fetch weather forecast from Open-Meteo.
    Returns current conditions, hourly forecast, and daily forecast.
    """
    params = {
        "latitude": WEATHER_LAT,
        "longitude": WEATHER_LON,
        "timezone": TIMEZONE,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "current": "temperature_2m,relative_humidity_2m,weather_code,apparent_temperature",
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "forecast_days": 8,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(FORECAST_URL, params=params)

        if response.status_code != 200:
            raise WeatherError(f"Weather API error: {response.status_code}")

        return response.json()


async def get_air_quality() -> dict:
    """
    Fetch air quality and UV data from Open-Meteo.
    Returns hourly AQI and UV index.
    """
    params = {
        "latitude": WEATHER_LAT,
        "longitude": WEATHER_LON,
        "timezone": TIMEZONE,
        "hourly": "us_aqi,uv_index",
        "forecast_days": 2,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(AIR_QUALITY_URL, params=params)

        if response.status_code != 200:
            raise WeatherError(f"Air quality API error: {response.status_code}")

        return response.json()


async def get_all_weather() -> dict | None:
    """
    Fetch all weather data and combine into normalized format.
    Returns None if any API call fails.
    """
    try:
        # Fetch both APIs
        weather_data = await get_weather_data()
        air_quality_data = await get_air_quality()

        # Extract current conditions
        weather_code = weather_data["current"]["weather_code"]
        current = {
            "temp": round(weather_data["current"]["temperature_2m"]),
            "feels_like": round(weather_data["current"]["apparent_temperature"]),
            "humidity": round(weather_data["current"]["relative_humidity_2m"]),
            "weather_code": weather_code,
            "condition": _weather_code_to_condition(weather_code),
        }

        # Extract today's data (first day in daily arrays)
        daily = weather_data["daily"]
        today = {
            "high": round(daily["temperature_2m_max"][0]),
            "low": round(daily["temperature_2m_min"][0]),
            "sunrise": _format_time(daily["sunrise"][0]),
            "sunset": _format_time(daily["sunset"][0]),
        }

        # Build hourly forecast (next 24 hours)
        hourly_weather = weather_data["hourly"]
        hourly_aq = air_quality_data["hourly"]

        # Find current hour index (use configured timezone)
        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz)
        current_hour = now.replace(minute=0, second=0, microsecond=0, tzinfo=None)

        hourly = []
        for i in range(len(hourly_weather["time"])):
            hour_time = datetime.fromisoformat(hourly_weather["time"][i])
            if hour_time < current_hour:
                continue
            if len(hourly) >= 24:
                break

            # Get AQI and UV for this hour (if available)
            aqi = None
            uv = None
            if i < len(hourly_aq["time"]):
                aqi_val = hourly_aq["us_aqi"][i]
                uv_val = hourly_aq["uv_index"][i]
                aqi = round(aqi_val) if aqi_val is not None else None
                uv = round(uv_val, 1) if uv_val is not None else None

            hour_code = hourly_weather["weather_code"][i]
            hourly.append({
                "hour": _format_hour(hourly_weather["time"][i]),
                "temp": round(hourly_weather["temperature_2m"][i]),
                "precip_chance": round(hourly_weather["precipitation_probability"][i] or 0),
                "wind_speed": round(hourly_weather["wind_speed_10m"][i]),
                "wind_dir": _degrees_to_compass(hourly_weather["wind_direction_10m"][i]),
                "uv": uv,
                "aqi": aqi,
                "icon": _weather_code_to_icon(hour_code),
            })

        # Calculate max UV and max AQI for the next 24 hours
        uv_values = [h["uv"] for h in hourly if h["uv"] is not None]
        aqi_values = [h["aqi"] for h in hourly if h["aqi"] is not None]
        today["max_uv"] = max(uv_values) if uv_values else None
        today["max_aqi"] = max(aqi_values) if aqi_values else None

        # Build 7-day forecast (skip today, get next 7 days)
        daily_forecast = []
        for i in range(1, min(8, len(daily["time"]))):
            daily_forecast.append({
                "date": _format_date(daily["time"][i]),
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
                "precip_chance": round(daily["precipitation_probability_max"][i] or 0),
            })

        return {
            "current": current,
            "today": today,
            "hourly": hourly,
            "daily": daily_forecast,
        }

    except Exception as e:
        # Log error but don't crash - weather is optional
        print(f"Weather fetch error: {e}")
        return None
