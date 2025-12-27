from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import CALENDAR_IDS, TIMEZONE
from app.oauth import refresh_access_token

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class CalendarError(Exception):
    """Raised when calendar operations fail."""

    pass


def _parse_event_time(event: dict, timezone: ZoneInfo) -> tuple[datetime | None, bool]:
    """
    Parse event start time. Returns (datetime, is_all_day).
    All-day events have 'date' key, timed events have 'dateTime' key.
    """
    start = event.get("start", {})

    if "date" in start:
        # All-day event
        date_str = start["date"]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone), True

    if "dateTime" in start:
        # Timed event
        dt_str = start["dateTime"]
        dt = datetime.fromisoformat(dt_str)
        return dt.astimezone(timezone), False

    return None, False


def _parse_event_end_time(event: dict, timezone: ZoneInfo) -> datetime | None:
    """Parse event end time."""
    end = event.get("end", {})

    if "date" in end:
        date_str = end["date"]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone)

    if "dateTime" in end:
        dt_str = end["dateTime"]
        dt = datetime.fromisoformat(dt_str)
        return dt.astimezone(timezone)

    return None


def normalize_event(event: dict, calendar_id: str, timezone: ZoneInfo) -> dict | None:
    """
    Normalize a Google Calendar event into our unified structure.
    Returns None if event should be skipped.
    """
    # Skip cancelled events
    if event.get("status") == "cancelled":
        return None

    start_dt, is_all_day = _parse_event_time(event, timezone)
    if start_dt is None:
        return None

    end_dt = _parse_event_end_time(event, timezone)

    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(No title)"),
        "date": start_dt.strftime("%Y-%m-%d"),
        "date_formatted": start_dt.strftime("%a %b %-d"),
        "start_time": "" if is_all_day else start_dt.strftime("%-I:%M %p"),
        "end_time": "" if is_all_day or end_dt is None else end_dt.strftime("%-I:%M %p"),
        "all_day": is_all_day,
        "location": event.get("location"),
        "calendar_id": calendar_id,
    }


async def fetch_calendar_events(
    access_token: str,
    calendar_id: str,
    timezone: ZoneInfo,
    time_min: datetime,
    time_max: datetime,
) -> list[dict]:
    """Fetch events from a single calendar."""
    events = []
    page_token = None

    async with httpx.AsyncClient() as client:
        while True:
            params = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await client.get(
                f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                raise CalendarError(f"Failed to fetch calendar {calendar_id}: {response.text}")

            data = response.json()

            for event in data.get("items", []):
                normalized = normalize_event(event, calendar_id, timezone)
                if normalized:
                    events.append(normalized)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return events


async def get_all_events() -> list[dict]:
    """
    Fetch events from all configured calendars for the next 365 days.
    Returns sorted list of events.
    """
    access_token = await refresh_access_token()
    timezone = ZoneInfo(TIMEZONE)

    now = datetime.now(timezone)
    time_min = now
    time_max = now + timedelta(days=365)

    all_events = []
    for calendar_id in CALENDAR_IDS:
        events = await fetch_calendar_events(
            access_token, calendar_id, timezone, time_min, time_max
        )
        all_events.extend(events)

    # Sort: by date, then all-day events first, then by start time
    def sort_key(e: dict) -> tuple:
        return (
            e["date"],
            0 if e["all_day"] else 1,
            e["start_time"] if e["start_time"] else "",
        )

    all_events.sort(key=sort_key)
    return all_events
