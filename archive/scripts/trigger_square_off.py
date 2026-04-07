"""
Manual Trigger for Auto Square-off
Use this to force the 3:15 PM square-off logic to run immediately.
"""
import sys
import os
from datetime import datetime
import pytz

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.session_manager import session_manager
from services.paper_service import paper_service
from services.websocket_manager import ws_manager

def trigger_all():
    all_sessions = session_manager.get_all_sessions()
    if not all_sessions:
        print("❌ No active sessions found.")
        return

    # Mock token map (simplified)
    # The actual heartbeat passes a token map, but check_and_square_off 
    # will fallback to watchlist ltp if token_map is missing/empty for specific tokens.
    token_map = {} 
    
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    print(f"🕒 Current IST Time: {now_ist.strftime('%H:%M:%S')}")

    for sid, session in all_sessions.items():
        print(f"\n--- Processing Session: {session.client_id} (SID: {sid[:8]}) ---")
        
        # Reset the "last square off" flag for testing so we can re-run the logic
        session.last_auto_square_off = "" 
        
        # We manually call the logic that usually runs in the heartbeat
        print(f"📡 Triggering check_and_square_off...")
        paper_service.check_and_square_off(sid, token_map)

if __name__ == "__main__":
    trigger_all()
