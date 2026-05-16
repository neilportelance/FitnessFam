"""
report.py — generates the shareable combined HTML for the group
Pulls data from leaderboard.py and points.py logic directly.
Run after leaderboard.py and points.py have been run at least once,
or just use run.py which does everything in sequence.
"""
import json
from pathlib import Path
from datetime import datetime
import calendar

# Import core logic from sibling scripts
import sys
sys.path.insert(0, str(Path(__file__).parent))

from leaderboard import (
    load_config, get_access_token, fetch_all_activities, load_anchor,
    build_name_map, get_label, get_top3_distance, get_top3_pace,
    get_top3_sessions_tiered, load_alltime, update_alltime, save_archive,
    ACTIVITY_ORDER, ACTIVITY_EMOJI, DISTANCE_ACTIVITIES, NO_PACE_ACTIVITIES,
    MEDAL_COLORS, RANK_EMOJI, fmt_dist, fmt_time, fmt_pace, olympic_podium,
    render_alltime_section_html, render_alltime_tier_html, render_tier_html,
    INTENSITY_TIERS, ACTIVITY_LABELS as LB_LABELS,
    load_cache, find_anchor_idx
)
from points import calculate_totals

ALLTIME_FILE = Path("alltime.json")
GOAL = 80

def build_report_html(month_activities, month_name, alltime, broken_records, totals):
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    expected = round((GOAL / days_in_month) * today.day, 2)

    name_map = build_name_map(month_activities)
    present = set(get_label(a.get("sport_type","")) for a in month_activities)

    broken_set = set()
    for label, metric, entry in broken_records:
        broken_set.add((label, metric, entry["name"]))

    # ── Points column ─────────────────────────────────────────────────────────
    sorted_athletes = sorted(totals.items(), key=lambda x: x[0])
    points_rows = ""
    for name, data in sorted_athletes:
        pts = data["points"]
        pct = min(pts / GOAL * 100, 100)
        color = "#16A34A" if pts >= GOAL else "#F59E0B" if pts >= 60 else "#EF4444"
        diff = round(pts - expected, 2)
        if pts >= GOAL:
            pace_str = "✓ done"
            pace_color = "#16A34A"
        elif diff >= 0:
            pace_str = f"+{diff}"
            pace_color = "#16A34A"
        else:
            pace_str = str(diff)
            pace_color = "#EF4444"
        goal_badge = ' <span class="goal-badge">✓</span>' if pts >= GOAL else ""
        points_rows += f'''
        <div class="pts-row">
          <div class="pts-name">{name}{goal_badge}</div>
          <div class="pts-bar-wrap"><div class="pts-bar" style="width:{pct:.0f}%;background:{color}"></div></div>
          <div class="pts-val" style="color:{color}">{pts}</div>
          <div class="pts-pace" style="color:{pace_color}">{pace_str}</div>
        </div>'''

    # ── Leaderboard column ────────────────────────────────────────────────────
    lb_sections = ""
    distance_labels = [l for l in ACTIVITY_ORDER if l in present and l in DISTANCE_ACTIVITIES]

    def row_html(medal, content, is_record=False):
        bg, border, text = MEDAL_COLORS.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
        badge = ' <span class="rec-badge">🏆 Record</span>' if is_record else ""
        return f'<div class="lb-row" style="background:{bg};border-left:3px solid {border};color:{text}"><span class="lb-medal">{medal}</span><span class="lb-entry">{content}{badge}</span></div>'

    def broken_flags(podium, metric, lbl):
        return [(lbl, metric, line[2:].strip().split("—")[0].strip()) in broken_set for _, line in podium]

    for label in distance_labels:
        emoji = ACTIVITY_EMOJI.get(label, "🏅")
        dist_p = get_top3_distance(month_activities, label, name_map)
        pace_p = get_top3_pace(month_activities, label, name_map)
        if not dist_p and not pace_p:
            continue
        section_rows = f'<div class="lb-act-title">{emoji} {label}</div>'
        if dist_p:
            section_rows += '<div class="lb-sub">📏 Longest</div>'
            flags = broken_flags(dist_p, "distance", label)
            for i,(medal,line) in enumerate(dist_p):
                section_rows += row_html(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        if pace_p and label not in NO_PACE_ACTIVITIES:
            section_rows += '<div class="lb-sub">⚡ Fastest pace</div>'
            flags = broken_flags(pace_p, "pace", label)
            for i,(medal,line) in enumerate(pace_p):
                section_rows += row_html(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        lb_sections += f'<div class="lb-section">{section_rows}</div>'

    for tier_name, tier in INTENSITY_TIERS.items():
        if not any(l in present for l in tier["labels"]):
            continue
        sess_p = get_top3_sessions_tiered(month_activities, tier["labels"], tier["short"], name_map)
        if not sess_p:
            continue
        section_rows = f'<div class="lb-act-title">{tier_name}</div>'
        for medal, line in sess_p:
            section_rows += row_html(medal, line[2:].strip())
        lb_sections += f'<div class="lb-section">{section_rows}</div>'

    # ── All time column ───────────────────────────────────────────────────────
    all_distance = set(distance_labels) | {l for l in alltime if l in DISTANCE_ACTIVITIES}
    all_distance_ordered = [l for l in ACTIVITY_ORDER if l in all_distance] + sorted(l for l in all_distance if l not in ACTIVITY_ORDER)
    at_sections = ""
    for label in all_distance_ordered:
        if label in alltime:
            at_sections += render_alltime_section_html(label, alltime)
    for tier_name, tier in INTENSITY_TIERS.items():
        at_sections += render_alltime_tier_html(tier_name, tier, alltime)

    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{month_name} — Lively Fitness Challenge</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F3F4F6;padding:24px 16px;color:#111827}}
  .page-header{{max-width:1280px;margin:0 auto 20px}}
  .page-header h1{{font-size:24px;font-weight:700;margin-bottom:2px}}
  .page-header p{{font-size:13px;color:#6B7280}}
  .columns{{display:grid;grid-template-columns:1fr 1.4fr 1fr;gap:20px;max-width:1280px;margin:0 auto}}
  .col-header{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7280;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #E5E7EB}}
  .col-header.lb{{color:#2563EB;border-color:#BFDBFE}}
  .col-header.at{{color:#7C3AED;border-color:#DDD6FE}}

  /* Points */
  .pts-card{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .pts-meta{{font-size:11px;color:#6B7280;margin-bottom:12px}}
  .pts-col-labels{{display:flex;align-items:center;gap:8px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#9CA3AF;padding-bottom:6px;border-bottom:1px solid #E5E7EB;margin-bottom:4px}}
  .pts-row{{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #F9FAFB}}
  .pts-row:last-child{{border-bottom:none}}
  .pts-name{{min-width:80px;font-size:13px;font-weight:500;display:flex;align-items:center;gap:4px}}
  .pts-bar-wrap{{flex:1;height:6px;background:#E5E7EB;border-radius:3px;overflow:hidden}}
  .pts-bar{{height:100%;border-radius:3px}}
  .pts-val{{min-width:32px;text-align:right;font-weight:700;font-size:13px}}
  .pts-pace{{min-width:52px;text-align:right;font-size:12px;font-weight:500}}
  .goal-badge{{font-size:10px;background:#DCFCE7;color:#166534;padding:1px 5px;border-radius:3px;font-weight:600}}

  /* Leaderboard */
  .lb-section{{background:#fff;border-radius:12px;padding:12px 12px 8px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .lb-act-title{{font-size:13px;font-weight:600;color:#111827;padding:4px 6px;background:#F9FAFB;border-radius:5px;margin-bottom:6px}}
  .lb-sub{{font-size:10px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em;margin:6px 0 4px 2px}}
  .lb-row{{display:flex;align-items:center;gap:6px;padding:5px 8px;border-radius:6px;margin-bottom:3px}}
  .lb-medal{{font-size:14px;flex-shrink:0}}
  .lb-entry{{font-size:12px;font-weight:500;flex:1}}
  .rec-badge{{font-size:9px;font-weight:600;background:#FEF3C7;color:#92400E;padding:1px 5px;border-radius:3px;margin-left:3px}}

  /* All time */
  .section{{background:#FAFAFE;border:1px solid #EDE9FE;border-radius:10px;padding:10px 12px 6px;margin-bottom:10px}}
  .section-title{{font-size:13px;font-weight:600;color:#4C1D95;padding:4px 6px;background:#F5F3FF;border-radius:5px;margin-bottom:6px}}
  .at-row{{display:flex;align-items:center;gap:6px;padding:5px 4px;border-bottom:1px solid #F3F4F6;font-size:11px}}
  .at-row:last-child{{border-bottom:none}}
  .at-label{{color:#7C3AED;font-weight:600;min-width:80px;font-size:10px}}
  .at-name{{font-weight:600;color:#111827;flex:1}}
  .at-val{{color:#374151;font-weight:500}}
  .at-month{{font-size:9px;color:#9CA3AF;margin-left:4px;white-space:nowrap}}

  .footer{{max-width:1280px;margin:16px auto 0;text-align:center;font-size:11px;color:#9CA3AF}}
  @media(max-width:800px){{.columns{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="page-header">
  <h1>🏆 {month_name}</h1>
  <p>Lively Fitness Challenge</p>
</div>
<div class="columns">

  <div>
    <div class="col-header">Points standings</div>
    <div class="pts-card">
      <div class="pts-meta">Goal: {GOAL} pts &nbsp;·&nbsp; Expected today: {expected} pts (day {today.day}/{days_in_month})</div>
      <div class="pts-col-labels">
        <div style="min-width:80px">Name</div>
        <div style="flex:1"></div>
        <div style="min-width:32px;text-align:right">Pts</div>
        <div style="min-width:52px;text-align:right">Pace</div>
      </div>
      {points_rows}
    </div>
  </div>

  <div>
    <div class="col-header lb">Monthly top 3</div>
    {lb_sections}
  </div>

  <div>
    <div class="col-header at">All time records</div>
    {at_sections}
  </div>

</div>
<div class="footer">Generated {generated}</div>
</body>
</html>'''


def build_mobile_html(month_activities, month_name, alltime, broken_records, totals):
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    expected = round((GOAL / days_in_month) * today.day, 2)

    name_map = build_name_map(month_activities)
    present = set(get_label(a.get("sport_type","")) for a in month_activities)

    broken_set = set()
    for label, metric, entry in broken_records:
        broken_set.add((label, metric, entry["name"]))

    DARK_MEDAL = {
        "🥇": ("rgba(245,158,11,0.13)", "#F59E0B", "#FDE68A"),
        "🥈": ("rgba(255,255,255,0.06)", "#94A3B8", "#CBD5E1"),
        "🥉": ("rgba(194,98,45,0.12)", "#C2622D", "#FCA572"),
    }

    def bar_color(pts):
        pct = pts / GOAL * 100
        if pts >= GOAL: return "#2AB5A8"
        if pct >= 75: return "#3DBE6A"
        if pct >= 50: return "#C9B830"
        if pct >= 25: return "#D4832A"
        return "#D94F4F"

    def val_color(pts):
        return bar_color(pts)

    def pace_str(pts, diff):
        if pts >= GOAL: return "DONE 🎉"
        return f"+{diff}" if diff >= 0 else str(diff)

    def pace_color(pts, diff):
        if pts >= GOAL: return "#2AB5A8"
        return "#4BA87A" if diff >= 0 else "#B85C5C"

    def pace_weight(pts):
        return "800" if pts >= GOAL else "500"

    def bar_html(pts):
        pct = min(pts / GOAL * 100, 100)
        color = bar_color(pts)
        if pts >= GOAL:
            return f'<div class="pts-bar-wrap"><div class="bar-done"></div></div>'
        return f'<div class="pts-bar-wrap"><div class="pts-bar" style="width:{pct:.0f}%;background:{color}"></div></div>'

    def dm_row(medal, content, is_record=False):
        bg, border, text = DARK_MEDAL.get(medal, ("rgba(255,255,255,0.05)","#475569","#94A3B8"))
        badge = ' 🏆' if is_record else ""
        return f'<div class="lb-row" style="background:{bg};border-left:2px solid {border};color:{text}"><span class="lb-medal">{medal}</span><span class="lb-entry">{content}{badge}</span></div>'

    # ── Points ────────────────────────────────────────────────────────────────
    sorted_athletes = sorted(totals.items(), key=lambda x: x[0])
    points_rows = ""
    for name, data in sorted_athletes:
        pts = data["points"]
        diff = round(pts - expected, 2)
        name_style = f'color:#2AB5A8;font-weight:700' if pts >= GOAL else 'color:#FFFFFF;font-weight:600'
        points_rows += f'<div class="pts-row"><div class="pts-name" style="{name_style}">{name}</div>{bar_html(pts)}<div class="pts-val" style="color:{val_color(pts)}">{pts}</div><div class="pts-pace" style="color:{pace_color(pts,diff)};font-weight:{pace_weight(pts)}">{pace_str(pts,diff)}</div></div>'

    # ── Leaderboard ───────────────────────────────────────────────────────────
    lb_sections = ""
    distance_labels_m = [l for l in ACTIVITY_ORDER if l in present and l in DISTANCE_ACTIVITIES]

    def m_broken_flags(podium, metric, lbl):
        return [(lbl, metric, line[2:].strip().split("—")[0].strip()) in broken_set for _, line in podium]

    for label in distance_labels_m:
        emoji = ACTIVITY_EMOJI.get(label, "🏅")
        dist_p = get_top3_distance(month_activities, label, name_map)
        pace_p = get_top3_pace(month_activities, label, name_map)
        if not dist_p and not pace_p:
            continue
        rows = f'<div class="lb-card-title">{emoji} {label}</div>'
        if dist_p:
            rows += '<div class="lb-sub">📏 Longest</div>'
            flags = m_broken_flags(dist_p, "distance", label)
            for i,(medal,line) in enumerate(dist_p):
                rows += dm_row(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        if pace_p and label not in NO_PACE_ACTIVITIES:
            rows += '<div class="lb-sub">⚡ Fastest pace</div>'
            flags = m_broken_flags(pace_p, "pace", label)
            for i,(medal,line) in enumerate(pace_p):
                rows += dm_row(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        lb_sections += f'<div class="lb-card">{rows}</div>'

    for tier_name, tier in INTENSITY_TIERS.items():
        if not any(l in present for l in tier["labels"]):
            continue
        sess_p = get_top3_sessions_tiered(month_activities, tier["labels"], tier["short"], name_map)
        if not sess_p:
            continue
        rows = f'<div class="lb-card-title">{tier_name}</div>'
        for medal, line in sess_p:
            rows += dm_row(medal, line[2:].strip())
        lb_sections += f'<div class="lb-card">{rows}</div>'

    # ── All time ──────────────────────────────────────────────────────────────
    all_distance_m = set(distance_labels_m) | {l for l in alltime if l in DISTANCE_ACTIVITIES}
    all_distance_m_ordered = [l for l in ACTIVITY_ORDER if l in all_distance_m] + sorted(l for l in all_distance_m if l not in ACTIVITY_ORDER)
    at_sections = ""

    for label in all_distance_m_ordered:
        if label not in alltime:
            continue
        emoji = ACTIVITY_EMOJI.get(label, "🏅")
        data = alltime[label]
        rows = f'<div class="at-card-title">{emoji} {label}</div>'
        if "distance" in data:
            rows += '<div class="lb-sub">📏 Longest</div>'
            for i, e in enumerate(data["distance"][:3]):
                rows += dm_row(RANK_EMOJI[i], f'{e["name"]} — {e["display"]}')
        if "pace" in data and label not in NO_PACE_ACTIVITIES:
            rows += '<div class="lb-sub">⚡ Fastest pace</div>'
            for i, e in enumerate(data["pace"][:3]):
                rows += dm_row(RANK_EMOJI[i], f'{e["name"]} — {e["display"]}')
        at_sections += f'<div class="at-card">{rows}</div>'

    for tier_name, tier in INTENSITY_TIERS.items():
        combined = {}
        for label in tier["labels"]:
            if label not in alltime or "sessions" not in alltime[label]:
                continue
            short = tier["short"].get(label, label)
            for entry in alltime[label]["sessions"]:
                n = entry["name"]
                if n not in combined:
                    combined[n] = {"name": n, "total": 0, "parts": {}}
                combined[n]["total"] += entry["value"]
                combined[n]["parts"][short] = entry["value"]
        if not combined:
            continue
        ranked = sorted(combined.values(), key=lambda x: x["total"], reverse=True)[:3]
        rows = f'<div class="at-card-title">{tier_name}</div><div class="lb-sub">🔢 Most sessions</div>'
        for i, e in enumerate(ranked):
            parts = [f"{s} x{c}" if c > 1 else s for s, c in sorted(e["parts"].items())]
            display = f"{e['total']} session{'s' if e['total']!=1 else ''} ({', '.join(parts)})"
            rows += dm_row(RANK_EMOJI[i], f'{e["name"]} — {display}')
        at_sections += f'<div class="at-card">{rows}</div>'

    generated = datetime.now().strftime("%b %d, %Y %I:%M %p")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{month_name} — Lively Fitness</title>

<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#2E3240;color:#F1F5F9;width:390px;padding:0;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#363A4F 0%,#2E3240 100%);padding:20px 16px 16px;border-bottom:1px solid rgba(255,255,255,0.1);position:relative;overflow:hidden}}
  .header::before{{content:'';position:absolute;top:-40px;right:-40px;width:140px;height:140px;background:radial-gradient(circle,rgba(56,189,248,0.1) 0%,transparent 70%);border-radius:50%}}
  .header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}}
  .header h1{{font-size:28px;font-weight:800;letter-spacing:-0.5px;color:#fff}}
  .header-badge{{background:rgba(255,255,255,0.2);border:1.5px solid rgba(255,255,255,0.6);color:#fff;font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;letter-spacing:0.08em}}
  .header p{{font-size:12px;color:#94A3B8}}
  .section-label{{font-size:14px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:16px 16px 8px;display:flex;align-items:center;gap:8px}}
  .section-label::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,0.15)}}
  .section-label.pts{{color:#FFFFFF}}
  .section-label.lb{{color:#FFFFFF}}
  .section-label.at{{color:#FFFFFF}}
  .pts-wrap{{padding:0 16px 8px}}
  .pts-meta{{font-size:11px;color:#94A3B8;margin-bottom:10px;display:flex;align-items:center;gap:6px}}
  .pts-meta span{{background:rgba(56,189,248,0.1);color:#38BDF8;padding:2px 7px;border-radius:10px;font-weight:600}}
  .pts-col-head{{display:flex;align-items:center;gap:6px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#8896A8;padding:0 0 6px;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:2px}}
  .pts-row{{display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.05)}}
  .pts-row:last-child{{border-bottom:none}}
  .pts-name{{min-width:76px;font-size:13px;font-weight:500;color:#F1F5F9}}
  .pts-bar-wrap{{flex:1;height:5px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden}}
  .pts-bar{{height:100%;border-radius:3px}}
  .bar-done{{height:100%;border-radius:3px;background:#2AB5A8;position:relative;overflow:hidden}}
  .bar-done::after{{content:'';position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.35),transparent);animation:shimmer 2s ease-in-out infinite}}
  @keyframes shimmer{{0%{{left:-60%}}100%{{left:140%}}}}
  .pts-val{{min-width:36px;text-align:right;font-weight:700;font-size:14px}}
  .pts-pace{{min-width:52px;text-align:right;font-size:11px;font-weight:600}}
  .lb-wrap{{padding:0 16px}}
  .lb-card{{background:#383C4E;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:10px 12px 8px;margin-bottom:8px}}
  .lb-card-title{{font-size:15px;font-weight:700;color:#F1F5F9;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.1)}}
  .at-card{{background:#383C4E;border:1px solid rgba(52,211,153,0.25);border-radius:12px;padding:10px 12px 8px;margin-bottom:8px}}
  .at-card-title{{font-size:15px;font-weight:700;color:#34D399;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(52,211,153,0.15)}}
  .lb-sub{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#8896A8;margin:8px 0 4px 2px}}
  .lb-row{{display:flex;align-items:center;gap:7px;padding:5px 8px;border-radius:7px;margin-bottom:3px}}
  .lb-row:last-child{{margin-bottom:0}}
  .lb-medal{{font-size:14px;flex-shrink:0}}
  .lb-entry{{font-size:12px;font-weight:500;flex:1}}
  .footer{{font-size:10px;color:#6B7280;text-align:center;padding:16px;opacity:0.8}}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <h1>🏆 {month_name}</h1>
    <div class="header-badge">LIVELY FITNESS CLUB</div>
  </div>
  <p>Monthly challenge · Goal: {GOAL} pts</p>
</div>

<div class="section-label pts">Points standings</div>
<div class="pts-wrap">
  <div class="pts-meta">📅 Day {today.day}/{days_in_month} · On pace = <span>{expected} pts</span></div>
  <div class="pts-col-head">
    <div style="min-width:76px">Athlete</div>
    <div style="flex:1"></div>
    <div style="min-width:36px;text-align:right">Pts</div>
    <div style="min-width:52px;text-align:right">Pace</div>
  </div>
  {points_rows}
</div>

<div class="section-label lb">Monthly Top 3</div>
<div class="lb-wrap">{lb_sections}</div>

<div class="section-label at">All Time Records</div>
<div class="lb-wrap">{at_sections}</div>

<div class="footer">Generated {generated} · Lively Fitness Challenge</div>
</body>
</html>'''


def build_mobile_light_html(month_activities, month_name, alltime, broken_records, totals):
    """Light theme version — same structure, different skin."""
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    expected = round((GOAL / days_in_month) * today.day, 2)

    name_map = build_name_map(month_activities)
    present = set(get_label(a.get("sport_type","")) for a in month_activities)

    broken_set = set()
    for label, metric, entry in broken_records:
        broken_set.add((label, metric, entry["name"]))

    LIGHT_MEDAL = {
        "🥇": ("#FFF8E7", "#F59E0B", "#92400E"),
        "🥈": ("#F3F4F6", "#9CA3AF", "#374151"),
        "🥉": ("#FFF3EE", "#C2622D", "#7C2D12"),
    }

    def bar_color(pts):
        pct = pts / GOAL * 100
        if pts >= GOAL: return "#0D9488"
        if pct >= 75: return "#16A34A"
        if pct >= 50: return "#CA8A04"
        if pct >= 25: return "#EA580C"
        return "#DC2626"

    def val_color(pts):
        pct = pts / GOAL * 100
        if pts >= GOAL: return "#0D9488"
        if pct >= 75: return "#15803D"
        if pct >= 50: return "#B45309"
        if pct >= 25: return "#C2410C"
        return "#B91C1C"

    def pace_display(pts, diff):
        if pts >= GOAL: return "DONE 🎉"
        return f"+{diff}" if diff >= 0 else str(diff)

    def pace_col(pts, diff):
        if pts >= GOAL: return "#0D9488"
        return "#15803D" if diff >= 0 else "#B91C1C"

    def lm_row(medal, content, is_record=False):
        bg, border, text = LIGHT_MEDAL.get(medal, ("#F9FAFB","#D1D5DB","#111827"))
        badge = ' 🏆' if is_record else ""
        return f'<div class="lb-row" style="background:{bg};border-left:2px solid {border};color:{text}"><span class="lb-medal">{medal}</span><span class="lb-entry">{content}{badge}</span></div>'

    # Points rows
    sorted_athletes = sorted(totals.items(), key=lambda x: x[0])
    points_rows = ""
    for name, data in sorted_athletes:
        pts = data["points"]
        pct = min(pts / GOAL * 100, 100)
        diff = round(pts - expected, 2)
        name_style = f'color:#0D9488;font-weight:700' if pts >= GOAL else 'color:#111827;font-weight:600'
        bar = f'<div class="pts-bar-wrap"><div class="bar-done"></div></div>' if pts >= GOAL else f'<div class="pts-bar-wrap"><div class="pts-bar" style="width:{pct:.0f}%;background:{bar_color(pts)}"></div></div>'
        points_rows += f'<div class="pts-row"><div class="pts-name" style="{name_style}">{name}</div>{bar}<div class="pts-val" style="color:{val_color(pts)}">{pts}</div><div class="pts-pace" style="color:{pace_col(pts,diff)};font-weight:{"700" if pts >= GOAL else "500"}">{pace_display(pts,diff)}</div></div>'

    # Leaderboard
    lb_sections = ""
    distance_labels_l = [l for l in ACTIVITY_ORDER if l in present and l in DISTANCE_ACTIVITIES]

    def l_broken_flags(podium, metric, lbl):
        return [(lbl, metric, line[2:].strip().split("—")[0].strip()) in broken_set for _, line in podium]

    for label in distance_labels_l:
        emoji = ACTIVITY_EMOJI.get(label, "🏅")
        dist_p = get_top3_distance(month_activities, label, name_map)
        pace_p = get_top3_pace(month_activities, label, name_map)
        if not dist_p and not pace_p:
            continue
        rows = f'<div class="lb-card-title">{emoji} {label}</div>'
        if dist_p:
            rows += '<div class="lb-sub">📏 Longest</div>'
            flags = l_broken_flags(dist_p, "distance", label)
            for i,(medal,line) in enumerate(dist_p):
                rows += lm_row(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        if pace_p and label not in NO_PACE_ACTIVITIES:
            rows += '<div class="lb-sub">⚡ Fastest pace</div>'
            flags = l_broken_flags(pace_p, "pace", label)
            for i,(medal,line) in enumerate(pace_p):
                rows += lm_row(medal, line[2:].strip(), flags[i] if i < len(flags) else False)
        lb_sections += f'<div class="lb-card">{rows}</div>'

    for tier_name, tier in INTENSITY_TIERS.items():
        if not any(l in present for l in tier["labels"]):
            continue
        sess_p = get_top3_sessions_tiered(month_activities, tier["labels"], tier["short"], name_map)
        if not sess_p:
            continue
        rows = f'<div class="lb-card-title">{tier_name}</div>'
        for medal, line in sess_p:
            rows += lm_row(medal, line[2:].strip())
        lb_sections += f'<div class="lb-card">{rows}</div>'

    # All time
    all_distance_l = set(distance_labels_l) | {l for l in alltime if l in DISTANCE_ACTIVITIES}
    all_distance_l_ordered = [l for l in ACTIVITY_ORDER if l in all_distance_l] + sorted(l for l in all_distance_l if l not in ACTIVITY_ORDER)
    at_sections = ""
    for label in all_distance_l_ordered:
        if label not in alltime:
            continue
        emoji = ACTIVITY_EMOJI.get(label, "🏅")
        data = alltime[label]
        rows = f'<div class="at-card-title">{emoji} {label}</div>'
        if "distance" in data:
            rows += '<div class="lb-sub">📏 Longest</div>'
            for i, e in enumerate(data["distance"][:3]):
                rows += lm_row(RANK_EMOJI[i], f'{e["name"]} — {e["display"]}')
        if "pace" in data and label not in NO_PACE_ACTIVITIES:
            rows += '<div class="lb-sub">⚡ Fastest pace</div>'
            for i, e in enumerate(data["pace"][:3]):
                rows += lm_row(RANK_EMOJI[i], f'{e["name"]} — {e["display"]}')
        at_sections += f'<div class="at-card">{rows}</div>'

    for tier_name, tier in INTENSITY_TIERS.items():
        combined = {}
        for label in tier["labels"]:
            if label not in alltime or "sessions" not in alltime[label]:
                continue
            short = tier["short"].get(label, label)
            for entry in alltime[label]["sessions"]:
                n = entry["name"]
                if n not in combined:
                    combined[n] = {"name": n, "total": 0, "parts": {}}
                combined[n]["total"] += entry["value"]
                combined[n]["parts"][short] = entry["value"]
        if not combined:
            continue
        ranked = sorted(combined.values(), key=lambda x: x["total"], reverse=True)[:3]
        rows = f'<div class="at-card-title">{tier_name}</div><div class="lb-sub">🔢 Most sessions</div>'
        for i, e in enumerate(ranked):
            parts = [f"{s} x{c}" if c > 1 else s for s, c in sorted(e["parts"].items())]
            display = f"{e['total']} session{'s' if e['total']!=1 else ''} ({', '.join(parts)})"
            rows += lm_row(RANK_EMOJI[i], f'{e["name"]} — {display}')
        at_sections += f'<div class="at-card">{rows}</div>'

    generated = datetime.now().strftime("%b %d, %Y %I:%M %p")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{month_name} — Lively Fitness</title>

<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F3F4F6;color:#111827;width:390px;padding:0;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#1E3A5F 0%,#1E293B 100%);padding:20px 16px 16px;position:relative;overflow:hidden}}
  .header::before{{content:'';position:absolute;top:-40px;right:-40px;width:140px;height:140px;background:radial-gradient(circle,rgba(255,255,255,0.08) 0%,transparent 70%);border-radius:50%}}
  .header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}}
  .header h1{{font-size:28px;font-weight:800;letter-spacing:-0.5px;color:#fff}}
  .header-badge{{background:rgba(255,255,255,0.15);border:1.5px solid rgba(255,255,255,0.5);color:#fff;font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;letter-spacing:0.08em}}
  .header p{{font-size:12px;color:rgba(255,255,255,0.7)}}
  .section-label{{font-size:14px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:16px 16px 8px;display:flex;align-items:center;gap:8px}}
  .section-label::after{{content:'';flex:1;height:1px;background:#D1D5DB}}
  .section-label.pts{{color:#1D4ED8}}
  .section-label.lb{{color:#6D28D9}}
  .section-label.at{{color:#047857}}
  .pts-wrap{{padding:0 16px 8px}}
  .pts-meta{{font-size:11px;color:#6B7280;margin-bottom:10px;display:flex;align-items:center;gap:6px}}
  .pts-meta span{{background:#DBEAFE;color:#1D4ED8;padding:2px 7px;border-radius:10px;font-weight:600}}
  .pts-col-head{{display:flex;align-items:center;gap:6px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#9CA3AF;padding:0 0 6px;border-bottom:1px solid #E5E7EB;margin-bottom:2px}}
  .pts-row{{display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid #F3F4F6}}
  .pts-row:last-child{{border-bottom:none}}
  .pts-name{{min-width:76px;font-size:13px;font-weight:600;color:#111827}}
  .pts-bar-wrap{{flex:1;height:5px;background:#E5E7EB;border-radius:3px;overflow:hidden}}
  .pts-bar{{height:100%;border-radius:3px}}
  .bar-done{{height:100%;border-radius:3px;background:#0D9488;position:relative;overflow:hidden}}
  .bar-done::after{{content:'';position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.5),transparent);animation:shimmer 2s ease-in-out infinite}}
  @keyframes shimmer{{0%{{left:-60%}}100%{{left:140%}}}}
  .pts-val{{min-width:36px;text-align:right;font-weight:700;font-size:14px}}
  .pts-pace{{min-width:52px;text-align:right;font-size:11px;font-weight:500}}
  .lb-wrap{{padding:0 16px}}
  .lb-card{{background:#fff;border:0.5px solid #E5E7EB;border-radius:12px;padding:10px 12px 8px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .lb-card-title{{font-size:15px;font-weight:700;color:#111827;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #F3F4F6}}
  .at-card{{background:#fff;border:0.5px solid #A7F3D0;border-radius:12px;padding:10px 12px 8px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
  .at-card-title{{font-size:15px;font-weight:700;color:#047857;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #D1FAE5}}
  .lb-sub{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#9CA3AF;margin:8px 0 4px 2px}}
  .lb-row{{display:flex;align-items:center;gap:7px;padding:5px 8px;border-radius:7px;margin-bottom:3px}}
  .lb-row:last-child{{margin-bottom:0}}
  .lb-medal{{font-size:14px;flex-shrink:0}}
  .lb-entry{{font-size:12px;font-weight:500;flex:1}}
  .footer{{font-size:10px;color:#9CA3AF;text-align:center;padding:16px}}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <h1>🏆 {month_name}</h1>
    <div class="header-badge">LIVELY FITNESS CLUB</div>
  </div>
  <p>Monthly challenge · Goal: {GOAL} pts</p>
</div>

<div class="section-label pts">Points standings</div>
<div class="pts-wrap">
  <div class="pts-meta">📅 Day {today.day}/{days_in_month} · On pace = <span>{expected} pts</span></div>
  <div class="pts-col-head">
    <div style="min-width:76px">Athlete</div>
    <div style="flex:1"></div>
    <div style="min-width:36px;text-align:right">Pts</div>
    <div style="min-width:52px;text-align:right">Pace</div>
  </div>
  {points_rows}
</div>

<div class="section-label lb">Monthly Top 3</div>
<div class="lb-wrap">{lb_sections}</div>

<div class="section-label at">All Time Records</div>
<div class="lb-wrap">{at_sections}</div>

<div class="footer">Generated {generated} · Lively Fitness Challenge</div>
</body>
</html>'''


def main():
    print("📋 Generating combined report...")

    activities = load_cache()
    if not activities:
        print("Cache is empty — run python leaderboard.py first.")
        return
    print(f"✓ Loaded {len(activities)} activities from cache\n")

    anchor = load_anchor()
    if anchor is None:
        print("No anchor set — run: python run.py --set-anchor")
        return

    anchor_idx = find_anchor_idx(activities, anchor)
    month_activities = activities[:anchor_idx]
    if not month_activities:
        print("No activities found before anchor.")
        return

    month_key = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")

    alltime, broken_records = update_alltime(month_activities, month_key)
    totals, _ = calculate_totals(month_activities)

    # Create reports subfolder
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Desktop report
    html = build_report_html(month_activities, month_name, alltime, broken_records, totals)
    path = reports_dir / "report.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Desktop report saved to {path.resolve()}")

    # Mobile dark report
    mobile_html = build_mobile_html(month_activities, month_name, alltime, broken_records, totals)
    mobile_path = reports_dir / "report_mobile_dark.html"
    with open(mobile_path, "w", encoding="utf-8") as f:
        f.write(mobile_html)
    print(f"✓ Mobile dark report saved to {mobile_path.resolve()}")

    # Mobile light report
    mobile_light_html = build_mobile_light_html(month_activities, month_name, alltime, broken_records, totals)
    mobile_light_path = reports_dir / "report_mobile_light.html"
    with open(mobile_light_path, "w", encoding="utf-8") as f:
        f.write(mobile_light_html)
    print(f"✓ Mobile light report saved to {mobile_light_path.resolve()}")


if __name__ == "__main__":
    main()

