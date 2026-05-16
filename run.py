"""
run.py — single command to run everything day-to-day

Usage:
    python run.py               # fetch + leaderboard + points + report
    python run.py --set-anchor  # set month anchor (run on 1st of month)
    python run.py --build-alltime  # bootstrap all time records (run once ever)
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def run_step(label, script, args=""):
    print(f"\n{'─'*40}")
    print(f"▶ {label}")
    print(f"{'─'*40}")
    cmd = f"python {script} {args}".strip()
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n❌ {label} failed — stopping.")
        sys.exit(1)

def main():
    args = sys.argv[1:]

    print("🏃 Lively Fitness Challenge — Run Script")
    print(f"   {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

    if "--set-anchor" in args:
        run_step("Setting month anchor", "leaderboard.py", "--set-anchor")
        print("\n✓ Anchor set. Run 'python run.py' anytime to generate reports.")
        return

    if "--build-alltime" in args:
        run_step("Building all time records", "leaderboard.py", "--build-alltime")
        print("\n✓ All time records built. Run 'python run.py' to generate reports.")
        return

    # Normal run
    run_step("Leaderboard + all time update", "leaderboard.py")
    run_step("Points calculator", "points.py")
    run_step("Combined report", "report.py")

    print(f"\n{'─'*40}")
    print("✓ All done! Files generated in reports/:")
    print("   report.html               — desktop (scorer reference)")
    print("   report_mobile_dark.html   — mobile dark theme")
    print("   report_mobile_light.html  — mobile light theme")
    print("   points.html               — points breakdown (scorer only)")
    print(f"{'─'*40}\n")

if __name__ == "__main__":
    main()
