
import json
import os
from datetime import datetime

HISTORY_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\history_B38590.json"
SESSIONS_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"

def restore():
    print("--- Starting Watchlist Recovery ---")
    
    # 1. Load History
    if not os.path.exists(HISTORY_FILE):
        print("No history file found.")
        return

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # 2. Extract Unique Stocks
    stock_map = {}
    for t in history:
        sym = t['symbol']
        if sym not in stock_map:
            stock_map[sym] = {
                "symbol": sym,
                "token": t['token'],
                "exch_seg": "BSE" if "SENSEX" in sym or "BANKEX" in sym else "NSE",
                "ltp": 0.0,
                "pdc": 0.0,
                "pdh": 0.0,
                "pdl": 0.0,
                "loading": False
            }
    
    unique_stocks = list(stock_map.values())
    print(f"Found {len(unique_stocks)} unique stocks in history.")

    # 3. Load Sessions
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    # 4. Find Latest Session
    latest_sid = None
    latest_time = None

    for sid, data in sessions.items():
        # Only check active/recent
        ts_str = data.get('last_activity', '')
        if not ts_str: continue
        try:
            # Simple string verify or parsing? String comparison works for ISO format
            if latest_time is None or ts_str > latest_time:
                latest_time = ts_str
                latest_sid = sid
        except: pass

    if not latest_sid:
        print("No active sessions found.")
        return

    print(f"Restoring to Session: {latest_sid} (Last Active: {latest_time})")

    # 5. Merge/Restore
    current_wl = sessions[latest_sid].get('watchlist', [])
    existing_syms = {x['symbol'] for x in current_wl}
    
    added_count = 0
    for s in unique_stocks:
        if s['symbol'] not in existing_syms:
            current_wl.append(s)
            added_count += 1
            print(f" + Restored: {s['symbol']}")
    
    sessions[latest_sid]['watchlist'] = current_wl

    # 6. Save (Atomic)
    temp_file = SESSIONS_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=4, default=str)
        f.flush()
        os.fsync(f.fileno())
    
    os.replace(temp_file, SESSIONS_FILE)
    print(f"Transformation Complete. Added {added_count} items to watchlist.")

if __name__ == "__main__":
    restore()
