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


def _format_time(dt: datetime) -> str:
    """
    Format time cleanly: no leading zeros, no :00 for on-the-hour times.

    Examples:
    - 12:00 PM -> "12 PM"
    - 08:00 AM -> "8 AM"
    - 10:30 PM -> "10:30 PM"
    - 08:45 PM -> "8:45 PM"
    """
    if dt.minute == 0:
        return dt.strftime("%-I %p")
    else:
        return dt.strftime("%-I:%M %p")


def _format_date_range(start_dt: datetime, end_dt: datetime | None, is_all_day: bool) -> str:
    """
    Format the date, showing a range for multi-day events.

    For all-day events, Google Calendar's end date is exclusive (day after last day),
    so we subtract 1 day to get the actual last day.

    Examples:
    - Single day all-day: "Wed Mar 18"
    - Multi-day all-day same month: "Wed Mar 18-22"
    - Multi-day all-day cross month: "Mon Mar 30-Apr 1"
    - Multi-day timed same month: "Mon Mar 30 10 PM-Apr 1 10 AM"
    - Multi-day timed cross month: "Mon Mar 30 10 PM-Apr 1 10 AM"
    """
    start_date_formatted = start_dt.strftime("%a %b %-d")

    if end_dt is None:
        return start_date_formatted

    # For all-day events, end date is exclusive, so subtract 1 day
    if is_all_day:
        actual_end = end_dt - timedelta(days=1)
    else:
        actual_end = end_dt

    # Check if it's a single-day event
    if start_dt.date() == actual_end.date():
        return start_date_formatted

    # Multi-day event - format the range
    if is_all_day:
        # All-day multi-day: just show dates
        if start_dt.month == actual_end.month:
            return f"{start_date_formatted}-{actual_end.day}"
        else:
            return f"{start_date_formatted}-{actual_end.strftime('%b %-d')}"
    else:
        # Timed multi-day: include times
        start_time = _format_time(start_dt)
        end_time = _format_time(actual_end)
        end_date_formatted = actual_end.strftime("%b %-d")
        return f"{start_date_formatted} {start_time}-{end_date_formatted} {end_time}"


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
        "date_formatted": _format_date_range(start_dt, end_dt, is_all_day),
        "start_time": "" if is_all_day else _format_time(start_dt),
        "end_time": "" if is_all_day or end_dt is None else _format_time(end_dt),
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
