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
    """
    Check alerts for a given stock and trigger if conditions are met.
    This runs on the backend to ensure logs are created even if UI is disconnected.
    """
    from services.session_manager import session_manager
    from services.alert_service import check_alert_trigger, create_alert_log
    
    session = session_manager.get_session(session_id)
    if not session or session.is_paused:
        return

    triggered_alerts = []
    for alert in list(session.alerts):
        if str(alert['token']) == str(stock['token']) and alert.get('active', True):
            if check_alert_trigger(alert, stock):
                # Triggered!
                print(f"🔔 ALERT TRIGGERED: {stock['symbol']} hit {alert['price']} ({alert['condition']}) at LTP: {stock['ltp']}")
                log_entry = create_alert_log(stock, alert)
                session.logs.insert(0, log_entry)
                session.alerts.remove(alert)
                triggered_alerts.append({"alert": alert, "log": log_entry})
                
    if triggered_alerts:
        # Save session immediately so logs and alert removals persist
        session_manager.save_session(session_id)
        
        # Broadcast to all connected WebSockets for this session
        from services.websocket_manager import ws_manager
        for triggered in triggered_alerts:
            ws_manager.broadcast_callbacks[session_id](session_id, {
                "type": "alert_triggered",
                "alert": triggered['alert'],
                "log": triggered['log']
            })

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, SmartWebSocketV2] = {}  # session_id -> websocket
        self.token_maps: Dict[str, Dict] = {}  # session_id -> {token -> stock_data}
        self.broadcast_callbacks: Dict[str, Callable] = {}  # session_id -> callback
        self.lock = threading.Lock()
        self.heartbeat_thread = None
        self.running = True

    def _start_heartbeat(self):
        """
        Sends a ping every 20 seconds to keep Cloud Run and Mobile connections alive
        Enhanced with error handling and automatic restart on failure
        """
        consecutive_errors = 0
        max_errors = 5
        
        while self.running:
            try:
                # HEARTBEAT increased to 5s for Cloud Run/Mobile stability
                time.sleep(5)
                with self.lock:
                    active_sessions = list(self.broadcast_callbacks.items())
                    
                if active_sessions:
                    print(f"💓 Heartbeat: {len(active_sessions)} active WebSocket connections")
                    
                for session_id, callback in active_sessions:
                    try:
                        # Send a tiny ping message
                        callback(session_id, {"type": "ping", "timestamp": time.time()})
                        consecutive_errors = 0  # Reset on success
                    except Exception as e:
                        consecutive_errors += 1
                        print(f"⚠️ Heartbeat failed for {session_id}: {e}")
                        if consecutive_errors >= max_errors:
                            print(f"❌ Too many heartbeat failures ({consecutive_errors}), cleaning up session {session_id}")
                            with self.lock:
                                if session_id in self.broadcast_callbacks:
                                    del self.broadcast_callbacks[session_id]
                            consecutive_errors = 0
                            
            except Exception as e:
                print(f"❌ Heartbeat thread error: {e}")
                time.sleep(5)  # Wait a bit before retrying

    def start_websocket(self, session_id: str, jwt_token: str, api_key: str, 
                       client_id: str, feed_token: str, watchlist: List[Dict],
                       broadcast_callback: Callable):
        
        # Start heartbeat thread if not running
        if self.heartbeat_thread is None:
            self.heartbeat_thread = threading.Thread(target=self._start_heartbeat, daemon=True)
            self.heartbeat_thread.start()

        try:
            sws = SmartWebSocketV2(jwt_token, api_key, client_id, feed_token)
        except Exception as e:
            print(f"WebSocket Init Error for {session_id}: {e}")
            return False

        token_map = {str(s['token']): s for s in watchlist}
        
        with self.lock:
            self.connections[session_id] = sws
            self.token_maps[session_id] = token_map
            self.broadcast_callbacks[session_id] = broadcast_callback

        def on_data(wsapp, message):
            # DYNAMIC LOOKUP: Always get the latest callback for this session
            # This allows the stream to survive cross-tab refreshes
            def _get_callback():
                with self.lock:
                    return self.broadcast_callbacks.get(session_id)

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
                                callback(session_id, {
                                    'type': 'price_update',
                                    'data': {'token': str(token), 'symbol': stock['symbol'], 'ltp': stock['ltp']}
                                })
                
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
                        callback(session_id, {
                            'type': 'price_update',
                            'data': {'token': str(token), 'symbol': stock['symbol'], 'ltp': real_price}
                        })
            except Exception as e:
                pass

        def on_open(wsapp):
            print(f"WebSocket Connected for {session_id}")
            with self.lock:
                callback = self.broadcast_callbacks.get(session_id)
            if callback:
                callback(session_id, {'type': 'status', 'data': {'status': 'CONNECTED'}})
            
            # Subscribe to Watchlist
            token_list_str = [str(item['token']) for item in watchlist]
            
            # AUTO-SUBSCRIBE MAJOR INDICES (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)
            # This ensures they update in real-time without constant polling
            indices_tokens = ["99926000", "99926009", "99926012", "99919000"]
            for t in indices_tokens:
                if t not in token_list_str:
                    token_list_str.append(t)
                    # Add to token_map so price updates are recognized
                    if t not in token_map:
                        symbol = "NIFTY 50" if t == "99926000" else \
                                 "NIFTY BANK" if t == "99926009" else \
                                 "NIFTY FIN SERVICE" if t == "99926012" else \
                                 "SENSEX"
                        token_map[t] = {"symbol": symbol, "token": t, "ltp": 0}

            if token_list_str:
                sws.subscribe("watchlist", 3, [{"exchangeType": 1, "tokens": token_list_str}])

        def on_close(wsapp, code, reason):
            print(f"WebSocket Closed for {session_id}")
            broadcast_callback(session_id, {'type': 'status', 'data': {'status': 'DISCONNECTED'}})

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_close = on_close
        
        threading.Thread(target=sws.connect, daemon=True).start()
        return True

    def subscribe_token(self, session_id: str, token: str, stock_data: dict):
        """Add a single token to an existing WebSocket subscription"""
        with self.lock:
            sws = self.connections.get(session_id)
            token_map = self.token_maps.get(session_id)
            if sws and token_map is not None:
                token_map[str(token)] = stock_data
                try:
                    sws.subscribe("watchlist", 3, [{"exchangeType": 1, "tokens": [str(token)]}])
                    print(f"✅ Subscribed to new token: {token} for session {session_id}")
                    return True
                except Exception as e:
                    print(f"❌ Failed to subscribe to token {token}: {e}")
        return False

    def unsubscribe_token(self, session_id: str, token: str):
        """Remove a token from subscription"""
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