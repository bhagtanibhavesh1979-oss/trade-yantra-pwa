"""
Persistence Service (JSON)
Handles saving and loading session data to/from backend/data/sessions.json
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

class PersistenceService:
    def __init__(self):
        self.lock = threading.RLock()
        self._cache = {}
        self._last_loaded = None
        self.use_db = False 
        
        # Local Cache Directory
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _read_all(self, force_refresh: bool = False) -> Dict:
        """Fetch all sessions from Local File"""
        if not force_refresh:
            if self._cache and self._last_loaded:
                if (datetime.now() - self._last_loaded).total_seconds() < 2:
                    return self._cache

        local_data = {}
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
            except Exception as e:
                print(f"[WARN] [DISK] Primary DB corrupt: {e}. Trying backup...")
        
        if not local_data and os.path.exists(SESSIONS_FILE + ".bak"):
            try:
                with open(SESSIONS_FILE + ".bak", 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                print(f"[OK] [DISK] Restored from backup. Items: {len(local_data)}")
            except: pass

        data = {}
        if local_data:
            data.update(local_data)
        
        if not data and self._cache:
            return self._cache
            
        self._cache = data
        self._last_loaded = datetime.now()
        return data

    def _write_all(self, data: Dict):
        """Save all sessions to Local File"""
        with self.lock:
            self._cache = data

        try:
            if os.path.exists(SESSIONS_FILE):
                import shutil
                backup_file = SESSIONS_FILE + ".bak"
                try:
                    shutil.copy2(SESSIONS_FILE, backup_file)
                except: pass

            temp_file = SESSIONS_FILE + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, default=str)
                f.flush()
                os.fsync(f.fileno())
            
            os.replace(temp_file, SESSIONS_FILE)
        except Exception as e:
            print(f"[ERR] [DISK] Write Error: {e}")

    def save_session(self, session_id: str, session):
        with self.lock:
            data = self._read_all(force_refresh=True)
            
            memory_balance = float(getattr(session, 'virtual_balance', 0.0))
            stored_balance = float(data.get(session_id, {}).get('virtual_balance', 0.0))
            
            final_balance = memory_balance
            if memory_balance == 0.0 and stored_balance > 0.0:
                final_balance = stored_balance
                session.virtual_balance = final_balance
                print(f"[SHIELD] [PROTECTION] Restored balance {stored_balance} for {session_id[:8]}")

            session_data = {
                "client_id": session.client_id,
                "jwt_token": session.jwt_token,
                "feed_token": session.feed_token,
                "refresh_token": getattr(session, 'refresh_token', ''),
                "api_key": session.api_key,
                "data_api_key": getattr(session, 'data_api_key', session.api_key),
                "is_paused": getattr(session, 'is_paused', False),
                "selected_date": getattr(session, 'selected_date', None),
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "watchlist": session.watchlist if session.watchlist is not None else data.get(session_id, {}).get('watchlist', []),
                "alerts": session.alerts if session.alerts is not None else data.get(session_id, {}).get('alerts', []),
                "logs": session.logs[:500] if hasattr(session, 'logs') and session.logs is not None else [],
                "auto_paper_trade": getattr(session, 'auto_paper_trade', False),
                "auto_live_trade": getattr(session, 'auto_live_trade', False),
                "strategy_mode": getattr(session, 'strategy_mode', 'BOUNCE'),
                "trigger_mode": getattr(session, 'trigger_mode', 'CANDLE_CLOSE'),
                "buffer_pct": getattr(session, 'buffer_pct', 0.45),
                "trade_quantity": getattr(session, 'trade_quantity', 100),
                "trade_capital": getattr(session, 'trade_capital', 0.0),
                "global_target": getattr(session, 'global_target', None),
                "global_stop_loss": getattr(session, 'global_stop_loss', None),
                "virtual_balance": float(getattr(session, 'virtual_balance', 500000.0)),
                "paper_trades": session.paper_trades if hasattr(session, 'paper_trades') and session.paper_trades is not None else data.get(session_id, {}).get('paper_trades', []),
                "prev_candle_closes": getattr(session, '_prev_candle_closes', {}),
                "last_auto_square_off": getattr(session, 'last_auto_square_off', '')
            }

            data[session_id] = session_data
            
            print(f"[DEBUG] About to save session {session_id[:8]}...")
            print(f"[DEBUG]   session.virtual_balance = {getattr(session, 'virtual_balance', 'NOT SET')}")
            print(f"[DEBUG]   session_data['virtual_balance'] = {session_data.get('virtual_balance', 'NOT SET')}")
            
            self._write_all(data)
            
            with self.lock:
                self._cache = {}
                self._last_loaded = None
            
            print(f"[OK] Persistence: Session {session_id} saved")
            print(f"    Balance: {balance if 'balance' in locals() else getattr(session, 'virtual_balance', 0.0)} | Watchlist: {len(session_data['watchlist'])} | Alerts: {len(session_data['alerts'])} | Trades: {len(session_data['paper_trades'])}")

    def get_atomic_balance(self, client_id: str) -> float:
        """Fetch the atomic balance if session balance is missing"""
        # Logic removed; return 0 so caller handles initialization logic. Local files do this well. 
        return 0.0

    def load_sessions(self) -> Dict:
        return self._read_all()

    def get_session_by_session_id(self, session_id: str) -> Dict:
        data = self._read_all(force_refresh=True)
        return data.get(session_id, {})

    def get_session_by_client(self, client_id: str) -> Dict:
        data = self._read_all(force_refresh=True)
        client_sessions = [
            (sid, s_data) for sid, s_data in data.items() 
            if str(s_data.get('client_id', '')).upper() == client_id.upper()
        ]
        
        if not client_sessions:
            return {}
            
        client_sessions.sort(key=lambda x: x[1].get('last_activity', ''), reverse=True)
        return client_sessions[0][1]

    def get_latest_session_by_client_id(self, client_id: str) -> Dict:
        return self.get_session_by_client(client_id)

    def cleanup_old_sessions(self, days: int = 7):
        pass

    def add_to_trade_history(self, client_id: str, trade: Dict):
        """Append a closed trade to the permanent history file (Local only)"""
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        
        with self.lock:
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except:
                    history = []
            
            found = False
            for i, t in enumerate(history):
                if t.get('id') == trade.get('id'):
                    history[i] = trade
                    found = True
                    break
            
            if not found:
                history.append(trade)
            
            if len(history) > 2000:
                history = history[-2000:]
                
            try:
                content = json.dumps(history, indent=4, default=str)
                with open(history_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"[ERROR] Failed to save trade history for {client_id}: {e}")

    def get_trade_history(self, client_id: str) -> List[Dict]:
        """Load the permanent history for a client (Local)"""
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def is_recently_traded(self, client_id: str, token: str, seconds: int = 5) -> bool:
        history = self.get_trade_history(client_id)
        if not history: return False
        
        now = datetime.now(timezone.utc)
        token = str(token)
        
        for trade in reversed(history[-10:]):
            if str(trade.get('token')) == token:
                created_at = trade.get('created_at')
                if not created_at: continue
                try:
                    dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                    if (now - dt).total_seconds() < seconds:
                        return True
                except: continue
        return False

    def clear_trade_history(self, client_id: str):
        """Delete identifying history files for a client (Local)"""
        client_id = str(client_id).upper()
        history_file = os.path.join(DATA_DIR, f"history_{client_id}.json")
        
        with self.lock:
            if os.path.exists(history_file):
                try:
                    os.remove(history_file)
                    print(f" [OK] Local history deleted: {history_file}")
                except Exception as e:
                    print(f"[ERR] [ERROR] Local history delete failed: {e}")
        
    def get_performance_stats(self, client_id: str, current_balance: float = 100000.0, extra_trades: List[Dict] = None) -> Dict:
        history = self.get_trade_history(client_id) or []
        
        if extra_trades:
            trades_map = {str(t.get('id')): t for t in history}
            for t in extra_trades:
                trades_map[str(t.get('id'))] = t
            history = list(trades_map.values())

        if not history:
            return {
                "stats": {"win_rate": 0, "total_trades": 0, "net_pnl": 0, "profit_factor": 0},
                "equity_curve": []
            }

        closed_trades = [t for t in history if t.get('status') == 'CLOSED']
        closed_trades.sort(key=lambda x: x.get('closed_at', ''))

        stats = {
            "total_trades": len(history),
            "wins": len([t for t in closed_trades if t.get('pnl', 0) > 0]),
            "losses": len([t for t in closed_trades if t.get('pnl', 0) <= 0]),
            "net_pnl": sum(t.get('pnl', 0) for t in closed_trades),
            "total_profit": sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) > 0),
            "total_loss": abs(sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) < 0)),
        }

        stats["win_rate"] = round((stats["wins"] / stats["total_trades"] * 100), 1) if stats["total_trades"] > 0 else 0
        stats["profit_factor"] = round((stats["total_profit"] / stats["total_loss"]), 2) if stats["total_loss"] > 0 else (stats["total_profit"] if stats["total_profit"] > 0 else 0)

        curve = []
        running_balance = current_balance - sum(t.get('pnl', 0) for t in closed_trades if t.get('status') == 'CLOSED')
        
        curve.append({"time": "Start", "balance": round(running_balance, 2)})

        for i, t in enumerate(closed_trades):
            running_balance += t.get('pnl', 0)
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
            "equity_curve": curve[-30:]
        }

persistence_service = PersistenceService()
