
import json
import os

SESSIONS_FILE = r"c:\Users\bhave\Downloads\trade-yantra\backend\data\sessions.json"

def audit_balance():
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    for sid, data in sessions.items():
        if not data.get('paper_trades'): continue

        start_bal = 500000.0
        realized_pnl = 0.0
        blocked_margin = 0.0
        
        open_trades = []

        for t in data.get('paper_trades', []):
            qty = int(t.get('quantity', 100))
            if t['status'] == 'CLOSED':
                realized_pnl += float(t.get('pnl', 0.0))
            elif t['status'] == 'OPEN':
                entry = float(t['entry_price'])
                margin = entry * qty
                blocked_margin += margin
                open_trades.append(f"{t['symbol']} ({margin:.0f})")

        # Correct Formula: 
        # Available Balance = Start + Realized - Blocked
        new_balance = start_bal + realized_pnl - blocked_margin
        
        print(f"Session {sid[:8]}:")
        print(f"  Start:      {start_bal}")
        print(f"  Realized:   {realized_pnl:+.2f}")
        print(f"  Blocked:    -{blocked_margin:.2f}  ({len(open_trades)} trades)")
        print(f"  Calculated: {new_balance:.2f}")
        print(f"  Current:    {data.get('virtual_balance', 0.0):.2f}")
        
        # Update
        data['virtual_balance'] = new_balance

    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=4, default=str)
        
    print("Audit Complete. Balances reconciled.")

if __name__ == "__main__":
    audit_balance()
