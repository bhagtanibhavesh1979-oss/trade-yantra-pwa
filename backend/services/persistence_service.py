"""
Persistence Service
Handles saving and loading session data to/from disk
"""
import json
import os
import threading
from typing import Dict, List, Optional
from datetime import datetime

DATA_FILE = "data/sessions.json"

class PersistenceService:
    def __init__(self):
        self.lock = threading.Lock()
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        if not os.path.exists("data"):
            os.makedirs("data")

    def save_sessions(self, sessions_data: Dict):
        """
        Save all sessions to disk
        """
        try:
            with self.lock:
                # Convert sessions to serializable format
                serializable_data = {}
                for session_id, session in sessions_data.items():
                    serializable_data[session_id] = {
                        "client_id": session.client_id,
                        "jwt_token": session.jwt_token,
                        "feed_token": session.feed_token,
                        "api_key": session.api_key,
                        "watchlist": session.watchlist,
                        "alerts": session.alerts,
                        "logs": session.logs[-50:],  # Keep last 50 logs
                        "is_paused": session.is_paused,
                        "last_activity": session.last_activity.isoformat() if session.last_activity else None
                    }
                
                with open(DATA_FILE, 'w') as f:
                    json.dump(serializable_data, f, indent=2)
                
                print(f"Saved {len(sessions_data)} sessions to disk")
        except Exception as e:
            print(f"Failed to save sessions: {e}")

    def load_sessions(self) -> Dict:
        """
        Load sessions from disk
        """
        if not os.path.exists(DATA_FILE):
            return {}
            
        try:
            with self.lock:
                with open(DATA_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load sessions: {e}")
            return {}

# Global instance
persistence_service = PersistenceService()
