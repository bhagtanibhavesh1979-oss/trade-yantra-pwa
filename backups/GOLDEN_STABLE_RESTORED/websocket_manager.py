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
import os
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta
import pytz
import logging

# Setup Logger with IST Timezone
logger = logging.getLogger("websocket_manager")
logger.setLevel(logging.INFO)

class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, pytz.timezone('Asia/Kolkata'))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

try:
    today_str = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, "logs", today_str)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "app.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = ISTFormatter('[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s', datefmt='%y%m%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    logger.info(f"[INIT] Logging initialized for websocket_manager in IST. Target: {log_file}")
except Exception as e:
    print(f"[ERR] Failed to initialize logging IST handler: {e}")

def tick_round(price):
    if price is None: return 0.0
    try:
        return round(float(price) * 20) / 20.0
    except:
        return float(price)

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

    def get_live_trade_quantity(ltp):
        """Calculates quantity for LIVE TRADING based on Capital OR Fixed Lot"""
        try:
            # 1. Check for Fixed Capital Setting (session.trade_capital)
            cap = getattr(session, 'trade_capital', 0)
            if cap > 0:
                qty = int(cap / ltp)
                return max(1, qty) # Minimum 1
            
            # 2. Fallback to Fixed Quantity (session.trade_quantity)
            # Defaults to 1 for live if not set (User must configure)
            return getattr(session, 'trade_quantity', 1) 
        except:
            return 1
    
    # Opening Protection Filter (Avoid 9:30 AM fake spikes)
    opening_bias = getattr(session, '_opening_bias', {}).get(str(stock['token']))
    protection_end = getattr(session, '_opening_protection_end', {}).get(str(stock['token']), 0)
    is_protected = time.time() < protection_end

    for alert in active_alerts:
        if str(alert['token']) == str(stock['token']) and alert.get('active', True):
            alert_type = str(alert.get('type', '')).upper()
            
            # --- OPENING PROTECTION CHECK ---
            if is_protected and opening_bias:
                # If 15m Trend is SELL, block "BUY" momentum alerts
                if opening_bias == "SELL" and "BUY" in alert_type:
                    continue
                # If 15m Trend is BUY, block "SELL" momentum alerts
                if opening_bias == "BUY" and "SELL" in alert_type:
                    continue

            # NEW: AUTO_ alerts must ONLY be processed by the 15-minute candle loop,
            # regardless of trigger_mode. Skipping them here prevents them from being
            # consumed by real-time ticks.
            if alert_type.startswith('AUTO_'):
                continue

            if check_alert_trigger(alert, stock):

                log_entry = create_alert_log(stock, alert)
                session.logs.insert(0, log_entry)
                session.alerts.remove(alert)
                triggered_alerts.append({"alert": alert, "log": log_entry})
                
    # --- SAME-TYPE ALERT FILTER (Prevent multi-trigger on same candle spike) ---
    if triggered_alerts:
        from services.websocket_manager import ws_manager
        client_id = session.client_id
        if client_id not in ws_manager.last_alert_times:
            ws_manager.last_alert_times[client_id] = {}
            
        filtered_triggers = []
        for item in triggered_alerts:
            alert = item['alert']
            alert_type = alert.get('type', '')
            token = str(alert['token'])
            key = f"{token}_{alert_type}"
            
            last_at = ws_manager.last_alert_times[client_id].get(key, 0)
            if (time.time() - last_at) < 2:
                print(f"[SHIELD] [ALERT-DEDUPE] Ignoring redundant alert {alert_type} for {stock['symbol']} (Triggered < 2s ago)")
                continue
            
            ws_manager.last_alert_times[client_id][key] = time.time()
            filtered_triggers.append(item)
        triggered_alerts = filtered_triggers

    # --- SMART SL / TRAP MONITORING (Match Backtest Logic) ---
    # This ensures we don't exit on random wicks unless the structure (Prev Close) supports the Trap
    if session.paper_trades and trigger_mode != 'CANDLE_CLOSE':
        from services.websocket_manager import ws_manager
        
        # --- TRADE COOLDOWN & CANDLE LOCK (Prevent Flapping) ---
        # 1. Standard Cooldown (60s) - PER CLIENT
        client_id = session.client_id
        last_trades = ws_manager.last_stock_trade_times.get(client_id, {})
        last_trade_at = last_trades.get(str(stock['token']), 0)
        COOLDOWN_SECONDS = 60
        
        if (time.time() - last_trade_at) < COOLDOWN_SECONDS:
            return

        # 2. Candle Lock (Prevent more than 1 SAR per 15min interval to match Lab)
        interval_mins = 15
        now_ts = int(time.time())
        current_candle_start = (now_ts // (interval_mins * 60)) * (interval_mins * 60)
        
        if not hasattr(ws_manager, 'last_sar_intervals'):
            ws_manager.last_sar_intervals = {}
        if client_id not in ws_manager.last_sar_intervals:
            ws_manager.last_sar_intervals[client_id] = {}
            
        last_flip_interval = ws_manager.last_sar_intervals[client_id].get(str(stock['token']), 0)
        if last_flip_interval == current_candle_start:
            return

        is_in_cooldown = (time.time() - last_trade_at) < COOLDOWN_SECONDS
        
        prev_closes = getattr(session, '_prev_candle_closes', {})
        trades_to_close = []
        
        for trade in session.paper_trades:
            if trade['status'] == 'OPEN' and trade.get('smart_sl', False):
                 token = str(trade['token'])
                 # Only process if this is the stock being updated in this tick or we have data
                 if token != str(stock['token']): continue
                 
                 # Dynamic TRAP evaluation based on Strategy Levels (SAR based on price touch)
                 # Reconstruct levels from active alerts
                 strategy_alerts = [a for a in active_alerts if str(a.get('token')) == token and str(a.get('type','')).startswith('AUTO_')]
                 if not strategy_alerts: continue
                 
                 # Filter and sort levels
                 levels = sorted([{'p': float(a['price']), 'n': a.get('type','')} for a in strategy_alerts], key=lambda x: x['p'])
                 buffer_pct = getattr(session, 'buffer_pct', 0.45) / 100.0
                 prev_c = prev_closes.get(token)
                 if prev_c is None: continue # Safe guard
                 
                 ltp = float(stock['ltp'])
                 
                 if trade['side'] == 'BUY':
                     # TRAP / SAR Logic for LONG position
                     for lv in levels:
                         b = lv['p'] * buffer_pct
                         # Break below support level
                         if ltp <= (lv['p'] - b) and prev_c >= (lv['p'] - b):
                             if is_in_cooldown:
                                 # print(f"[DEBUG] [COOLDOWN] Skipping SAR Break (TRAP) for {stock['symbol']} - cooldown active")
                                 break
                             trades_to_close.append((trade, lv['p'] - b, f"TRAP_{lv['n']}"))
                             break
                         # Rejection from resistance
                         elif ltp >= (lv['p'] + b) and prev_c < lv['p']: # simplified rejection intra-candle
                             if is_in_cooldown:
                                 # print(f"[DEBUG] [COOLDOWN] Skipping SAR Rejection for {stock['symbol']} - cooldown active")
                                 break
                             trades_to_close.append((trade, lv['p'], f"REJECTION_{lv['n']}"))
                             break
                 else:
                     # TRAP / SAR Logic for SHORT position
                     for lv in levels:
                         b = lv['p'] * buffer_pct
                         # Break above resistance level
                         if ltp >= (lv['p'] + b) and prev_c <= (lv['p'] + b):
                             if is_in_cooldown:
                                 # print(f"[DEBUG] [COOLDOWN] Skipping SAR Break (TRAP) for {stock['symbol']} - cooldown active")
                                 break
                             trades_to_close.append((trade, lv['p'] + b, f"TRAP_{lv['n']}"))
                             break
                         # Rejection from support
                         elif ltp <= (lv['p'] - b) and prev_c > lv['p']:
                             if is_in_cooldown:
                                 # print(f"[DEBUG] [COOLDOWN] Skipping SAR Rejection for {stock['symbol']} - cooldown active")
                                 break
                             trades_to_close.append((trade, lv['p'], f"REJECTION_{lv['n']}"))
                             break
        if trades_to_close:
            from services.paper_service import paper_service
            from services.live_service import live_service
            from services.risk_service import risk_service
            
            for t, price, reason in trades_to_close:
                print(f"[STOP] [SMART-SL] Closing {t['symbol']} @ {price}. Trap Confirmed (Level touch limit).")
                
                # 1. Close Existing Paper Trade
                paper_service.close_virtual_trade(session_id, t['id'], price, reason=reason)
                
                # IMMEDIATELY OPEN REVERSE POSITION using exact exit price
                if "TRAP" in reason or "REJECTION" in reason:
                    new_side = 'SELL' if t['side'] == 'BUY' else 'BUY'
                    print(f"[SAR] [REVERSAL] Triggering real-time reversal exactly at limit {price} for {t['symbol']}: {t['side']} -> {new_side}")
                    
                    # A. PAPER REVERSAL
                    if getattr(session, 'auto_paper_trade', False):
                        # Use the specific reason (TRAP_M etc) for the NEW trade to match Lab
                        paper_service.create_virtual_trade(
                            session_id, stock, new_side, reason, 
                            quantity=t.get('quantity', 100),
                            strategy_mode=getattr(session, 'strategy_mode', 'SAR'),
                            smart_sl=True,
                            entry_price=price
                        )
                        # Update Cooldown and Candle Lock - PER CLIENT
                        client_id = session.client_id
                        if client_id not in ws_manager.last_stock_trade_times:
                            ws_manager.last_stock_trade_times[client_id] = {}
                        ws_manager.last_stock_trade_times[client_id][token] = time.time()
                        
                        # Update Candle Lock Interval
                        if client_id not in ws_manager.last_sar_intervals:
                            ws_manager.last_sar_intervals[client_id] = {}
                        ws_manager.last_sar_intervals[client_id][token] = (int(time.time()) // (15 * 60)) * (15 * 60)
                    
                    # B. LIVE REVERSAL (Double Quantity Net Order)
                    if getattr(session, 'auto_live_trade', False) and risk_service.check_safety(session_id):
                        live_qty = get_live_trade_quantity(price)
                        # Reversal needs double the current position to flip
                        live_submit_qty = live_qty * 2
                        
                        if risk_service.check_margin(session_id, stock['symbol'], live_submit_qty, price):
                            live_service.place_live_order(
                                session_id, stock, new_side, live_submit_qty, 
                                tag=f"LIVE_SAR_FLIP",
                                product_type="INTRADAY"
                            )
                
    if triggered_alerts:
        from services.websocket_manager import ws_manager
        from services.paper_service import paper_service
        from services.live_service import live_service
        from services.risk_service import risk_service
        
        # Determine if we should trade (Paper OR Live)
        is_paper = getattr(session, 'auto_paper_trade', False)
        is_live = getattr(session, 'auto_live_trade', False)
        
        if is_paper or is_live:
            # --- Trigger Mode Check ---
            trigger_mode = getattr(session, 'trigger_mode', 'CANDLE_CLOSE')
            
            # Helper to calculate TGT and SL based on levels
            def get_level_based_targets(ltp, side, all_alerts):
                try:
                    # Get all AUTO levels for this stock
                    relevant_levels = sorted([
                        float(a['price']) for a in all_alerts 
                        if str(a['token']) == str(stock['token']) and str(a.get('type','')).startswith('AUTO_')
                    ])
                    
                    if not relevant_levels:
                        # Fallback to simple percentage if no levels found
                        diff = ltp * 0.015 # 1.5%
                        b = ltp * (getattr(session, 'buffer_pct', 0.45) / 100.0)
                        if side == "BUY":
                            return round(ltp + diff, 2), round(ltp - b, 2)
                        else:
                            return round(ltp - diff, 2), round(ltp + b, 2)

                    tgt, sl = None, None
                    buffer_pct = getattr(session, 'buffer_pct', 0.45) / 100.0

                    if side == "BUY":
                        # Target is the next level above
                        tgt_lv = next((p for p in relevant_levels if p > ltp + 0.01), None)
                        if tgt_lv: tgt = tgt_lv
                        else: tgt = round(ltp + (relevant_levels[1] - relevant_levels[0]), 2) if len(relevant_levels) > 1 else round(ltp * 1.015, 2)

                        # SL is the level just below
                        sl_lv = next((p for p in reversed(relevant_levels) if p < ltp - 0.01), None)
                        if sl_lv: sl = round(sl_lv - (sl_lv * buffer_pct), 2)
                        else: sl = round(ltp - (ltp * buffer_pct), 2)
                    else:
                        # Target is the next level below
                        tgt_lv = next((p for p in reversed(relevant_levels) if p < ltp - 0.01), None)
                        if tgt_lv: tgt = tgt_lv
                        else: tgt = round(ltp - (relevant_levels[1] - relevant_levels[0]), 2) if len(relevant_levels) > 1 else round(ltp * 0.985, 2)

                        # SL is the level just above
                        sl_lv = next((p for p in relevant_levels if p > ltp + 0.01), None)
                        if sl_lv: sl = round(sl_lv + (sl_lv * buffer_pct), 2)
                        else: sl = round(ltp + (ltp * buffer_pct), 2)
                    
                    return round(tgt, 2), round(sl, 2)
                except Exception as e:
                    print(f"DEBUG: TGT/SL Calculation error: {e}")
                    return None, None

            all_known_alerts = list(session.alerts) + [t['alert'] for t in triggered_alerts]

            for triggered in triggered_alerts:
                alert = triggered['alert']
                alert_type = str(alert.get('type', '')).upper()
                
                if trigger_mode == 'CANDLE_CLOSE' and alert_type.startswith('AUTO_'):
                    continue

                side = None
                mode = getattr(session, 'strategy_mode', 'BOUNCE')
                alert_cond = alert.get('condition', 'ABOVE').upper() # ABOVE or BELOW
                
                if mode == 'BOUNCE':
                    # Hit ABOVE alert (Resistance) -> SELL (Reversal)
                    # Hit BELOW alert (Support) -> BUY (Reversal)
                    side = 'SELL' if alert_cond == 'ABOVE' else 'BUY'
                else:
                    # SAR Momentum Mode (Follow trend breakout)
                    # Hit ABOVE alert (Breakout UP) -> BUY
                    # Hit BELOW alert (Breakout DOWN) -> SELL
                    side = 'BUY' if alert_cond == 'ABOVE' else 'SELL'

                if side:
                    # Check for Session Global SL/TGT Overrides first
                    target_price = getattr(session, 'global_target', None)
                    stop_loss = getattr(session, 'global_stop_loss', None)

                    # If not set globally, use Level-based Tighter Logic (Next Level)
                    if target_price is None or stop_loss is None:
                        calc_tgt, calc_sl = get_level_based_targets(stock['ltp'], side, all_known_alerts)
                        if target_price is None: target_price = calc_tgt
                        if stop_loss is None: stop_loss = calc_sl

                    # Align Reason with Lab
                    clean_label = alert_type.replace('AUTO_', '')
                    print(f"[TARGET] [AUTO] Triggering {side} for {stock['symbol']} @ {stock['ltp']} | TGT: {target_price} | SL: {stop_loss}")
                    
                    # Calculate Quantities
                    live_order_qty = get_live_trade_quantity(stock['ltp'])
                    paper_order_qty = 100 # Fixed Default for Paper Trades
                    
                    # FUND CHECK before calling service to log it properly
                    current_bal = getattr(session, 'virtual_balance', 0)
                    req_margin = stock['ltp'] * paper_order_qty * 0.05 # Paper Margin 5%
                    is_live_check = getattr(session, 'auto_live_trade', False)

                    if not is_live_check and current_bal < req_margin:
                        err_msg = f"[ERR] [FUNDS] Skipped {side} {stock['symbol']} - Insufficient Virtual Balance (Req: {req_margin:,.0f}, Bal: {current_bal:,.0f})"
                        session.logs.insert(0, {"time": datetime.now(pytz.utc).isoformat(), "symbol": stock['symbol'], "msg": err_msg, "type": "error"})
                        session_manager.save_session(session_id)
                        continue

                    # --- TRUE SAR EXECUTION FLOW for BOTH Paper & Live ---
                    # --- TRUE SAR EXECUTION FLOW ---
                    # 1. LIVE EXECUTION (Optimized: Double Quantity / Net Order)
                    if is_live and risk_service.check_safety(session_id):
                        open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
                        
                        live_submit_qty = live_order_qty # Default for fresh entry
                        is_reversal_live = False

                        if open_trade and open_trade['side'] != side:
                            # REVERSAL DETECTED: We are Long X, want Short Y.
                            # Since Paper Quantity (100) != Live Quantity, we cannot use open_trade['quantity'].
                            # We assume the user holds 'live_order_qty' in the live account.
                            # Net Order = Sell (Old + New) = 2 * live_order_qty
                            live_submit_qty = live_order_qty * 2
                            is_reversal_live = True
                            print(f"[FAST] [LIVE-SAR] Optimizing Reversal: {stock['symbol']} {open_trade['side']} -> {side}. Sending {side} {live_submit_qty} Qty (2x Lot).")
                        elif open_trade and open_trade['side'] == side:
                             # Already in position (No Pyramiding)
                             continue # Skip Live
                        
                        if is_in_cooldown:
                            # print(f"[DEBUG] [COOLDOWN] Skipping AUTO trade for {stock['symbol']} - cooldown active")
                            continue

                        # Place Single Net Order
                        if risk_service.check_margin(session_id, stock['symbol'], live_submit_qty, stock['ltp']):
                             tag = f"SAR_{clean_label}" if is_reversal_live else f"AUTO_{clean_label}"
                             live_service.place_live_order(
                                 session_id, stock, side, abs(live_submit_qty), 
                                 tag=tag,
                                 product_type="INTRADAY" # Explicitly MIS
                             )

                    # Update Cooldown
                    if session_id not in ws_manager.last_stock_trade_times:
                        ws_manager.last_stock_trade_times[session_id] = {}
                    ws_manager.last_stock_trade_times[session_id][str(stock['token'])] = time.time()

                    # 2. PAPER EXECUTION (Keep Close+Open for cleaner UI tracking)
                    # We still do Close + Open for Paper to maintain accurate PnL history per trade leg.
                    open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
                    if open_trade:
                        if open_trade['side'] != side:
                            # Paper Close Prev
                            paper_service.close_virtual_trade(session_id, open_trade['id'], stock['ltp'], reason=f"SAR_{clean_label}")
                        else:
                            # Already in position
                            continue

                    # Paper Open New
                    paper_service.create_virtual_trade(
                        session_id, stock, side, clean_label, 
                        quantity=paper_order_qty,
                        target_price=target_price, 
                        stop_loss=stop_loss,
                        strategy_mode=mode,
                        smart_sl=True
                    )


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
        self.lock = threading.RLock() # Changed to RLock to prevent deadlocks
        self.session_locks: Dict[str, threading.Lock] = {} # Per-session execution locks
        self.heartbeat_thread = None
        self.last_tick_times: Dict[str, float] = {}
        self.last_refresh_times: Dict[str, float] = {}
        self.last_stock_trade_times: Dict[str, Dict[str, float]] = {} # {client_id: {token: timestamp}}
        self.last_alert_times: Dict[str, Dict[str, float]] = {} # {client_id: {token_type: timestamp}}
        self.running = True
        self._last_strategy_tick = ""

    def _threaded_alert_check(self, session_id: str, stock: dict):
        """Wrapper for threaded alert execution with Non-Blocking Lock to prevent race conditions"""
        # 1. Get or create the lock for this specific session
        with self.lock:
            if session_id not in self.session_locks:
                self.session_locks[session_id] = threading.Lock()
            s_lock = self.session_locks[session_id]

        # 2. Try to acquire the lock without blocking. 
        # If another thread is already processing alerts for this session, we skip this tick.
        if not s_lock.acquire(blocking=False):
            # Already processing a tick for this session, skip to prevent race condition/duplicates
            if time.time() % 10 < 0.1: # Throttled debug log
                print(f"[DEBUG] [WS] Skipping concurrent tick for {session_id[:8]} (Lock Active)")
            return

        try:
            check_and_trigger_alerts(session_id, stock)
        except Exception as e:
            print(f"[ERROR] Threaded Alert Check Failed: {e}")
        finally:
            # Always release the lock
            s_lock.release()

    def _start_heartbeat(self):
        """Send heartbeats and monitor connection health"""
        logger.info("[HEARTBEAT] Heartbeat thread STARTED")
        consecutive_errors = 0
        max_errors = 10
        while self.running:
            try:
                # Use shorter wait for debugging (revert to 10s later)
                time.sleep(10)
                # print(f"[DEBUG] [HEARTBEAT] Loop tic: {time.time()}")

                
                # 1. Send Heartbeats to Frontend
                with self.lock:
                    active_sessions = list(self.broadcast_callbacks.items())
                
                for session_id, callback in active_sessions:
                    try:
                        callback(session_id, {"type": "heartbeat", "data": {"timestamp": time.time()}})
                        consecutive_errors = 0
                    except Exception as e:
                        logger.error(f"[HEARTBEAT] Error sending heartbeat to frontend for {session_id[:8]}: {e}", exc_info=True)
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            logger.warning(f"[HEARTBEAT] Max consecutive errors reached for {session_id[:8]}. Stopping websocket.")
                            self.stop_websocket(session_id)
                            consecutive_errors = 0
            
                # 2. Connection Health Check (Market Hours)
                utc_now = datetime.now(pytz.utc)
                ist_now = utc_now.astimezone(pytz.timezone('Asia/Kolkata'))
                
                market_start = ist_now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = ist_now.replace(hour=15, minute=35, second=0, microsecond=0)
                is_market_active = market_start <= ist_now <= market_end

                if is_market_active:
                    with self.lock:
                        # Check everyone who should have a connection (active frontend sessions)
                        active_sid_list = list(self.broadcast_callbacks.keys())
                    
                    for sid in active_sid_list:
                        try:
                            last_tick = self.last_tick_times.get(sid, 0)
                            last_recovery = self.last_refresh_times.get(sid, 0)
                            
                            # If no data for 60 seconds during market, or connection object missing, reconnect
                            with self.lock:
                                is_missing = sid not in self.connections
                                
                            # Use 30s backoff for recovery attempts to allow 429 locks to clear
                            if (is_missing or (time.time() - last_tick > 60)) and (time.time() - last_recovery > 30):
                                logger.warning(f"[WS] Connection check for {sid[:8]}: {'Missing' if is_missing else 'Stale'}. Attempting recovery in background...")
                                self._recover_session(sid)
                        except Exception as e:
                            logger.error(f"[HEARTBEAT] Error during connection health check for {sid[:8]}: {e}", exc_info=True)

                # 3. Strategy Execution Check (Every 15 minutes)
                try:
                    # Get Current Time in IST
                    utc_now = datetime.now(pytz.utc)
                    ist_now = utc_now.astimezone(pytz.timezone('Asia/Kolkata'))
                    
                    # Log heartbeat occasionally for debug
                    if ist_now.second < 12:
                        logger.debug(f"[HEARTBEAT] Server Time (IST): {ist_now.strftime('%H:%M:%S')}")

                    # Market Hours: 9:15 AM to 3:30 PM
                    # We check exactly at :00, :15, :30, :45 intervals for strategy
                    
                    # CATCH-UP LOGIC: If we just started or missed an interval, check the CURRENT or most RECENT 15m block
                    # This ensures if we start at 9:31 AM, we still process the 9:30 AM candle.
                    target_minute = (ist_now.minute // 15) * 15
                    check_time = ist_now.replace(minute=target_minute, second=0, microsecond=0)
                    
                    start_trading_time = ist_now.replace(hour=9, minute=30, second=0, microsecond=0)
                    market_end = ist_now.replace(hour=15, minute=15, second=0, microsecond=0)

                    if start_trading_time <= check_time <= market_end:
                        # TRIGGER once per 15m interval (using date + time for unique tracking)
                        tag = check_time.strftime('%Y-%m-%d %H:%M')
                        if not hasattr(self, '_last_strategy_tick'): self._last_strategy_tick = ""
                        
                        if self._last_strategy_tick != tag:
                            # 10s Offset: Wait until 10s past the mark to allow broker data to finalize
                            is_exact = (ist_now.minute % 15 == 0 and ist_now.second >= 10 and ist_now.second < 55)
                            # 15m Catch-up: If we missed the exact mark (e.g. server restart), trigger if within 15m
                            is_catchup = (not is_exact and (ist_now - check_time).total_seconds() < 900)
                            
                            if is_exact or is_catchup:
                                if is_catchup:
                                    logger.info(f"[CATCH-UP] [STRATEGY] Late start detected at {ist_now.strftime('%H:%M:%S')}. Processing {tag} candle.")
                                
                                self._last_strategy_tick = tag
                                from services.session_manager import session_manager
                                all_sessions = session_manager.get_all_sessions()
                                
                                for sid, session in all_sessions.items():
                                    is_p = getattr(session, 'auto_paper_trade', False)
                                    is_l = getattr(session, 'auto_live_trade', False)
                                    if (is_p or is_l) and not session.is_paused:
                                        logger.info(f"[TIME] [STRATEGY] Triggering check for {session.client_id} (SID: {sid[:8]}) for interval {tag}")
                                        threading.Thread(target=self._process_candle_trades, args=(sid, check_time), daemon=True).start()
                except Exception as e:
                    logger.error(f"[ERROR] Strategy check failed: {e}", exc_info=True)


                # 3. Auto-Square Off Check 
                session_tokens_copy = {}
                try:
                    with self.lock:
                        session_ids = list(self.token_maps.keys())
                        for sid in session_ids:
                            session_tokens_copy[sid] = self.token_maps[sid].copy()
                except Exception as e:
                    logger.error(f"[HEARTBEAT] Error copying session tokens for square-off: {e}", exc_info=True)

                if session_tokens_copy:
                    try:
                        from services.paper_service import paper_service
                        for sid, tokens in session_tokens_copy.items():
                            if tokens:
                                # Serialize EOD check with session lock
                                with self.lock:
                                    if sid not in self.session_locks:
                                        self.session_locks[sid] = threading.Lock()
                                    s_lock = self.session_locks[sid]
                                
                                # Blocking lock for square-off to ensure it completes
                                with s_lock:
                                    paper_service.check_and_square_off(sid, tokens)
                    except Exception as e:
                        logger.error(f"[ERROR] Auto-Square off check failed: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"[ERROR] Heartbeat thread exception: {e}", exc_info=True)
                time.sleep(10)

    def _recover_session(self, session_id: str):
        """Refreshes tokens and restarts WebSocket for a session"""
        from services.session_manager import session_manager
        
        # 1. Decide if we need to refresh tokens
        last_ref = self.last_refresh_times.get(session_id, 0)
        last_tick = self.last_tick_times.get(session_id, 0)
        
        # Refresh if tokens are older than 5 mins AND we are currently disconnected/stale
        if (time.time() - last_ref > 300):
            logger.info(f"[REFRESH] [RECOVER] Attempting periodic token refresh for {session_id[:8]}...")
            self.last_refresh_times[session_id] = time.time()
            success = session_manager.refresh_session_tokens(session_id)
            if not success:
                logger.error(f"[ERR] [RECOVER] Token refresh failed. Aborting connection attempt to prevent 429 lock.")
                return False
        else:
            logger.info(f"[INFO] [RECOVER] Using existing tokens for {session_id[:8]} (Refresh throttled)")
        
        # 2. Restart WebSocket
        session = session_manager.get_session(session_id)
        if session:
            # Update tick time to avoid immediate re-trigger
            self.last_tick_times[session_id] = time.time()
            
            # Close existing if any to avoid 429 Connection Limit Exceeded
            with self.lock:
                if session_id in self.connections:
                    try:
                        logger.info(f"[DISC] [RECOVER] Closing old connection for {session_id[:8]}...")
                        self.connections[session_id].close_connection()
                        time.sleep(1) # Small delay to let socket release
                    except Exception as ce:
                        logger.warning(f"[WARN] [RECOVER] Error closing old connection: {ce}", exc_info=True)
                    finally:
                        if session_id in self.connections:
                            del self.connections[session_id]
            
            # Start new
            callback = self.broadcast_callbacks.get(session_id)
            if callback:
                # Use data key if available, but be ready to fallback if it's known bad
                key_to_use = session.data_api_key if (session.data_api_key and session.data_api_key.strip()) else session.api_key
                self.start_websocket(
                    session_id, session.jwt_token, key_to_use, 
                    session.client_id, session.feed_token, session.watchlist, 
                    callback
                )

    def ensure_heartbeat(self):
        """Ensure the background heartbeat/strategy thread is running"""
        with self.lock:
            needs_start = False
            if self.heartbeat_thread is None:
                needs_start = True
            elif not self.heartbeat_thread.is_alive():
                logger.warning("[AUTH] Heartbeat thread was found DEAD. Restarting...")
                needs_start = True
                
            if needs_start:
                self.running = True
                self.heartbeat_thread = threading.Thread(target=self._start_heartbeat, daemon=True)
                self.heartbeat_thread.start()
                logger.info("[AUTH] Background Strategy Heartbeat initiated.")

    def start_websocket(self, session_id_or_obj, jwt_token=None, api_key=None, 
                       client_id=None, feed_token=None, watchlist=None,
                       broadcast_callback=None):
        """
        Main entry point to start the data stream for a session.
        Can be called with a Session object or individual parameters.
        """
        # Ensure heartbeat is running for strategy processing
        self.ensure_heartbeat()

        # --- Handle Overloaded Signature (Session Object vs Params) ---
        if hasattr(session_id_or_obj, 'session_id'):
            # It's a Session object
            session = session_id_or_obj
            session_id = session.session_id
            jwt_token = session.jwt_token
            api_key = session.data_api_key or session.api_key
            client_id = session.client_id
            feed_token = session.feed_token
            watchlist = session.watchlist
            # Find an existing callback or use a dummy if none (Recovery handles broadcast later)
            with self.lock:
                broadcast_callback = self.broadcast_callbacks.get(session_id, lambda sid, msg: None)
        else:
            session_id = session_id_or_obj

        # --- IDEMPOTENCY GUARD ---
        # Don't restart if we already have an active connection for this session
        with self.lock:
            if session_id in self.connections:
                logger.info(f"[WS] Session {session_id[:8]} already has an active stream. Skipping restart.")
                return True

        logger.debug(f"[DEBUG] Attempting to start Angel One WebSocket for session {session_id}")
        if not all([jwt_token, api_key, client_id, feed_token]):
            logger.error(f"[ERR] [WS] Missing credentials: jwt={bool(jwt_token)}, api={bool(api_key)}, id={bool(client_id)}, feed={bool(feed_token)}")
            return False

        try:
            # SmartWebSocketV2 NEEDS the 'Bearer ' prefix, but our REST API needs it RAW.
            # We add it here just for the WebSocket connection.
            ws_jwt = jwt_token
            if not ws_jwt.startswith("Bearer "):
                ws_jwt = f"Bearer {ws_jwt}"

            sws = SmartWebSocketV2(ws_jwt, api_key, client_id, feed_token, max_retry_attempt=0)
            
            # MONKEY-PATCH for SDK Bug: _on_close takes 2 args, but library passes 4
            # We fix it at the instance level.
            def patched_on_close(wsapp_inst, *args):
                sws.on_close(wsapp_inst, *args)
            
            def patched_on_error(wsapp_inst, err, *args):
                sws.on_error(wsapp_inst, err, *args)

            sws._on_close = patched_on_close
            sws._on_error = patched_on_error
            
            print(f"[OK] [WS] SmartWebSocketV2 instance created for {session_id}")
            print(f"[KEY] [WS-HANDSHAKE] Using Key: {api_key[:5]}..., ID: {client_id}, JWT: {jwt_token[:5]}..., Feed: {feed_token[:5]}...")
        except Exception as e:
            print(f"[ERR] [WS] Failed to initialize SmartWebSocketV2: {e}")
            return False

        token_map = {str(s['token']): s for s in watchlist}
        print(f"[WS] Watchlist size: {len(watchlist)} tokens")
        with self.lock:
            self.connections[session_id] = sws
            self.token_maps[session_id] = token_map
            self.broadcast_callbacks[session_id] = broadcast_callback
            # Initialize tick timer to avoid immediate stale recovery
            self.last_tick_times[session_id] = time.time()

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
                # print(f"DEBUG: RAW MESSAGE RX for {session_id[:8]}")
                from services.session_manager import session_manager
                callback = _get_callback()
                if not callback: return

                if isinstance(message, (list, dict)):
                    if isinstance(message, dict): message = [message]
                    for tick in message:
                        token = tick.get('token') or tick.get('tk')
                        # 'last_traded_price' for quote, 'ltp' for ltpData, 'c' for some binary variants
                        # The SmartStream V2 typically uses 'last_traded_price' in the parsed dict
                        raw_price = tick.get('last_traded_price') or tick.get('ltp') or tick.get('c')
                        
                        # DEBUG FILTER: Print one update every 5 seconds per token to avoid spam
                        current_ts = time.time()
                        if token and current_ts - self.last_tick_times.get(session_id, 0) > 5:
                           print(f"[WS-DEBUG] {session_id[:8]} Data RX: {token} -> {raw_price}")

                        if token and raw_price is not None:
                            self.last_tick_times[session_id] = time.time()
                            stock = token_map.get(str(token))
                            if stock:
                                stock['ltp'] = float(raw_price) / 100.0 if 'last_traded_price' in tick else float(raw_price)
                            # 3. Handle Alert Triggering (Threaded to prevent WS lag)
                            triggered_alerts = []
                            session = session_manager.get_session(session_id)
                            
                            # Initial fast filter (Check if ANY alert condition is met)
                            # We clone a snapshot to pass to the thread so LTP doesn't change
                            stock_snapshot = stock.copy()
                            if session and session.alerts:
                                # Start a background thread to process complex trade logic
                                # This ensures the WebSocket loop (price updates) never freezes
                                threading.Thread(
                                    target=self._threaded_alert_check,
                                    args=(session_id, stock_snapshot),
                                    daemon=True
                                ).start()
                                
                            _broadcast_price(callback, str(token), stock['symbol'], stock['ltp'])
                
                elif isinstance(message, bytes) and len(message) > 50:
                    token_bytes = message[2:27]
                    token = token_bytes.replace(b'\x00', b'').decode('utf-8')
                    ltp_bytes = message[43:51]
                    ltp_paise = struct.unpack('<q', ltp_bytes)[0]
                    real_price = ltp_paise / 100.0
                    
                    if time.time() - self.last_tick_times.get(session_id, 0) > 5:
                         print(f"[WS-DEBUG] {session_id[:8]} BINARY RX: {token} -> {real_price}")

                    self.last_tick_times[session_id] = time.time()
                    stock = token_map.get(str(token))
                    if stock:
                        stock['ltp'] = real_price
                        
                        # Threaded Alert Check (Binary)
                        stock_snapshot = stock.copy()
                        session = session_manager.get_session(session_id)
                        if session and session.alerts:
                            threading.Thread(
                                target=self._threaded_alert_check,
                                args=(session_id, stock_snapshot),
                                daemon=True
                            ).start()

                        _broadcast_price(callback, str(token), stock['symbol'], real_price)
            except: pass

        def on_open(wsapp):
            print(f"[OK] [WS] WebSocket Connected for session {session_id}")
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

        def on_close(wsapp, *args):
            # Args might be (code, reason) or more depending on library version
            code = args[0] if len(args) > 0 else 'unknown'
            reason = args[1] if len(args) > 1 else 'unknown'
            print(f"[DISC] [WS] WebSocket Closed for session {session_id}. Code: {code}, Reason: {reason}")
            print(f"[WS] Full args: {args}")
            with self.lock:
                if session_id in self.connections:
                    del self.connections[session_id]
            broadcast_callback(session_id, {'type': 'status', 'data': {'status': 'DISCONNECTED'}})

        def on_error(wsapp, error, *args):
            print(f"[ERR] [WS] WebSocket Error for session {session_id}")
            print(f"[WS] Error type: {type(error)}")
            print(f"[WS] Error message: {error}")
            print(f"[WS] Error args: {args}")
            import traceback
            traceback.print_exc()
            with self.lock:
                if session_id in self.connections:
                    del self.connections[session_id]
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

    def _process_candle_trades(self, session_id: str, ist_time: datetime):
        """
        Executes Strategy Logic mirroring the Backtest Service exactly.
        - Uses strict crossovers (Previous Close vs Current Close).
        - Respects Buffers and Strategy Modes (SAR/Bounce).
        - No Pyramiding (Averaging).
        """
        try:
            self._process_candle_trades_inner(session_id, ist_time)
        except Exception as e:
            import traceback
            print(f"[CRITICAL] [STRATEGY] _process_candle_trades CRASHED for {session_id[:8]}: {e}")
            traceback.print_exc()

    def _process_candle_trades_inner(self, session_id: str, ist_time: datetime):
        """Inner implementation with full error visibility and session locking"""
        from services.session_manager import session_manager
        from services.paper_service import paper_service
        from services.live_service import live_service
        from services.risk_service import risk_service
        
        # Lock acquisition for strategy processing
        with self.lock:
            if session_id not in self.session_locks:
                self.session_locks[session_id] = threading.Lock()
            s_lock = self.session_locks[session_id]
        
        # --- STAGGERED EXECUTION (Rate Limit Protection) ---
        # Random jitter to prevent all sessions from colliding on Angel API at same second
        import random
        jitter = random.uniform(0.5, 12.0)
        time.sleep(jitter)
        
        # We use a BLOCKING lock here because strategy execution is critical
        # and happens only once every 15 mins. We must wait for any tick check to finish.
        with s_lock:
            session = session_manager.get_session(session_id)
            if not session:
                print(f"[ERR] [STRATEGY] No session object for {session_id[:8]}")
                return
            
        # Check if EITHER mode is active
        is_paper = getattr(session, 'auto_paper_trade', False)
        is_live = getattr(session, 'auto_live_trade', False)
        
        if (not is_paper and not is_live):
            # print(f"[DEBUG] [STRATEGY] skipping {session_id[:8]} - auto modes OFF")
            return
            
        if session.is_paused:
            print(f"[DEBUG] [STRATEGY] skipping {session_id[:8]} - session paused")
            return
        
        current_interval_tag = ist_time.strftime('%Y-%m-%d %H:%M')
        
        last_run = getattr(session, '_last_candle_run', '')
        if last_run == current_interval_tag: return
        session._last_candle_run = current_interval_tag
        
        token_map = self.token_maps.get(session_id, {})
        watchlist = list(session.watchlist)
        print(f"[STRATEGY] [TIME] 15m Candle Close Check {current_interval_tag} for {session.client_id} (SID: {session_id[:8]})")

        # Establish prev_close if missing, especially at 9:30 AM
        if not hasattr(session, '_prev_candle_closes'): 
            session._prev_candle_closes = {}
        # Ensure opening protection dicts exist (critical: avoids AttributeError crash at 9:30 AM)
        if not hasattr(session, '_opening_bias'):
            session._opening_bias = {}
        if not hasattr(session, '_opening_protection_end'):
            session._opening_protection_end = {}
        
        is_opening_candle = (ist_time.hour == 9 and ist_time.minute == 30)
        
        # SOLUTION: If we don't have prev_close, we DON'T trade at 9:30 AM unless it's a gap-up/down
        buffer_pct = getattr(session, 'buffer_pct', 0.45) / 100.0
        
        # --- 2. Track Crossovers & Fetch Candle Data ---
        # OPTIMIZATION: Create one API instance for the entire session loop
        from SmartApi import SmartConnect
        from services.angel_service import angel_service
        
        api_key_to_use = session.data_api_key if (session.data_api_key and session.data_api_key.strip()) else session.api_key
        api_instance = SmartConnect(api_key=api_key_to_use)
        api_instance.setAccessToken(session.jwt_token)
        api_instance.setUserId(session.client_id)
        
        # Helper for safer candle fetch with key fallback
        def _get_candle_safe(req_data, attempt=0):
            try:
                res = angel_service.fetch_candle_data(api_instance, req_data, priority='high')
                
                # Check for AG8004 (Key), AG8001/AB1019 (Token), AB1004 (Rate)
                err_code = ""
                if res and not res.get('status'):
                    err_code = str(res.get('errorcode', '') or res.get('errorCode', ''))
                
                # --- AUTO-REFRESH LOGIC (AG8001 / AB1019 / Invalid Token) ---
                # NOTE: Angel uses AB1019 for both 'Invalid Session' AND 'Too many requests'.
                # We only refresh if it's actually an auth issue.
                is_auth_error = err_code == 'AG8001' or (err_code == 'AB1019' and "too many requests" not in str(res).lower())
                
                if is_auth_error or "invalid token" in str(res).lower():
                    print(f"[RECOVERY] [STRATEGY] Token expired ({err_code}) for {session.client_id}. Refreshing...")
                    if session_manager.refresh_session_tokens(session_id):
                        # RE-INITIALIZE api_instance with fresh session token
                        # We must get the updated session object first
                        new_session = session_manager.get_session(session_id)
                        if new_session and new_session.jwt_token:
                            api_instance.setAccessToken(new_session.jwt_token)
                            print(f"[OK] [STRATEGY] Token refreshed. Retrying getCandleData...")
                            # Retry once with the new token
                            retry_res = angel_service.fetch_candle_data(api_instance, req_data)
                            return retry_res
                    else:
                        print(f"[ERR] [STRATEGY] Auto-refresh failed for {session.client_id}. Strategy check will likely fail.")

                
                # --- RATE LIMIT BACKOFF (AB1004) ---
                if err_code == 'AB1004' and attempt < 2:
                    print(f"[RETRY] [RATE-LIMIT] hit AB1004 for {req_data.get('symboltoken')}. Waiting 5s...")
                    time.sleep(5)
                    return _get_candle_safe(req_data, attempt + 1)

                is_invalid_key = (err_code == 'AG8004')
                
                if not is_invalid_key and res and res.get('status'):
                    return res
                
                # If AG8004 or we have reason to suspect the key, try primary
                if (is_invalid_key or not res) and api_key_to_use != session.api_key:
                    print(f"[WARN] API Key {api_key_to_use} failed. Retrying with primary key {session.api_key}")
                    try:
                        fallback_api = SmartConnect(api_key=session.api_key)
                        fallback_api.setAccessToken(session.jwt_token)
                        fallback_api.setUserId(session.client_id)
                        return angel_service.fetch_candle_data(fallback_api, req_data)
                    except Exception as fe:
                        print(f"[ERR] Fallback candle fetch failed: {fe}")
                        return None
                return res
            except Exception as e:
                err_msg = str(e).lower()
                print(f"[ERR] Candle fetch exception: {e}")
                
                # If exception indicates invalid key, try fallback
                if ("api key" in err_msg or "ag8004" in err_msg) and api_key_to_use != session.api_key:
                    print(f"[RECOVERY] Exception suggests invalid key. Trying primary key {session.api_key}")
                    try:
                        fallback_api = SmartConnect(api_key=session.api_key)
                        fallback_api.setAccessToken(session.jwt_token)
                        fallback_api.setUserId(session.client_id)
                        return angel_service.fetch_candle_data(fallback_api, req_data)
                    except Exception as fe:
                        print(f"[ERR] Fallback recovery failed: {fe}")
                return None

        # Diagnostic: Gather eligible stocks with AUTO_ alerts
        eligible_stocks = []
        total_auto = 0
        
        for stock in watchlist:
            token = str(stock['token'])
            # Use all AUTO alerts associated with this stock in the current session
            # as requested by user (ignore creation date)
            strategy_alerts = [
                a for a in session.alerts 
                if str(a.get('token')) == token 
                and str(a.get('type','')).startswith('AUTO_')
                and a.get('active', True)
            ]
            total_auto += len(strategy_alerts)
            
            if strategy_alerts:
                eligible_stocks.append((stock, strategy_alerts))

        if total_auto > 0:
            print(f"[STRATEGY] [DIAG] Session {session_id[:8]}: {total_auto} AUTO alerts found. {len(eligible_stocks)} stocks eligible.")
        
        if not eligible_stocks:
            if total_auto > 0:
                print(f"[STRATEGY] [SKIP] No eligible stocks for {session_id[:8]} (All {total_auto} alerts are stale or timestamp missing)")
            return

        print(f"[STRATEGY] Processing {len(eligible_stocks)} eligible stocks for {session.client_id}")

        # At market open (9:30 AM), wait 30s for Angel API to finalize the 9:15-9:30 candle.
        # Moved outside the loop to prevent multiplying the delay by number of stocks.
        if is_opening_candle:
            print(f"[STRATEGY] [OPENING] Waiting 30s for Angel API to finalize 9:15-9:30 candle...")
            time.sleep(30)

        for stock, strategy_alerts in eligible_stocks:
            try:
                # Rate limit protection between stocks
                time.sleep(1.5)
                token = str(stock['token'])
                symbol = stock['symbol']
                
                print(f"[STRATEGY] [DIAG] Checking {symbol} ({token}). Alerts: {[a.get('type') for a in strategy_alerts]}")
                ltp = 0.0
                live_data = token_map.get(token)
                if live_data and live_data.get('ltp'): 
                    ltp = float(live_data['ltp'])
                else: 
                    ltp = float(stock.get('ltp', 0.0))
                
                if ltp <= 0: 
                    continue

                # Get Open Position for this stock
                open_trade = next((t for t in session.paper_trades if str(t['token']) == token and t['status'] == 'OPEN'), None)
                current_side = open_trade['side'] if open_trade else None
                
                prev_close_ref = session._prev_candle_closes.get(token)
                
                # --- FETCH REAL 15-MIN CANDLE ---
                open_p, high_p, low_p, close_p = ltp, ltp, ltp, ltp
                for attempt in range(3):
                    try:
                        end_dt = ist_time + timedelta(minutes=1)
                        end_dt_str = end_dt.strftime('%Y-%m-%d %H:%M')
                        from_dt = (ist_time - timedelta(minutes=15))
                        start_dt_str = from_dt.strftime('%H:%M')
                        full_from_dt_str = (ist_time - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M')
                        
                        req_data = {
                            "exchange": stock.get('exch_seg', 'NSE'),
                            "symboltoken": stock['token'],
                            "interval": "FIFTEEN_MINUTE", 
                            "fromdate": full_from_dt_str,
                            "todate": end_dt_str,
                            "symbol": stock.get('symbol')
                        }
                        
                        c_data = _get_candle_safe(req_data)
                        if c_data and c_data.get('data'):
                            targeted_candle = next((c for c in reversed(c_data['data']) if start_dt_str in c[0]), None)
                            if targeted_candle:
                                open_p, high_p, low_p, close_p = float(targeted_candle[1]), float(targeted_candle[2]), float(targeted_candle[3]), float(targeted_candle[4])
                                print(f"[CANDLE] {stock['symbol']} Targeted {start_dt_str}: O={open_p} H={high_p} L={low_p} C={close_p}")
                                break
                        
                        if attempt < 2: 
                            time.sleep(2)
                        else:
                            print(f"[WARN] [CANDLE] {stock['symbol']} No data. Using LTP {ltp}")
                    except Exception as ce:
                        if attempt == 2: print(f"[WARN] [CANDLE] {stock['symbol']} Fetch Error: {ce}")
                        time.sleep(2)

                # Update References
                session._prev_candle_closes[token] = close_p
                if is_opening_candle: prev_close_ref = open_p 
                elif prev_close_ref is None: prev_close_ref = open_p

                # --- SIGNAL LOGIC ---
                levels = sorted([{'p': float(a['price']), 'n': a.get('type',''), 'obj': a} for a in strategy_alerts], key=lambda x: x['p'])
                trigger_mode = getattr(session, 'trigger_mode', 'CANDLE_CLOSE')
                test_p_up = high_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                test_p_down = low_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                mode = getattr(session, 'strategy_mode', 'SAR') 
                
                signal_side = None
                label_tag = "STRATEGY"
                trigger_lv_p = None
                exit_price_fixed = tick_round(close_p)

                # 1. TRAP/REJECTION SAR (Existing Position Only)
                if mode != 'BOUNCE' and current_side:
                    for lv in levels:
                        b = lv['p'] * buffer_pct
                        if current_side == "BUY":
                            if test_p_down < (lv['p'] - b) and prev_close_ref >= (lv['p'] - b):
                                signal_side, label_tag, trigger_lv_p = "SELL", f"TRAP_{lv['n']}", lv['p']
                                exit_price_fixed = tick_round(lv['p'] - b)
                                break
                            elif high_p >= (lv['p'] + b) and close_p < lv['p']:
                                signal_side, label_tag, trigger_lv_p = "SELL", f"REJECTION_{lv['n']}", lv['p']
                                exit_price_fixed = tick_round(close_p)
                                break
                        elif current_side == "SELL":
                            if test_p_up > (lv['p'] + b) and prev_close_ref <= (lv['p'] + b):
                                signal_side, label_tag, trigger_lv_p = "BUY", f"TRAP_{lv['n']}", lv['p']
                                exit_price_fixed = tick_round(lv['p'] + b)
                                break
                            elif low_p <= (lv['p'] - b) and close_p > lv['p']:
                                signal_side, label_tag, trigger_lv_p = "BUY", f"REJECTION_{lv['n']}", lv['p']
                                exit_price_fixed = tick_round(close_p)
                                break

                # 2. BREAKOUT SAR (Detect flips even if open)
                if not signal_side:
                    # Scan for Breakouts
                    temp_side, temp_tag = None, None
                    # Search for BUY Breakout
                    for lv in reversed(levels):
                        b = lv['p'] * buffer_pct
                        if test_p_up > (lv['p'] + b) and (prev_close_ref <= (lv['p'] + b) or is_opening_candle):
                            temp_side, temp_tag = "BUY", lv['n']
                            exit_price_fixed = tick_round(close_p) if trigger_mode == 'CANDLE_CLOSE' else tick_round(max(open_p, lv['p'] + b))
                            break
                    # Search for SELL Breakout (if no BUY)
                    if not temp_side:
                        for lv in levels:
                            b = lv['p'] * buffer_pct
                            if test_p_down < (lv['p'] - b) and (prev_close_ref >= (lv['p'] - b) or is_opening_candle):
                                temp_side, temp_tag = "SELL", lv['n']
                                exit_price_fixed = tick_round(close_p) if trigger_mode == 'CANDLE_CLOSE' else tick_round(min(open_p, lv['p'] - b))
                                break
                    
                    if temp_side and temp_side != current_side:
                        signal_side, label_tag = temp_side, temp_tag

                # 3. SAFETY (SL/TGT)
                if open_trade and not signal_side:
                    sl = float(open_trade.get('stop_loss')) if open_trade.get('stop_loss') else None
                    tgt = float(open_trade.get('target')) if open_trade.get('target') else None
                    if sl and ((current_side == "BUY" and test_p_down <= sl) or (current_side == "SELL" and test_p_up >= sl)):
                        signal_side, label_tag, exit_price_fixed = "EXIT", "STOP_LOSS", sl
                    elif tgt and ((current_side == "BUY" and test_p_up >= tgt) or (current_side == "SELL" and test_p_down <= tgt)):
                        signal_side, label_tag, exit_price_fixed = "EXIT", "TARGET_BOOKED", tgt

                # --- EXECUTION ---
                if signal_side == "EXIT":
                    paper_service.close_virtual_trade(session_id, open_trade['id'], tick_round(exit_price_fixed), reason=label_tag)
                elif signal_side and signal_side != current_side:
                    # SAR Flip
                    paper_order_qty = 100
                    live_order_qty = 1 # Simplified helper call inside or pass session
                    try:
                        cap = getattr(session, 'trade_capital', 0)
                        live_order_qty = max(1, int(cap / exit_price_fixed)) if cap > 0 else getattr(session, 'trade_quantity', 1)
                    except: pass

                    print(f"[OK] Signal {signal_side} on {symbol} @ {exit_price_fixed} [{label_tag}]")
                    
                    if is_live:
                        if risk_service.check_safety(session_id):
                            qty = live_order_qty * 2 if (open_trade and open_trade['side'] != signal_side) else live_order_qty
                            if risk_service.check_margin(session_id, token, qty, exit_price_fixed):
                                print(f"🚀 [LIVE] [INIT] Placing LIVE {signal_side} order for {symbol} x {qty}...")
                                live_service.place_live_order(session_id, stock, signal_side, abs(qty), tag=f"SAR_{label_tag}", product_type="INTRADAY")
                            else:
                                print(f"⚠️ [LIVE] [SKIP] {symbol} failed margin check.")
                        else:
                            print(f"⚠️ [LIVE] [SKIP] {symbol} failed safety check.")

                    if open_trade:
                        paper_service.close_virtual_trade(session_id, open_trade['id'], exit_price_fixed, reason=label_tag)
                    
                    paper_service.create_virtual_trade(
                        session_id, stock, signal_side, label_tag, 
                        quantity=paper_order_qty, strategy_mode=mode, smart_sl=True, entry_price=exit_price_fixed
                    )
                else:
                    # No signal for this stock
                    if time.time() % 60 < 2: print(f"[STRATEGY] [DIAG] {symbol}: No Signal.")

            except Exception as e:
                import traceback
                print(f"[ERR] [STRATEGY] Failed processing {stock.get('symbol')} for session {session_id[:8]}: {e}")
                traceback.print_exc()

    def stop_websocket(self, session_id: str):
        with self.lock:
            if session_id in self.connections:
                try:
                    self.connections[session_id].close_connection()
                except: pass
                del self.connections[session_id]
                del self.token_maps[session_id]
                del self.broadcast_callbacks[session_id]
                if session_id in self.session_locks:
                    del self.session_locks[session_id]

    def stop_all(self):
        self.running = False
        with self.lock:
            self.connections.clear()
            self.token_maps.clear()
            self.broadcast_callbacks.clear()

ws_manager = WebSocketManager()