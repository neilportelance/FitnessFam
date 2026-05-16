import shutil
import os
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path(f"backup-{datetime.now().strftime('%Y-%m-%d-%H%M')}")
BACKUP_DIR.mkdir(exist_ok=True)

FILES = [
    "leaderboard.py",
    "points.py", 
    "report.py",
    "run.py",
    "cache2.json",
    "alltime.json",
    "anchor2.json",
    "config.json",
    ".gitignore",
    "requirements.txt",
    ".github/workflows/leaderboard.yml",
]

for f in FILES:
    src = Path(f)
    if src.exists():
        dest = BACKUP_DIR / src.name
        shutil.copy2(src, dest)
        print(f"✓ {f}")
    else:
        print(f"  skipped (not found): {f}")

print(f"\n✓ Backup saved to {BACKUP_DIR}")
