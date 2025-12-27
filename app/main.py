from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.calendar import get_all_events
from app.config import API_SECRET, CALENDAR_IDS, TIMEZONE
from app.oauth import OAuthError, exchange_code_for_tokens, generate_auth_url
from app.storage import delete_token, is_authenticated
from app.weather import get_all_weather

app = FastAPI(title="TRMNL Calendar")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# In-memory state storage for OAuth (simple single-user approach)
_oauth_state: str | None = None


@app.get("/")
async def root():
    """Redirect to setup page."""
    return RedirectResponse(url="/setup")


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, success: bool = False, error: str | None = None):
    """Setup page for Google OAuth."""
    global _oauth_state

    auth_url = None
    if not is_authenticated():
        auth_url, _oauth_state = generate_auth_url()

    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "is_authenticated": is_authenticated(),
            "calendar_ids": CALENDAR_IDS,
            "auth_url": auth_url,
            "success": success,
            "error": error,
        },
    )


@app.get("/oauth/callback")
async def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle Google OAuth callback."""
    global _oauth_state

    if error:
        return RedirectResponse(url=f"/setup?error={error}")

    if not code:
        return RedirectResponse(url="/setup?error=No authorization code received")

    # Validate state
    if state != _oauth_state:
        return RedirectResponse(url="/setup?error=Invalid state parameter")

    try:
        await exchange_code_for_tokens(code)
        _oauth_state = None
        return RedirectResponse(url="/setup?success=1")
    except OAuthError as e:
        return RedirectResponse(url=f"/setup?error={str(e)}")


@app.get("/disconnect")
async def disconnect():
    """Disconnect Google Calendar (delete stored token)."""
    delete_token()
    return RedirectResponse(url="/setup")


@app.get("/api/events")
async def get_events(request: Request):
    """
    Get calendar events for TRMNL polling.
    Returns JSON with events for the next 365 days.
    Requires Authorization: Bearer <API_SECRET> header.
    """
    # Check API key
    if API_SECRET:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing or invalid Authorization header"},
                status_code=401,
            )
        token = auth_header[7:]  # Remove "Bearer " prefix
        if token != API_SECRET:
            return JSONResponse(
                {"error": "unauthorized", "message": "Invalid API key"},
                status_code=401,
            )

    if not is_authenticated():
        return JSONResponse(
            {
                "error": "not_authenticated",
                "message": "Please visit /setup to connect Google Calendar",
            },
            status_code=401,
        )

    try:
        events = await get_all_events()
        weather = await get_all_weather()  # Returns None on error
        timezone = ZoneInfo(TIMEZONE)
        now = datetime.now(timezone)

        return {
            "generated_at": now.isoformat(),
            "timezone": TIMEZONE,
            "event_count": len(events),
            "events": events,
            "weather": weather,
        }
    except OAuthError as e:
        return JSONResponse(
            {
                "error": "token_expired",
                "message": f"Google authorization expired: {e}. Visit /setup to reconnect.",
            },
            status_code=401,
        )
    except Exception as e:
        return JSONResponse(
            {
                "error": "calendar_error",
                "message": str(e),
            },
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
