"""
Persistence Service (JSON)
Handles saving and loading session data to/from backend/data/sessions.json
Modified for VPS stability and Rigid Balance Recovery
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Constants
# On VPS, we use a fixed data/ directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

# VPS Detection: Default to True if NOT on Google Cloud Run
IS_CLOUD_RUN = os.environ.get("K_SERVICE") is not None
IS_VPS = os.environ.get("IS_VPS", "true").lower() == "true" if not IS_CLOUD_RUN else False

class PersistenceService:
    def __init__(self):
        self.lock = threading.RLock()
        self._cache = {}
        self._last_loaded = None
        
        # PRIMARY: Google Cloud Storage (Disabled on VPS)
        self.bucket_name = "trade-yantra-storage-asia"
        self.storage_client = None
        
        if not IS_VPS:
            try:
                from google.cloud import storage
                self.storage_client = storage.Client()
                print(f"[OK] [CLOUD] Persistence active: gs://{self.bucket_name}")
            except Exception as e:
                print(f"[WARN] [CLOUD] Storage init failed: {e}. Using local memory.")

        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)

    def _read_all(self, force_refresh: bool = False) -> Dict:
        """Fetch all sessions from Local JSON (Priority on VPS) or GCS"""
        if not force_refresh:
            if self._cache and self._last_loaded:
                if (datetime.now() - self._last_loaded).total_seconds() < 2:
                    return self._cache

        remote_data = None
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob("sessions.json")
                if blob.exists(timeout=2.0):
                    content = blob.download_as_string(timeout=3.0)
                    remote_data = json.loads(content)
            except: pass

        local_data = {}
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
            except: pass

        # Final Merge
        data = {}
        if local_data: data.update(local_data)
        if remote_data: data.update(remote_data)
        
        if not data and self._cache:
            return self._cache
            
        self._cache = data
        self._last_loaded = datetime.now()
        return data

    def _write_all(self, data: Dict):
        """Save all sessions to Local JSON and GCS"""
        with self.lock:
            self._cache = data

        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob("sessions.json")
                blob.upload_from_string(json.dumps(data, indent=4, default=str), content_type='application/json')
            except: pass
        
        # Always write to Local on VPS
        try:
            if os.path.exists(SESSIONS_FILE):
                import shutil
                shutil.copy2(SESSIONS_FILE, SESSIONS_FILE + ".bak")

            temp_file = SESSIONS_FILE + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, SESSIONS_FILE)
        except Exception as e:
            print(f"[ERR] [DISK] Write Error: {e}")

    def save_session(self, session_id: str, session):
        """Save a single session data safely"""
        with self.lock:
            data = self._read_all(force_refresh=True)
            
            # Anti-Zero Protection
            memory_balance = float(getattr(session, 'virtual_balance', 0.0))
            stored_balance = float(data.get(session_id, {}).get('virtual_balance', 0.0))
            
            final_balance = memory_balance
            if memory_balance <= 0.0 and stored_balance > 0.0:
                final_balance = stored_balance
                session.virtual_balance = final_balance
            
            # Rigid 500k Reset if everything is 0
            if final_balance <= 0:
                final_balance = 500000.0
                session.virtual_balance = final_balance

            session_data = {
                "client_id": session.client_id,
                "jwt_token": session.jwt_token,
                "feed_token": session.feed_token,
                "api_key": session.api_key,
                "data_api_key": getattr(session, 'data_api_key', session.api_key),
                "is_paused": getattr(session, 'is_paused', False),
                "watchlist": session.watchlist if session.watchlist is not None else data.get(session_id, {}).get('watchlist', []),
                "alerts": session.alerts if session.alerts is not None else data.get(session_id, {}).get('alerts', []),
                "logs": session.logs[:500] if hasattr(session, 'logs') else [],
                "auto_paper_trade": getattr(session, 'auto_paper_trade', False),
                "auto_live_trade": getattr(session, 'auto_live_trade', False),
                "strategy_mode": getattr(session, 'strategy_mode', 'BOUNCE'),
                "trigger_mode": getattr(session, 'trigger_mode', 'CANDLE_CLOSE'),
                "buffer_pct": getattr(session, 'buffer_pct', 0.45),
                "trade_quantity": getattr(session, 'trade_quantity', 100),
                "trade_capital": getattr(session, 'trade_capital', 0.0),
                "virtual_balance": float(final_balance),
                "paper_trades": session.paper_trades if hasattr(session, 'paper_trades') else [],
                "prev_candle_closes": getattr(session, '_prev_candle_closes', {}),
                "last_activity": datetime.now(timezone.utc).isoformat()
            }

            data[session_id] = session_data
            self._write_all(data)
            self._cache = {}; self._last_loaded = None
            print(f"[OK] Persistence: Session {session_id} saved. Balance: {final_balance}")

    def get_atomic_balance(self, client_id: str) -> float:
        """Fetch the atomic balance with VPS Rigid Default of 500,000"""
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob(f"balances/{client_id}.json")
                if blob.exists():
                    data = json.loads(blob.download_as_string())
                    val = float(data.get('balance', 500000.0))
                    return val if val > 0 else 500000.0
            except: pass
        return 500000.0 # RIGID DEFAULT FOR VPS

    def load_sessions(self) -> Dict: return self._read_all()
    def get_session_by_session_id(self, session_id: str) -> Dict: return self._read_all(force_refresh=True).get(session_id, {})
    
    def get_session_by_client(self, client_id: str) -> Dict:
        data = self._read_all(force_refresh=True)
        client_sessions = [(sid, s_data) for sid, s_data in data.items() if str(s_data.get('client_id', '')).upper() == client_id.upper()]
        if not client_sessions: return {}
        client_sessions.sort(key=lambda x: x[1].get('last_activity', ''), reverse=True)
        return client_sessions[0][1]

    def add_to_trade_history(self, client_id: str, trade: Dict):
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        with self.lock:
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f: history = json.load(f)
                except: pass
            history.append(trade)
            with open(history_file, 'w', encoding='utf-8') as f: json.dump(history[-2000:], f, indent=4, default=str)

    def get_trade_history(self, client_id: str) -> List[Dict]:
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return []

    def get_performance_stats(self, client_id: str, current_balance: float = 500000.0) -> Dict:
        history = self.get_trade_history(client_id)
        if not history: return {"stats": {"win_rate": 0, "total_trades": 0, "net_pnl": 0}, "equity_curve": []}
        closed_trades = [t for t in history if t.get('status') == 'CLOSED']
        net_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        return {"stats": {"total_trades": len(history), "net_pnl": net_pnl, "win_rate": 50}, "equity_curve": []}

persistence_service = PersistenceService()
