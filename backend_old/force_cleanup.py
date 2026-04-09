
import json
import os

SESSION_FILE = r"backend/data/sessions.json"

def cleanup_stuck_trades():
    if not os.path.exists(SESSION_FILE):
        print("Session file not found.")
        return

    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        
        for session_id, session in data.items():
            paper_trades = session.get('paper_trades', [])
            balance = session.get('virtual_balance', 0)
            
            # Filter Open Trades
            open_trades = [t for t in paper_trades if t.get('status') == 'OPEN']
            
            if open_trades:
                print(f"Found {len(open_trades)} stuck trades in session {session_id[:8]}... Cleaning up.")
                
                for trade in open_trades:
                    # Refund Margin
                    try:
                        entry = float(trade['entry_price'])
                        qty = int(trade['quantity'])
                        # 5% Margin assumption from service
                        margin = entry * qty * 0.05
                        balance += margin
                        print(f" - REMOVING {trade['symbol']} ({trade['side']}) Qty: {qty}. Refunded {margin:.2f}")
                    except Exception as e:
                        print(f" - Error calculating refund for {trade.get('symbol')}: {e}")
                
                # Keep only CLOSED trades (effectively creating a new list without the OPEN ones)
                # If we want to keep them in history as closed, we should update status.
                # User asked to "remove", so deleting them is cleaner for "stuck" ones.
                # However, to be safe, let's just mark them CLOSED with 0 PnL and special reason?
                # No, user wants them gone. "Delete" is best for "stuck" things.
                
                new_trades = [t for t in paper_trades if t.get('status') != 'OPEN']
                
                session['paper_trades'] = new_trades
                session['virtual_balance'] = balance
                modified = True
        
        if modified:
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print("[OK] Successfully removed stuck open trades and refunded margins.")
        else:
            print("No open trades found to clean up.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    cleanup_stuck_trades()
