import secrets
from urllib.parse import urlencode

import httpx

from app.config import (
    GOOGLE_AUTH_URL,
    GOOGLE_CALENDAR_SCOPE,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_TOKEN_URL,
)
from app.storage import load_token, save_token


class OAuthError(Exception):
    """Raised when OAuth operations fail."""

    pass


def generate_auth_url() -> tuple[str, str]:
    """
    Generate the Google OAuth authorization URL.
    Returns (auth_url, state_token).
    """
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return auth_url, state


async def exchange_code_for_tokens(code: str) -> str:
    """
    Exchange authorization code for tokens.
    Stores the refresh token and returns the access token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
        )

        if response.status_code != 200:
            raise OAuthError(f"Token exchange failed: {response.text}")

        data = response.json()

        if "refresh_token" not in data:
            raise OAuthError("No refresh token in response")

        save_token(data["refresh_token"])
        return data["access_token"]


async def refresh_access_token() -> str:
    """
    Use the stored refresh token to get a new access token.
    Raises OAuthError if refresh fails or no token stored.
    """
    refresh_token = load_token()
    if not refresh_token:
        raise OAuthError("No refresh token stored")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code != 200:
            raise OAuthError(f"Token refresh failed: {response.text}")

        data = response.json()
        return data["access_token"]
