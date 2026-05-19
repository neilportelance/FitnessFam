import json
import requests
from pathlib import Path
from datetime import datetime

CONFIG_FILE = Path("config.json")
ANCHOR_FILE = Path("anchor.json")

# ── Point Rules ───────────────────────────────────────────────────────────────

# Distance-based: points per km of eligible distance
DISTANCE_RATES = {
    "Run":                  1.0,   # 1pt/km (pace must be <= 9:00/km)
    "Nordic Ski / XC Ski":  1.0,   # same as run
    "Walk / Hike":          1/1.5, # 1pt/1.5km
    "Paddle / Kayak / SUP": 1/1.5, # same as walk
    "Mountain Bike":        1/2.0, # 1pt/2km
    "Road Bike":            1/3.0, # 1pt/3km
    "Indoor Bike / Spin":   1/3.0, # 1pt/3km
    "Swim":                 3.0,   # 3pt/km
    "Downhill Ski":         1/4.0, # 1pt/4km, but only 2/3 of distance counts
}

# Time-based: points per hour
TIME_RATES = {
    "Crossfit / HIIT / High Intensity": 5.0,
    "Elliptical / High Intensity":      5.0,
    "Tennis / Squash / High Intensity": 5.0,
    "Team Sports / Medium Intensity":   3.5,
    "Pickleball / Medium Intensity":    3.5,
    "Gym / Medium Intensity":           3.5,
    "Yoga / Low Intensity":             2.5,
}

RUN_MAX_PACE_SEC_PER_KM = 9 * 60  # 9:00/km — slower than this → flag as walk

# Max distance per activity type (meters) — flag if exceeded
MAX_DISTANCE = {
    "Run":               35000,
    "Walk / Hike":       10000,
    "Paddle / Kayak / SUP": 30000,
    "Road Bike":         150000,
    "Indoor Bike / Spin": 100000,
    "Mountain Bike":     80000,
    "Swim":              5000,
    "Nordic Ski / XC Ski": 50000,
    "Downhill Ski":      80000,
}

# Speed limits in km/h (min, max) — flag if outside range
SPEED_LIMITS = {
    "Walk / Hike":       (1.0, 8.0),
    "Run":               (4.0, 20.0),
    "Road Bike":         (5.0, 60.0),
    "Indoor Bike / Spin": (5.0, 60.0),
    "Mountain Bike":     (3.0, 40.0),
    "Swim":              (0.5, 12.0),
    "Paddle / Kayak / SUP": (1.0, 15.0),
    "Nordic Ski / XC Ski": (2.0, 30.0),
}

MEMBERS_FILE = Path("members.json")

def load_members():
    if not MEMBERS_FILE.exists():
        return set(), set()
    data = json.load(open(MEMBERS_FILE))
    excluded, known = set(), set()
    for m in data["members"]:
        key = f"{m['firstname']} {m['lastname']}"
        known.add(key)
        if not m["participating"]:
            excluded.add(key)
    return excluded, known

EXCLUDED_ATHLETES, KNOWN_ATHLETES = load_members()

ACTIVITY_LABELS = {
    "Run": "Run", "TrailRun": "Run",
    "NordicSki": "Nordic Ski / XC Ski", "BackcountrySki": "Nordic Ski / XC Ski",
    "Walk": "Walk / Hike", "Hike": "Walk / Hike",
    "Kayaking": "Paddle / Kayak / SUP", "Canoeing": "Paddle / Kayak / SUP",
    "StandUpPaddling": "Paddle / Kayak / SUP",
    "MountainBikeRide": "Mountain Bike",
    "Ride": "Road Bike", "GravelRide": "Road Bike",
    "VirtualRide": "Indoor Bike / Spin", "Rowing": "Indoor Bike / Spin",
    "Swim": "Swim",
    "AlpineSki": "Downhill Ski",
    "Yoga": "Yoga / Low Intensity", "IceSkate": "Yoga / Low Intensity",
    "Workout": "Gym / Medium Intensity", "WeightTraining": "Gym / Medium Intensity",
    "RockClimbing": "Gym / Medium Intensity",
    "Elliptical": "Elliptical / High Intensity", "StairStepper": "Elliptical / High Intensity",
    "Crossfit": "Crossfit / HIIT / High Intensity",
    "HighIntensityIntervalTraining": "Crossfit / HIIT / High Intensity",
    "Tennis": "Tennis / Squash / High Intensity", "Squash": "Tennis / Squash / High Intensity",
    "Pickleball": "Pickleball / Medium Intensity",
    "Soccer": "Team Sports / Medium Intensity", "Hockey": "Team Sports / Medium Intensity",
    "IceHockey": "Team Sports / Medium Intensity", "Handball": "Team Sports / Medium Intensity",
    "Basketball": "Team Sports / Medium Intensity", "Football": "Team Sports / Medium Intensity",
    "Volleyball": "Team Sports / Medium Intensity",
}

# ── Auth / Fetch (shared with leaderboard.py) ─────────────────────────────────

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_access_token(config):
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": config["refresh_token"],
        "grant_type": "refresh_token"
    })
    res.raise_for_status()
    data = res.json()
    config["refresh_token"] = data["refresh_token"]
    save_config(config)
    return data["access_token"]

def fetch_all_activities(token, club_id):
    activities = []
    page = 1
    while True:
        res = requests.get(
            f"https://www.strava.com/api/v3/clubs/{club_id}/activities",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 200, "page": page}
        )
        res.raise_for_status()
        data = res.json()
        if not data:
            break
        activities.extend(data)
        print(f"  Fetched page {page} ({len(activities)} activities so far...)")
        if len(data) < 200:
            break
        page += 1
    return activities

def load_anchor():
    if ANCHOR_FILE.exists():
        with open(ANCHOR_FILE) as f:
            return json.load(f)
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_label(sport_type):
    return ACTIVITY_LABELS.get(sport_type, sport_type)

def fmt_time(s):
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def fmt_pace(distance_m, time_s):
    if distance_m <= 0:
        return "N/A"
    p = time_s / (distance_m / 1000)
    return f"{int(p//60)}:{int(p%60):02d}/km"

def first_name(a):
    return a['athlete']['firstname']

REVIEW_FILE = Path("manual_review.json")

def load_review():
    if REVIEW_FILE.exists():
        with open(REVIEW_FILE) as f:
            return json.load(f)
    return {"approved": [], "denied": []}

REVIEW = load_review()

def is_denied(athlete_name, activity_name, distance_m=0):
    for r in REVIEW.get("denied", []):
        if r.get("athlete", "").startswith(athlete_name.split()[0]) and r.get("activity") == activity_name:
            detail = r.get("detail", "")
            if detail and distance_m:
                try:
                    denied_km = float(detail.split("km")[0].strip().split()[-1])
                    if abs(denied_km - distance_m/1000) > 0.5:
                        continue
                except:
                    pass
            return True
    return False

def is_approved(athlete_name, activity_name):
    return any(
        r.get("athlete", "").startswith(athlete_name.split()[0]) and
        r.get("activity") == activity_name
        for r in REVIEW.get("approved", [])
    )

# ── Points Calculation ────────────────────────────────────────────────────────

def calculate_activity(a):
    """
    Returns a dict:
      name, sport_type, label, points, display, flag, flag_reason, review
    """
    sport_type = a.get("sport_type", "Unknown")
    label = get_label(sport_type)
    name = first_name(a)
    distance_m = a.get("distance", 0)
    moving_time_s = a.get("moving_time", 0)
    activity_name = a.get("name", "")

    # Name-based overrides — e.g. hockey logged as ice skating, floor hockey logged as HIIT
    activity_name_lower = activity_name.lower()
    if label == "Yoga / Low Intensity" and any(kw in activity_name_lower for kw in ["puck", "hockey", "shinny"]):
        label = "Team Sports / Medium Intensity"
    if label == "Crossfit / HIIT / High Intensity" and "floor hockey" in activity_name_lower:
        label = "Team Sports / Medium Intensity"

    full_name = f"{name} {a['athlete'].get('lastname', '')}"

    # Check manual review decisions
    if is_denied(full_name, activity_name, distance_m):
        result = {"name": name, "sport_type": sport_type, "label": label,
                  "activity_name": activity_name, "points": 0.0,
                  "display": "Denied by reviewer", "flag": True,
                  "flag_reason": "❌ Denied by reviewer", "review": True, "denied": True}
        return result

    approved = is_approved(full_name, activity_name)

    result = {
        "name": name,
        "sport_type": sport_type,
        "label": label,
        "activity_name": activity_name,
        "points": 0.0,
        "display": "",
        "flag": False,
        "flag_reason": "",
        "review": False,
    }

    # ── Unknown activity type ──
    if sport_type not in ACTIVITY_LABELS:
        result["flag"] = True
        result["flag_reason"] = f"Unknown sport type '{sport_type}' — not in ruleset"
        result["review"] = True
        return result

    # ── Distance-based ──
    if label in DISTANCE_RATES:

        # No distance tracked
        if distance_m <= 0:
            result["flag"] = True
            result["flag_reason"] = "No distance tracked — manual entry needed"
            result["review"] = True
            return result

        # Pace check for runs
        if label == "Run" and moving_time_s > 0:
            pace = moving_time_s / (distance_m / 1000)
            if pace > RUN_MAX_PACE_SEC_PER_KM:
                # Convert to walk points
                walk_pts = (distance_m / 1000) * DISTANCE_RATES["Walk / Hike"]
                result["points"] = walk_pts
                result["display"] = f"{distance_m/1000:.2f} km @ {fmt_pace(distance_m, moving_time_s)} → counted as walk"
                result["flag"] = True
                result["flag_reason"] = f"Pace {fmt_pace(distance_m, moving_time_s)} > 9:00/km — converted to walk points ({walk_pts:.2f} pts)"
                result["review"] = True
                return result

        # Downhill ski: 2/3 of distance
        if label == "Downhill Ski":
            effective_km = (distance_m / 1000) * (2/3)
            pts = effective_km * DISTANCE_RATES[label]
            result["points"] = pts
            result["display"] = f"{distance_m/1000:.2f} km → {effective_km:.2f} km effective (2/3 rule) → {pts:.2f} pts"
            return result

        # Normal distance activity
        pts = (distance_m / 1000) * DISTANCE_RATES[label]
        result["points"] = pts
        pace_str = f" @ {fmt_pace(distance_m, moving_time_s)}" if moving_time_s > 0 and label == "Run" else ""
        result["display"] = f"{distance_m/1000:.2f} km{pace_str} → {pts:.2f} pts"

        # Sanity checks — flag but still count
        flags = []
        if label in MAX_DISTANCE and distance_m > MAX_DISTANCE[label]:
            flags.append(f"unusually long ({distance_m/1000:.1f} km) — verify activity")
        if label in SPEED_LIMITS and moving_time_s > 0:
            speed_kmh = (distance_m / 1000) / (moving_time_s / 3600)
            min_speed, max_speed = SPEED_LIMITS[label]
            if speed_kmh < min_speed:
                flags.append(f"very slow pace ({speed_kmh:.1f} km/h) — possible GPS error or vehicle")
            elif speed_kmh > max_speed:
                flags.append(f"very fast pace ({speed_kmh:.1f} km/h) — verify activity")
        if flags:
            result["flag"] = True
            result["flag_reason"] = "; ".join(flags)
            result["review"] = True

        return result

    # ── Time-based ──
    if label in TIME_RATES:
        pts = (moving_time_s / 3600) * TIME_RATES[label]
        result["points"] = pts
        result["display"] = f"{fmt_time(moving_time_s)} @ {TIME_RATES[label]} pts/hr → {pts:.2f} pts"
        return result

    # Fallback — shouldn't hit this if ACTIVITY_LABELS is complete
    result["flag"] = True
    result["flag_reason"] = "No point rule found — manual entry needed"
    result["review"] = True
    return result

# ── Totals ────────────────────────────────────────────────────────────────────

def calculate_totals(month_activities):
    filtered = []
    for a in month_activities:
        fn = a.get("athlete", {}).get("firstname", "")
        ln = a.get("athlete", {}).get("lastname", "")
        key = f"{fn} {ln}"
        if key not in EXCLUDED_ATHLETES:
            filtered.append(a)
    results = [calculate_activity(a) for a in filtered]

    # Group by athlete
    totals = {}
    for r in results:
        name = r["name"]
        if name not in totals:
            totals[name] = {"points": 0.0, "activities": []}
        totals[name]["points"] = totals[name]["points"] + r["points"]
        totals[name]["activities"].append(r)

    return totals, results

# ── HTML Output ───────────────────────────────────────────────────────────────

def build_points_html(totals, month_name):
    GOAL = 80
    today = datetime.now()
    days_in_month = (datetime(today.year, today.month % 12 + 1, 1) - datetime(today.year, today.month, 1)).days if today.month < 12 else 31
    expected = round((GOAL / days_in_month) * today.day, 2)

    # Sort alphabetically
    sorted_athletes = sorted(totals.items(), key=lambda x: x[0])

    # Athlete summary rows
    summary_rows = ""
    for name, data in sorted_athletes:
        pts = round(data["points"], 2)
        pct = min(pts / GOAL * 100, 100)
        color = "#16A34A" if pts >= GOAL else "#F59E0B" if pts >= 60 else "#EF4444"
        badge = ' <span style="background:#DCFCE7;color:#166534;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">✓ Goal met</span>' if pts >= GOAL else ""
        has_review = any(r["review"] for r in data["activities"])
        review_badge = ' <span style="background:#FEF3C7;color:#92400E;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600">⚠️ Review</span>' if has_review else ""

        diff = round(pts - expected, 2)
        if pts >= GOAL:
            pace_str = "—"
            pace_color = "#16A34A"
        elif diff >= 0:
            pace_str = f"+{diff} ahead"
            pace_color = "#16A34A"
        else:
            pace_str = f"{diff} behind"
            pace_color = "#EF4444"

        summary_rows += f'''
        <div class="athlete-row">
          <div class="athlete-name">{name}{badge}{review_badge}</div>
          <div class="progress-wrap">
            <div class="progress-bar" style="width:{pct:.0f}%;background:{color}"></div>
          </div>
          <div class="pts-label" style="color:{color}">{pts} / {GOAL}</div>
          <div class="pace-label" style="color:{pace_color}">{pace_str}</div>
        </div>'''

    # Detail table per athlete — alphabetical
    detail_html = ""
    for name, data in sorted_athletes:
        has_flags = any(r["flag"] for r in data["activities"])
        pending_pts = sum(r["points"] for r in data["activities"] if r["review"])
        confirmed_pts = round(data["points"] - pending_pts, 2)
        pending_pts = round(pending_pts, 2)
        total_pts = round(data["points"], 2)

        pending_str = f' &nbsp;·&nbsp; <span style="color:#92400E">⚠️ Pending: {pending_pts} pts</span> &nbsp;·&nbsp; <span style="color:#166534">✓ Confirmed: {confirmed_pts} pts</span>' if pending_pts > 0 else ""

        rows = ""
        for r in data["activities"]:
            flag_td = ""
            row_class = ""
            row_style = ""

            if r.get("denied"):
                row_class = "denied-row"
                row_style = "opacity:0.4;text-decoration:line-through;"
                flag_td = f'<td class="flag-cell">❌ Denied by reviewer</td>'
            elif r["review"]:
                row_class = "review-row"
                # Build GitHub issue link
                athlete_full = f"{name} {data['activities'][0]['name'] if data['activities'] else ''}"
                issue_title = f"Review: {name} - {r['activity_name']}"
                issue_body = f"**Athlete:** {name}\n**Activity:** {r['activity_name']}\n**Type:** {r['label']}\n**Detail:** {r['display']}\n**Points:** {round(r['points'],2)}\n**Flag reason:** {r['flag_reason']}"
                import urllib.parse
                issue_url = f"https://github.com/neilportelance/FitnessFam/issues/new?title={urllib.parse.quote(issue_title)}&body={urllib.parse.quote(issue_body)}&labels=pending-review"
                flag_td = f'<td class="flag-cell">⚠️ {r["flag_reason"]} &nbsp;<a href="{issue_url}" target="_blank" class="review-btn">Open Review</a></td>'
            elif r["flag"]:
                row_class = "flag-row"
                flag_td = f'<td class="flag-cell">🔴 {r["flag_reason"]}</td>'
            else:
                flag_td = '<td class="flag-cell"></td>'

            rows += f'''<tr class="{row_class}" style="{row_style}">
              <td class="act-name-cell">{r["activity_name"]}</td>
              <td class="type-cell">{r["label"]}</td>
              <td class="detail-cell">{r["display"]}</td>
              <td class="pts-cell">{round(r["points"], 2)}</td>
              {flag_td}
            </tr>'''

        detail_html += f'''
        <div class="detail-section">
          <div class="detail-header">
            {name} — <span class="total-pts">{total_pts} pts</span>{pending_str}
            {"<span class='has-flags'>⚠️ has items needing review</span>" if has_flags else ""}
          </div>
          <table class="detail-table">
            <thead><tr>
              <th>Activity</th><th>Type</th><th>Detail</th><th>Pts</th><th>Notes</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>'''

    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{month_name} Points — Lively Fitness Challenge</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F3F4F6;padding:24px 16px;color:#111827}}
  .wrap{{max-width:960px;margin:0 auto}}
  h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
  .subtitle{{font-size:13px;color:#6B7280;margin-bottom:24px}}
  h2{{font-size:16px;font-weight:600;margin-bottom:12px;color:#374151}}
  .card{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .athlete-row{{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #F3F4F6}}
  .athlete-row:last-child{{border-bottom:none}}
  .athlete-name{{min-width:140px;font-weight:500;font-size:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
  .progress-wrap{{flex:1;height:8px;background:#E5E7EB;border-radius:4px;overflow:hidden}}
  .progress-bar{{height:100%;border-radius:4px;transition:width 0.3s}}
  .pts-label{{min-width:70px;text-align:right;font-weight:600;font-size:14px}}
  .pace-label{{min-width:100px;text-align:right;font-weight:500;font-size:13px}}
  .detail-section{{margin-bottom:24px}}
  .detail-header{{font-size:14px;font-weight:600;padding:8px 12px;background:#F9FAFB;border-radius:8px 8px 0 0;border:1px solid #E5E7EB;display:flex;align-items:center;gap:10px}}
  .total-pts{{color:#2563EB}}
  .has-flags{{font-size:12px;color:#92400E;background:#FEF3C7;padding:2px 8px;border-radius:4px}}
  .detail-table{{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #E5E7EB;border-top:none}}
  .detail-table th{{background:#F9FAFB;padding:7px 10px;text-align:left;font-weight:600;font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.04em;border-bottom:1px solid #E5E7EB}}
  .detail-table td{{padding:7px 10px;border-bottom:1px solid #F3F4F6;vertical-align:top}}
  .detail-table tr:last-child td{{border-bottom:none}}
  .flag-row td{{background:#FFF5F5}}
  .review-row td{{background:#FFFBEB}}
  .denied-row td{{background:#FFF5F5;opacity:0.5;text-decoration:line-through}}
  .review-btn{{display:inline-block;margin-left:8px;padding:2px 8px;background:#1D4ED8;color:#fff;border-radius:4px;font-size:11px;font-weight:600;text-decoration:none}}
  .review-btn:hover{{background:#1E40AF}}
  .flag-cell{{font-size:12px;color:#92400E}}
  .pts-cell{{font-weight:600;text-align:right;white-space:nowrap}}
  .act-name-cell{{color:#374151}}
  .type-cell{{color:#6B7280;white-space:nowrap}}
  .detail-cell{{color:#374151}}
  .footer{{text-align:center;font-size:11px;color:#9CA3AF;margin-top:16px}}
  .goal-line{{font-size:12px;color:#6B7280;margin-bottom:8px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>📊 {month_name} Points</h1>
  <div class="subtitle">Lively Fitness Challenge — Goal: {GOAL} pts</div>

  <div class="card">
    <h2>Standings</h2>
    <div class="goal-line">Goal: {GOAL} pts &nbsp;|&nbsp; Expected by today (day {today.day}/{days_in_month}): <strong>{expected} pts</strong> &nbsp;|&nbsp; ✓ = goal met &nbsp;|&nbsp; ⚠️ = needs manual review</div>
    <div class="athlete-row" style="font-size:11px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:4px;border-bottom:2px solid #E5E7EB">
      <div class="athlete-name">Athlete</div>
      <div class="progress-wrap"></div>
      <div class="pts-label">Points</div>
      <div class="pace-label">Pacing</div>
    </div>
    {summary_rows}
  </div>

  <div class="card">
    <h2>Activity breakdown</h2>
    {detail_html}
  </div>

  <div class="footer">Generated {generated} — ⚠️ flagged items require manual review before finalizing</div>
</div>
</body>
</html>'''

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("📊 Strava Points Calculator")
    print("─" * 30)

    from leaderboard import load_cache, find_anchor_idx, load_anchor as lb_load_anchor

    activities = load_cache()
    if not activities:
        print("Cache is empty — run python leaderboard.py first.")
        return
    print(f"✓ Loaded {len(activities)} activities from cache\n")

    anchor = lb_load_anchor()
    if anchor is None:
        print("No anchor set — run leaderboard.py --set-anchor first.")
        return

    anchor_count = find_anchor_idx(activities, anchor)
    print(f"⚓ Anchor: {anchor_count} activities at month start")
    print(f"  {len(activities) - anchor_count} activities this month\n")

    month_activities = activities[anchor_count:]
    if not month_activities:
        print("No activities found before anchor.")
        return

    month_name = datetime.now().strftime("%B %Y")
    totals, results = calculate_totals(month_activities)

    # Terminal summary
    today = datetime.now()
    days_in_month = (datetime(today.year, today.month % 12 + 1, 1) - datetime(today.year, today.month, 1)).days if today.month < 12 else 31
    expected = round((80 / days_in_month) * today.day, 2)
    print(f"Expected by today (day {today.day}/{days_in_month}): {expected} pts\n")
    print(f"{'Athlete':<20} {'Points':>8}  {'Pacing':>10}  {'Status'}")
    print("─" * 55)
    for name, data in sorted(totals.items(), key=lambda x: x[0]):
        pts = round(data["points"], 2)
        diff = round(pts - expected, 2)
        pace_str = "goal met" if pts >= 80 else (f"+{diff}" if diff >= 0 else str(diff))
        status = "✓ Goal met" if pts >= 80 else f"{round(80 - pts, 2)} pts to go"
        has_review = any(r["review"] for r in data["activities"])
        review_str = " ⚠️" if has_review else ""
        print(f"{name:<20} {pts:>8}  {pace_str:>10}  {status}{review_str}")

    # Review items
    review_items = [r for r in results if r["review"]]
    if review_items:
        print(f"\n⚠️  {len(review_items)} item(s) need manual review:")
        print("─" * 45)
        for r in review_items:
            print(f"  {r['name']:<15} {r['label']:<25} {r['flag_reason']}")

    # HTML
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    html = build_points_html(totals, month_name)
    html_path = reports_dir / "points.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ Points report saved to {html_path.resolve()}")

if __name__ == "__main__":
    main()
