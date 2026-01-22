"""
WebSocket Manager - Handles Angel One SmartAPI WebSocket
Maintained with Heartbeat for Google Cloud Run & Mobile stability
"""
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import threading
import struct
import asyncio
import json
import time
from typing import Dict, List, Callable, Optional
import datetime

def check_and_trigger_alerts(session_id: str, stock: dict):
    from services.session_manager import session_manager
    from services.alert_service import check_alert_trigger, create_alert_log
    
    session = session_manager.get_session(session_id)
    if not session or session.is_paused:
        return

    triggered_alerts = []
    # Make a copy to iterate safely
    active_alerts = list(session.alerts)
    
    for alert in active_alerts:
        if str(alert['token']) == str(stock['token']) and alert.get('active', True):
            if check_alert_trigger(alert, stock):
                log_entry = create_alert_log(stock, alert)
                session.logs.insert(0, log_entry)
                session.alerts.remove(alert)
                triggered_alerts.append({"alert": alert, "log": log_entry})
                
    if triggered_alerts:
        if session.auto_paper_trade:
            from services.paper_service import paper_service
            
            # --- Helper to calculate Diff ---
            # We use both remaining active session.alerts AND the triggered ones to find context
            def calculate_diff_and_target(trigger_price, trigger_type, all_alerts):
                diff = 0.0
                
                # 1. Try to find diff from High/Low
                # We need to parse types to find pairs
                # Types: AUTO_S1...S6, AUTO_R1...R6, AUTO_HIGH, AUTO_LOW
                
                # Simplify: Just group by type
                levels = {}
                for a in all_alerts:
                    if str(a['token']) == str(stock['token']) and str(a.get('type','')).startswith('AUTO_'):
                        levels[a['type']] = a['price']
                
                # Add current trigger if missing (it implies we know its price)
                levels[trigger_type] = trigger_price

                # Try to calculate Diff
                if 'AUTO_HIGH' in levels and 'AUTO_LOW' in levels:
                    diff = (levels['AUTO_HIGH'] - levels['AUTO_LOW']) / 2.0
                elif 'AUTO_R1' in levels and 'AUTO_HIGH' in levels:
                    diff = levels['AUTO_R1'] - levels['AUTO_HIGH']
                elif 'AUTO_LOW' in levels and 'AUTO_S1' in levels:
                    diff = levels['AUTO_LOW'] - levels['AUTO_S1']
                elif 'AUTO_R2' in levels and 'AUTO_R1' in levels:
                    diff = levels['AUTO_R2'] - levels['AUTO_R1']
                elif 'AUTO_S1' in levels and 'AUTO_S2' in levels:
                    diff = levels['AUTO_S1'] - levels['AUTO_S2']
                
                if diff <= 0: return None
                
                # Calculate Target
                # S(N) -> +Diff
                # LOW -> +2*Diff
                # HIGH -> -2*Diff
                # R(N) -> -Diff
                
                if 'AUTO_S' in trigger_type: return trigger_price + diff
                if 'AUTO_R' in trigger_type: return trigger_price - diff
                if trigger_type == 'AUTO_LOW': return trigger_price + (2 * diff)
                if trigger_type == 'AUTO_HIGH': return trigger_price - (2 * diff)
                
                return None

            # Collect all known alerts for this token (Active + Triggered)
            all_known_alerts = list(session.alerts) + [t['alert'] for t in triggered_alerts]

            for triggered in triggered_alerts:
                alert = triggered['alert']
                side = None
                alert_type = str(alert.get('type', '')).upper()
                
                # --- Side Determination ---
                if any(x in alert_type for x in ['LOW', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6']):
                    side = 'BUY'
                elif any(x in alert_type for x in ['HIGH', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']):
                    side = 'SELL'
                if not side:
                    if alert.get('condition') == 'BELOW': side = 'BUY'
                    elif alert.get('condition') == 'ABOVE': side = 'SELL'
                
                if side:
                    # Determine Target
                    target_price = None
                    if alert_type.startswith('AUTO_'):
                        target_price = calculate_diff_and_target(alert['price'], alert_type, all_known_alerts)
                        if target_price:
                            print(f"[AUTO] Calculated Target for {stock['symbol']} ({alert_type}): {target_price:.2f}")

                    paper_service.create_virtual_trade(session_id, stock, side, alert_type, target_price=target_price)

        session_manager.save_session(session_id)
        from services.websocket_manager import ws_manager
        paper_trades_data = getattr(session, 'paper_trades', [])
        for triggered in triggered_alerts:
            ws_manager.broadcast_callbacks[session_id](session_id, {
                "type": "alert_triggered",
                "data": {
                    "alert": triggered['alert'],
                    "log": triggered['log'],
                    "paper_trades": paper_trades_data
                }
            })

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, SmartWebSocketV2] = {}
        self.token_maps: Dict[str, Dict] = {}
        self.broadcast_callbacks: Dict[str, Callable] = {}
        self.lock = threading.Lock()
        self.heartbeat_thread = None
        self.running = True

    def _start_heartbeat(self):
        """Send heartbeats to keep connections alive"""
        consecutive_errors = 0
        max_errors = 10  # Increased from 5 to be more lenient
        while self.running:
            try:
                time.sleep(10)  # Heartbeat every 10 seconds
                
                # 1. Send Heartbeats
                with self.lock:
                    active_sessions = list(self.broadcast_callbacks.items())
                
                for session_id, callback in active_sessions:
                    try:
                        callback(session_id, {"type": "heartbeat", "data": {"timestamp": time.time()}})
                        consecutive_errors = 0
                    except Exception as e:
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            print(f"[WARN] Removing stale session {session_id} after {max_errors} consecutive errors")
                            with self.lock:
                                if session_id in self.broadcast_callbacks:
                                    del self.broadcast_callbacks[session_id]
                            consecutive_errors = 0
            
                # 2. Auto-Square Off Check (Run periodically outside the broadcast loop)
                # Safely copy data needed to check logic without holding lock during execution
                session_tokens_copy = {}
                try:
                    with self.lock:
                        session_ids = list(self.token_maps.keys())
                        for sid in session_ids:
                            # Shallow copy of the token map just for square off checking
                            session_tokens_copy[sid] = self.token_maps[sid].copy()
                except Exception:
                    pass

                # Check square off for each session without holding WS lock
                # usage of paper_service here is now safe from deadlock with ws_manager.lock
                if session_tokens_copy:
                    try:
                        from services.paper_service import paper_service
                        for sid, tokens in session_tokens_copy.items():
                            if tokens:
                                paper_service.check_and_square_off(sid, tokens)
                    except Exception as e:
                        print(f"[ERROR] Auto-Square off check failed: {e}")

            except Exception as e:
                print(f"[ERROR] Heartbeat thread exception: {e}")
                time.sleep(10)  # Match the normal sleep interval

    def start_websocket(self, session_id: str, jwt_token: str, api_key: str, 
                       client_id: str, feed_token: str, watchlist: List[Dict],
                       broadcast_callback: Callable):
        if self.heartbeat_thread is None:
            self.heartbeat_thread = threading.Thread(target=self._start_heartbeat, daemon=True)
            self.heartbeat_thread.start()

        try:
            sws = SmartWebSocketV2(jwt_token, api_key, client_id, feed_token)
        except:
            return False

        token_map = {str(s['token']): s for s in watchlist}
        with self.lock:
            self.connections[session_id] = sws
            self.token_maps[session_id] = token_map
            self.broadcast_callbacks[session_id] = broadcast_callback

        def _get_callback():
            with self.lock:
                return self.broadcast_callbacks.get(session_id)

        def _broadcast_price(callback, token_id, symbol, current_ltp):
            from services.session_manager import session_manager
            session = session_manager.get_session(session_id)
            paper_trades_data = []
            if session and getattr(session, 'paper_trades', []):
                from services.paper_service import paper_service
                paper_service.update_live_pnl(session_id, token_map)
                paper_trades_data = session.paper_trades
                
            callback(session_id, {
                'type': 'price_update',
                'data': {
                    'token': str(token_id), 'symbol': symbol, 'ltp': current_ltp, 'paper_trades': paper_trades_data
                }
            })

        def on_data(wsapp, message):
            try:
                callback = _get_callback()
                if not callback: return

                if isinstance(message, (list, dict)):
                    if isinstance(message, dict): message = [message]
                    for tick in message:
                        token = tick.get('token') or tick.get('tk')
                        raw_price = tick.get('last_traded_price') or tick.get('ltp') or tick.get('c')
                        if token and raw_price is not None:
                            stock = token_map.get(str(token))
                            if stock:
                                stock['ltp'] = float(raw_price) / 100.0 if 'last_traded_price' in tick else float(raw_price)
                                check_and_trigger_alerts(session_id, stock)
                                _broadcast_price(callback, str(token), stock['symbol'], stock['ltp'])
                
                elif isinstance(message, bytes) and len(message) > 50:
                    token_bytes = message[2:27]
                    token = token_bytes.replace(b'\x00', b'').decode('utf-8')
                    ltp_bytes = message[43:51]
                    ltp_paise = struct.unpack('<q', ltp_bytes)[0]
                    real_price = ltp_paise / 100.0
                    stock = token_map.get(str(token))
                    if stock:
                        stock['ltp'] = real_price
                        check_and_trigger_alerts(session_id, stock)
                        _broadcast_price(callback, str(token), stock['symbol'], real_price)
            except: pass

        def on_open(wsapp):
            with self.lock:
                callback = self.broadcast_callbacks.get(session_id)
            if callback:
                callback(session_id, {'type': 'status', 'data': {'status': 'CONNECTED'}})
            
            auto_indices = {
                "1": ["99926000", "99926009", "99926012", "99926013", "99926023", "99926003", "99926011", "99926015", "99926024", "99926010"],
                "3": ["99919000"]
            }
            exchange_tokens = {"1": [], "3": []}
            for stock in watchlist:
                exch = str(stock.get('exch_seg', 'NSE')).upper()
                exch_type = "3" if "BSE" in exch else "1"
                exchange_tokens[exch_type].append(str(stock['token']))
            
            watchlist_tokens = [str(s['token']) for s in watchlist]
            for etype, tokens in auto_indices.items():
                for t in tokens:
                    if t not in watchlist_tokens:
                        exchange_tokens[etype].append(t)
                        if t not in token_map:
                            symbol = "INDEX"
                            token_map[t] = {"symbol": symbol, "token": t, "ltp": 0}

            for etype, tokens in exchange_tokens.items():
                if tokens:
                    try:
                        sws.subscribe("watchlist", 3, [{"exchangeType": int(etype), "tokens": tokens}])
                    except: pass

        def on_close(wsapp, code, reason):
            broadcast_callback(session_id, {'type': 'status', 'data': {'status': 'DISCONNECTED'}})

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_close = on_close
        threading.Thread(target=sws.connect, daemon=True).start()
        return True

    def subscribe_token(self, session_id: str, token: str, stock_data: dict):
        with self.lock:
            sws = self.connections.get(session_id)
            token_map = self.token_maps.get(session_id)
            if sws and token_map is not None:
                token_map[str(token)] = stock_data
                exch = str(stock_data.get('exch_seg', 'NSE')).upper()
                exch_type = 3 if "BSE" in exch else 1
                try:
                    sws.subscribe("watchlist", 3, [{"exchangeType": exch_type, "tokens": [str(token)]}])
                    return True
                except: pass
        return False

    def unsubscribe_token(self, session_id: str, token: str):
        with self.lock:
            sws = self.connections.get(session_id)
            token_map = self.token_maps.get(session_id)
            if sws and token_map:
                if str(token) in token_map:
                    del token_map[str(token)]
                    try:
                        sws.unsubscribe("watchlist", 3, [{"exchangeType": 1, "tokens": [str(token)]}])
                        return True
                    except: pass
        return False

    def stop_websocket(self, session_id: str):
        with self.lock:
            if session_id in self.connections:
                try:
                    self.connections[session_id].close()
                except: pass
                del self.connections[session_id]
                del self.token_maps[session_id]
                del self.broadcast_callbacks[session_id]

    def stop_all(self):
        self.running = False
        with self.lock:
            self.connections.clear()
            self.token_maps.clear()
            self.broadcast_callbacks.clear()

ws_manager = WebSocketManager()