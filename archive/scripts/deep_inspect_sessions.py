import json
import os

def deep_inspect():
    path = r'backend/data/sessions.json'
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Session with 135 alerts
    target_sid = "33c87081-731a-4c12-9214-9a24967810a8"
    if target_sid not in data:
        print(f"Session {target_sid} not found.")
        return

    sdata = data[target_sid]
    alerts = sdata.get('alerts', [])
    print(f"Session {target_sid}")
    print(f"Total Alerts: {len(alerts)}")
    
    if alerts:
        # Check a few
        for i in range(min(5, len(alerts))):
            a = alerts[i]
            print(f"  Alert {i}: {a.get('label')} @ {a.get('price')} | Type: {a.get('type')} | Created: {a.get('created_at')}")
        
        # Aggregate dates
        dates = {}
        for a in alerts:
            d = str(a.get('created_at', ''))[:10]
            dates[d] = dates.get(d, 0) + 1
        print(f"\nAlert count by date: {dates}")

if __name__ == "__main__":
    deep_inspect()
