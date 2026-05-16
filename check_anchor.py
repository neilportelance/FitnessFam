from leaderboard import load_cache, load_anchor, find_anchor_idx

acts = load_cache()
anchor = load_anchor()
idx = find_anchor_idx(acts, anchor)

a = acts[idx]
name = f"{a['athlete']['firstname']} {a['athlete']['lastname']}"
print(f"Cache size: {len(acts)}")
print(f"Anchor index: {idx}")
print(f"Anchor activity: {name} — {a.get('sport_type')} — {a.get('name')}")
print(f"Month activities: {idx}")
print(f"Has fingerprint: {'fingerprint' in anchor}")
