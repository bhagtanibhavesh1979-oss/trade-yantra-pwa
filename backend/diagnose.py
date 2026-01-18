import sys
import os
import asyncio
from services.session_manager import session_manager

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock setup
session_id = "test-session"
client_id = "test-client"

print("--- STARTING DIAGNOSTIC ---")

try:
    from routes import indices, watchlist, auth
    print("Imports success")
except Exception as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

async def test_endpoints():
    print(f"Creating test session {session_id}...")
    try:
        # Create a dummy session manually to bypass login
        from services.session_manager import Session
        session = Session(session_id, client_id, "jwt", "feed", "api_key")
        session_manager.sessions[session_id] = session
        print("Session created.")
    except Exception as e:
        print(f"Session creation error: {e}")
        return

    print("\n--- TESTING INDICES ---")
    try:
        res = await indices.get_indices(session_id)
        print(f"Indices Result: {res.keys() if res else 'None'}")
    except Exception as e:
        print(f"!!! INDICES CRASH !!!: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- TESTING WATCHLIST ---")
    try:
        res = await watchlist.get_watchlist(session_id, client_id)
        print(f"Watchlist Result: {res.keys() if res else 'None'}")
    except Exception as e:
        print(f"!!! WATCHLIST CRASH !!!: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_endpoints())
    print("\n--- DIAGNOSTIC COMPLETE ---")
