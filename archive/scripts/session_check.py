import requests
import json
import time

def check_current_state():
    # Use the session ID from the file
    try:
        data = json.load(open('backend/data/sessions.json'))
        rs = sorted(data.items(), key=lambda x: x[1].get('last_activity', ''), reverse=True)
        session_id = rs[0][0]
        session_data = rs[0][1]
    except Exception as e:
        print(f"Error reading sessions: {e}")
        return

    print(f"--- Session: {session_id} ---")
    print(f"Client ID: {session_data.get('client_id')}")
    print(f"Auto Trade: {session_data.get('auto_paper_trade')}")
    print(f"Strategy: {session_data.get('strategy_mode')}")
    print(f"Last Activity: {session_data.get('last_activity')}")
    print(f"Watchlist Count: {len(session_data.get('watchlist', []))}")
    print(f"Alerts Count: {len(session_data.get('alerts', []))}")
    print(f"Paper Trades: {len(session_data.get('paper_trades', []))}")

    # Check backend health
    try:
        r = requests.get("http://127.0.0.1:8002/health")
        print(f"Backend Health: {r.status_code} - {r.json()}")
    except:
        print("Backend Health: FAILED")

    # Check if indices API is working for this session
    try:
        r = requests.get(f"http://127.0.0.1:8002/api/indices/{session_id}")
        print(f"Indices API: {r.status_code}")
        if r.status_code == 200:
            indices = r.json().get('indices', [])
            print(f"  Found {len(indices)} indices")
    except Exception as e:
        print(f"Indices API: FAILED ({e})")

if __name__ == "__main__":
    check_current_state()
