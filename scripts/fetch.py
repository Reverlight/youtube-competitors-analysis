#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-auth>=2.0.0",
#   "google-auth-oauthlib>=1.0.0",
#   "google-auth-httplib2>=0.2.0",
#   "google-api-python-client>=2.0.0",
# ]
# ///
"""
fetch.py — Fetch YouTube video data for a channel and save it as CSV.

First-time setup (OAuth):
    ./fetch.py --setup
    ./fetch.py --auth-code <CODE_FROM_GOOGLE>

Normal usage:
    ./fetch.py --channel <UC_ID_or_@handle> --days 30 --label my_channel
    ./fetch.py --channel @markiplier --days 7 --label comp_markiplier

CSV files are saved to:
    <skill_dir>/youtube_data/<label>_<days>d_<YYYYMMDD>.csv
"""

import argparse
import base64
import csv
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR  = SKILL_DIR / "youtube_data"
TOKEN_FILE    = SKILL_DIR / "token.json"
CREDS_FILE    = SKILL_DIR / "credentials.json"
VERIFIER_FILE = SKILL_DIR / "code_verifier.txt"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def get_env_creds() -> dict:
    client_id     = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return {}
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def load_credentials() -> Credentials | None:
    if TOKEN_FILE.exists():
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    return None


def save_credentials(creds: Credentials) -> None:
    TOKEN_FILE.write_text(creds.to_json())


def build_flow() -> InstalledAppFlow:
    if CREDS_FILE.exists():
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    else:
        env_creds = get_env_creds()
        if not env_creds:
            print(json.dumps({
                "error": "no_credentials",
                "message": (
                    "No Google credentials found. Either:\n"
                    "  1. Place credentials.json in the skill directory, OR\n"
                    "  2. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in openclaw.json\n\n"
                    "Get credentials at: https://console.cloud.google.com/apis/credentials\n"
                    "(Create an OAuth 2.0 Client ID → Desktop app)"
                )
            }))
            sys.exit(1)
        flow = InstalledAppFlow.from_client_config(env_creds, SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    return flow


def authenticate(auth_code: str = "") -> Credentials:
    creds = load_credentials()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            pass  # fall through to re-auth

    # Exchange auth code for token
    if auth_code:
        flow = build_flow()
        code_verifier = VERIFIER_FILE.read_text().strip() if VERIFIER_FILE.exists() else None
        flow.fetch_token(code=auth_code, code_verifier=code_verifier)
        if VERIFIER_FILE.exists():
            VERIFIER_FILE.unlink()
        save_credentials(flow.credentials)
        print(json.dumps({"status": "authenticated", "message": "✅ YouTube authenticated successfully!"}))
        sys.exit(0)

    # Not authenticated — generate auth URL with PKCE
    code_verifier  = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    VERIFIER_FILE.write_text(code_verifier)

    flow = build_flow()
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    print(json.dumps({
        "error": "not_authenticated",
        "auth_url": auth_url,
        "message": (
            f"👉 Open this URL in your browser:\n{auth_url}\n\n"
            "After approving, Google will show you a code.\n"
            "Paste it back and I will complete authentication."
        )
    }))
    sys.exit(1)


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

def resolve_channel(yt, ident: str) -> str:
    if ident.startswith("UC"):
        return ident
    handle = ident.lstrip("@")
    resp = yt.channels().list(part="id", forHandle=handle).execute()
    if resp.get("items"):
        return resp["items"][0]["id"]
    resp = yt.search().list(part="snippet", type="channel", q=handle, maxResults=1).execute()
    items = resp.get("items", [])
    if not items:
        print(json.dumps({"error": "channel_not_found", "message": f"Could not resolve channel: {ident!r}"}))
        sys.exit(1)
    return items[0]["snippet"]["channelId"]


def fetch_videos(yt, channel_id: str, days: int) -> list[dict]:
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    videos, page_token = [], None
    while True:
        resp = yt.search().list(
            part="id,snippet", channelId=channel_id, type="video",
            order="date", publishedAfter=after, maxResults=50, pageToken=page_token
        ).execute()
        ids = [i["id"]["videoId"] for i in resp.get("items", [])]
        if ids:
            stats = yt.videos().list(part="statistics,snippet", id=",".join(ids)).execute()
            for item in stats.get("items", []):
                sn = item.get("snippet", {})
                st = item.get("statistics", {})
                videos.append({
                    "video_id":      item["id"],
                    "channel_id":    channel_id,
                    "title":         sn.get("title", ""),
                    "description":   sn.get("description", "")[:500],
                    "published_at":  sn.get("publishedAt", ""),
                    "view_count":    int(st.get("viewCount", 0)),
                    "like_count":    int(st.get("likeCount", 0)),
                    "comment_count": int(st.get("commentCount", 0)),
                })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup",     action="store_true", help="Generate Google OAuth URL")
    parser.add_argument("--auth-code", type=str, default="", help="Exchange auth code for token")
    parser.add_argument("--channel",   type=str, default="", help="Channel ID (UC...) or @handle")
    parser.add_argument("--days",      type=int, default=30, help="Days back to fetch")
    parser.add_argument("--label",     type=str, default="channel", help="Output file label")
    args = parser.parse_args()

    if args.setup:
        authenticate()  # will print auth URL and exit
        return

    if args.auth_code:
        authenticate(auth_code=args.auth_code)
        return

    if not args.channel:
        print(json.dumps({"error": "missing_channel", "message": "--channel is required"}))
        sys.exit(1)

    creds = authenticate()
    yt = build("youtube", "v3", credentials=creds)

    print(json.dumps({"status": "resolving", "channel": args.channel}))
    channel_id = resolve_channel(yt, args.channel)

    videos = fetch_videos(yt, channel_id, args.days)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = DATA_DIR / f"{args.label}_{args.days}d_{date_str}.csv"

    fields = ["video_id", "channel_id", "title", "description", "published_at",
              "view_count", "like_count", "comment_count"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(videos)

    print(json.dumps({
        "status": "done",
        "label": args.label,
        "channel_id": channel_id,
        "videos_saved": len(videos),
        "file": str(out_path),
    }))


if __name__ == "__main__":
    main()