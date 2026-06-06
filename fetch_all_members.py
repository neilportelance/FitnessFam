"""fetch_all_members.py — Fetch personal feeds for all authorized members."""
import json
import subprocess
from pathlib import Path

TOKENS_FILE = Path("member_tokens.json")

if TOKENS_FILE.exists():
    tokens = json.load(open(TOKENS_FILE))
    for key in tokens:
        parts = key.split(" ", 1)
        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ""
        print(f"Fetching {key}...")
        subprocess.run(["python", "fetch_member.py", "--refresh", firstname, lastname])
else:
    print("No member_tokens.json found, skipping personal feeds.")
