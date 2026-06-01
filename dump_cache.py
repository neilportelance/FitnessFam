import json

acts = json.load(open('cache2.json'))
anchor_count = json.load(open('anchor2.json'))['anchor_count']

with open('cache_dump2.txt', 'w') as f:
    for i, a in enumerate(acts):
        flag = ' <-- ANCHOR' if i == anchor_count else ''
        name = a['athlete']['firstname'] + ' ' + a['athlete']['lastname']
        f.write(f"{i} {name} {a.get('sport_type')} {round(a.get('distance',0)/1000,1)} {a.get('moving_time')}{flag}\n")

print(f'Done. {len(acts)} activities written to cache_dump2.txt')
