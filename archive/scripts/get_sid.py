import json
import os

sessions_file = 'backend/data/sessions.json'
if os.path.exists(sessions_file):
    with open(sessions_file, 'r') as f:
        data = json.load(f)
        if data:
            # Sort by last_activity
            sorted_sessions = sorted(data.items(), key=lambda x: x[1].get('last_activity', ''), reverse=True)
            print(sorted_sessions[0][0])
