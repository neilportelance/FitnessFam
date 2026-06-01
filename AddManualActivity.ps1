@"
import json
acts = json.load(open('cache2-addmissing.json'))
new = {'athlete': {'resource_state': 2, 'firstname': 'Connor', 'lastname': 'M.'}, 'name': 'Morning Walk', 'distance': 2550, 'moving_time': 1903, 'elapsed_time': 1903, 'total_elevation_gain': 0, 'type': 'Walk', 'sport_type': 'Walk', 'workout_type': None}
acts.insert(90, new)
json.dump(acts, open('cache2-addmissing.json', 'w'), indent=2)
print(f'Done. Total: {len(acts)}')
"@ | python