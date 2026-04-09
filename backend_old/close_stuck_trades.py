"""
One-shot script to force-close stuck OPEN paper trades.
Run this while the backend is STOPPED, then restart the backend.
"""
import json
import os
from datetime import datetime, timezone

SESSIONS_FILE = "data/sessions.json"
HISTORY_FILE = "data/history_B38590.json"
STUCK_TRADE_IDS = {"v1772684112_17869", "v1772684112_17094"}

def tick_round(price):
    return round(float(price) * 20) / 20.0

now_iso = datetime.now(timezone.utc).isoformat()
fixed = 0

# FIX SESSIONS.JSON
if os.path.exists(SESSIONS_FILE):
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    for session_id, session_data in sessions.items():
        paper_trades = session_data.get("paper_trades", [])
        for trade in paper_trades:
            if trade.get("id") in STUCK_TRADE_IDS and trade.get("status") == "OPEN":
                entry_price = float(trade.get("entry_price", 0))
                exit_price = tick_round(entry_price)
                qty = int(trade.get("quantity", 100))
                
                trade["status"] = "CLOSED"
                trade["exit_price"] = exit_price
                trade["closed_at"] = now_iso
                trade["exit_reason"] = "MANUAL_FORCE_CLOSE"
                
                if trade["side"] == "BUY":
                    trade["pnl"] = round((exit_price - entry_price) * qty, 2)
                else:
                    trade["pnl"] = round((entry_price - exit_price) * qty, 2)
                
                print(f"[sessions.json] Closed {trade['symbol']} ({trade['id']}) "
                      f"{trade['side']} @ {exit_price} | Session: {session_id[:8]}")
                fixed += 1

    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=4)

# FIX HISTORY FILE
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    for trade in history:
        if trade.get("status") == "OPEN":
            entry_price = float(trade.get("entry_price", 0))
            exit_price = tick_round(entry_price)
            qty = int(trade.get("quantity", 100))
            
            trade["status"] = "CLOSED"
            trade["exit_price"] = exit_price
            trade["closed_at"] = now_iso
            trade["exit_reason"] = "MANUAL_FORCE_CLOSE"
            
            if trade["side"] == "BUY":
                trade["pnl"] = round((exit_price - entry_price) * qty, 2)
            else:
                trade["pnl"] = round((entry_price - exit_price) * qty, 2)
            
            print(f"[history config] Closed {trade['symbol']} ({trade['id']}) "
                  f"{trade['side']} @ {exit_price}")
            fixed += 1

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

print(f"\n[DONE] Fixed {fixed} total trade instances. Restart backend.")
