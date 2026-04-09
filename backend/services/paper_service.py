from datetime import datetime, timedelta, timezone
from typing import Optional
import threading
import logging
import os
from services.persistence_service import persistence_service

# Setup Logger
logger = logging.getLogger("paper_service")
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
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
except Exception as e:
    print(f"[ERR] Failed to initialize logging for paper_service: {e}")

def tick_round(price):
    if price is None: return None
    return round(float(price) * 20) / 20.0

class PaperService:
    def __init__(self):
        self.lock = threading.RLock()
        self.logger = logger
        self.MARGIN_MULTIPLIER = 0.05  # 5% margin (20x leverage) for paper trading

    def create_virtual_trade(self, session_id: str, stock: dict, side: str, alert_name: str, quantity: int = 100, target_price: Optional[float] = None, stop_loss: Optional[float] = None, strategy_mode: str = "SAR", smart_sl: bool = False, entry_price: Optional[float] = None):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
        
        with self.lock:
            # 1. Cross-Session Deduplication: Check if this token was recently traded in history by this client
            if persistence_service.is_recently_traded(session.client_id, stock['token'], seconds=5):
                self.logger.info(f"[SHIELD] [DEDUPE] Ignoring redundant {side} trigger for {stock['symbol']} (Already in history)")
                return

            # 2. Check if there's already an open trade for this stock in memory
            open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
            
            if open_trade:
                # Same Side: AVERAGE THE POSITION
                if open_trade['side'] == side:
                    new_qty = quantity
                    new_price = entry_price if entry_price is not None else float(stock['ltp'])
                    old_qty = int(open_trade.get('quantity', 100)) # Default 100 if missing
                    if old_qty == 0: old_qty = 100
                    
                    required_margin = new_price * new_qty * self.MARGIN_MULTIPLIER
                    current_balance = getattr(session, 'virtual_balance', 0.0)
                    
                    if current_balance < required_margin:
                        self.logger.warning(f"[WARN] INSUFFICIENT FUNDS for averaging {stock['symbol']} (Required: {required_margin:.2f}, Available: {current_balance:.2f}) for client {session.client_id}")
                        return

                    # Update existing trade (Weighted Average)
                    old_price = float(open_trade.get('entry_price', 0))
                    total_qty = old_qty + new_qty
                    avg_price = ((old_price * old_qty) + (new_price * new_qty)) / total_qty
                    
                    open_trade['quantity'] = total_qty
                    open_trade['entry_price'] = avg_price
                    # Append trigger level if not already there
                    if alert_name not in open_trade.get('trigger_level', ''):
                        open_trade['trigger_level'] = f"{open_trade.get('trigger_level', '')} + {alert_name}"
                    
                    # Deduct margin for averaging
                    session.virtual_balance = current_balance - required_margin
                    
                    # Log the averaging move
                    log_msg = f" Averaged {side}: Added {new_qty} {stock['symbol']} @ {new_price:.2f}. New Avg: {avg_price:.2f}, Total: {total_qty}"
                    session.logs.insert(0, {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "symbol": stock['symbol'],
                        "msg": log_msg,
                        "type": "paper_trade_average",
                        "current_price": new_price
                    })
                    
                    # Update trade mode to show it was averaged
                    open_trade['mode'] = 'AVERAGED'
                    
                    # Update Stop Loss and Target if provided
                    if stop_loss:
                        open_trade['stop_loss'] = stop_loss
                    if target_price:
                        open_trade['target'] = target_price
                    
                    # --- CRITICAL: Save to permanent history immediately ---
                    try:
                        persistence_service.add_to_trade_history(session.client_id, open_trade)
                    except Exception as e:
                        self.logger.error(f"[ERROR] Failed to add averaged trade to history for client {session.client_id}: {e}")

                    session_manager.save_session(session_id)
                    self.logger.info(f"[TRADE] POSITION AVERAGED for client {session.client_id}: {stock['symbol']} {total_qty} @ {avg_price}. Bal: {session.virtual_balance:.2f}")
                    return
                else:
                    # Opposite Side: Close existing (Stop and Reverse)
                    self.logger.info(f"[SAR] TRIGGERED for client {session.client_id}: Closing {open_trade['side']} to open {side} for {stock['symbol']}")
                    # Use alert_name directly to match Lab reasons (e.g. TRAP_M)
                    self.close_virtual_trade(session_id, open_trade['id'], tick_round(stock.get('ltp', 0)), reason=alert_name)
                    # DO NOT RETURN - Fall through to open the new position on the other side
                    pass

            # Check balance (Default to 10M for indices support)
            if not hasattr(session, 'virtual_balance') or session.virtual_balance is None:
                 session.virtual_balance = 10000000.0
            
            if entry_price is None:
                entry_price = float(stock.get('ltp', 0))
            
            required_margin = entry_price * quantity * self.MARGIN_MULTIPLIER
            
            # Check for insufficient funds
            current_balance = session.virtual_balance
            if current_balance < required_margin:
                self.logger.warning(f"[WARN] INSUFFICIENT FUNDS for new {side} trade for {stock['symbol']} (Required: {required_margin:.2f}, Available: {current_balance:.2f}) for client {session.client_id}")
                return

            trade_id = f"v{int(datetime.now().timestamp())}_{stock['token']}"

            trade = {
                "id": trade_id,
                "symbol": stock['symbol'],
                "token": stock['token'],
                "side": side,
                "entry_price": tick_round(entry_price),
                "exit_price": None,
                "quantity": quantity,
                "stop_loss": tick_round(stop_loss),
                "target": tick_round(target_price),
                "status": "OPEN",
                "pnl": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "closed_at": None,
                "trigger_level": alert_name,
                "mode": "NEW",
                "strategy_mode": strategy_mode,
                "smart_sl": smart_sl
            }
            
            # DEDUCT MARGIN FROM BALANCE
            session.virtual_balance = current_balance - required_margin
            
            session.paper_trades.insert(0, trade)
            
            # --- CRITICAL: Save to permanent history immediately ---
            try:
                persistence_service.add_to_trade_history(session.client_id, trade)
            except Exception as e:
                self.logger.error(f"[ERROR] Failed to add new trade to history for client {session.client_id}: {e}")

            # Add a log entry
            target_msg = f" | TGT: {target_price:.2f}" if target_price else ""
            log_msg = f"[EXEC] Virtual {side} Order for {quantity} Qty of {stock['symbol']} executed at {stock['ltp']} ({alert_name}){target_msg}"
            session.logs.insert(0, {
                "time": datetime.now(timezone.utc).isoformat(),
                "symbol": stock['symbol'],
                "msg": log_msg,
                "type": "paper_trade",
                "current_price": stock['ltp']
            })
            
            session_manager.save_session(session_id)
            self.logger.info(f"[TRADE] PAPER TRADE OPENED for client {session.client_id}: {side} {stock['symbol']} at {stock['ltp']}. Bal: {session.virtual_balance:.2f}")

    def close_virtual_trade(self, session_id: str, trade_id: str, exit_price: float, reason: str = "MANUAL"):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            for trade in session.paper_trades:
                if trade['id'] == trade_id and trade['status'] == 'OPEN':
                    exit_price = tick_round(exit_price)
                    trade['status'] = 'CLOSED'
                    trade['exit_price'] = exit_price
                    trade['closed_at'] = datetime.now(timezone.utc).isoformat()
                    trade['exit_reason'] = reason
                    
                    qty = int(trade.get('quantity', 100))
                    if qty == 0: qty = 100
                    entry_price = float(trade['entry_price'])
                    exit_price = float(exit_price)
                    
                    # Calculate PNL
                    if trade['side'] == 'BUY':
                        trade['pnl'] = (exit_price - entry_price) * qty
                    else:
                        trade['pnl'] = (entry_price - exit_price) * qty
                        
                    # CREDIT MARGIN AND PNL BACK TO BALANCE
                    try:
                        margin_released = entry_price * qty * self.MARGIN_MULTIPLIER
                        pnl = float(trade.get('pnl', 0.0))
                        current_bal = float(getattr(session, 'virtual_balance', 500000.0))
                        session.virtual_balance = current_bal + margin_released + pnl
                    except Exception as e:
                        self.logger.error(f"[ERROR] Failed to update balance during close for client {session.client_id}, trade {trade_id}: {e}")

                    log_msg = f"Virtual position for {trade['symbol']} CLOSED ({reason}) at {exit_price}. PNL: {trade['pnl']:.2f}"
                    session.logs.insert(0, {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "symbol": trade['symbol'],
                        "message": log_msg,
                        "type": "paper_trade_close",
                        "current_price": exit_price,
                        "pnl": trade['pnl']
                    })
                    
                    session_manager.save_session(session_id)
                    
                    # --- PERMANENT HISTORY RECORDING ---
                    try:
                        persistence_service.add_to_trade_history(session.client_id, trade)
                    except Exception as e:
                        self.logger.warning(f"[WARN] Failed to record trade in history for client {session.client_id}, trade {trade_id}: {e}")

                    self.logger.info(f"[CLOSE] PAPER TRADE CLOSED for client {session.client_id}: {trade['symbol']} at {exit_price}. PNL: {trade['pnl']:.2f} ({reason})")
                    break

    def update_live_pnl(self, session_id: str, token_map: dict):
        """Calculates floating PNL for all open virtual positions"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            trades_to_close = []
            for trade in session.paper_trades:
                if trade['status'] == 'OPEN':
                    stock_token = str(trade['token'])
                    stock_info = token_map.get(stock_token)
                    if stock_info:
                        ltp = stock_info.get('ltp')
                        if ltp is not None:
                            ltp = float(ltp)
                            entry = float(trade['entry_price'])
                            qty = int(trade.get('quantity', 1))
                            if trade['side'] == 'BUY':
                                trade['pnl'] = (ltp - entry) * qty
                            else:
                                trade['pnl'] = (entry - ltp) * qty
                            
                            # Check Stoploss
                            sl = trade.get('stop_loss')
                            if sl is not None and not trade.get('smart_sl', False):
                                if trade['side'] == 'BUY' and ltp <= float(sl):
                                    trades_to_close.append((trade['id'], ltp, "STOPLOSS"))
                                elif trade['side'] == 'SELL' and ltp >= float(sl):
                                    trades_to_close.append((trade['id'], ltp, "STOPLOSS"))

                            # Check Target
                            tgt = trade.get('target')
                            if tgt is not None:
                                if trade['side'] == 'BUY' and ltp >= float(tgt):
                                    trades_to_close.append((trade['id'], ltp, "TARGET_HIT"))
                                elif trade['side'] == 'SELL' and ltp <= float(tgt):
                                    trades_to_close.append((trade['id'], ltp, "TARGET_HIT"))
        
        for t_id, price, close_reason in trades_to_close:
            self.close_virtual_trade(session_id, t_id, price, close_reason)

    def set_virtual_balance(self, session_id: str, amount: float, client_id: Optional[str] = None):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id, client_id=client_id)
        if not session:
            return
        
        with self.lock:
            old_balance = getattr(session, 'virtual_balance', 0.0)
            self.logger.info(f"[BALANCE] Setting balance for client {session.client_id} (session {session_id[:8]})...")
            
            # Allow any positive amount
            session.virtual_balance = amount if amount > 0 else 1000000.0
            session_manager.save_session(session_id)
            self.logger.info(f"[BALANCE] Updated: {old_balance:.2f} -> {amount:.2f}")

    def set_stop_loss(self, session_id: str, trade_id: str, sl_price: float):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            for trade in session.paper_trades:
                if trade['id'] == trade_id and trade['status'] == 'OPEN':
                    trade['stop_loss'] = sl_price
                    session_manager.save_session(session_id)
                    self.logger.info(f"[SL] STOPLOSS SET: {trade['symbol']} at {sl_price:.2f}")
                    break

    def set_target(self, session_id: str, trade_id: str, target_price: float):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            for trade in session.paper_trades:
                if trade['id'] == trade_id and trade['status'] == 'OPEN':
                    trade['target'] = target_price
                    session_manager.save_session(session_id)
                    self.logger.info(f"[TGT] TARGET SET: {trade['symbol']} at {target_price:.2f}")
                    break

    def close_all_open_trades(self, session_id: str, reason: str = "AUTO_SQUARE_OFF"):
        """Closes all open positions (Generic)"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session: return
        
        token_map = {str(s['token']): s for s in session.watchlist}
        self.close_all_open_trades_with_prices(session_id, token_map, reason)

    def check_and_square_off(self, session_id: str, token_map: dict):
        # Checks time and closes all positions if > 15:15 IST
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session: return

        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        
        # 1. Check Time (Square off window 3:15 PM - 3:35 PM)
        square_off_time = now_ist.replace(hour=15, minute=15, second=0, microsecond=0)
        end_time = now_ist.replace(hour=15, minute=35, second=0, microsecond=0)
        
        today_str = now_ist.strftime("%Y-%m-%d")
        
        if now_ist < square_off_time or now_ist > end_time:
            return

        # 2. Prevent Redundant Square-Off
        if getattr(session, 'last_auto_square_off', '') == today_str:
            return

        # 3. Trigger Square-Off for Paper and/or Live
        is_p = getattr(session, 'auto_paper_trade', False)
        is_l = getattr(session, 'auto_live_trade', False)
        
        if not is_p and not is_l:
            return

        performed_sq = False

        # --- LIVE SQUARE-OFF ---
        if is_l:
            try:
                from services.live_service import live_service
                live_service.close_all_live_positions(session_id)
                performed_sq = True
            except Exception as e:
                self.logger.error(f"❌ [AUTO] Live square-off failed for {session.client_id}: {e}")

        # --- PAPER SQUARE-OFF ---
        open_trades = [t for t in session.paper_trades if t.get('status') == 'OPEN']
        if is_p and open_trades:
            self.logger.info(f" [AUTO] Market Time {now_ist.strftime('%H:%M:%S')} - Triggering Paper Square-Off for {len(open_trades)} trades...")
            self.close_all_open_trades_with_prices(session_id, token_map, reason="EOD_SQUARE_OFF")
            performed_sq = True
        elif is_p:
            self.logger.info(f" [AUTO] No open paper trades for client {session.client_id}.")

        # 4. Mark as done for today
        session.last_auto_square_off = today_str
        session_manager.save_session(session_id)
        if performed_sq:
            self.logger.info(f" ✅ [AUTO] EOD Square-off sequence complete for {session.client_id}")

    def close_all_open_trades_with_prices(self, session_id: str, token_map: dict, reason: str = "EOD_SQUARE_OFF"):
        """Closes all open trades using the provided price map"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session: return
        
        trades_to_close = []
        with self.lock:
            # 1. Fetch In-Memory Trades
            for trade in session.paper_trades:
                if trade['status'] == 'OPEN':
                    token = str(trade['token'])
                    price = 0.0
                    if token in token_map:
                        price = float(token_map[token].get('ltp', 0.0))
                    
                    if price <= 0:
                        for stock in session.watchlist:
                            if str(stock['token']) == token:
                                price = float(stock.get('ltp', 0.0))
                                break
                    
                    if price > 0:
                        trades_to_close.append((trade['id'], price))
                    else:
                        trades_to_close.append((trade['id'], float(trade.get('entry_price', 0))))

            # 2. Fetch Historical Trades (Sync Cleanup)
            history = persistence_service.get_trade_history(session.client_id) or []
            memory_ids = {t['id'] for t in session.paper_trades}
            
            for h_trade in history:
                if h_trade.get('status') == 'OPEN' and h_trade.get('id') not in memory_ids:
                    token = str(h_trade.get('token'))
                    h_id = h_trade.get('id')
                    price = float(token_map.get(token, {}).get('ltp', 0.0))
                    if price <= 0:
                        price = float(h_trade.get('entry_price', 0))
                    trades_to_close.append((h_id, price, "HISTORICAL_SYNC"))

        # Close trades...
        for item in trades_to_close:
            try:
                if len(item) == 3: # Historical Sync
                    tid, price, res = item
                    self.close_virtual_trade(session_id, tid, price, reason=res)
                else:
                    tid, price = item
                    self.close_virtual_trade(session_id, tid, price, reason=reason)
            except Exception as e:
                self.logger.error(f"[ERROR] Failed to close trade {item[0]}: {e}")
                
        if trades_to_close:
            self.logger.info(f"[AUTO] Attempted to square off {len(trades_to_close)} positions for client {session.client_id}")

paper_service = PaperService()
