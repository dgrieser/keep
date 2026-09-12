"""Master-token acquisition via gpsoauth."""

from __future__ import annotations

import secrets

import gpsoauth

EMBEDDED_SETUP_URL = "https://accounts.google.com/EmbeddedSetup"

LOGIN_INSTRUCTIONS = f"""\
To authorize this tool you need a one-time OAuth token from Google:

  1. Open {EMBEDDED_SETUP_URL} in a browser (an incognito window works well).
  2. Sign in with the Google account whose notes you want to manage.
  3. Accept the terms. The page may then show an endless loading spinner; that is fine.
  4. Open the browser's developer tools -> Application/Storage -> Cookies for
     accounts.google.com and copy the value of the cookie named "oauth_token".
     It starts with "oauth2_4/".

The oauth_token is exchanged once for a long-lived master token, which is stored locally.
"""


class AuthError(Exception):
    """Raised when the token exchange fails."""


def new_android_id() -> str:
    """Return a random 16-character hex device identifier."""
    return secrets.token_hex(8)


def exchange_oauth_token(email: str, oauth_token: str, android_id: str) -> str:
    """Exchange an EmbeddedSetup ``oauth_token`` cookie for a master token."""
    oauth_token = oauth_token.strip()
    if not oauth_token:
        raise AuthError("Empty oauth_token.")
    response = gpsoauth.exchange_token(email, oauth_token, android_id)
    token = response.get("Token")
    if not token:
        detail = response.get("Error") or response.get("ErrorDetail") or "unknown error"
        raise AuthError(f"Token exchange failed: {detail}")
    return token
