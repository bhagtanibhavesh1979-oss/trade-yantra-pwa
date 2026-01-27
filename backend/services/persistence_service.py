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
# On Cloud Run, the filesystem is read-only except for /tmp
# We detect Cloud Run by the presence of K_SERVICE environment variable
if os.environ.get("K_SERVICE"):
    DATA_DIR = "/tmp/data"
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")

SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

class PersistenceService:
    def __init__(self):
        self.lock = threading.RLock()
        self._cache = {}
        self._last_loaded = None
        
        # PRIMARY: Google Cloud Storage (ASIA-SOUTH1 - Mumbai)
        self.bucket_name = "trade-yantra-storage-asia"  # HARDCODED - DO NOT CHANGE
        self.storage_client = None
        self.use_db = False 
        
        try:
            from google.cloud import storage
            self.storage_client = storage.Client()
            print(f"✅ [CLOUD] Persistence active: gs://{self.bucket_name}")
        except Exception as e:
            print(f"⚠️ [CLOUD] Storage init failed: {e}. Using local memory.")

        # Local Cache Directory (used as backup ONLY)
        if not os.environ.get("K_SERVICE"):
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)


    def _read_all(self, force_refresh: bool = False) -> Dict:
        """Fetch all sessions from GCS (Primary Store)"""
        # CRITICAL FIX: Only use cache if NOT force_refresh
        if not force_refresh:
            if self._cache and self._last_loaded:
                if (datetime.now() - self._last_loaded).total_seconds() < 2:
                    return self._cache

        # 1. Fetch from GCS (ALWAYS when force_refresh=True)
        remote_data = None
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob("sessions.json")
                if blob.exists(timeout=2.0):
                    content = blob.download_as_string(timeout=3.0)
                    remote_data = json.loads(content)
                    print(f"📊 [CLOUD] Loaded {len(remote_data)} sessions. Local Cache: {len(self._cache)}")
                else:
                    # File doesn't exist yet, but it's not an error
                    remote_data = {}
            except Exception as e:
                print(f"❌ [CLOUD] Read Error: {e}")
                # CRITICAL: If cloud read fails, return the CACHE, not an empty local map
                if self._cache: return self._cache

        # 2. Local Fallback (Only works on your local laptop)
        local_data = {}
        if not os.environ.get("K_SERVICE") and os.path.exists(SESSIONS_FILE):
             try:
                 with open(SESSIONS_FILE, 'r') as f:
                     local_data = json.load(f)
             except: pass

        # 3. Final Merge (Robust merging to prevent data loss)
        data = {}
        if local_data:
            data.update(local_data)
        if remote_data:
            data.update(remote_data)
        
        # If both failed and we have cache, don't return {}
        if not data and self._cache:
            return self._cache
            
        self._cache = data
        self._last_loaded = datetime.now()
        return data

    def _write_all(self, data: Dict):
        """Save all sessions to GCS (Synchronous for Reliability)"""
        # Always update memory cache first
        with self.lock:
            self._cache = data

        # On Cloud Run, background threads are unreliable. Perform synchronous upload.
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob("sessions.json")
                blob.upload_from_string(
                    json.dumps(data, indent=4, default=str),
                    content_type='application/json'
                )
            except Exception as e:
                print(f"❌ [CLOUD] Upload Error: {e}")
        
        # Local mirror if not in cloud
        if not os.environ.get("K_SERVICE"):
            try:
                with open(SESSIONS_FILE, 'w') as f:
                    json.dump(data, f, indent=4, default=str)
            except: pass

    def save_session(self, session_id: str, session):
        """Save a single session data safely"""
        with self.lock:
            # 1. Force fresh read to get latest data from other instances/GCS
            data = self._read_all(force_refresh=True)
            
            # 2. Build session data
            # Anti-Zero Protection: Prevent fresh memory (0) from wiping stored money.
            memory_balance = getattr(session, 'virtual_balance', 0.0)
            stored_balance = data.get(session_id, {}).get('virtual_balance', 0.0)
            
            final_balance = memory_balance
            if memory_balance == 0.0 and stored_balance > 0.0:
                final_balance = stored_balance
                # Sync back to memory to prevent future overwrites
                session.virtual_balance = final_balance
                print(f"🛡️ [PROTECTION] Prevented 0 overwriting ₹{stored_balance} for {session_id[:8]}")

            session_data = {
                "client_id": session.client_id,
                "jwt_token": session.jwt_token,
                "feed_token": session.feed_token,
                "api_key": session.api_key,
                "is_paused": getattr(session, 'is_paused', False),
                "selected_date": getattr(session, 'selected_date', None),
                "last_activity": datetime.now().isoformat(),
                "watchlist": session.watchlist if session.watchlist else data.get(session_id, {}).get('watchlist', []),
                "alerts": session.alerts if session.alerts else data.get(session_id, {}).get('alerts', []),
                "logs": session.logs[:500] if hasattr(session, 'logs') else [],
                "auto_paper_trade": getattr(session, 'auto_paper_trade', False),
                "strategy_mode": getattr(session, 'strategy_mode', 'BOUNCE'),
                "trigger_mode": getattr(session, 'trigger_mode', 'CANDLE_CLOSE'),
                "buffer_pct": getattr(session, 'buffer_pct', 0.25),
                "virtual_balance": max(500000.0, float(getattr(session, 'virtual_balance', 500000.0))),
                "paper_trades": getattr(session, 'paper_trades', [])[:1000]
            }

            # 3. Write Atomic Balance Backup
            balance = getattr(session, 'virtual_balance', 0.0)
            if balance > 0:
                self._write_atomic_balance(session.client_id, balance)

            # 4. Update the main map and write (Synchronous)
            data[session_id] = session_data
            
            # DEBUG: Log what we're about to save
            print(f"[DEBUG] About to save session {session_id[:8]}...")
            print(f"[DEBUG]   session.virtual_balance = {getattr(session, 'virtual_balance', 'NOT SET')}")
            print(f"[DEBUG]   session_data['virtual_balance'] = {session_data.get('virtual_balance', 'NOT SET')}")
            
            self._write_all(data)
            
            # CRITICAL: Clear cache after write so next read is FRESH
            with self.lock:
                self._cache = {}
                self._last_loaded = None
            
            print(f"[OK] Persistence: Session {session_id} saved")
            print(f"    Balance: ₹{balance} | Watchlist: {len(session_data['watchlist'])} | Alerts: {len(session_data['alerts'])} | Trades: {len(session_data['paper_trades'])}")

    def _write_atomic_balance(self, client_id: str, balance: float):
        """Save balance to a per-client file for ultimate recovery"""
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob(f"balances/{client_id}.json")
                blob.upload_from_string(
                    json.dumps({"client_id": client_id, "balance": balance, "updated_at": datetime.now().isoformat()}),
                    content_type='application/json'
                )
            except: pass

    def get_atomic_balance(self, client_id: str) -> float:
        """Fetch the atomic balance if session balance is missing"""
        if self.storage_client:
            try:
                bucket = self.storage_client.bucket(self.bucket_name)
                blob = bucket.blob(f"balances/{client_id}.json")
                if blob.exists():
                    data = json.loads(blob.download_as_string())
                    val = float(data.get('balance', 500000.0))
                    return val if val > 0 else 500000.0
            except: pass
        return 500000.0  # Rigid Default as requested

    def load_sessions(self) -> Dict:
        """Load all sessions from JSON file"""
        return self._read_all()

    def get_session_by_session_id(self, session_id: str) -> Dict:
        """Get session data for a specific session_id"""
        data = self._read_all(force_refresh=True)
        return data.get(session_id, {})

    def get_session_by_client(self, client_id: str) -> Dict:
        """Get the most recent session data for a specific client_id"""
        data = self._read_all(force_refresh=True)
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
            
            # Add or update trade in history
            found = False
            for i, t in enumerate(history):
                if t.get('id') == trade.get('id'):
                    history[i] = trade
                    found = True
                    break
            
            if not found:
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
        
    def get_performance_stats(self, client_id: str, current_balance: float = 100000.0) -> Dict:
        """Calculate deep performance analytics for a client"""
        history = self.get_trade_history(client_id)
        if not history:
            return {
                "stats": {"win_rate": 0, "total_trades": 0, "net_pnl": 0, "profit_factor": 0},
                "equity_curve": []
            }

        # Sort by closed_at to build equity curve
        closed_trades = [t for t in history if t.get('status') == 'CLOSED']
        closed_trades.sort(key=lambda x: x.get('closed_at', ''))

        stats = {
            "total_trades": len(closed_trades),
            "wins": len([t for t in closed_trades if t.get('pnl', 0) > 0]),
            "losses": len([t for t in closed_trades if t.get('pnl', 0) <= 0]),
            "net_pnl": sum(t.get('pnl', 0) for t in closed_trades),
            "total_profit": sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) > 0),
            "total_loss": abs(sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) < 0)),
        }

        stats["win_rate"] = round((stats["wins"] / stats["total_trades"] * 100), 1) if stats["total_trades"] > 0 else 0
        stats["profit_factor"] = round((stats["total_profit"] / stats["total_loss"]), 2) if stats["total_loss"] > 0 else (stats["total_profit"] if stats["total_profit"] > 0 else 0)

        # Build Equity Curve
        curve = []
        # We estimate the starting balance by subtracting total P&L from current
        running_balance = current_balance - sum(t.get('pnl', 0) for t in closed_trades if t.get('status') == 'CLOSED')
        
        # Point 0: Start
        curve.append({"time": "Start", "balance": round(running_balance, 2)})

        for i, t in enumerate(closed_trades):
            running_balance += t.get('pnl', 0)
            # Use short time format for mobile charts
            try:
                dt = datetime.fromisoformat(t.get('closed_at', ''))
                time_label = dt.strftime('%H:%M') if dt.date() == datetime.now().date() else dt.strftime('%d/%m')
            except:
                time_label = f"T{i+1}"
                
            curve.append({
                "time": time_label,
                "balance": round(running_balance, 2),
                "pnl": round(t.get('pnl', 0), 2),
                "symbol": t.get('symbol')
            })

        return {
            "stats": stats,
            "equity_curve": curve[-30:] # Last 30 points for mobile view
        }

# Global instance
persistence_service = PersistenceService()
