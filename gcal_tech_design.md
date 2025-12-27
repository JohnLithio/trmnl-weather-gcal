# TRMNL Custom Google Calendar Plugin (FastAPI)
**Technical Design Document**

---

## 1. Background & Motivation

TRMNL provides a built-in Google Calendar plugin that works well for common use cases, but it has two limitations for advanced personal workflows:

1. It limits event visibility to approximately the next 30 days.
2. It offers limited control over rendering behavior in mashups and compact layouts.

This project defines a **TRMNL Private Plugin** that:
- Authenticates directly with Google Calendar via OAuth 2.0
- Fetches **events for the next 365 days**
- Combines events from **multiple Google calendars** (personal, work, shared)
- Provides event data as **JSON for TRMNL's Liquid templates**
- Is designed for **single-user personal use**
- Is implemented using **FastAPI**

This document is intended to be a **complete handoff** to a coding agent that can implement the system without additional context.

---

## 2. High-Level Architecture

### Actors
- **TRMNL** – Polls your server at a configured refresh interval
- **FastAPI Server** – Handles Google OAuth, calendar fetching, returns JSON
- **Google Calendar API** – Source of calendar data
- **User (you)** – Sets up Google OAuth once, designs templates in TRMNL

### Data Flow Overview

```
┌─────────────────────────────────────────────────────┐
│                    TRMNL Setup                       │
│  1. Create Private Plugin (Polling strategy)        │
│  2. Set Polling URL: https://your-server/api/events │
│  3. Design layout templates in Markup Editor        │
└─────────────────────────────────────────────────────┘
                         │
                         │ polls every N minutes
                         ▼
┌─────────────────────────────────────────────────────┐
│                  Your FastAPI Server                │
│                                                     │
│  GET /api/events                                    │
│    → Fetch events from Google Calendar              │
│    → Return JSON for TRMNL to render                │
│                                                     │
│  GET /setup                                         │
│    → One-time Google OAuth setup page               │
│                                                     │
│  GET /oauth/callback                                │
│    → Handle Google OAuth callback                   │
│    → Store refresh token                            │
└─────────────────────────────────────────────────────┘
                         │
                         │ Google Calendar API
                         ▼
┌─────────────────────────────────────────────────────┐
│               Your Google Calendars                 │
└─────────────────────────────────────────────────────┘
```

### One-Time Setup Flow

1. Deploy server to Cloud Run
2. Visit `https://your-server/setup`
3. Click "Connect Google Calendar"
4. Complete Google OAuth consent
5. Server stores refresh token
6. Create Private Plugin in TRMNL with polling URL

---

## 3. Non-Goals / Constraints

- **Single user only** (no multi-user tenancy)
- **No incremental sync** (full calendar fetch on each poll)
- **Low event volume** (no performance tuning required)
- **No public marketplace distribution** (Private Plugin)
- **No background jobs required**
- **Templates live in TRMNL** (not in server code)

---

## 4. Technology Stack

### Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **HTTP Client:** httpx
- **Auth:** OAuth 2.0 (Google only)
- **Deployment:** Google Cloud Run (recommended)

### External APIs
- **Google Calendar API v3**
- **Google OAuth 2.0**

### Storage
- **File-based JSON** for refresh token
  - `data/google_token.json`
  - Persists via Cloud Run volume mount
  - Survives container restarts

### Timezone
- **Default:** `America/Chicago`
- Configurable via `TIMEZONE` environment variable

---

## 5. Google Cloud Setup

### 5.1 Create Google Cloud Project
1. Create a new project in Google Cloud Console
2. Enable **Google Calendar API**

### 5.2 OAuth Consent Screen
- Type: External
- Scopes:
  - `https://www.googleapis.com/auth/calendar.readonly`
- Add your Google account as a test user

### 5.3 OAuth Client
- Type: Web Application
- Redirect URI: `https://<CLOUD_RUN_URL>/oauth/callback`
  - Example: `https://trmnl-gcal-abc123-uc.a.run.app/oauth/callback`
- Save:
  - Client ID → `GOOGLE_CLIENT_ID`
  - Client Secret → `GOOGLE_CLIENT_SECRET`

---

## 6. TRMNL Private Plugin Setup

Create a new Private Plugin in TRMNL:

1. Navigate to **Plugins → Private Plugin → New**
2. Set **Strategy**: Polling
3. Set **Polling URL**: `https://<CLOUD_RUN_URL>/api/events`
4. Configure refresh interval as desired
5. Design templates in **Markup Editor** for each layout size

---

## 7. Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | OAuth client ID | `123...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `https://your-server/oauth/callback` |
| `CALENDAR_IDS` | Comma-separated calendar IDs | `primary,work@group.calendar.google.com` |
| `TIMEZONE` | IANA timezone | `America/Chicago` |

---

## 8. API Endpoints

### 8.1 Events Endpoint (`GET /api/events`)

Called by TRMNL's polling mechanism. Returns calendar events as JSON.

**Response Format:**
```json
{
  "generated_at": "2025-12-26T10:30:00-06:00",
  "timezone": "America/Chicago",
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
  ]
}
```

**Error Response (not authenticated):**
```json
{
  "error": "not_authenticated",
  "message": "Please visit /setup to connect Google Calendar"
}
```

### 8.2 Setup Page (`GET /setup`)

HTML page for one-time Google OAuth setup.

**If not authenticated:**
- Shows "Connect Google Calendar" button
- Button links to Google OAuth consent

**If authenticated:**
- Shows "Connected" status
- Shows configured calendars
- Shows "Disconnect" option

### 8.3 OAuth Callback (`GET /oauth/callback`)

Handles Google OAuth redirect.

**Query Parameters:**
- `code` - Authorization code from Google
- `error` - Error message (if user denied)

**Behavior:**
1. Exchange code for tokens via Google token endpoint
2. Store refresh token to `data/google_token.json`
3. Redirect to `/setup?success=1`

---

## 9. Data Model

### 9.1 Stored Token
```json
{
  "refresh_token": "1//0g...",
  "created_at": "2025-12-26T10:00:00Z"
}
```

### 9.2 Event Structure
```json
{
  "id": "string",
  "summary": "string",
  "date": "2025-12-26",
  "date_formatted": "Thu Dec 26",
  "start_time": "10:00 AM",
  "end_time": "11:00 AM",
  "all_day": false,
  "location": "string | null",
  "calendar_id": "string"
}
```

---

## 10. Calendar Data Fetching

### 10.1 Access Token Refresh

Use stored refresh token to obtain access token:

```
POST https://oauth2.googleapis.com/token
```

Parameters:
- `client_id`
- `client_secret`
- `refresh_token`
- `grant_type=refresh_token`

### 10.2 Event Fetching

For each calendar ID in `CALENDAR_IDS`:

```
GET https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events
```

Query parameters:
- `timeMin = now (RFC3339)`
- `timeMax = now + 365 days`
- `singleEvents = true`
- `orderBy = startTime`
- `maxResults = 2500`
- Handle pagination via `nextPageToken`

### 10.3 Event Processing

**Processing Rules:**
- Skip cancelled events (`status == "cancelled"`)
- Handle both timed and all-day events
- Convert all times to configured timezone
- **Sorting:** Within a single day, all-day events appear first, then timed events by start time

**Date/Time Formatting:**
- Date: `Thu Dec 26` format (`%a %b %-d`)
- Time: `10:00 AM` format (`%-I:%M %p`)

---

## 11. TRMNL Liquid Templates

Templates are created in TRMNL's Markup Editor, not in server code.

### 11.1 Available Variables

The JSON from `/api/events` is available in templates:
- `{{ generated_at }}` - When data was fetched
- `{{ timezone }}` - Configured timezone
- `{{ event_count }}` - Total number of events
- `{{ events }}` - Array of event objects

### 11.2 Sample Full Layout Template

```liquid
<div class="view view--full">
  <div class="layout layout--col">
    <div class="title_bar">
      <span class="title">Calendar</span>
      <span class="instance">{{ generated_at | date: "%b %-d" }}</span>
    </div>
    <div class="content content--col gap--space-between">
      {% for event in events limit:20 %}
      <div class="meta" style="font-size:18px;">
        <span style="font-weight:800; min-width:90px; display:inline-block;">
          {{ event.date_formatted }}
        </span>
        <span style="font-weight:600;">{{ event.summary }}</span>
        {% if event.all_day %}
        <span>(All day)</span>
        {% else %}
        <span>{{ event.start_time }}–{{ event.end_time }}</span>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
</div>
```

### 11.3 Layout Limits

| Layout | Event Limit | Notes |
|--------|-------------|-------|
| Full | 20 | Full detail |
| Half Vertical | 8 | Left/right mashup |
| Half Horizontal | 8 | Top/bottom mashup |
| Quadrant | 3 | Ultra-compact |

---

## 12. Error Handling

### Invalid/Expired Refresh Token

When Google rejects the refresh token:
1. Return error JSON from `/api/events`:
```json
{
  "error": "token_expired",
  "message": "Google authorization expired. Visit /setup to reconnect."
}
```
2. User visits `/setup` to re-authenticate

### No Token Stored

If no token file exists:
```json
{
  "error": "not_authenticated",
  "message": "Please visit /setup to connect Google Calendar"
}
```

---

## 13. Security Considerations

- Never log refresh tokens
- Use HTTPS only (enforced by Cloud Run)
- `/api/events` is public (TRMNL needs to access it)
  - Consider adding API key via query param for extra security
- Token file stored in Cloud Run volume (not in container image)

---

## 14. Deployment Notes

### Cloud Run

- Stateless container with volume mount for token persistence
- No custom domain required - use Cloud Run URL directly
- Environment variables set in Cloud Run console
- Minimum CPU/memory (personal use)

### Volume Mount

To persist the token file across container restarts:

```bash
# Create a Cloud Run volume
gcloud run services update trmnl-gcal \
  --add-volume name=data,type=cloud-storage,bucket=your-bucket \
  --add-volume-mount volume=data,mount-path=/app/data
```

Or use Cloud Run's built-in secret manager for the token.

### Cost Expectations

- Google Calendar API: free (quota-based)
- Cloud Run: ~$0/month for personal usage

---

## 15. Future Enhancements (Optional)

- Caching calendar responses
- Incremental sync via `syncToken`
- Per-calendar color coding
- Event filtering (all-day, private, keywords)
- API key authentication for `/api/events`
- Calendar selection via `/setup` UI

---

## 16. Summary

This design specifies a **TRMNL Private Plugin** for Google Calendar using FastAPI:

| Feature | Implementation |
|---------|---------------|
| Calendar range | 365 days |
| Multiple calendars | Via `CALENDAR_IDS` env var |
| Templates | TRMNL Markup Editor (Liquid) |
| Authentication | Google OAuth 2.0 |
| Data format | JSON (TRMNL polls) |
| Deployment | Cloud Run with volume |
| User setup | One-time via `/setup` page |

A coding agent can implement this system end-to-end using only this document.
