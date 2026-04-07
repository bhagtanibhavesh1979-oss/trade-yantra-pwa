import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    with open('backend/data/sessions.json', 'r') as f:
        data = json.load(f)
        for sid, sdata in data.items():
            if sdata.get('auto_paper_trade'):
                print(f"Session: {sid[:8]}")
                print(f"  client_id: {sdata.get('client_id')}")
                print(f"  auto_paper_trade: {sdata.get('auto_paper_trade')}")
                
                # Check paper trades
                trades = sdata.get('paper_trades', [])
                today_trades = [t for t in trades if t.get('entry_time', '').startswith('2026-03-06')]
                print(f"  Today's Paper Trades: {len(today_trades)}")
                for t in today_trades:
                    print(f"    {t.get('symbol')} {t.get('side')} at {t.get('entry_time')} reason: {t.get('reason')} id: {t.get('id')}")
                    
                print("-" * 40)
except Exception as e:
    print(f"Error: {e}")
