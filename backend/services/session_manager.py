"""
Session Manager - In-memory session storage
Sessions are cleared on server restart
"""
import uuid
from typing import Dict, Optional
from datetime import datetime
import threading
from services.persistence_service import persistence_service

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
        self.paper_trades = [] # List of virtual trade objects
        self.virtual_balance = 0.0 # Virtual wallet balance
        self.is_paused = False
        self.auto_paper_trade = False
        self.selected_date = None  # User-selected date for High/Low (YYYY-MM-DD)
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.websocket_clients = []  # List of WebSocket connections

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()
        self._load_from_disk()

    def _load_from_disk(self):
        """Cleanup old sessions on startup"""
        persistence_service.cleanup_old_sessions()
        print("Session manager initialized")

    def save_session(self, session_id: str):
        """Saves session data to JSON safely in background"""
        session = self.get_session(session_id)
        if not session:
            return
            
        def _save_bg():
            if not hasattr(self, '_active_saves'):
                self._active_saves = set()
            if not hasattr(self, '_pending_saves'):
                self._pending_saves = set()
            
            with self.lock:
                if session_id in self._active_saves:
                    # Mark as pending so it runs again after current finishes
                    self._pending_saves.add(session_id)
                    return
                self._active_saves.add(session_id)
            
            try:
                while True:
                    persistence_service.save_session(session_id, session)
                    
                    with self.lock:
                        if session_id in self._pending_saves:
                            self._pending_saves.remove(session_id)
                            # Loop again to save the latest state
                            continue
                        else:
                            self._active_saves.remove(session_id)
                            break
            except Exception as e:
                print(f"[ERROR] Background save FAILED for session {session_id}: {e}")
                with self.lock:
                    self._active_saves.discard(session_id)
                    
        threading.Thread(target=_save_bg, daemon=True).start()

    def create_session(self, client_id: str, jwt_token: str, feed_token: str, api_key: str) -> Session:
        """Create a new session and restore user data if available"""
        existing_data = persistence_service.get_session_by_client(client_id)
        
        session_id = str(uuid.uuid4())
        session = Session(session_id, client_id, jwt_token, feed_token, api_key)
        
        if existing_data:
            print(f"[OK] Restoring data for client {client_id} from JSON")
            session.watchlist = existing_data.get('watchlist', [])
            session.alerts = existing_data.get('alerts', [])
            session.logs = existing_data.get('logs', [])
            session.paper_trades = existing_data.get('paper_trades', [])
            session.virtual_balance = existing_data.get('virtual_balance', 0.0)
            session.is_paused = existing_data.get('is_paused', False)
            session.auto_paper_trade = existing_data.get('auto_paper_trade', False)
            print(f"[OK] Restored {len(session.watchlist)} watchlist items, {len(session.alerts)} alerts, {len(session.paper_trades)} paper trades, Balance: {session.virtual_balance}")
        
        with self.lock:
            self.sessions[session_id] = session
        
        self.save_session(session_id)
        return session

    def get_session(self, session_id: str, client_id: Optional[str] = None) -> Optional[Session]:
        """Get session by ID, restore from JSON if not in memory"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_activity = datetime.now()
                return session
        
        # 1. Try JSON lookup by session_id
        session_data = persistence_service.get_session_by_session_id(session_id)
        
        # 2. SELF-HEALING: Try client_id if session_id not found
        if not session_data and client_id:
            print(f"[WARN] Session {session_id} not found. Healing via client_id {client_id}...")
            session_data = persistence_service.get_latest_session_by_client_id(client_id)
            
        # 3. LAST RESORT: Search for ANY latest record
        if not session_data:
            data = persistence_service.load_sessions()
            if data:
                latest_sid = None
                latest_time = ""
                for sid, s_data in data.items():
                    act = s_data.get('last_activity', '')
                    if act > latest_time:
                        latest_time = act
                        latest_sid = sid
                
                if latest_sid:
                    print(f"[INFO] Found dormant record {latest_sid}. Healing...")
                    session_data = data[latest_sid]

        if session_data:
            print(f"[OK] Recovered session data for client {session_data['client_id']}")
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
            session.paper_trades = session_data.get('paper_trades', [])
            session.virtual_balance = session_data.get('virtual_balance', 0.0)
            session.is_paused = session_data.get('is_paused', False)
            session.auto_paper_trade = session_data.get('auto_paper_trade', False)
            session.last_activity = datetime.now()
            
            with self.lock:
                self.sessions[session_id] = session
            
            # Re-initialize SmartAPI
            if session.jwt_token and session.api_key and not session.smart_api:
                from SmartApi import SmartConnect
                try:
                    smart_api = SmartConnect(api_key=session.api_key)
                    smart_api.setAccessToken(session.jwt_token)
                    session.smart_api = smart_api
                    print(f"[OK] SmartAPI re-initialized for {session.client_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to re-initialize SmartAPI: {e}")

            return session
        
        return None

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
        """Clear all sessions"""
        with self.lock:
            self.sessions.clear()

# Global session manager instance
session_manager = SessionManager()
