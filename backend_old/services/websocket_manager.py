"""
WebSocket Manager - Handles Angel One SmartAPI WebSocket
MODERN APRIL 2026 VERSION - Optimized for VPS Stability
"""
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import threading
import struct
import asyncio
import json
import time
import os
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta
import pytz
import logging

# Setup Logger
logger = logging.getLogger("websocket_manager")
logger.setLevel(logging.INFO)

try:
    today_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, "logs", today_str)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "app.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s', datefmt='%y%m%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f"[INIT] Modern WebSocket Logger active: {log_file}")
except Exception as e:
    print(f"[ERR] Logger init failed: {e}")

def get_ist_now():
    """Helper to get current time in IST (UTC+5:30) regardless of server time"""
    return datetime.now(pytz.timezone('Asia/Kolkata'))

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
            
            # Helper to calculate Diff & Target (MODERN APRIL LOGIC)
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
                
                mode = getattr(session, 'strategy_mode', 'BOUNCE')
                if mode == 'BOUNCE':
                    if 'AUTO_S' in trigger_type: return trigger_price + diff
                    if 'AUTO_R' in trigger_type: return trigger_price - diff
                    if trigger_type == 'AUTO_LOW': return trigger_price + (2 * diff)
                    if trigger_type == 'AUTO_HIGH': return trigger_price - (2 * diff)
                else:
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

                mode = getattr(session, 'strategy_mode', 'BOUNCE')
                trigger_price = float(stock['ltp'])
                target_p = calculate_diff_and_target(trigger_price, alert_type, all_known_alerts)
                
                side = 'BUY'
                if mode == 'BOUNCE':
                    if 'AUTO_S' in alert_type or trigger_price < (alert['price'] + 0.1): side = 'BUY'
                    else: side = 'SELL'
                else: # SAR
                    if alert.get('condition') == 'ABOVE': side = 'BUY'
                    else: side = 'SELL'

                paper_service.create_virtual_trade(
                    session_id, stock, side, 
                    alert_type.replace('AUTO_',''), 
                    target_price=target_p
                )

        # Broadcast update
        if session_id in ws_manager.broadcast_callbacks:
            ws_manager.broadcast_callbacks[session_id](session_id, {
                "type": "alert_triggered",
                "data": {
                    "alert": triggered_alerts[0]['alert'],
                    "log": triggered_alerts[0]['log'],
                    "paper_trades": session.paper_trades
                }
            })

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, SmartWebSocketV2] = {}
        self.token_maps: Dict[str, Dict] = {}
        self.broadcast_callbacks: Dict[str, Callable] = {}
        self.lock = threading.RLock()
        self.session_locks: Dict[str, threading.Lock] = {}
        self.heartbeat_thread = None
        self.last_tick_times: Dict[str, float] = {}
        self.running = True
        self._last_strategy_tick = ""

    def _threaded_alert_check(self, session_id: str, stock: dict):
        with self.lock:
            if session_id not in self.session_locks:
                self.session_locks[session_id] = threading.Lock()
            s_lock = self.session_locks[session_id]
        
        if not s_lock.acquire(blocking=False):
            return

        try:
            check_and_trigger_alerts(session_id, stock)
        except Exception as e:
            logger.error(f"Alert check failed: {e}")
        finally:
            s_lock.release()

    def _start_heartbeat(self):
        logger.info("[HEARTBEAT] Thread STARTED")
        while self.running:
            try:
                time.sleep(10)
                with self.lock:
                    active_sessions = list(self.broadcast_callbacks.items())
                
                for sid, callback in active_sessions:
                    try:
                        callback(sid, {"type": "heartbeat", "data": {"timestamp": time.time()}})
                    except:
                        self.stop_websocket(sid)
            
                ist_now = get_ist_now()
                # Strategy (Every 15 mins)
                target_min = (ist_now.minute // 15) * 15
                check_time = ist_now.replace(minute=target_min, second=0, microsecond=0)
                
                if 9 <= ist_now.hour <= 15:
                    tag = check_time.strftime('%Y-%m-%d %H:%M')
                    if self._last_strategy_tick != tag:
                        if ist_now.minute % 15 == 0 and ist_now.second >= 10:
                            self._last_strategy_tick = tag
                            from services.session_manager import session_manager
                            for sid, session in session_manager.get_all_sessions().items():
                                if not session.is_paused:
                                    threading.Thread(target=self._process_candle_trades, args=(sid, check_time), daemon=True).start()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                time.sleep(10)

    def start_websocket(self, session_id: str, jwt_token, api_key, client_id, feed_token, watchlist, broadcast_callback):
        if self.heartbeat_thread is None or not self.heartbeat_thread.is_alive():
            self.running = True
            self.heartbeat_thread = threading.Thread(target=self._start_heartbeat, daemon=True)
            self.heartbeat_thread.start()

        try:
            ws_jwt = jwt_token if jwt_token.startswith("Bearer ") else f"Bearer {jwt_token}"
            sws = SmartWebSocketV2(ws_jwt, api_key, client_id, feed_token)
            
            def on_data(wsapp, message):
                try:
                    callback = self.broadcast_callbacks.get(session_id)
                    if not callback: return
                    self.last_tick_times[session_id] = time.time()
                    
                    if isinstance(message, list):
                        for tick in message:
                            token = tick.get('token')
                            price = (tick.get('last_traded_price') or tick.get('ltp', 0)) / 100.0 if 'last_traded_price' in tick else tick.get('ltp', 0)
                            stock = self.token_maps.get(session_id, {}).get(str(token))
                            if stock:
                                stock['ltp'] = price
                                threading.Thread(target=self._threaded_alert_check, args=(session_id, stock.copy()), daemon=True).start()
                                callback(session_id, {'type': 'price_update', 'data': {'token': str(token), 'symbol': stock['symbol'], 'ltp': price}})
                except: pass

            sws.on_data = on_data
            sws.on_open = lambda ws: [sws.subscribe("watchlist", 3, [{"exchangeType": 1, "tokens": [s['token'] for s in watchlist]}])]
            sws.on_close = lambda ws, *a: self.stop_websocket(session_id)
            
            with self.lock:
                self.connections[session_id] = sws
                self.token_maps[session_id] = {str(s['token']): s for s in watchlist}
                self.broadcast_callbacks[session_id] = broadcast_callback
            
            threading.Thread(target=sws.connect, daemon=True).start()
            return True
        except: return False

    def _process_candle_trades(self, session_id: str, ist_time: datetime):
        # FULL MODERN APRIL 6th CANDLE LOGIC
        from services.session_manager import session_manager
        from services.paper_service import paper_service
        from services.angel_service import angel_service
        
        session = session_manager.get_session(session_id)
        if not session or session.is_paused: return
        
        logger.info(f"[STRATEGY] Processing 15m for {session.client_id} @ {ist_time}")
        watchlist = list(session.watchlist)
        buffer_pct = getattr(session, 'buffer_pct', 0.45) / 100.0

        for stock in watchlist:
            token = str(stock['token'])
            strategy_alerts = [a for a in session.alerts if str(a.get('token')) == token and str(a.get('type','')).startswith('AUTO_')]
            if not strategy_alerts: continue

            # Fetch 15m candle
            from_dt = (ist_time - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M')
            to_dt = ist_time.strftime('%Y-%m-%d %H:%M')
            req = {"exchange": stock['exch_seg'], "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_dt, "todate": to_dt}
            
            # Using session's own API connection
            c_data = angel_service.fetch_candle_data(session.smart_api, req)
            if c_data and c_data.get('data'):
                candle = c_data['data'][-1]
                o, h, l, c = float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4])
                
                # Check levels for crossover
                levels = sorted([{'p': float(a['price']), 'n': a.get('type','')} for a in strategy_alerts], key=lambda x: x['p'])
                prev_c = session._prev_candle_closes.get(token, o)
                session._prev_candle_closes[token] = c
                
                for lv in levels:
                    b = lv['p'] * buffer_pct
                    if c > (lv['p'] + b) and prev_c <= (lv['p'] + b):
                         paper_service.create_virtual_trade(session_id, stock, "BUY", lv['n'], entry_price=c)
                         break
                    elif c < (lv['p'] - b) and prev_c >= (lv['p'] - b):
                         paper_service.create_virtual_trade(session_id, stock, "SELL", lv['n'], entry_price=c)
                         break

    def stop_websocket(self, session_id):
        with self.lock:
            if session_id in self.connections:
                try: self.connections[session_id].close_connection()
                except: pass
                del self.connections[session_id]

    def stop_all(self):
        self.running = False
        with self.lock: self.connections.clear()

ws_manager = WebSocketManager()