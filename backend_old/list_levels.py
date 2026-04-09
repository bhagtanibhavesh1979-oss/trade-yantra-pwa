import json
import os

def list_all_havells_levels():
    path = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"
    target_client = "B38590"
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get latest session
    sessions = [s for sid, s in data.items() if s.get('client_id') == target_client]
    sessions.sort(key=lambda x: x.get('last_activity', ''), reverse=True)
    
    if not sessions:
        print("No sessions found.")
        return
        
    session = sessions[0]
    alerts = [a for a in session.get('alerts', []) if str(a.get('token')) == "9819"]
    
    print(f"Session {session.get('last_activity')} - Havells Alerts ({len(alerts)}):")
    for a in sorted(alerts, key=lambda x: float(x.get('price', 0))):
        print(f"  {a.get('type'):<15} @ {float(a.get('price')):<10} ({a.get('condition')})")

if __name__ == "__main__":
    list_all_havells_levels()
