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
        """Load sessions from disk on startup"""
        data = persistence_service.load_sessions()
        for session_id, s_data in data.items():
            try:
                # Reconstruct session
                session = Session(
                    session_id,
                    s_data['client_id'],
                    s_data.get('jwt_token', ''),
                    s_data.get('feed_token', ''),
                    s_data.get('api_key', '')
                )
                session.watchlist = s_data.get('watchlist', [])
                session.alerts = s_data.get('alerts', [])
                session.logs = s_data.get('logs', [])
                session.is_paused = s_data.get('is_paused', False)
                if s_data.get('last_activity'):
                    session.last_activity = datetime.fromisoformat(s_data['last_activity'])
                
                self.sessions[session_id] = session
            except Exception as e:
                print(f"Error loading session {session_id}: {e}")
        
        print(f"Loaded {len(self.sessions)} sessions from disk")

    def save_session(self, session_id: str):
        """Trigger save for a specific session"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                persistence_service.save_session(session_id, session)

    def create_session(self, client_id: str, jwt_token: str, feed_token: str, api_key: str) -> Session:
        """Create a new session"""
        # Check if we have an existing session for this client_id to restore data
        existing_session = next((s for s in self.sessions.values() if s.client_id == client_id), None)
        
        session_id = str(uuid.uuid4())
        session = Session(session_id, client_id, jwt_token, feed_token, api_key)
        
        if existing_session:
            print(f"Restoring data for client {client_id} from previous session")
            session.watchlist = existing_session.watchlist
            session.alerts = existing_session.alerts
            session.logs = existing_session.logs
            # We don't restore is_paused usually on new login, but let's keep it clean
        
        with self.lock:
            self.sessions[session_id] = session
        
        self.save_session(session_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_activity = datetime.now()
            return session

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
