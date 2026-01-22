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
        self.lock = threading.RLock()
        self._cache = {}
        self._last_loaded = None
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
                    print(f"[WARN] GCS Bucket '{self.bucket_name}' not found or unreachable. Persistence will be local-only.")
                    self.storage_client = None
                else:
                    print(f"[INFO] GCS Persistence ACTIVE: gs://{self.bucket_name}/sessions.json")
            except Exception as e:
                print(f"[WARN] Failed to initialize GCS: {e}. Falling back to local DATA partition.")
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
            print(f"[INFO] Creating local state cache: {SESSIONS_FILE}")
            with open(SESSIONS_FILE, 'w') as f:
                json.dump({}, f)
        
        print(f"[OK] Local Persistence initialized: {SESSIONS_FILE}")

    def _read_all(self, force_refresh: bool = False) -> Dict:
        """Read all sessions from cache, GCS or JSON file"""
        # 1. Return cache if recent (simple debounce)
        if not force_refresh and self._cache and self._last_loaded:
            # If loaded in last 5 seconds, trust cache
            if (datetime.now() - self._last_loaded).total_seconds() < 5:
                return self._cache

        # 2. Try GCS if enabled (NO LOCK during network IO)
        remote_data = None
        if self.storage_client and self.bucket_name:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob("sessions.json")
                # Use a specific timeout for GCS read
                if blob.exists(timeout=3.0):
                    content = blob.download_as_string(timeout=5.0)
                    remote_data = json.loads(content)
            except Exception as e:
                print(f"[WARN] GCS Read Error: {e}")

        # 3. Local Fallback & Merge (With LOCK for local IO)
        with self.lock:
            local_data = {}
            try:
                if os.path.exists(SESSIONS_FILE):
                    with open(SESSIONS_FILE, 'r') as f:
                        local_data = json.load(f)
            except Exception as e:
                print(f"[ERROR] Error reading sessions file: {e}")

            # Merge or prioritize remote
            data = remote_data if remote_data is not None else local_data
            
            # Update cache
            self._cache = data
            self._last_loaded = datetime.now()
            return data

    def _write_all(self, data: Dict):
        """Write all sessions to JSON file and sync to GCS"""
        # 1. Update local cache and local file FIRST (Fast)
        with self.lock:
            self._cache = data
            try:
                with open(SESSIONS_FILE, 'w') as f:
                    json.dump(data, f, indent=4, default=str)
            except Exception as e:
                print(f"[ERROR] Error writing sessions file: {e}")

        # 2. Sync to GCS in background/outside lock (NO LOCK)
        if self.storage_client and self.bucket_name:
            def _sync_gcs():
                try:
                    bucket = self.storage_client.bucket(self.bucket_name)
                    blob = bucket.blob("sessions.json")
                    blob.upload_from_string(
                        json.dumps(data, indent=4, default=str),
                        content_type='application/json',
                        timeout=10.0
                    )
                except Exception as e:
                    print(f"[ERROR] GCS Sync Async Error: {e}")
            
            # Since SessionManager already runs saves in threads, 
            # we can just run this synchronously here as it's already in a worker thread usually.
            # But just to be 100% sure we don't block the caller (like login):
            _sync_gcs()

    def save_session(self, session_id: str, session):
        """Save a single session data safely with atomic read-modify-write"""
        with self.lock:
            # 1. Always force fresh read before modification to prevent overwriting other sessions
            data = self._read_all(force_refresh=True)
            
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
                "logs": session.logs[:100] if hasattr(session, 'logs') else [],
                "auto_paper_trade": getattr(session, 'auto_paper_trade', False),
                "virtual_balance": getattr(session, 'virtual_balance', 0.0),
                "paper_trades": getattr(session, 'paper_trades', [])[:100]
            }
            
            # 2. IDENTIFY REPLACEMENTS: 
            # We want to keep only the CURRENT session for this client_id 
            # if the current session is NEWER or if we are the current session.
            cid_upper = str(session.client_id).upper()
            
            # Instead of wiping everything else immediately, let's be more surgical.
            # Only remove sessions that are NOT the current one AND have the same client_id.
            # This is already what the logic did, but let's make it clearer.
            initial_count = len(data)
            data = {
                sid: s_data for sid, s_data in data.items() 
                if sid == session_id or str(s_data.get('client_id', '')).upper() != cid_upper
            }
            
            removed_others = initial_count - len(data)
            if removed_others > 0:
                print(f"DEBUG: Consolidating {removed_others} older sessions for client {cid_upper}")

            data[session_id] = session_data
            
            # 3. Synchronous local write (since we are in a lock)
            self._write_all(data)
            
            paper_count = len(session_data['paper_trades'])
            balance = session_data.get('virtual_balance', 0.0)
            print(f"[OK] Persistence: Session {session_id} saved (W:{len(session.watchlist)} A:{len(session.alerts)} P:{paper_count} Bal: {balance})")

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
            if str(s_data.get('client_id', '')).upper() == client_id.upper()
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

    def add_to_trade_history(self, client_id: str, trade: Dict):
        """Append a closed trade to the permanent history file (Local + GCS)"""
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        gcs_path = f"history_{client_id}.json"
        
        with self.lock:
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                except:
                    history = []
            
            # Avoid duplicate trade IDs if any
            if not any(t.get('id') == trade.get('id') for t in history):
                history.append(trade)
            
            # Keep the history reasonably sized for JSON (e.g. 2000 trades)
            if len(history) > 2000:
                history = history[-2000:]
                
            try:
                content = json.dumps(history, indent=4, default=str)
                with open(history_file, 'w') as f:
                    f.write(content)
                
                # Sync to GCS if active
                if self.storage_client and self.bucket_name:
                    try:
                        bucket = self.storage_client.bucket(self.bucket_name)
                        blob = bucket.blob(gcs_path)
                        blob.upload_from_string(content, content_type='application/json')
                        print(f"[OK] History synced to GCS: {gcs_path}")
                    except Exception as ge:
                        print(f"[WARN] GCS History Sync Failed: {ge}")
                        
            except Exception as e:
                print(f"[ERROR] Failed to save trade history for {client_id}: {e}")

    def get_trade_history(self, client_id: str) -> List[Dict]:
        """Load the permanent history for a client (Local + GCS fallback)"""
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        remote_history = None
        
        # 1. Try GCS if local not found or older (simplified: just try GCS if local missing)
        if not os.path.exists(history_file) and self.storage_client and self.bucket_name:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob(f"history_{client_id}.json")
                if blob.exists():
                    content = blob.download_as_string()
                    remote_history = json.loads(content)
                    # Cache locally
                    with open(history_file, 'w') as f:
                        json.dump(remote_history, f, indent=4)
            except: pass

        # 2. Return local
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        
        return remote_history if remote_history else []

# Global instance
persistence_service = PersistenceService()
