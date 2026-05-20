"""
process_review.py — Parse a GitHub Issue and update manual_review.json

Usage:
    python process_review.py "<issue_title>" "<decision>" "<issue_body>"
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

REVIEW_FILE = Path("manual_review.json")
CACHE2_FILE = Path("cache2.json")
DENIED_LOG_FILE = Path("denied_log.json")

def load_review():
    if REVIEW_FILE.exists():
        with open(REVIEW_FILE) as f:
            return json.load(f)
    return {"approved": [], "denied": []}

def save_review(data):
    with open(REVIEW_FILE, "w") as f:
        json.dump(data, f, indent=2)

def parse_issue(title, body):
    """Extract activity details from issue body."""
    fields = {}
    patterns = {
        "athlete":     r"\*\*Athlete:\*\*\s*(.+)",
        "activity":    r"\*\*Activity:\*\*\s*(.+)",
        "type":        r"\*\*Type:\*\*\s*(.+)",
        "detail":      r"\*\*Detail:\*\*\s*(.+)",
        "points":      r"\*\*Points:\*\*\s*(.+)",
        "flag_reason": r"\*\*Flag reason:\*\*\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, body)
        fields[key] = match.group(1).strip() if match else ""

    return fields

def main():
    if len(sys.argv) < 3:
        print("Usage: python process_review.py <title> <decision> [body]")
        sys.exit(1)

    title = sys.argv[1]
    decision = sys.argv[2].lower()
    body = sys.argv[3] if len(sys.argv) > 3 else ""

    if decision not in ("approved", "denied"):
        print(f"Invalid decision: {decision}")
        sys.exit(1)

    fields = parse_issue(title, body)
    print(f"Processing: {fields.get('athlete')} — {fields.get('activity')} → {decision}")

    review = load_review()

    # Remove from opposite list if exists
    opposite = "approved" if decision == "denied" else "denied"
    review[opposite] = [
        r for r in review[opposite]
        if not (r.get("athlete") == fields.get("athlete") and
                r.get("activity") == fields.get("activity"))
    ]

    # Add to decision list if not already there
    entry = {
        "athlete": fields.get("athlete", ""),
        "activity": fields.get("activity", ""),
        "type": fields.get("type", ""),
        "detail": fields.get("detail", ""),
        "points": fields.get("points", ""),
        "flag_reason": fields.get("flag_reason", ""),
    }

    existing = [
        r for r in review[decision]
        if r.get("athlete") == entry["athlete"] and r.get("activity") == entry["activity"]
    ]
    if not existing:
        review[decision].append(entry)

    save_review(review)
    print(f"✓ Saved to manual_review.json ({decision})")

    # If denied, remove from cache2.json and log full activity
    if decision == "denied" and CACHE2_FILE.exists():
        acts = json.load(open(CACHE2_FILE))
        before = len(acts)
        firstname = entry["athlete"].split()[0] if entry["athlete"] else ""
        activity_name = entry["activity"]
        try:
            denied_km = float(entry["detail"].split("km")[0].strip().split()[-1])
        except:
            denied_km = None

        def should_remove(a):
            if a.get("athlete", {}).get("firstname", "") != firstname:
                return False
            if a.get("name", "") != activity_name:
                return False
            if denied_km is not None:
                if abs(a.get("distance", 0)/1000 - denied_km) > 0.5:
                    return False
            return True

        removed = [a for a in acts if should_remove(a)]
        kept = [a for a in acts if not should_remove(a)]

        # Log to denied_log.json (full audit trail)
        log = []
        if DENIED_LOG_FILE.exists():
            log = json.load(open(DENIED_LOG_FILE))
        for a in removed:
            log.append({
                "denied_at": datetime.now().isoformat(),
                "reason": entry.get("flag_reason", ""),
                "review_entry": entry,
                "activity": a
            })
        json.dump(log, open(DENIED_LOG_FILE, "w"), indent=2)

        # Save to denied_activities.json for points.html display (crossed out)
        denied_acts_file = Path("denied_activities.json")
        denied_acts = []
        if denied_acts_file.exists():
            denied_acts = json.load(open(denied_acts_file))
        for a in removed:
            denied_acts.append({
                "activity": a,
                "reason": entry.get("flag_reason", ""),
                "denied_at": datetime.now().isoformat()
            })
        json.dump(denied_acts, open(denied_acts_file, "w"), indent=2)

        json.dump(kept, open(CACHE2_FILE, "w"))
        print(f"✓ Removed {len(removed)} activities from cache2.json")
        print(f"✓ Logged to {DENIED_LOG_FILE} and denied_activities.json")

if __name__ == "__main__":
    main()
