"""
process_review.py — Parse a GitHub Issue and update manual_review.json

Usage:
    python process_review.py "<issue_title>" "<decision>" "<issue_body>"
"""

import sys
import json
import re
from pathlib import Path

REVIEW_FILE = Path("manual_review.json")

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

if __name__ == "__main__":
    main()
