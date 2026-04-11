"""
Session Manager - In-memory session storage
Sessions are cleared on server restart
"""
import uuid
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
import threading
import time
from services.persistence_service import persistence_service

class Session:
    def __init__(self, session_id: str, client_id: str, jwt_token: str, feed_token: str, api_key: str, data_api_key: Optional[str] = None):
        self.session_id = session_id
        self.client_id = client_id.upper()
        self.jwt_token = jwt_token
        self.feed_token = feed_token
        self.api_key = api_key
        self.data_api_key = data_api_key or api_key # Fallback to main key
        self.refresh_token = None
        self.smart_api = None  # Authenticated SmartConnect instance
        # --- CREDENTIALS FOR AUTO DAILY RE-LOGIN ---
        # Stored so the backend can self-heal every morning at 9 AM IST
        self._password = None       # PIN/password
        self._totp_secret = None    # TOTP base32 secret
        self.watchlist = []  # List of {symbol, token, exch_seg, ltp, wc}
        self.alerts = []  # List of {id, symbol, token, condition, price, active}
        self.logs = []  # List of {time, symbol, msg}
        self.paper_trades = [] # List of virtual trade objects
        self.virtual_balance = 1000000.0 # Virtual wallet balance
        self.is_paused = False
        self.auto_paper_trade = False
        self.auto_live_trade = False # Master Switch for Real Money Trading
        self.strategy_mode = 'BOUNCE' # 'BOUNCE' or 'SAR'
        self.trigger_mode = 'CANDLE_CLOSE' # 'CANDLE_CLOSE' or 'INSTANT'
        self.buffer_pct = 0.45 # Default 0.45%
        self.trade_quantity = 100 # Default Quantity
        self.global_target = None
        self.global_stop_loss = None
        self.selected_date = None  # User-selected date for High/Low (YYYY-MM-DD)
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.websocket_clients = []  # List of WebSocket connections
        self.last_auto_square_off = '' # Format: YYYY-MM-DD
        self.market_offset = 0.10 # Default 0.10 INR for Market-to-Limit conversion

    def update_tokens(self, jwt_token: str, feed_token: str, refresh_token: str):
        """Update session tokens and re-init SmartAPI"""
        self.jwt_token = jwt_token
        self.feed_token = feed_token
        self.refresh_token = refresh_token
        if self.smart_api:
            self.smart_api.setAccessToken(jwt_token)
            self.smart_api.setRefreshToken(refresh_token)
        else:
            from SmartApi import SmartConnect
            self.smart_api = SmartConnect(api_key=self.api_key)
            self.smart_api.setAccessToken(jwt_token)
            self.smart_api.setRefreshToken(refresh_token)
        print(f"[REFRESH] [SESSION] Tokens updated for {self.client_id}")

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()
        self._active_saves = set()
        self._pending_saves = set()
        self._load_from_disk()
        self._start_daily_scheduler()

    def _start_daily_scheduler(self):
        """Start background thread that re-logs in all sessions at 9:00 AM IST daily.
        Uses only built-in Python modules (threading + datetime) — no extra packages needed.
        """
        def _seconds_until_next_9am_ist():
            """Calculate seconds until the next 9:00 AM IST (UTC+5:30)."""
            ist_offset = timedelta(hours=5, minutes=30)
            now_ist = datetime.now(timezone.utc) + ist_offset
            target = now_ist.replace(hour=9, minute=0, second=0, microsecond=0)
            if now_ist >= target:
                # Already past 9 AM today — schedule for tomorrow
                target += timedelta(days=1)
            return (target - now_ist).total_seconds()

        def _run_scheduler():
            print("[SCHEDULER] Daily re-login scheduler started. Fires at 09:00 AM IST every day.")
            while True:
                wait_secs = _seconds_until_next_9am_ist()
                hrs = int(wait_secs // 3600)
                mins = int((wait_secs % 3600) // 60)
                print(f"[SCHEDULER] Next auto re-login in {hrs}h {mins}m (at 09:00 AM IST).")
                time.sleep(wait_secs)
                self.daily_relogin_all()

        t = threading.Thread(target=_run_scheduler, daemon=True, name="DailyReloginScheduler")
        t.start()
        print("[SCHEDULER] Background scheduler thread started.")


    def _load_from_disk(self):
        """Load all sessions from disk into memory on startup"""
        print("[REFRESH] [BOOT] Loading sessions from disk...")
        try:
            persistence_service.cleanup_old_sessions()
            all_data = persistence_service._read_all(force_refresh=True)
            
            # --- AUTO-CLEANUP STUCK TRADES ON BOOT ---
            if all_data:
                cleaned_count = 0
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                for sid, s_data in all_data.items():
                    p_trades = s_data.get('paper_trades', [])
                    # PRESERVE TODAY'S TRADES: Only cleanup if trade date < today
                    open_trades = []
                    for t in p_trades:
                        if t.get('status') == 'OPEN':
                            created_at = t.get('created_at', '')
                            # If created_at is today, preserve it
                            if created_at and today_str in created_at:
                                continue
                            open_trades.append(t)
                    
                    if open_trades:
                        open_ids = {t['id'] for t in open_trades}
                        print(f" [BOOT] Found {len(open_trades)} stuck OPEN trades (pre-today) in {sid[:8]}. Closing them...")
                        
                        # Option 2: DELETE (Cleaner for 'stuck' ghosts)
                        s_data['paper_trades'] = [t for t in p_trades if t.get('id') not in open_ids]
                        
                        # Refund Margin (Rough Estimate)
                        refund = sum(float(t.get('entry_price', 0)) * int(t.get('quantity', 0)) * 0.05 for t in open_trades)
                        current_bal = float(s_data.get('virtual_balance', 0))
                        s_data['virtual_balance'] = current_bal + refund
                        cleaned_count += 1
                
                if cleaned_count > 0:
                     print(f" [BOOT] Saving cleaned state for {cleaned_count} sessions...")
                     persistence_service._write_all(all_data)
            # ----------------------------------------
            if all_data:
                # --- GROUP BY CLIENT AND FIND LATEST ---
                latest_sessions = {}
                for sid, s_data in all_data.items():
                    cid = s_data.get('client_id', '').upper()
                    if not cid: continue
                    
                    last_act = s_data.get('last_activity', '')
                    has_alerts = len(s_data.get('alerts', [])) > 0
                    
                    if cid not in latest_sessions:
                        latest_sessions[cid] = (sid, s_data)
                    else:
                        current_best_data = latest_sessions[cid][1]
                        current_best_has_alerts = len(current_best_data.get('alerts', [])) > 0
                        
                        # PRIORITY LOGIC:
                        # 1. If this session has alerts but current best doesn't -> PICK THIS
                        # 2. If both have alerts or both none -> PICK LATEST activity
                        if has_alerts and not current_best_has_alerts:
                            latest_sessions[cid] = (sid, s_data)
                        elif has_alerts == current_best_has_alerts:
                            if last_act > current_best_data.get('last_activity', ''):
                                latest_sessions[cid] = (sid, s_data)
                
                print(f" [BOOT] Found {len(all_data)} sessions on disk. Loading {len(latest_sessions)} unique client sessions.")
                
                for session_id, session_data in latest_sessions.values():
                    try:
                        session = Session(
                            session_id,
                            session_data['client_id'],
                            session_data.get('jwt_token', ''),
                            session_data.get('feed_token', ''),
                            session_data.get('api_key', ''),
                            session_data.get('data_api_key')
                        )
                        session.refresh_token = session_data.get('refresh_token', '')
                        session.watchlist = session_data.get('watchlist', [])
                        session.alerts = session_data.get('alerts', [])
                        session.logs = session_data.get('logs', [])
                        session.paper_trades = session_data.get('paper_trades', [])
                        session.virtual_balance = session_data.get('virtual_balance', 0.0)
                        session.is_paused = session_data.get('is_paused', False)
                        session.auto_paper_trade = session_data.get('auto_paper_trade', False)
                        session.auto_live_trade = session_data.get('auto_live_trade', False)
                        session.strategy_mode = session_data.get('strategy_mode', 'BOUNCE')
                        session.trigger_mode = session_data.get('trigger_mode', 'CANDLE_CLOSE')
                        session.buffer_pct = session_data.get('buffer_pct', 0.45)
                        session.trade_quantity = session_data.get('trade_quantity', 100)
                        session.last_auto_square_off = session_data.get('last_auto_square_off', '')
                        
                        self.sessions[session_id] = session
                        
                        # Re-init SmartAPI and VERIFY TOKEN
                        if session.jwt_token and session.api_key:
                            from SmartApi import SmartConnect
                            from services.angel_service import angel_service
                            
                            try:
                                print(f" [BOOT] Verifying token for {session.client_id}...")
                                smart_api = SmartConnect(api_key=session.api_key)
                                smart_api.setAccessToken(session.jwt_token)
                                smart_api.setRefreshToken(session.refresh_token)
                                smart_api.setUserId(session.client_id)
                                session.smart_api = smart_api
                                
                                # Try a small API call to see if it works
                                profile = smart_api.getProfile(session.refresh_token)
                                if profile and profile.get('status'):
                                    print(f"[OK] [BOOT] Session alive for {session.client_id}")
                                else:
                                    # Use angel_service to get a readable error
                                    err_code = profile.get('errorcode') if profile else 'UNKNOWN'
                                    msg = angel_service.get_error_message(err_code)
                                    print(f"[WARN] [BOOT] Token Status for {session.client_id}: {msg}. Attempting refresh...")
                                    
                                    if self.refresh_session_tokens(session_id):
                                        print(f"[OK] [BOOT] Tokens refreshed for {session.client_id}")
                                        self.sessions[session_id] = session
                                    else:
                                        print(f"[ERR] [BOOT] Refresh failed for {session.client_id}. Removing dead session.")
                                        # Do NOT add to self.sessions
                            except Exception as api_err:
                                err_msg = str(api_err)
                                print(f"[WARN] [BOOT] Token check error for {session.client_id}: {err_msg}. Trying refresh...")
                                if self.refresh_session_tokens(session_id):
                                    print(f"[OK] [BOOT] Recovered {session.client_id} via refresh.")
                                    self.sessions[session_id] = session
                                else:
                                    print(f"[ERR] [BOOT] Could not recover {session.client_id}. Removing.")
                            
                    except Exception as e:
                        print(f"[ERR] [BOOT] Failed to load session {session_id[:8]}: {e}")
                
                print(f"[OK] [BOOT] Loaded {len(self.sessions)} sessions into memory.")
                
                # --- SYNC HISTORY FILES WITH IN-MEMORY STATE ---
                # After boot cleanup strips stuck OPEN trades from sessions.json,
                # we also need to close them in history_*.json to prevent the
                # summary merge from resurrecting ghost OPEN positions.
                try:
                    for session in self.sessions.values():
                        history = persistence_service.get_trade_history(session.client_id) or []
                        in_memory_ids = {t['id'] for t in session.paper_trades}
                        now_iso = datetime.utcnow().isoformat() + "Z"
                        changed = False
                        for t in history:
                            # If trade is OPEN in history, but NOT in current memory session, close it
                            if t.get('status') == 'OPEN' and t['id'] not in in_memory_ids:
                                t['status'] = 'CLOSED'
                                t['exit_price'] = t.get('entry_price')
                                t['pnl'] = 0.0
                                t['closed_at'] = now_iso
                                t['exit_reason'] = 'BOOT_SYNC_CLEANUP'
                                changed = True
                                print(f" [BOOT] History sync: Closed orphan trade {t['id']} ({t.get('symbol')}) from history")
                        if changed:
                            # Write all updates back
                            for t in history:
                                persistence_service.add_to_trade_history(session.client_id, t)
                except Exception as sync_err:
                    print(f"[WARN] [BOOT] History sync error (non-fatal): {sync_err}")
                # -----------------------------------------------
                
            # -----------------------------------------------
                
                # Restore Live Trading Master Switch if ANY session has it enabled
                from services.live_service import live_service
                from services.websocket_manager import ws_manager
                
                has_active_auto = False
                for s in self.sessions.values():
                    if getattr(s, 'auto_live_trade', False):
                        live_service.toggle_live_trading(True)
                        print("[WARN] [BOOT] Live Trading Master Switch RESTORED to ON")
                    
                    if getattr(s, 'auto_live_trade', False) or getattr(s, 'auto_paper_trade', False):
                        has_active_auto = True
                
                # If any active session exists, kickstart the heartbeat for background strategy
                if has_active_auto:
                    print("[BOOT] Active auto-trading sessions found. Kickstarting Strategy Heartbeat...")
                    ws_manager.ensure_heartbeat()
            else:
                print("[INFO] [BOOT] No sessions found on disk.")
        except Exception as e:
            print(f"[ERR] [BOOT] Critical error loading sessions: {e}")
        
        print("Session manager initialized")

    def save_session(self, session_id: str):
        """Saves session data to JSON safely in background"""
        session = self.get_session(session_id)
        if not session:
            return
            
        try:
            persistence_service.save_session(session_id, session)
        except Exception as e:
            print(f"[ERROR] Save FAILED for session {session_id}: {e}")

    def create_session(self, client_id: str, jwt_token: str, feed_token: str, api_key: str, data_api_key: Optional[str] = None) -> Session:
        """Create a new session and restore user data if available"""
        client_id = client_id.upper()
        
        # 0. Clean up any existing in-memory session for this client
        # This prevents 429 Connection Limit Exceeded by ensuring only ONE 
        # WebSocket is active per account.
        with self.lock:
            existing_sids = [sid for sid, s in self.sessions.items() if s.client_id == client_id]
        
        for old_sid in existing_sids:
            print(f" [SESSION] [PURGE] Wiping old Zombie session {old_sid[:8]} for client {client_id}")
            self.stop_session_automation(old_sid) # NEW: Explicitly stop threads
            self.delete_session(old_sid)

        existing_data = persistence_service.get_session_by_client(client_id)
        
        session_id = str(uuid.uuid4())
        session = Session(session_id, client_id, jwt_token, feed_token, api_key, data_api_key)
        session.refresh_token = existing_data.get('refresh_token') if existing_data else None
        
        if existing_data:
            print(f"[OK] Restoring data for client {client_id} from JSON")
            session.watchlist = existing_data.get('watchlist', [])
            session.alerts = existing_data.get('alerts', [])
            session.logs = existing_data.get('logs', [])
            session.paper_trades = existing_data.get('paper_trades', [])
            session.virtual_balance = existing_data.get('virtual_balance', 0.0)
            
            # Atomic Recovery Fallback
            if not session.virtual_balance or session.virtual_balance == 0:
                atomic_bal = persistence_service.get_atomic_balance(client_id)
                session.virtual_balance = atomic_bal
                print(f"[MONEY] [LOGIN] Rigid balance {session.virtual_balance} enforced for {client_id}")

            session.is_paused = existing_data.get('is_paused', False)
            session.auto_paper_trade = existing_data.get('auto_paper_trade', False)
            session.auto_live_trade = existing_data.get('auto_live_trade', False)
            session.strategy_mode = existing_data.get('strategy_mode', 'BOUNCE')
            session.trigger_mode = existing_data.get('trigger_mode', 'CANDLE_CLOSE')
            session.buffer_pct = existing_data.get('buffer_pct', 0.45)
            session.trade_quantity = existing_data.get('trade_quantity', 100)
            session.trade_capital = existing_data.get('trade_capital', 0.0)
            session.last_auto_square_off = existing_data.get('last_auto_square_off', '')
            session._prev_candle_closes = existing_data.get('prev_candle_closes', {})
            print(f"[OK] Restored {len(session.watchlist)} watchlist items, {len(session.alerts)} alerts, {len(session.paper_trades)} paper trades, Balance: {session.virtual_balance}")
        
        with self.lock:
            self.sessions[session_id] = session
        
        self.save_session(session_id)
        return session

    def get_session(self, session_id: str, client_id: Optional[str] = None) -> Optional[Session]:
        """Get session by ID, restore from JSON if not in memory"""
        with self.lock:
            # 1. Check Memory FIRST
            session = self.sessions.get(session_id)
            if session:
                session.last_activity = datetime.now()
                return session
        
        # 2. HEALING: If not in memory, we MUST try to restore from JSON/GCS
        print(f"[RECOVERY] Session {session_id} not in memory. Searching disk... (CID: {client_id})")
        session_data = {}
        
        # A. Try by Session ID
        session_data = persistence_service.get_session_by_session_id(session_id)
        
        # B. If session_id failed but we have client_id, try by Client ID
        if not session_data and client_id:
            print(f"[RECOVERY] Session ID lookup failed. Trying Client ID heal for {client_id}...")
            session_data = persistence_service.get_latest_session_by_client_id(client_id)
            
        if session_data:
            print(f"[OK] Recovered session for client {session_data.get('client_id')}")
            session = Session(
                session_id,
                session_data['client_id'],
                session_data.get('jwt_token', ''),
                session_data.get('feed_token', ''),
                session_data.get('api_key', ''),
                session_data.get('data_api_key')
            )
            session.refresh_token = session_data.get('refresh_token', '')
            session.watchlist = session_data.get('watchlist', [])
            session.alerts = session_data.get('alerts', [])
            session.logs = session_data.get('logs', [])
            session.paper_trades = session_data.get('paper_trades', [])
            session.virtual_balance = session_data.get('virtual_balance', 0.0)
            session._prev_candle_closes = session_data.get('prev_candle_closes', {})
            if not session.virtual_balance or session.virtual_balance == 0:
                # Ultimate fallback to atomic per-client balance file
                atomic_bal = persistence_service.get_atomic_balance(session.client_id)
                session.virtual_balance = atomic_bal
                print(f"[MONEY] [RESTORED] Rigid balance {session.virtual_balance} enforced for {session.client_id}")

            session.is_paused = session_data.get('is_paused', False)
            session.auto_paper_trade = session_data.get('auto_paper_trade', False)
            session.auto_live_trade = session_data.get('auto_live_trade', False)
            session.strategy_mode = session_data.get('strategy_mode', 'BOUNCE')
            session.trigger_mode = session_data.get('trigger_mode', 'CANDLE_CLOSE')
            session.buffer_pct = session_data.get('buffer_pct', 0.45)
            session.trade_quantity = session_data.get('trade_quantity', 100)
            session.trade_capital = session_data.get('trade_capital', 0.0)
            session.last_activity = datetime.now()
            
            with self.lock:
                self.sessions[session_id] = session
            
            # Re-initialize SmartAPI
            if session.jwt_token and session.api_key and not session.smart_api:
                from SmartApi import SmartConnect
                from services.angel_service import angel_service
                try:
                    smart_api = SmartConnect(api_key=session.api_key)
                    smart_api.setAccessToken(session.jwt_token)
                    smart_api.setRefreshToken(session.refresh_token)
                    smart_api.setUserId(session.client_id)
                    session.smart_api = smart_api
                    
                    # Verify on recovery
                    profile = smart_api.getProfile(session.refresh_token)
                    if not profile or not profile.get('status'):
                        print(f"[WARN] [RECOVERY] Profile check failed for {session.client_id}. Refreshing...")
                        self.refresh_session_tokens(session_id)
                    else:
                        print(f"[OK] SmartAPI re-initialized for {session.client_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to re-initialize SmartAPI: {e}")

            # --- CRITICAL RECOVERY: Restart WebSocket Stream ---
            # If we recovered from disk, the background data flow is dead.
            # We must restart it immediately so strategy doesn't skip this session.
            # We add a small delay to let any previous process release its socket.
            from services.websocket_manager import ws_manager
            try:
                print(f"[RECOVERY] [OK] Delaying 3s for connection stability...")
                time.sleep(3)
                print(f"[RECOVERY] [OK] Triggering background WebSocket restart for {session.client_id}...")
                ws_manager.start_websocket(session)
            except Exception as wse:
                print(f"[ERR] [RECOVERY] Failed to restart WebSocket for {session.client_id}: {wse}")

            return session
        
        return None

    def refresh_session_tokens(self, session_id: str) -> bool:
        """Attempt to refresh tokens. Falls back to full re-login if refresh fails."""
        session = self.get_session(session_id)
        if not session:
            return False

        from services.angel_service import angel_service
        from SmartApi import SmartConnect

        # --- STEP 1: Try token refresh (fast path) ---
        if session.refresh_token:
            print(f"[REFRESH] Attempting token refresh for {session.client_id}...")
            try:
                api = session.smart_api
                if not api:
                    api = SmartConnect(api_key=session.api_key)
                    api.setAccessToken(session.jwt_token)
                    api.setRefreshToken(session.refresh_token)

                new_tokens = angel_service.refresh_access_token(api, session.refresh_token)
                if new_tokens:
                    session.update_tokens(
                        jwt_token=new_tokens['jwt_token'],
                        feed_token=new_tokens['feed_token'],
                        refresh_token=new_tokens['refresh_token']
                    )
                    self.save_session(session_id)
                    print(f"[OK] [REFRESH] Tokens renewed for {session.client_id}")
                    return True
                else:
                    print(f"[WARN] [REFRESH] Token refresh returned empty for {session.client_id}. Trying full re-login...")
            except Exception as e:
                print(f"[WARN] [REFRESH] Refresh error for {session.client_id}: {e}. Trying full re-login...")

        # --- STEP 2: Full re-login using stored credentials (safe fallback) ---
        if session._password and session._totp_secret:
            print(f"[REFRESH] [RELOGIN] Attempting full re-login for {session.client_id}...")
            try:
                success, message, smart_api, tokens = angel_service.login(
                    session.api_key,
                    session.client_id,
                    session._password,
                    session._totp_secret
                )
                if success and tokens:
                    session.smart_api = smart_api
                    session.update_tokens(
                        jwt_token=tokens['jwt_token'],
                        feed_token=tokens['feed_token'],
                        refresh_token=tokens['refresh_token']
                    )
                    self.save_session(session_id)
                    print(f"[OK] [RELOGIN] Full re-login successful for {session.client_id}")
                    return True
                else:
                    print(f"[ERR] [RELOGIN] Re-login failed for {session.client_id}: {message}")
            except Exception as e:
                print(f"[ERR] [RELOGIN] Re-login crashed for {session.client_id}: {e}")
        else:
            print(f"[ERR] [REFRESH] No credentials stored for {session.client_id}. Cannot auto re-login. User must log in manually.")

        return False

    def daily_relogin_all(self):
        """Called automatically at 9:00 AM IST to refresh all sessions before market opens."""
        print("[SCHEDULER] [DAILY] 9:00 AM IST - Running daily re-login for all sessions...")
        sessions_copy = self.get_all_sessions()
        success_count = 0
        for session_id, session in sessions_copy.items():
            if session._password and session._totp_secret:
                print(f"[SCHEDULER] Re-logging in {session.client_id}...")
                ok = self.refresh_session_tokens(session_id)
                if ok:
                    success_count += 1
                    print(f"[SCHEDULER] [OK] {session.client_id} re-logged in successfully.")
                else:
                    print(f"[SCHEDULER] [ERR] {session.client_id} re-login failed. Manual login required.")
            else:
                print(f"[SCHEDULER] [SKIP] {session.client_id} — no stored credentials (login once manually to enable auto re-login).")
        print(f"[SCHEDULER] [DAILY] Done. {success_count}/{len(sessions_copy)} sessions refreshed.")

    def stop_session_automation(self, session_id: str):
        """Explicitly stop background tasks for a session without deleting data"""
        from services.websocket_manager import ws_manager
        ws_manager.stop_websocket(session_id)
        print(f" [SESSION] [AUTO-STOP] Stopped automation for {session_id[:8]}")

    def delete_session(self, session_id: str) -> bool:
        """Delete a session - Clears all background tasks"""
        # Ensure WebSocket is closed before deleting session
        # This prevents 429 "Connection Limit Exceeded" errors
        self.stop_session_automation(session_id)
        
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                print(f" [SESSION] Deleted and memory cleared for {session_id[:8]}")
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
