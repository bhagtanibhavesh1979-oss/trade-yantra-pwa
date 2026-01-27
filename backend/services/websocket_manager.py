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
    trigger_mode = getattr(session, 'trigger_mode', 'CANDLE_CLOSE')
    
    for alert in active_alerts:
        if str(alert['token']) == str(stock['token']) and alert.get('active', True):
            # NEW: If Candle Close mode, ignore AUTO_ alerts in this Tick loop
            # This keeps them alive for the _process_candle_trades loop
            alert_type = str(alert.get('type', '')).upper()
            if alert_type.startswith('AUTO_') and trigger_mode == 'CANDLE_CLOSE':
                continue

            if check_alert_trigger(alert, stock):
                log_entry = create_alert_log(stock, alert)
                session.logs.insert(0, log_entry)
                session.alerts.remove(alert)
                triggered_alerts.append({"alert": alert, "log": log_entry})
                
    if triggered_alerts:
        from services.websocket_manager import ws_manager
        from services.paper_service import paper_service
        
        if session.auto_paper_trade:
            # --- Trigger Mode Check ---
            trigger_mode = getattr(session, 'trigger_mode', 'CANDLE_CLOSE')
            
            # Helper to calculate Diff & Target
            def calculate_diff_and_target(trigger_price, trigger_type, all_alerts):
                diff = 0.0
                levels = {}
                for a in all_alerts:
                    if str(a['token']) == str(stock['token']) and str(a.get('type','')).startswith('AUTO_'):
                        levels[a['type']] = a['price']
                levels[trigger_type] = trigger_price

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
                
                # Logic Pattern Check
                mode = getattr(session, 'strategy_mode', 'BOUNCE')
                
                if mode == 'BOUNCE':
                    # Reversal targets
                    if 'AUTO_S' in trigger_type: return trigger_price + diff
                    if 'AUTO_R' in trigger_type: return trigger_price - diff
                    if trigger_type == 'AUTO_LOW': return trigger_price + (2 * diff)
                    if trigger_type == 'AUTO_HIGH': return trigger_price - (2 * diff)
                else:
                    # SAR Momentum targets (Follow the trend)
                    if 'AUTO_S' in trigger_type: return trigger_price - diff
                    if 'AUTO_R' in trigger_type: return trigger_price + diff
                    if trigger_type == 'AUTO_LOW': return trigger_price - (2 * diff)
                    if trigger_type == 'AUTO_HIGH': return trigger_price + (2 * diff)
                return None

            all_known_alerts = list(session.alerts) + [t['alert'] for t in triggered_alerts]

            for triggered in triggered_alerts:
                alert = triggered['alert']
                alert_type = str(alert.get('type', '')).upper()
                
                if trigger_mode == 'CANDLE_CLOSE' and alert_type.startswith('AUTO_'):
                    continue

                side = None
                mode = getattr(session, 'strategy_mode', 'BOUNCE')
                if mode == 'BOUNCE':
                    if any(x in alert_type for x in ['LOW', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6']): side = 'BUY'
                    elif any(x in alert_type for x in ['HIGH', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']): side = 'SELL'
                else:
                    if any(x in alert_type for x in ['LOW', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6']): side = 'SELL'
                    elif any(x in alert_type for x in ['HIGH', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']): side = 'BUY'

                if side:
                    target_price = calculate_diff_and_target(alert['price'], alert_type, all_known_alerts)
                    paper_service.create_virtual_trade(session_id, stock, side, alert_type, target_price=target_price)

        session_manager.save_session(session_id)
        
        # Broadcast the update
        paper_trades_data = getattr(session, 'paper_trades', [])
        for triggered in triggered_alerts:
            if session_id in ws_manager.broadcast_callbacks:
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
            
                # 2. Live 15-Minute Candle Check (Every minute)
                try:
                    now = datetime.datetime.now()
                    # We check for candle closes every 1 min, but execute only at :00, :15, :30, :45
                    if now.minute in [0, 1, 15, 16, 30, 31, 45, 46]:
                        with self.lock:
                            active_sessions = list(self.broadcast_callbacks.items())
                        
                        for sid, callback in active_sessions:
                            threading.Thread(target=self._process_candle_trades, args=(sid,), daemon=True).start()
                except Exception as e:
                    print(f"[ERROR] Candle check failed: {e}")

                # 3. Auto-Square Off Check 
                session_tokens_copy = {}
                try:
                    with self.lock:
                        session_ids = list(self.token_maps.keys())
                        for sid in session_ids:
                            session_tokens_copy[sid] = self.token_maps[sid].copy()
                except Exception: pass

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
                time.sleep(10)

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

        def on_error(wsapp, error):
            print(f"❌ [WS] WebSocket Error: {error}")
            broadcast_callback(session_id, {'type': 'status', 'data': {'status': 'ERROR', 'error': str(error)}})

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_error = on_error
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

    def _process_candle_trades(self, session_id: str):
        """Fetches last two 15m candles and triggers crossing logic"""
        from services.session_manager import session_manager
        from services.angel_service import angel_service
        from services.paper_service import paper_service
        
        session = session_manager.get_session(session_id)
        if not session or not session.auto_paper_trade or session.is_paused: return
        
        watchlist = list(session.watchlist)
        strategy_alerts = [a for a in list(session.alerts) if str(a.get('type', '')).startswith('AUTO_')]
        if not watchlist or not strategy_alerts: return
        
        # Determine 15m windows
        now = datetime.datetime.now()
        rem = now.minute % 15
        end_time_cur = now.replace(second=0, microsecond=0) - datetime.timedelta(minutes=rem)
        start_time_prev = end_time_cur - datetime.timedelta(minutes=30) # Get 2 candles
        
        # Prevent double execution in the same minute
        last_run = getattr(session, '_last_candle_run', '')
        current_minute = now.strftime('%H:%M')
        if last_run == current_minute: return
        session._last_candle_run = current_minute

        print(f"[LIVE] 📊 Running Strategy Candle Check for {session_id} ({current_minute})")
        
        for stock in watchlist:
            try:
                # 1. Fetch latest candles
                req = {
                    "exchange": stock.get('exch_seg', 'NSE'),
                    "symboltoken": str(stock['token']),
                    "interval": "FIFTEEN_MINUTE",
                    "fromdate": start_time_prev.strftime('%Y-%m-%d %H:%M'),
                    "todate": end_time_cur.strftime('%Y-%m-%d %H:%M')
                }
                res = angel_service.fetch_candle_data(session.smart_api, req)
                if not (res and res.get('data') and len(res['data']) >= 2): continue
                
                # To be 100% sure we have crossing, we look at:
                # Candle 1 (Older): e.g. 9:30-9:45
                # Candle 2 (Newest Completed): e.g. 9:45-10:00
                c2 = res['data'][-1] # Newest closed candle
                c1 = res['data'][-2] # Previous candle
                
                o2, h2, l2, close2 = float(c2[1]), float(c2[2]), float(c2[3]), float(c2[4])
                close1 = float(c1[4])
                
                print(f"DEBUG: {stock['symbol']} 15m Candle: PrevClose: {close1}, CurrClose: {close2} (H:{h2} L:{l2})")

                # 2. Check against active alerts
                all_strategy_alerts = [a for a in list(session.alerts) if str(a.get('token')) == str(stock['token']) and str(a.get('type','')).startswith('AUTO_')]
                
                for alert in list(session.alerts):
                    if str(alert['token']) == str(stock['token']) and str(alert.get('type', '')).startswith('AUTO_'):
                        lv_p = float(alert.get('price', 0))
                        buffer_pct = getattr(session, 'buffer_pct', 0.25) / 100.0
                        buffer = lv_p * buffer_pct
                        triggered = False
                        side = None
                        
                        mode = getattr(session, 'strategy_mode', 'BOUNCE')

                        if mode == 'SAR':
                            # CROSSING LOGIC
                            # BUY: Previous was below, Current is above Resistance + Buffer
                            if alert['condition'] == 'ABOVE' and close1 <= (lv_p + buffer) and close2 > (lv_p + buffer):
                                triggered, side = True, "BUY"
                            # SELL: Previous was above, Current is below Support - Buffer
                            elif alert['condition'] == 'BELOW' and close1 >= (lv_p - buffer) and close2 < (lv_p - buffer):
                                triggered, side = True, "SELL"
                        else:
                            # BOUNCE LOGIC (Rejection)
                            # SELL: Wick touched Resistance but close is back below
                            if alert['condition'] == 'ABOVE' and h2 >= (lv_p + buffer) and close2 < lv_p and close1 < lv_p:
                                triggered, side = True, "SELL"
                            # BUY: Wick touched Support but close is back above
                            elif alert['condition'] == 'BELOW' and l2 <= (lv_p - buffer) and close2 > lv_p and close1 > lv_p:
                                triggered, side = True, "BUY"

                        if triggered:
                            print(f"✅ [STRATEGY] Triggered {side} for {stock['symbol']} at {close2}")
                            
                            # --- Target Calculation (Match check_and_trigger_alerts) ---
                            target_price = None
                            try:
                                diff = 0.0
                                levels = {a['type']: a['price'] for a in all_strategy_alerts}
                                
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
                                
                                if diff > 0:
                                    t_type = alert.get('type', '')
                                    mode = getattr(session, 'strategy_mode', 'BOUNCE')
                                    
                                    if mode == 'BOUNCE':
                                        if 'AUTO_S' in t_type: target_price = lv_p + diff
                                        elif 'AUTO_R' in t_type: target_price = lv_p - diff
                                        elif t_type == 'AUTO_LOW': target_price = lv_p + (2 * diff)
                                        elif t_type == 'AUTO_HIGH': target_price = lv_p - (2 * diff)
                                    else:
                                        # Momentum targets
                                        if 'AUTO_S' in t_type: target_price = lv_p - diff
                                        elif 'AUTO_R' in t_type: target_price = lv_p + diff
                                        elif t_type == 'AUTO_LOW': target_price = lv_p - (2 * diff)
                                        elif t_type == 'AUTO_HIGH': target_price = lv_p + (2 * diff)
                                    
                                    if target_price:
                                        print(f"DEBUG: Calculated Target for {stock['symbol']}: {target_price:.2f}")
                            except: pass

                            # Execute Paper Trade with Target
                            paper_service.create_virtual_trade(
                                session_id, stock, side, 
                                alert.get('label', alert.get('type', 'STRATEGY')), 
                                target_price=target_price
                            )
                            
                            # Remove alert after trigger
                            if alert in session.alerts:
                                session.alerts.remove(alert)
                            
            except Exception as e:
                print(f"[WARN] Failed to process candle for {stock['symbol']}: {e}")

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