import json
import requests
from pathlib import Path
from datetime import datetime

CONFIG_FILE  = Path("config.json")
ANCHOR_FILE  = Path("anchor.json")
ALLTIME_FILE = Path("alltime.json")
ARCHIVE_DIR  = Path("archive")

MIN_SESSION_SECONDS = 30 * 60

MEMBERS_FILE = Path("members.json")

def load_members():
    """Load members.json and return (excluded_set, known_set) of 'firstname lastname' keys."""
    if not MEMBERS_FILE.exists():
        return set(), set()
    data = json.load(open(MEMBERS_FILE))
    excluded = set()
    known = set()
    for m in data["members"]:
        key = f"{m['firstname']} {m['lastname']}"
        known.add(key)
        if not m["participating"]:
            excluded.add(key)
    return excluded, known

EXCLUDED_ATHLETES, KNOWN_ATHLETES = load_members()

# ── Activity Categories ───────────────────────────────────────────────────────

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
    "Workout": "Gym / Medium Intensity", "WeightTraining": "Gym / Medium Intensity", "RockClimbing": "Gym / Medium Intensity",
    "Elliptical": "Elliptical / High Intensity", "StairStepper": "Elliptical / High Intensity",
    "Crossfit": "Crossfit / HIIT / High Intensity", "HighIntensityIntervalTraining": "Crossfit / HIIT / High Intensity",
    "Tennis": "Tennis / Squash / High Intensity", "Squash": "Tennis / Squash / High Intensity",
    "Pickleball": "Pickleball / Medium Intensity",
    "Soccer": "Team Sports / Medium Intensity", "Hockey": "Team Sports / Medium Intensity",
    "IceHockey": "Team Sports / Medium Intensity", "Handball": "Team Sports / Medium Intensity",
    "Basketball": "Team Sports / Medium Intensity", "Football": "Team Sports / Medium Intensity",
    "Volleyball": "Team Sports / Medium Intensity",
}

MIN_DISTANCE = {
    "Run": 3000, "Road Bike": 5000,
    "Indoor Bike / Spin": 5000, "Mountain Bike": 5000, "Swim": 1000,
}

NO_PACE_ACTIVITIES = {"Walk / Hike", "Paddle / Kayak / SUP", "Downhill Ski"}

DISTANCE_ACTIVITIES = {
    "Run", "Nordic Ski / XC Ski", "Walk / Hike",
    "Paddle / Kayak / SUP", "Mountain Bike", "Road Bike", "Indoor Bike / Spin", "Swim", "Downhill Ski",
}

ACTIVITY_ORDER = [
    "Run", "Nordic Ski / XC Ski", "Road Bike", "Indoor Bike / Spin", "Mountain Bike",
    "Swim", "Downhill Ski", "Walk / Hike", "Paddle / Kayak / SUP",
    "Crossfit / HIIT / High Intensity", "Elliptical / High Intensity",
    "Tennis / Squash / High Intensity", "Team Sports / Medium Intensity",
    "Pickleball / Medium Intensity", "Gym / Medium Intensity", "Yoga / Low Intensity",
]

ACTIVITY_EMOJI = {
    "Run": "🏃", "Nordic Ski / XC Ski": "⛷️", "Walk / Hike": "🚶",
    "Paddle / Kayak / SUP": "🛶", "Mountain Bike": "🚵", "Road Bike": "🚴",
    "Indoor Bike / Spin": "🏠", "Swim": "🏊", "Downhill Ski": "🎿",
    "Yoga / Low Intensity": "🧘", "Gym / Medium Intensity": "💪",
    "Elliptical / High Intensity": "⚡", "Crossfit / HIIT / High Intensity": "🔥",
    "Tennis / Squash / High Intensity": "🎾", "Pickleball / Medium Intensity": "🏓",
    "Team Sports / Medium Intensity": "⚽",
}

# ── Intensity Tiers ───────────────────────────────────────────────────────────

INTENSITY_TIERS = {
    "🔥 High Intensity": {
        "labels": {"Crossfit / HIIT / High Intensity", "Elliptical / High Intensity", "Tennis / Squash / High Intensity"},
        "short": {"Crossfit / HIIT / High Intensity": "HIIT", "Elliptical / High Intensity": "Elliptical", "Tennis / Squash / High Intensity": "Tennis/Squash"},
    },
    "💪 Medium Intensity": {
        "labels": {"Gym / Medium Intensity", "Pickleball / Medium Intensity", "Team Sports / Medium Intensity"},
        "short": {"Gym / Medium Intensity": "Gym", "Pickleball / Medium Intensity": "Pickleball", "Team Sports / Medium Intensity": "Team Sports"},
    },
    "🧘 Low Intensity": {
        "labels": {"Yoga / Low Intensity"},
        "short": {"Yoga / Low Intensity": "Yoga"},
    },
}

def get_top3_sessions_tiered(activities, tier_labels, short_names, name_map):
    """Get top 3 sessions across all activities in a tier, with breakdown per activity."""
    filtered = [a for a in activities if get_label(a.get("sport_type","")) in tier_labels]
    # Count sessions per athlete per label
    counts = {}  # full_name -> {label -> count}
    for a in filtered:
        full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
        label = get_label(a.get("sport_type",""))
        if full not in counts:
            counts[full] = {}
        counts[full][label] = counts[full].get(label, 0) + 1
    # Total sessions per athlete
    totals = {full: sum(v.values()) for full, v in counts.items()}
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    # Build display strings
    result = []
    for full, total in ranked:
        breakdown = counts[full]
        parts = []
        for label in sorted(breakdown.keys()):
            short = short_names.get(label, label)
            cnt = breakdown[label]
            parts.append(f"{short} x{cnt}" if cnt > 1 else short)
        display = f"{total} session{'s' if total!=1 else ''} ({', '.join(parts)})"
        result.append((name_map.get(full, full.split()[0]), total, display))
    return olympic_podium(result)

RANK_EMOJI = ["🥇", "🥈", "🥉"]

MEDAL_COLORS = {
    "🥇": ("#FFF8E7", "#F59E0B", "#92400E"),
    "🥈": ("#F3F4F6", "#9CA3AF", "#374151"),
    "🥉": ("#FFF3EE", "#C2622D", "#7C2D12"),
}

# ── Auth ──────────────────────────────────────────────────────────────────────

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

# ── Fetch ─────────────────────────────────────────────────────────────────────

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

# ── Cache ─────────────────────────────────────────────────────────────────────

CACHE_FILE  = Path("cache.json")   # legacy, newest-first
CACHE2_FILE = Path("cache2.json")  # new, oldest-first
ANCHOR2_FILE = Path("anchor2.json")

def activity_fingerprint(a):
    """Unique key for an activity — used for deduplication."""
    return (
        a.get("athlete", {}).get("firstname", ""),
        a.get("athlete", {}).get("lastname", ""),
        a.get("sport_type", ""),
        round(a.get("distance", 0)),
        a.get("moving_time", 0),
    )

def load_cache():
    """Load cache2 (oldest-first). Migrates from cache.json if needed."""
    if CACHE2_FILE.exists():
        with open(CACHE2_FILE) as f:
            return json.load(f)
    # Migrate from old cache.json
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            old = json.load(f)
        # old cache is newest-first, reverse it
        migrated = list(reversed(old))
        with open(CACHE2_FILE, "w") as f:
            json.dump(migrated, f)
        print(f"  Migrated {len(migrated)} activities from cache.json → cache2.json (oldest-first)")
        return migrated
    return []

def merge_and_save_cache(fresh_activities):
    """
    Merge fresh API activities (newest-first) into cache2 (oldest-first).
    New activities are appended to the END of cache2.
    """
    cached = load_cache()
    existing_fps = {activity_fingerprint(a) for a in cached}
    # fresh_activities is newest-first from API; new ones not yet in cache
    new_entries = [a for a in fresh_activities if activity_fingerprint(a) not in existing_fps]
    # Append new entries oldest-first (reverse the new ones before appending)
    merged = cached + list(reversed(new_entries))
    with open(CACHE2_FILE, "w") as f:
        json.dump(merged, f)
    print(f"  Cache: {len(cached)} existing + {len(new_entries)} new = {len(merged)} total")
    return merged

# ── Anchor ────────────────────────────────────────────────────────────────────

def load_anchor():
    """Load anchor2 (count-based) or fall back to legacy anchor.json."""
    if ANCHOR2_FILE.exists():
        with open(ANCHOR2_FILE) as f:
            return json.load(f)
    if ANCHOR_FILE.exists():
        with open(ANCHOR_FILE) as f:
            return json.load(f)
    return None

def find_anchor_idx(activities, anchor):
    """
    For anchor2: anchor_count = number of activities at start of month.
    Month activities = everything FROM anchor_count onwards (newest end of cache).
    For legacy anchor: use fingerprint or index.
    """
    if "anchor_count" in anchor:
        return anchor["anchor_count"]
    # Legacy fingerprint
    if "fingerprint" in anchor:
        fp = tuple(anchor["fingerprint"])
        for i, a in enumerate(activities):
            if activity_fingerprint(a) == fp:
                return i
    return anchor.get("index", 0)

def save_anchor(anchor):
    with open(ANCHOR2_FILE, "w") as f:
        json.dump(anchor, f, indent=4)

def set_anchor(activities):
    """Set anchor as current cache size — everything after this is the new month."""
    anchor_count = len(activities)
    anchor = {"anchor_count": anchor_count}
    save_anchor(anchor)
    print(f"\n✓ Anchor set — {anchor_count} activities in cache. New month starts here.")
    return anchor_count


# ── Formatting ────────────────────────────────────────────────────────────────

def build_name_map(activities):
    name_map = {}
    for a in activities:
        full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
        name_map[full] = a['athlete']['firstname']
    return name_map

def get_label(sport_type):
    return ACTIVITY_LABELS.get(sport_type, sport_type)

REVIEW_FILE = Path("manual_review.json")

def load_review():
    if REVIEW_FILE.exists():
        with open(REVIEW_FILE) as f:
            return json.load(f)
    return {"approved": [], "denied": []}

REVIEW = load_review()

def is_denied_activity(a):
    """Check if an activity has been denied in manual_review.json."""
    fn = a.get("athlete", {}).get("firstname", "")
    name = a.get("name", "")
    return any(
        r.get("athlete", "").startswith(fn) and r.get("activity") == name
        for r in REVIEW.get("denied", [])
    )

def fmt_dist(m):
    return f"{m/1000:.1f} km"

def fmt_time(s):
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def fmt_pace(distance_m, time_s):
    if distance_m <= 0:
        return "N/A"
    p = time_s / (distance_m / 1000)
    return f"{int(p//60)}:{int(p%60):02d}/km"

# ── Olympic Podium ────────────────────────────────────────────────────────────

def olympic_podium(ranked):
    if not ranked:
        return []
    tiers, i = [], 0
    while i < len(ranked):
        cur = ranked[i][1]
        tier = []
        while i < len(ranked) and ranked[i][1] == cur:
            tier.append(ranked[i]); i += 1
        tiers.append(tier)
    result = []
    for idx, tier in enumerate(tiers[:3]):
        medal = RANK_EMOJI[idx]
        names = " & ".join(t[0] for t in tier)
        result.append((medal, f"{medal} {names} — {tier[0][2]}"))
    return result

# ── Rankings ──────────────────────────────────────────────────────────────────

def get_top3_distance(activities, label, name_map):
    min_d = MIN_DISTANCE.get(label, 0)
    filtered = [a for a in activities if get_label(a.get("sport_type",""))==label and a.get("distance",0)>=max(min_d,1)]
    best = {}
    for a in filtered:
        full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
        if full not in best or a["distance"] > best[full]["distance"]:
            best[full] = a
    ranked = sorted(best.values(), key=lambda a: a["distance"], reverse=True)
    return olympic_podium([(name_map[f"{a['athlete']['firstname']} {a['athlete']['lastname']}"], a["distance"],
        f"{fmt_dist(a['distance'])} — {fmt_time(a['moving_time'])}") for a in ranked])

def get_top3_pace(activities, label, name_map):
    min_d = MIN_DISTANCE.get(label, 0)
    filtered = [a for a in activities if get_label(a.get("sport_type",""))==label
        and a.get("distance",0)>=max(min_d,1) and a.get("moving_time",0)>0]
    best = {}
    for a in filtered:
        full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
        pace = a["moving_time"] / (a["distance"] / 1000)
        if full not in best or pace < best[full]["pace"]:
            best[full] = {**a, "pace": pace}
    ranked = sorted(best.values(), key=lambda a: a["pace"])
    return olympic_podium([(name_map[f"{a['athlete']['firstname']} {a['athlete']['lastname']}"], round(a["pace"]),
        f"{fmt_pace(a['distance'],a['moving_time'])} — {fmt_dist(a['distance'])}") for a in ranked])

def get_top3_sessions(activities, label, name_map):
    filtered = [a for a in activities if get_label(a.get("sport_type",""))==label
        and a.get("moving_time",0)>=MIN_SESSION_SECONDS]
    counts = {}
    for a in filtered:
        full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
        counts[full] = counts.get(full, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return olympic_podium([(name_map[name], count, f"{count} session{'s' if count!=1 else ''}") for name, count in ranked])

# ── All Time Records ──────────────────────────────────────────────────────────

def load_alltime():
    if ALLTIME_FILE.exists():
        with open(ALLTIME_FILE) as f:
            return json.load(f)
    return {}

def save_alltime(data):
    with open(ALLTIME_FILE, "w") as f:
        json.dump(data, f, indent=2)

def build_alltime_from_activities(activities, month_key):
    """Compute all time top 3 records from a flat list of activities."""
    name_map = build_name_map(activities)
    records = {}

    present = set(get_label(a.get("sport_type","")) for a in activities)
    for label in present:
        records[label] = {}
        if label in DISTANCE_ACTIVITIES:
            min_d = MIN_DISTANCE.get(label, 0)
            dist_acts = [a for a in activities if get_label(a.get("sport_type",""))==label and a.get("distance",0)>=max(min_d,1)]

            # Top 3 distance — best per athlete then top 3
            best_dist = {}
            for a in dist_acts:
                full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
                if full not in best_dist or a["distance"] > best_dist[full]["distance"]:
                    best_dist[full] = a
            top3_dist = sorted(best_dist.values(), key=lambda a: a["distance"], reverse=True)[:3]
            if top3_dist:
                records[label]["distance"] = [
                    {"name": name_map[f"{a['athlete']['firstname']} {a['athlete']['lastname']}"],
                     "value": a["distance"],
                     "display": f"{fmt_dist(a['distance'])} ({fmt_time(a['moving_time'])})",
                     "month": month_key}
                    for a in top3_dist
                ]

            # Top 3 pace — best per athlete then top 3
            if label not in NO_PACE_ACTIVITIES:
                pace_acts = [a for a in dist_acts if a.get("moving_time",0)>0]
                best_pace = {}
                for a in pace_acts:
                    full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
                    pace = a["moving_time"] / (a["distance"]/1000)
                    if full not in best_pace or pace < best_pace[full]["pace"]:
                        best_pace[full] = {**a, "pace": pace}
                top3_pace = sorted(best_pace.values(), key=lambda a: a["pace"])[:3]
                if top3_pace:
                    records[label]["pace"] = [
                        {"name": name_map[f"{a['athlete']['firstname']} {a['athlete']['lastname']}"],
                         "value": round(a["pace"]),
                         "display": f"{fmt_pace(a['distance'], a['moving_time'])} ({fmt_dist(a['distance'])})",
                         "month": month_key}
                        for a in top3_pace
                    ]
        else:
            sess_acts = [a for a in activities if get_label(a.get("sport_type",""))==label
                and a.get("moving_time",0)>=MIN_SESSION_SECONDS]
            counts = {}
            for a in sess_acts:
                full = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
                counts[full] = counts.get(full,0)+1
            top3_sess = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]
            if top3_sess:
                records[label]["sessions"] = [
                    {"name": name_map[name], "value": count,
                     "display": f"{count} session{'s' if count!=1 else ''}",
                     "month": month_key}
                    for name, count in top3_sess
                ]
    return records

def merge_alltime(existing, new_records):
    """Merge new top 3 lists into existing, keeping best 3 unique athletes. Returns (merged, broken records)."""
    merged = {k: {m: list(v) for m, v in metrics.items()} for k, metrics in existing.items()}
    broken = []

    for label, metrics in new_records.items():
        if label not in merged:
            merged[label] = {}
        for metric, new_entries in metrics.items():
            existing_entries = merged[label].get(metric, [])
            # Combine, keep best per athlete, then top 3
            combined = {e["name"]: e for e in existing_entries}
            for e in new_entries:
                name = e["name"]
                if name not in combined:
                    combined[name] = e
                else:
                    old = combined[name]
                    is_better = (e["value"] < old["value"]) if metric == "pace" else (e["value"] > old["value"])
                    if is_better:
                        combined[name] = e
            # Sort and take top 3
            reverse = metric != "pace"
            top3 = sorted(combined.values(), key=lambda x: x["value"], reverse=reverse)[:3]
            # Find newly broken records (entries that weren't in existing top 3)
            old_names = {e["name"] for e in existing_entries}
            old_top_val = existing_entries[0]["value"] if existing_entries else None
            for e in top3:
                is_new = e["name"] not in old_names
                is_better_than_best = old_top_val is None or (
                    (e["value"] < old_top_val) if metric == "pace" else (e["value"] > old_top_val)
                )
                if is_new or is_better_than_best:
                    broken.append((label, metric, e))
            merged[label][metric] = top3

    return merged, broken

def update_alltime(month_activities, month_key):
    existing = load_alltime()
    new_records = build_alltime_from_activities(month_activities, month_key)
    merged, broken = merge_alltime(existing, new_records)
    save_alltime(merged)
    return merged, broken

def build_alltime_bootstrap(activities):
    """Used by --build-alltime to process full history."""
    month_key = "historical"
    records = build_alltime_from_activities(activities, month_key)
    save_alltime(records)
    print(f"✓ All time records built from {len(activities)} activities")
    total = sum(len(v) for v in records.values())
    print(f"  {len(records)} categories, {total} records saved to {ALLTIME_FILE}")

# ── Archive ───────────────────────────────────────────────────────────────────

def save_archive(month_key, month_activities):
    ARCHIVE_DIR.mkdir(exist_ok=True)
    path = ARCHIVE_DIR / f"{month_key}.json"
    with open(path, "w") as f:
        json.dump(month_activities, f)
    print(f"✓ Archive saved to {path}")

# ── Text Message ──────────────────────────────────────────────────────────────

def build_message(month_activities, month_name):
    name_map = build_name_map(month_activities)
    present = set(get_label(a.get("sport_type","")) for a in month_activities)
    distance_labels = [l for l in ACTIVITY_ORDER if l in present and l in DISTANCE_ACTIVITIES]
    lines = [f"🏆 {month_name} Top 3", "─"*26]

    # Distance activities
    for label in distance_labels:
        emoji = ACTIVITY_EMOJI.get(label,"🏅")
        dist_p = get_top3_distance(month_activities, label, name_map)
        pace_p = get_top3_pace(month_activities, label, name_map)
        if not dist_p and not pace_p:
            continue
        lines.append(f"\n{emoji} {label}")
        if dist_p:
            lines.append("  📏 Longest")
            for _, line in dist_p: lines.append(f"    {line}")
        if pace_p and label not in NO_PACE_ACTIVITIES:
            lines.append("  ⚡ Fastest pace")
            for _, line in pace_p: lines.append(f"    {line}")

    # Intensity tiers
    for tier_name, tier in INTENSITY_TIERS.items():
        if not any(l in present for l in tier["labels"]):
            continue
        sess_p = get_top3_sessions_tiered(month_activities, tier["labels"], tier["short"], name_map)
        if not sess_p: continue
        lines.append(f"\n{tier_name}")
        for _, line in sess_p: lines.append(f"    {line}")

    return "\n".join(lines)

# ── HTML ──────────────────────────────────────────────────────────────────────

def render_tier_html(tier_name, tier, month_activities, name_map, broken_set):
    present = set(get_label(a.get("sport_type","")) for a in month_activities)
    if not any(l in present for l in tier["labels"]):
        return ""

    def row_html(medal, content):
        bg, border, text = MEDAL_COLORS.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
        return f'<div class="row" style="background:{bg};border-left:3px solid {border};color:{text}"><span class="medal">{medal}</span><span class="entry">{content}</span></div>'

    sess_p = get_top3_sessions_tiered(month_activities, tier["labels"], tier["short"], name_map)
    if not sess_p:
        return ""
    rows = f'<div class="section-title">{tier_name}</div>'
    for medal, line in sess_p:
        rows += row_html(medal, line[2:].strip())
    return f'<div class="section">{rows}</div>'

def render_alltime_tier_html(tier_name, tier, alltime):
    combined = {}
    for label in tier["labels"]:
        if label not in alltime or "sessions" not in alltime[label]:
            continue
        short = tier["short"].get(label, label)
        for entry in alltime[label]["sessions"]:
            name = entry["name"]
            if name not in combined:
                combined[name] = {"name": name, "total": 0, "parts": {}}
            combined[name]["total"] += entry["value"]
            combined[name]["parts"][short] = entry["value"]
    if not combined:
        return ""
    ranked = sorted(combined.values(), key=lambda x: x["total"], reverse=True)[:3]
    rows = f'<div class="section-title" style="background:#F0FDF4;color:#166534">{tier_name}</div>'
    rows += '<div class="sub-label">🔢 Most sessions</div>'
    for i, entry in enumerate(ranked):
        medal = RANK_EMOJI[i]
        bg, border, text = MEDAL_COLORS.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
        parts = [f"{s} x{c}" if c > 1 else s for s, c in sorted(entry["parts"].items())]
        display = f"{entry['total']} session{'s' if entry['total']!=1 else ''} ({', '.join(parts)})"
        rows += f'<div class="row" style="background:{bg};border-left:3px solid {border};color:{text}"><span class="medal">{medal}</span><span class="entry">{entry["name"]} — {display}</span></div>'
    return f'<div class="section" style="margin-bottom:10px;padding:10px 12px 8px">{rows}</div>'

def render_section_html(label, month_activities, name_map, alltime, broken_set):
    emoji = ACTIVITY_EMOJI.get(label,"🏅")
    rows = ""

    def row_html(medal, content, is_record=False):
        bg, border, text = MEDAL_COLORS.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
        badge = ' <span class="record-badge">🏆 New record</span>' if is_record else ""
        return f'<div class="row" style="background:{bg};border-left:3px solid {border};color:{text}"><span class="medal">{medal}</span><span class="entry">{content}{badge}</span></div>'

    def is_broken(label, metric, podium):
        if not podium: return []
        return [(label, metric, line[2:].strip().split("—")[0].strip()) in broken_set for _, line in podium]

    dist_p = get_top3_distance(month_activities, label, name_map)
    pace_p = get_top3_pace(month_activities, label, name_map)
    if not dist_p and not pace_p:
        return ""
    rows += f'<div class="section-title">{emoji} {label}</div>'
    if dist_p:
        rows += '<div class="sub-label">📏 Longest</div>'
        flags = is_broken(label, "distance", dist_p)
        for i,(medal,line) in enumerate(dist_p):
            rows += row_html(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
    if pace_p and label not in NO_PACE_ACTIVITIES:
        rows += '<div class="sub-label">⚡ Fastest pace</div>'
        flags = is_broken(label, "pace", pace_p)
        for i,(medal,line) in enumerate(pace_p):
            rows += row_html(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
    return f'<div class="section">{rows}</div>'

def render_alltime_section_html(label, alltime):
    if label not in alltime or label not in DISTANCE_ACTIVITIES:
        return ""
    emoji = ACTIVITY_EMOJI.get(label,"🏅")
    data = alltime[label]
    rows = f'<div class="section-title" style="background:#F0FDF4;color:#166534">{emoji} {label}</div>'

    def at_podium_rows(entries, sub_label):
        if not entries:
            return ""
        html = f'<div class="sub-label">{sub_label}</div>'
        for i, entry in enumerate(entries[:3]):
            medal = RANK_EMOJI[i]
            bg, border, text = MEDAL_COLORS.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
            html += f'<div class="row" style="background:{bg};border-left:3px solid {border};color:{text}"><span class="medal">{medal}</span><span class="entry">{entry["name"]} — {entry["display"]}</span></div>'
        return html

    if "distance" in data:
        rows += at_podium_rows(data["distance"], "📏 Longest")
    if "pace" in data and label not in NO_PACE_ACTIVITIES:
        rows += at_podium_rows(data["pace"], "⚡ Fastest pace")
    return f'<div class="section" style="margin-bottom:10px;padding:10px 12px 8px">{rows}</div>'

def build_html(month_activities, month_name, alltime, broken_records):
    name_map = build_name_map(month_activities)
    present = set(get_label(a.get("sport_type","")) for a in month_activities)
    distance_labels = [l for l in ACTIVITY_ORDER if l in present and l in DISTANCE_ACTIVITIES]
    all_distance = set(distance_labels) | {l for l in alltime if l in DISTANCE_ACTIVITIES}
    all_distance_ordered = [l for l in ACTIVITY_ORDER if l in all_distance] + sorted(l for l in all_distance if l not in ACTIVITY_ORDER)

    broken_set = set()
    for label, metric, entry in broken_records:
        broken_set.add((label, metric, entry["name"]))

    month_col = ""
    alltime_col = ""

    # Distance sections
    for label in all_distance_ordered:
        if label in present:
            month_col += render_section_html(label, month_activities, name_map, alltime, broken_set)
        if label in alltime:
            alltime_col += render_alltime_section_html(label, alltime)

    # Intensity tier sections
    for tier_name, tier in INTENSITY_TIERS.items():
        month_col += render_tier_html(tier_name, tier, month_activities, name_map, broken_set)
        alltime_col += render_alltime_tier_html(tier_name, tier, alltime)

    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{month_name} Leaderboard — Lively Fitness Challenge</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F3F4F6;padding:24px 16px}}
  h1{{font-size:22px;font-weight:700;color:#111827;margin-bottom:2px}}
  .subtitle{{font-size:13px;color:#6B7280;margin-bottom:20px}}
  .columns{{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:960px;margin:0 auto}}
  .col-header{{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7280;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #E5E7EB}}
  .col-header.at{{color:#7C3AED;border-color:#DDD6FE}}
  .section{{background:#fff;border-radius:12px;padding:14px 14px 10px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .section-title{{font-size:14px;font-weight:600;color:#111827;margin-bottom:8px;padding:5px 8px;background:#F9FAFB;border-radius:6px}}
  .at-title{{background:#F5F3FF;color:#4C1D95}}
  .sub-label{{font-size:11px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;margin:8px 0 5px 2px}}
  .row{{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:7px;margin-bottom:4px}}
  .medal{{font-size:16px;flex-shrink:0}}
  .entry{{font-size:13px;font-weight:500;flex:1}}
  .record-badge{{font-size:10px;font-weight:600;background:#FEF3C7;color:#92400E;padding:2px 6px;border-radius:4px;margin-left:4px;white-space:nowrap}}
  .page-header{{max-width:960px;margin:0 auto 16px;display:flex;align-items:baseline;gap:16px}}
  .footer{{max-width:960px;margin:16px auto 0;text-align:center;font-size:11px;color:#9CA3AF}}
  @media(max-width:600px){{.columns{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="page-header">
  <div>
    <h1>🏆 {month_name} Leaderboard</h1>
    <div class="subtitle">Lively Fitness Challenge</div>
  </div>
</div>
<div class="columns">
  <div>
    <div class="col-header">This month</div>
    {month_col}
  </div>
  <div>
    <div class="col-header at">All time records</div>
    {alltime_col}
  </div>
</div>
<div class="footer">Generated {generated}</div>
</body>
</html>'''

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import sys

    print("🏆 Strava Club Leaderboard")
    print("─" * 30)

    config = load_config()
    print("Refreshing access token...")
    token = get_access_token(config)
    print("✓ Token refreshed\n")

    print("Fetching club activities...")
    fresh = fetch_all_activities(token, config["club_id"])
    activities = merge_and_save_cache(fresh)
    print(f"✓ {len(activities)} total activities in cache\n")

    # ── Build all time from full history ──
    if "--build-alltime" in sys.argv:
        print("Building all time records from full cache...")
        build_alltime_bootstrap(activities)
        return

    # ── Set anchor ──
    if "--set-anchor" in sys.argv:
        set_anchor(activities)
        return

    # ── Normal run ──
    anchor = load_anchor()
    if anchor is None:
        if not sys.stdin.isatty():
            print("No anchor set and running non-interactively — run: python run.py --set-anchor locally first.")
            return
        print("No anchor set. Setting anchor now...\n")
        anchor_count = set_anchor(activities)
    else:
        anchor_count = find_anchor_idx(activities, anchor)
        print(f"⚓ Anchor: {anchor_count} activities at month start")
        print(f"  {len(activities) - anchor_count} activities this month\n")

    month_activities = activities[anchor_count:]

    # Filter excluded and flag unknown members
    unknown_members = set()
    filtered = []
    for a in month_activities:
        fn = a.get("athlete", {}).get("firstname", "")
        ln = a.get("athlete", {}).get("lastname", "")
        key = f"{fn} {ln}"
        if key in EXCLUDED_ATHLETES:
            continue
        if KNOWN_ATHLETES and key not in KNOWN_ATHLETES:
            unknown_members.add(key)
        filtered.append(a)
    month_activities = filtered

    if unknown_members:
        print(f"⚠️  Unknown members (not in members.json): {', '.join(sorted(unknown_members))}")

    # Filter denied activities from leaderboard
    month_activities = [a for a in month_activities if not is_denied_activity(a)]

    if not month_activities:
        print("No activities found before anchor. Try running --set-anchor to reset.")
        return

    month_key = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")

    # Warn unknown sport types
    unknown = set(a.get("sport_type") for a in month_activities if a.get("sport_type") not in ACTIVITY_LABELS)
    if unknown:
        print(f"⚠️  Unknown sport types: {', '.join(sorted(unknown))}\n")

    # Update all time records
    alltime, broken_records = update_alltime(month_activities, month_key)
    if broken_records:
        print(f"🏆 {len(broken_records)} new all time record(s) this month!")
        for label, metric, entry in broken_records:
            print(f"   {label} — {metric}: {entry['name']} ({entry['display']})")
        print()

    # Save archive
    save_archive(month_key, month_activities)

    # Text output
    message = build_message(month_activities, month_name)
    print("\n" + "─"*40)
    print(message)
    print("─"*40)

    # HTML output
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    html = build_html(month_activities, month_name, alltime, broken_records)
    html_path = reports_dir / "leaderboard.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ HTML saved to {html_path.resolve()}")

    # Clipboard
    try:
        import subprocess
        subprocess.run("clip", input=message.encode("utf-8"), check=True)
        print("✓ Text copied to clipboard!")
    except Exception:
        print("(Could not copy to clipboard — copy manually from above)")

if __name__ == "__main__":
    main()
