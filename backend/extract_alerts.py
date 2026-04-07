import json
import os

def extract_havells_alerts():
    path = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for sid, sdata in data.items():
        if sdata.get('client_id') == "B38590":
            print(f"Session: {sid[:8]}")
            alerts = sdata.get('alerts', [])
            havells_alerts = [a for a in alerts if str(a.get('token')) == "9819"]
            print(f"Found {len(havells_alerts)} Havells alerts.")
            for a in sorted(havells_alerts, key=lambda x: float(x.get('price', 0))):
                print(f"Type: {a.get('type')}, Price: {a.get('price')}, Condition: {a.get('condition')}, Active: {a.get('active')}")

if __name__ == "__main__":
    extract_havells_alerts()
