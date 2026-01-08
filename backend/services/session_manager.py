"""
Session Manager - In-memory session storage
Sessions are cleared on server restart (Railway sleep)
"""
import uuid
from typing import Dict, Optional
from datetime import datetime
import threading

class Session:
    def __init__(self, session_id: str, client_id: str, jwt_token: str, feed_token: str, api_key: str):
        self.session_id = session_id
        self.client_id = client_id
        self.jwt_token = jwt_token
        self.feed_token = feed_token
        self.api_key = api_key
        self.refresh_token = None
        self.smart_api = None  # Authenticated SmartConnect instance
        self.watchlist = []  # List of {symbol, token, exch_seg, ltp, wc}
        self.alerts = []  # List of {id, symbol, token, condition, price, active}
        self.logs = []  # List of {time, symbol, msg}
        self.is_paused = False
        self.selected_date = None  # User-selected date for High/Low (YYYY-MM-DD)
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.websocket_clients = []  # List of WebSocket connections

from services.persistence_service import persistence_service

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()
        self._load_from_disk()

    def _load_from_disk(self):
        """Load sessions from disk on startup - DISABLED for memory optimization"""
        # MEMORY OPTIMIZATION: Don't preload all sessions on startup
        # This was causing 512MB+ usage on Render's free tier
        # Sessions will be created fresh on login instead
        persistence_service.cleanup_old_sessions()
        # data = persistence_service.load_sessions()
        # for session_id, s_data in data.items():
        #     try:
        #         # Reconstruct session
        #         session = Session(
        #             session_id,
        #             s_data['client_id'],
        #             s_data.get('jwt_token', ''),
        #             s_data.get('feed_token', ''),
        #             s_data.get('api_key', '')
        #         )
        #         session.watchlist = s_data.get('watchlist', [])
        #         session.alerts = s_data.get('alerts', [])
        #         session.logs = s_data.get('logs', [])
        #         session.is_paused = s_data.get('is_paused', False)
        #         if s_data.get('last_activity'):
        #             session.last_activity = datetime.fromisoformat(s_data['last_activity'])
        #         
        #         self.sessions[session_id] = session
        #     except Exception as e:
        #         print(f"Error loading session {session_id}: {e}")
        
        print("Session manager initialized (memory-optimized mode)")

    def save_session(self, session_id: str):
        """
        Save session in background thread.
        This keeps the UI extremely snappy while ensuring data is persisted to Postgres.
        """
        def background_save():
            with self.lock:
                session = self.sessions.get(session_id)
                if not session:
                    return
                # We copy the data we need or just trust the session object
                # for simple lists like watchlist/alerts which are modified in-place
                try:
                    persistence_service.save_session(session_id, session)
                except Exception as e:
                    print(f"❌ Background save failed for {session_id}: {e}")
        
        # Start background task
        threading.Thread(target=background_save, daemon=True).start()

    def create_session(self, client_id: str, jwt_token: str, feed_token: str, api_key: str) -> Session:
        """Create a new session and restore user data from DB if available"""
        # Check if we have data for this client_id in the database
        existing_data = persistence_service.get_session_by_client(client_id)
        
        session_id = str(uuid.uuid4())
        session = Session(session_id, client_id, jwt_token, feed_token, api_key)
        
        if existing_data:
            print(f"Restoring data for client {client_id} from database")
            session.watchlist = existing_data.get('watchlist', [])
            session.alerts = existing_data.get('alerts', [])
            session.logs = existing_data.get('logs', [])
            session.is_paused = existing_data.get('is_paused', False)
        
        with self.lock:
            self.sessions[session_id] = session
        
        # Save in background - don't block the login response
        self.save_session(session_id)
        
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID, restore from DB if not in memory"""
        # 1. Check memory with lock
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_activity = datetime.now()
                return session
        
        # 2. If not found, check DB WITHOUT holding the global lock
        # This prevents blocking the whole app while waiting for Neon.tech
        print(f"🔄 Session {session_id} not in memory, attempting to restore from database")
        session_data = persistence_service.get_session_by_session_id(session_id)
        
        if session_data:
            print(f"✅ Restoring session {session_id} from database")
            session = Session(
                session_id,
                session_data['client_id'],
                session_data.get('jwt_token', ''),
                session_data.get('feed_token', ''),
                session_data.get('api_key', '')
            )
            session.watchlist = session_data.get('watchlist', [])
            session.alerts = session_data.get('alerts', [])
            session.logs = session_data.get('logs', [])
            session.is_paused = session_data.get('is_paused', False)
            session.last_activity = datetime.now()
            
            # 3. Store in memory with lock
            with self.lock:
                self.sessions[session_id] = session
            
            # 4. CRITICAL: Restore Angel One Connection if tokens exist
            if session.jwt_token and session.api_key and not session.smart_api:
                from services.angel_service import angel_service
                print(f"🔄 Re-initializing SmartAPI for session {session_id}")
                try:
                    from SmartApi import SmartConnect
                    smart_api = SmartConnect(api_key=session.api_key)
                    smart_api.setAccessToken(session.jwt_token)
                    session.smart_api = smart_api
                    print(f"✅ SmartAPI re-initialized for {session.client_id}")
                except Exception as e:
                    print(f"❌ Failed to re-initialize SmartAPI: {e}")

            return session
        
        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                self.save_session(session_id) # Save the deletion
                return True
            return False

    def get_all_sessions(self) -> Dict[str, Session]:
        """Get all active sessions"""
        with self.lock:
            return dict(self.sessions)

    def clear_all(self):
        """Clear all sessions (called on shutdown)"""
        with self.lock:
            self.sessions.clear()

# Global session manager instance
session_manager = SessionManager()
