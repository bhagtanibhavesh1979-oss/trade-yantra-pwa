"""
Persistence Service (JSON)
Handles saving and loading session data to/from backend/data/sessions.json
"""
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

class PersistenceService:
    def __init__(self):
        self.lock = threading.Lock()
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        self.storage_client = None
        
        # 1. Initialize GCS Client if bucket name is provided
        if self.bucket_name and "your-gcs-bucket-name" not in self.bucket_name:
            try:
                from google.cloud import storage
                self.storage_client = storage.Client()
                # Verify bucket exists/accessible with a short timeout
                bucket = self.storage_client.bucket(self.bucket_name)
                # Use a specific timeout for bucket existence check to prevent hangs
                if not bucket.exists(timeout=5.0):
                    print(f"⚠️  GCS Bucket '{self.bucket_name}' not found or unreachable. Persistence will be local-only.")
                    self.storage_client = None
                else:
                    print(f"☁️  GCS Persistence ACTIVE: gs://{self.bucket_name}/sessions.json")
            except Exception as e:
                print(f"⚠️  Failed to initialize GCS: {e}. Falling back to local DATA partition.")
                self.storage_client = None
        else:
            if self.bucket_name == "your-gcs-bucket-name":
                print("ℹ️ GCS placeholder detected. Using local persistence only.")
            self.storage_client = None

        # 2. Setup Local Cache Directory
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        # 3. Create local sessions.json if it doesn't exist
        if not os.path.exists(SESSIONS_FILE):
            print(f"📝 Creating local state cache: {SESSIONS_FILE}")
            with open(SESSIONS_FILE, 'w') as f:
                json.dump({}, f)
        
        print(f"✅ Local Persistence initialized: {SESSIONS_FILE}")

    def _read_all(self) -> Dict:
        """Read all sessions from GCS or JSON file"""
        with self.lock:
            # 1. Try GCS first if enabled
            if self.storage_client and self.bucket_name:
                try:
                    bucket = self.storage_client.bucket(self.bucket_name)
                    blob = bucket.blob("sessions.json")
                    if blob.exists():
                        content = blob.download_as_string()
                        return json.loads(content)
                    return {}
                except Exception as e:
                    print(f"⚠️ GCS Read Error: {e}. Falling back to local cache.")

            # 2. Local Fallback
            try:
                if os.path.exists(SESSIONS_FILE):
                    with open(SESSIONS_FILE, 'r') as f:
                        return json.load(f)
            except Exception as e:
                print(f"❌ Error reading sessions file: {e}")
            return {}

    def _write_all(self, data: Dict):
        """Write all sessions to JSON file and sync to GCS"""
        with self.lock:
            # 1. Always write locally first (fast cache)
            try:
                with open(SESSIONS_FILE, 'w') as f:
                    json.dump(data, f, indent=4, default=str)
            except Exception as e:
                print(f"❌ Error writing sessions file: {e}")

            # 2. Sync to GCS if enabled
            if self.storage_client and self.bucket_name:
                try:
                    bucket = self.storage_client.bucket(self.bucket_name)
                    blob = bucket.blob("sessions.json")
                    blob.upload_from_string(
                        json.dumps(data, indent=4, default=str),
                        content_type='application/json'
                    )
                except Exception as e:
                    print(f"❌ GCS Sync Error: {e}")

    def save_session(self, session_id: str, session):
        """Save a single session data safely"""
        data = self._read_all()
        
        session_data = {
            "client_id": session.client_id,
            "jwt_token": session.jwt_token,
            "feed_token": session.feed_token,
            "api_key": session.api_key,
            "is_paused": getattr(session, 'is_paused', False),
            "selected_date": getattr(session, 'selected_date', None),
            "last_activity": datetime.now().isoformat(),
            "watchlist": session.watchlist,
            "alerts": session.alerts,
            "logs": session.logs[-100:] if hasattr(session, 'logs') else [],
            "auto_paper_trade": getattr(session, 'auto_paper_trade', False),
            "paper_trades": getattr(session, 'paper_trades', [])[-50:]
        }
        
        data[session_id] = session_data
        self._write_all(data)
        print(f"✅ Persistence: Session {session_id} saved (W:{len(session.watchlist)} A:{len(session.alerts)})")

    def load_sessions(self) -> Dict:
        """Load all sessions from JSON file"""
        return self._read_all()

    def get_session_by_session_id(self, session_id: str) -> Dict:
        """Get session data for a specific session_id"""
        data = self._read_all()
        return data.get(session_id, {})

    def get_session_by_client(self, client_id: str) -> Dict:
        """Get the most recent session data for a specific client_id"""
        data = self._read_all()
        # Find the session with the latest last_activity for this client
        client_sessions = [
            (sid, s_data) for sid, s_data in data.items() 
            if s_data.get('client_id') == client_id
        ]
        
        if not client_sessions:
            return {}
            
        # Sort by last_activity descending
        client_sessions.sort(key=lambda x: x[1].get('last_activity', ''), reverse=True)
        return client_sessions[0][1]

    def get_latest_session_by_client_id(self, client_id: str) -> Dict:
        """Alias for get_session_by_client for compatibility"""
        return self.get_session_by_client(client_id)

    def cleanup_old_sessions(self, days: int = 7):
        """Cleanup logic (optional for JSON)"""
        # Not strictly needed for simple JSON persistence but good to have
        pass

# Global instance
persistence_service = PersistenceService()
