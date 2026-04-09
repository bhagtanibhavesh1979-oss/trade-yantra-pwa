
import json
import os

HISTORY_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\history_B38590.json"
SESSIONS_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"

def restore_trades():
    print("--- Starting Open Trade Restoration ---")
    
    # 1. Load History
    if not os.path.exists(HISTORY_FILE):
        print("No history file found.")
        return

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # 2. Find OPEN trades in history
    zombie_trades = [t for t in history if t.get('status') == 'OPEN']
    print(f"Found {len(zombie_trades)} trades marked as OPEN in history.")

    if not zombie_trades:
        print("No open trades to restore.")
        return

    # 3. Load Sessions
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    # 4. Find Latest Session
    latest_sid = None
    latest_time = None

    for sid, data in sessions.items():
        ts_str = data.get('last_activity', '')
        if not ts_str: continue
        try:
            if latest_time is None or ts_str > latest_time:
                latest_time = ts_str
                latest_sid = sid
        except: pass

    if not latest_sid:
        print("No active sessions found.")
        return

    print(f"Restoring to Session: {latest_sid}")
    
    # 5. Restore (Avoid Duplicates)
    active_session_trades = sessions[latest_sid].get('paper_trades', [])
    existing_ids = {t['id'] for t in active_session_trades}
    
    restored_count = 0
    for trade in zombie_trades:
        if trade['id'] not in existing_ids:
            # We insert at the beginning
            active_session_trades.insert(0, trade)
            restored_count += 1
            print(f" + Rezzed: {trade['symbol']} ({trade['side']}) from {trade['created_at']}")
    
    sessions[latest_sid]['paper_trades'] = active_session_trades

    # 6. Save
    temp_file = SESSIONS_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=4, default=str)
        f.flush()
        os.fsync(f.fileno())
    
    os.replace(temp_file, SESSIONS_FILE)
    print(f"Restoration Complete. {restored_count} zombie trades brought back to life.")

if __name__ == "__main__":
    restore_trades()
