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
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.websocket_clients = []  # List of WebSocket connections

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()

    def create_session(self, client_id: str, jwt_token: str, feed_token: str, api_key: str) -> Session:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        session = Session(session_id, client_id, jwt_token, feed_token, api_key)
        with self.lock:
            self.sessions[session_id] = session
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
