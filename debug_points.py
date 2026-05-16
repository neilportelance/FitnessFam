import json
from points import calculate_activity

ATHLETE = "Neil"  # Change this to check someone else

acts = json.load(open('cache2.json'))
anchor = json.load(open('anchor2.json'))['anchor_count']
month = acts[anchor:]
mine = [a for a in month if a['athlete']['firstname'] == ATHLETE]

total = 0
for a in mine:
    r = calculate_activity(a)
    total += r['points']
    flag = f"  ⚠️  {r['flag_reason']}" if r['flag'] else ''
    print(f"{r['activity_name']:<35} {r['label']:<25} {r['points']:>6}{flag}")

print(f"\nTotal: {total} pts ({len(mine)} activities)")
