
import json
import os
import datetime

SESSIONS_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"

# HARDCODED TRADES SAVED FROM TRUNCATED HISTORY
RESTORE_TRADES = [
    {
        "id": "v1769923805_14732", "symbol": "DLF-EQ", "token": "14732", "side": "BUY", 
        "entry_price": 639.55, "quantity": 100, "status": "OPEN", "trigger_level": "S1", "mode": "NEW"
    },
    {
        "id": "v1769923806_5258", "symbol": "INDUSINDBK-EQ", "token": "5258", "side": "BUY", 
        "entry_price": 902.1, "quantity": 100, "status": "OPEN", "trigger_level": "S4", "mode": "NEW"
    },
    {
        "id": "v1769923808_20560", "symbol": "DOLLAR-EQ", "token": "20560", "side": "BUY", 
        "entry_price": 318.35, "quantity": 100, "status": "OPEN", "trigger_level": "S5", "mode": "NEW"
    },
    {
        "id": "v1769924706_16675", "symbol": "BAJAJFINSV-EQ", "token": "16675", "side": "BUY", 
        "entry_price": 1945.1, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924706_8479", "symbol": "TVSMOTOR-EQ", "token": "8479", "side": "BUY", 
        "entry_price": 3673.0, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924709_13538", "symbol": "TECHM-EQ", "token": "13538", "side": "BUY", 
        "entry_price": 1744.3, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924709_341", "symbol": "BALRAMCHIN-EQ", "token": "341", "side": "BUY", 
        "entry_price": 436.5, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924710_5097", "symbol": "ETERNAL-EQ", "token": "5097", "side": "BUY", 
        "entry_price": 273.35, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924712_11723", "symbol": "JSWSTEEL-EQ", "token": "11723", "side": "BUY", 
        "entry_price": 1218.3, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924713_3426", "symbol": "TATAPOWER-EQ", "token": "3426", "side": "BUY", 
        "entry_price": 370.8, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924714_275", "symbol": "AUROPHARMA-EQ", "token": "275", "side": "BUY", 
        "entry_price": 1188.5, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924714_4963", "symbol": "ICICIBANK-EQ", "token": "4963", "side": "BUY", 
        "entry_price": 1360.9, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924716_371", "symbol": "BATAINDIA-EQ", "token": "371", "side": "SELL", 
        "entry_price": 872.75, "quantity": 100, "status": "OPEN", "trigger_level": "R4", "mode": "NEW"
    },
    {
        "id": "v1769924717_3063", "symbol": "VEDL-EQ", "token": "3063", "side": "BUY", 
        "entry_price": 670.0, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924720_637", "symbol": "CHAMBLFERT-EQ", "token": "637", "side": "BUY", 
        "entry_price": 446.7, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924722_17869", "symbol": "JSWENERGY-EQ", "token": "17869", "side": "BUY", 
        "entry_price": 459.9, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769924724_99919000", "symbol": "SENSEX", "token": "99919000", "side": "BUY", 
        "entry_price": 82629.16, "quantity": 100, "status": "OPEN", "trigger_level": "S6", "mode": "NEW"
    },
    {
        "id": "v1769925609_3405", "symbol": "TATACHEM-EQ", "token": "3405", "side": "SELL", 
        "entry_price": 749.0, "quantity": 100, "status": "OPEN", "trigger_level": "LOW", "mode": "NEW"
    },
    {
        "id": "v1769925614_3499", "symbol": "TATASTEEL-EQ", "token": "3499", "side": "SELL", 
        "entry_price": 191.9, "quantity": 100, "status": "OPEN", "trigger_level": "R1", "mode": "NEW"
    }
]

def force_restore():
    print(f"Loading Session File: {SESSIONS_FILE}")
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    # Find active session (most recent)
    latest_sid = None
    latest_time = None
    for sid, data in sessions.items():
        ts_str = data.get('last_activity', '')
        if not ts_str: continue
        if latest_time is None or ts_str > latest_time:
            latest_time = ts_str
            latest_sid = sid

    if not latest_sid:
        print("No active session found!")
        return

    print(f"Injecting into Session: {latest_sid}")
    
    current_trades = sessions[latest_sid].get('paper_trades', [])
    current_ids = {t['id'] for t in current_trades}
    
    added = 0
    for t in RESTORE_TRADES:
        if t['id'] not in current_ids:
            # Add missing fields
            if 'created_at' not in t: t['created_at'] = datetime.datetime.now().isoformat()
            if 'pnl' not in t: t['pnl'] = 0.0
            if 'stop_loss' not in t: t['stop_loss'] = None
            if 'target' not in t: t['target'] = None
            
            current_trades.insert(0, t)
            added += 1
            print(f" + Restored {t['symbol']} ({t['side']})")
            
    sessions[latest_sid]['paper_trades'] = current_trades
    
    # Save
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=4, default=str)
        
    print(f"DONE. Added {added} trades.")

if __name__ == "__main__":
    force_restore()
