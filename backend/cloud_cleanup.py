
import json
import os
import sys

# Ensure backend directory is in path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from backend.services.persistence_service import persistence_service
    
    print("[REFRESH] [CLEANUP] Starting cleanup of Cloud & Local session data...")
    
    # Force read from Cloud (True bypasses cache logic inside _read_all)
    all_data = persistence_service._read_all(force_refresh=True)
    
    if not all_data:
        print("[INFO] [CLEANUP] No session data found.")
    else:
        modified_count = 0
        for session_id, session_data in all_data.items():
            paper_trades = session_data.get('paper_trades', [])
            open_trades = [t for t in paper_trades if t.get('status') == 'OPEN']
            
            if open_trades:
                print(f" [CLEANUP] Found {len(open_trades)} stuck trades in session {session_id[:8]}")
                
                # Calculate Refund
                refund = 0.0
                for t in open_trades:
                    try:
                        entry = float(t['entry_price'])
                        qty = int(t['quantity'])
                        # 5% Margin assumption
                        margin = entry * qty * 0.05
                        refund += margin
                        print(f"   - Removed {t['symbol']} ({t['side']}). Refunded {margin:.2f}")
                    except: pass
                
                # Remove OPEN trades
                clean_trades = [t for t in paper_trades if t.get('status') != 'OPEN']
                session_data['paper_trades'] = clean_trades
                
                # Refund Balance
                current_bal = float(session_data.get('virtual_balance', 0))
                session_data['virtual_balance'] = current_bal + refund
                
                modified_count += 1
        
        if modified_count > 0:
            print(f" [CLEANUP] Saving clean state to Cloud/Disk for {modified_count} sessions...")
            persistence_service._write_all(all_data)
            print("[OK] [CLEANUP] Success! Trades removed from GCS and Local Disk.")
        else:
            print("[OK] [CLEANUP] No open trades found on Cloud/Disk.")

except Exception as e:
    print(f"[ERR] [ERROR] Cleanup failed: {e}")
