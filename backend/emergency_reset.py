import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

def force_reset():
    try:
        from services.persistence_service import persistence_service
        from services.session_manager import session_manager
        
        # 1. Look for active sessions
        sessions = session_manager.get_all_sessions()
        if not sessions:
            print("No active sessions in memory. Checking disk...")
            # If nothing in memory, persistence service will read from GCS/local
        
        # 2. Reset all trades for all sessions found
        count = 0
        cleaned_clients = set()
        for sid, session in sessions.items():
            print(f"Resetting session: {sid} (Client: {session.client_id})")
            session.paper_trades = []
            session.virtual_balance = 500000.0
            session.logs = []
            session_manager.save_session(sid)
            
            # 3. Clear permanent history for this client
            client_id = str(session.client_id).upper()
            if client_id not in cleaned_clients:
                print(f"Clearing history file for {client_id}...")
                persistence_service.clear_trade_history(client_id)
                cleaned_clients.add(client_id)
            
            count += 1
            
        if count == 0:
            print("No active sessions found to reset.")
            return

        print(f"DONE: Successfully reset {count} sessions and cleared history for {len(cleaned_clients)} clients.")
        
    except Exception as e:
        print(f"ERROR: Error during force reset: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_reset()
