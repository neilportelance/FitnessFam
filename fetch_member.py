"""
fetch_member.py — Exchange a Strava auth code for a personal refresh token
and fetch the member's activities into cache2.json

Usage:
    python fetch_member.py <auth_code> <firstname> <lastname_initial>

Example:
    python fetch_member.py a0f3226aadea20bad73a2985828c044517ce036a Neil P.
"""

import sys
import json
import requests
from pathlib import Path
from datetime import datetime

CONFIG_FILE  = Path("config.json")
CACHE2_FILE  = Path("cache2.json")
MEMBERS_FILE = Path("members.json")
TOKENS_FILE  = Path("member_tokens.json")  # stores individual refresh tokens

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def activity_fingerprint(a):
    return (
        a.get("athlete", {}).get("firstname", ""),
        a.get("athlete", {}).get("lastname", ""),
        a.get("sport_type", ""),
        round(a.get("distance", 0)),
        a.get("moving_time", 0),
    )

def exchange_code(code, config):
    """Exchange auth code for access + refresh tokens."""
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "grant_type": "authorization_code"
    })
    data = res.json()
    if "errors" in data:
        print(f"❌ Error exchanging code: {data}")
        sys.exit(1)
    return data

def get_personal_access_token(refresh_token, config):
    """Get a fresh access token using personal refresh token."""
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    data = res.json()
    return data["access_token"], data["refresh_token"]

def get_personal_access_token(refresh_token, config):
    """Get a fresh access token using personal refresh token."""
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    data = res.json()
    return data["access_token"], data["refresh_token"]

def fetch_personal_activities(access_token, after_timestamp=None):
    """Fetch all activities from personal feed."""
    activities = []
    page = 1
    while True:
        params = {"per_page": 200, "page": page}
        if after_timestamp:
            params["after"] = after_timestamp
        res = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )
        data = res.json()
        if not data:
            break
        activities.extend(data)
        print(f"  Fetched page {page} ({len(activities)} activities so far...)")
        if len(data) < 200:
            break
        page += 1
    return activities

def normalize_activity(a, firstname, lastname):
    """Normalize personal activity to match club feed format."""
    return {
        "athlete": {
            "resource_state": 2,
            "firstname": firstname,
            "lastname": lastname
        },
        "name": a.get("name", ""),
        "distance": a.get("distance", 0),
        "moving_time": a.get("moving_time", 0),
        "elapsed_time": a.get("elapsed_time", 0),
        "total_elevation_gain": a.get("total_elevation_gain", 0),
        "type": a.get("type", ""),
        "sport_type": a.get("sport_type", a.get("type", "")),
        "workout_type": a.get("workout_type"),
        "start_date": a.get("start_date", ""),
    }

def save_member_token(firstname, lastname, refresh_token):
    """Save personal refresh token to member_tokens.json."""
    tokens = {}
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE) as f:
            tokens = json.load(f)
    key = f"{firstname} {lastname}"
    tokens[key] = refresh_token
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"✓ Token saved for {key}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python fetch_member.py <auth_code> <firstname> <lastname>")
        print("       python fetch_member.py --refresh <firstname> <lastname>")
        sys.exit(1)

    mode = sys.argv[1]
    firstname = sys.argv[2]
    lastname = sys.argv[3] if len(sys.argv) > 3 else ""
    member_key = f"{firstname} {lastname}".strip()

    config = load_config()

    if mode == "--refresh":
        if not TOKENS_FILE.exists():
            print(f"❌ No member_tokens.json found")
            sys.exit(1)
        tokens = json.load(open(TOKENS_FILE))
        if member_key not in tokens:
            print(f"❌ No token found for {member_key}")
            sys.exit(1)
        print(f"\n🔄 Refreshing token for {member_key}...")
        access_token, new_refresh = get_personal_access_token(tokens[member_key], config)
        save_member_token(firstname, lastname, new_refresh)
    else:
        code = mode
        print(f"\n🔑 Exchanging auth code for {member_key}...")
        token_data = exchange_code(code, config)
        new_refresh = token_data["refresh_token"]
        access_token = token_data["access_token"]
        athlete = token_data.get("athlete", {})
        print(f"✓ Authorized as: {athlete.get('firstname')} {athlete.get('lastname')}")
        save_member_token(firstname, lastname, new_refresh)

    print(f"\n📥 Fetching personal activities for current month...")
    # Only fetch activities from the 1st of the current month
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    after_timestamp = int(month_start.timestamp())
    raw_activities = fetch_personal_activities(access_token, after_timestamp=after_timestamp)
    print(f"✓ Fetched {len(raw_activities)} activities since {month_start.strftime('%B 1, %Y')}")

    # Normalize to club feed format
    normalized = [normalize_activity(a, firstname, lastname) for a in raw_activities]
    # Reverse to oldest-first
    normalized = list(reversed(normalized))

    # Merge into cache2.json
    cache = []
    if CACHE2_FILE.exists():
        with open(CACHE2_FILE) as f:
            cache = json.load(f)

    existing_fps = {activity_fingerprint(a) for a in cache}
    new_entries = [a for a in normalized if activity_fingerprint(a) not in existing_fps]

    merged = cache + new_entries
    with open(CACHE2_FILE, "w") as f:
        json.dump(merged, f)

    print(f"✓ Added {len(new_entries)} new activities to cache ({len(merged)} total)")

    tokens = json.load(open(TOKENS_FILE))
    print(f"\n⚠️  Update the MEMBER_TOKENS GitHub secret with this value:")
    print(json.dumps(tokens, indent=2))
    print(f"\n✅ Done! Run python run.py to regenerate reports.")

if __name__ == "__main__":
    main()
