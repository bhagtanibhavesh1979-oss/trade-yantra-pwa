from datetime import datetime, timedelta
from typing import Optional
import threading

class PaperService:
    def __init__(self):
        self.lock = threading.RLock()

    def create_virtual_trade(self, session_id: str, stock: dict, side: str, alert_name: str, quantity: int = 100, target_price: Optional[float] = None):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
        
        with self.lock:
            # 1. Check if there's already an open trade for this stock
            open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
            
            if open_trade:
                # Same Side: AVERAGE THE POSITION
                if open_trade['side'] == side:
                    new_qty = quantity
                    new_price = float(stock['ltp'])
                    old_qty = int(open_trade.get('quantity', 100))
                    old_price = float(open_trade['entry_price'])
                    
                    required_margin = new_price * new_qty
                    current_balance = getattr(session, 'virtual_balance', 0.0)
                    
                    if current_balance < required_margin:
                        print(f"[WARN] INSUFFICIENT FUNDS for averaging {stock['symbol']}")
                        return

                    # Update existing trade (Weighted Average)
                    total_qty = old_qty + new_qty
                    avg_price = ((old_price * old_qty) + (new_price * new_qty)) / total_qty
                    
                    open_trade['quantity'] = total_qty
                    open_trade['entry_price'] = avg_price
                    # Append trigger level if not already there
                    if alert_name not in open_trade.get('trigger_level', ''):
                        open_trade['trigger_level'] = f"{open_trade.get('trigger_level', '')} + {alert_name}"
                    
                    # Deduct margin
                    session.virtual_balance = current_balance - required_margin
                    
                    # Log the averaging move
                    log_msg = f"🟢 Averaged {side}: Added {new_qty} {stock['symbol']} @ ₹{new_price:.2f}. New Avg: ₹{avg_price:.2f}, Total: {total_qty}"
                    session.logs.insert(0, {
                        "time": datetime.now().isoformat(),
                        "symbol": stock['symbol'],
                        "msg": log_msg,
                        "type": "paper_trade_average",
                        "current_price": new_price
                    })
                    
                    # Update trade mode to show it was averaged
                    open_trade['mode'] = 'AVERAGED'
                    
                    session_manager.save_session(session_id)
                    print(f"[TRADE] POSITION AVERAGED: {stock['symbol']} {total_qty} @ {avg_price}. Bal: {session.virtual_balance}")
                    return
                else:
                    # Opposite Side: Close existing (Stop and Reverse)
                    print(f"[TRADE] SAR TRIGGERED: Closing {open_trade['side']} to open {side} for {stock['symbol']}")
                    self.close_virtual_trade(session_id, open_trade['id'], stock['ltp'], reason=f"SAR_{alert_name}")
                    # DO NOT RETURN - Fall through to open the new position on the other side
                    pass

            # 2. Open New Position (or Reverse Position)
            # Check balance
            if getattr(session, 'virtual_balance', 0.0) <= 0:
                print(f"[WARN] SKIPPING TRADE: Virtual balance is 0 or negative for {session_id}")
                return

            entry_price = float(stock['ltp'])
            required_margin = entry_price * quantity
            
            # Check for insufficient funds
            current_balance = getattr(session, 'virtual_balance', 0.0)
            if current_balance < required_margin:
                print(f"[WARN] INSUFFICIENT FUNDS: Need {required_margin}, have {current_balance}")
                return

            trade_id = f"v{int(datetime.now().timestamp())}_{stock['token']}"

            trade = {
                "id": trade_id,
                "symbol": stock['symbol'],
                "token": stock['token'],
                "side": side,
                "entry_price": entry_price,
                "exit_price": None,
                "quantity": quantity,
                "stop_loss": None,
                "target": target_price,
                "status": "OPEN",
                "pnl": 0.0,
                "created_at": datetime.now().isoformat(),
                "closed_at": None,
                "trigger_level": alert_name,
                "mode": "NEW"
            }
            
            # DEDUCT MARGIN FROM BALANCE IMMEDIATELY
            session.virtual_balance = current_balance - required_margin
            
            session.paper_trades.insert(0, trade)
            
            # Add a log entry
            target_msg = f" | TGT: {target_price:.2f}" if target_price else ""
            log_msg = f"🚀 Virtual {side} Order for {quantity} Qty of {stock['symbol']} executed at ₹{stock['ltp']} ({alert_name}){target_msg}"
            session.logs.insert(0, {
                "time": datetime.now().isoformat(),
                "symbol": stock['symbol'],
                "msg": log_msg,
                "type": "paper_trade",
                "current_price": stock['ltp']
            })
            
            session_manager.save_session(session_id)
            print(f"[TRADE] PAPER TRADE OPENED: {side} {stock['symbol']} at {stock['ltp']}. Bal: {session.virtual_balance}")

    def close_virtual_trade(self, session_id: str, trade_id: str, exit_price: float, reason: str = "MANUAL"):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            for trade in session.paper_trades:
                if trade['id'] == trade_id and trade['status'] == 'OPEN':
                    trade['status'] = 'CLOSED'
                    trade['exit_price'] = exit_price
                    trade['closed_at'] = datetime.now().isoformat()
                    
                    qty = int(trade.get('quantity', 100))
                    entry_price = float(trade['entry_price'])
                    exit_price = float(exit_price)
                    
                    # Calculate PNL
                    if trade['side'] == 'BUY':
                        trade['pnl'] = (exit_price - entry_price) * qty
                    else:
                        trade['pnl'] = (entry_price - exit_price) * qty
                        
                    # CREDIT ENTIRE EXIT VALUE BACK TO BALANCE
                    margin_used = entry_price * qty
                    session.virtual_balance = getattr(session, 'virtual_balance', 0.0) + margin_used + trade['pnl']

                    log_msg = f"Virtual position for {trade['symbol']} CLOSED ({reason}) at ₹{exit_price}. PNL: ₹{trade['pnl']:.2f}"
                    session.logs.insert(0, {
                        "timestamp": datetime.now().isoformat(),
                        "symbol": trade['symbol'],
                        "message": log_msg,
                        "type": "paper_trade_close",
                        "current_price": exit_price,
                        "pnl": trade['pnl']
                    })
                    
                    session_manager.save_session(session_id)
                    
                    # --- PERMANENT HISTORY RECORDING ---
                    try:
                        from services.persistence_service import persistence_service
                        persistence_service.add_to_trade_history(session.client_id, trade)
                    except Exception as e:
                        print(f"[WARN] Failed to record trade in history: {e}")

                    print(f"[CLOSE] PAPER TRADE CLOSED: {trade['symbol']} at {exit_price}. PNL: {trade['pnl']} ({reason})")
                    break

    def update_live_pnl(self, session_id: str, token_map: dict):
        """Calculates floating PNL for all open virtual positions"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            trades_to_close = []
            # print(f"DEBUG: Updating Live PNL for {len(session.paper_trades)} trades")
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
                            if sl is not None:
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
            
            # Close trades outside the main loop to avoid double-locking if needed
            # (though with the same lock it might be fine on some systems, 
            # but let's be safe and use the collection approach)
        
        for t_id, price, reason in trades_to_close:
            self.close_virtual_trade(session_id, t_id, price, reason)

    def set_virtual_balance(self, session_id: str, amount: float):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
        
        with self.lock:
            old_balance = getattr(session, 'virtual_balance', 0.0)
            session.virtual_balance = amount
            # Force a synchronous save for critical balance updates
            persistence_service.save_session(session_id, session)
            print(f"[BALANCE] Virtual Balance updated for {session_id}: {old_balance} -> {amount}")

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
                    print(f"[SL] STOPLOSS SET: {trade['symbol']} at {sl_price}")
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
                    print(f"[TGT] TARGET SET: {trade['symbol']} at {target_price}")
                    break

    def close_all_open_trades(self, session_id: str, reason: str = "AUTO_SQUARE_OFF"):
        """Closes all open positions (Generic)"""
        # This version is usually called without a current price map
        # We will attempt to find prices in the session or use entry_price (last resort)
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session: return
        
        token_map = {str(s['token']): s for s in session.watchlist}
        self.close_all_open_trades_with_prices(session_id, token_map, reason)

    def check_and_square_off(self, session_id: str, token_map: dict):
        """Checks time and closes all positions if > 15:15 IST"""
        now = datetime.utcnow()
        # IST is UTC + 5:30
        ist_now = now + timedelta(hours=5, minutes=30)
        
        # 3:15 PM is usually auto-square off time for intraday
        # We also check if it's before end of market (usually 3:30) to ensure we have tick data
        if ist_now.hour == 15 and 15 <= ist_now.minute <= 45: 
             from services.session_manager import session_manager
             session = session_manager.get_session(session_id)
             if not session: return
             
             # Check if we already squared off today to avoid spamming logs
             today_date = ist_now.strftime('%Y-%m-%d')
             last_sq = getattr(session, 'last_auto_square_off', '')
             
             if last_sq != today_date:
                has_open = any(t['status'] == 'OPEN' for t in session.paper_trades)
                if has_open:
                    print(f"[AUTO] 🕒 3:15 PM IST reached. Squaring off positions for {session_id}")
                    self.close_all_open_trades_with_prices(session_id, token_map, reason="EOD_SQUARE_OFF")
                    session.last_auto_square_off = today_date
                    session_manager.save_session(session_id)

    def close_all_open_trades_with_prices(self, session_id: str, token_map: dict, reason: str = "EOD_SQUARE_OFF"):
         """Closes all open trades using the provided price map"""
         from services.session_manager import session_manager
         session = session_manager.get_session(session_id)
         if not session: return
         
         trades_to_close = []
         with self.lock:
             for trade in session.paper_trades:
                 if trade['status'] == 'OPEN':
                     token = str(trade['token'])
                     # Try to find LTP in token_map (WS) or watchlist
                     price = 0.0
                     if token in token_map:
                         price = float(token_map[token].get('ltp', 0.0))
                     
                     if price <= 0:
                         # Fallback: check session watchlist directly
                         for stock in session.watchlist:
                             if str(stock['token']) == token:
                                 price = float(stock.get('ltp', 0.0))
                                 break
                     
                     if price > 0:
                         trades_to_close.append((trade['id'], price))
                     else:
                         # Final resort: Exit at entry price (neutral) if no price available
                         # This is better than leaving it open and messy
                         trades_to_close.append((trade['id'], float(trade['entry_price'])))
            
         # Close outside lock iteration
         for tid, price in trades_to_close:
             self.close_virtual_trade(session_id, tid, price, reason=reason)
             
         if trades_to_close:
             print(f"[AUTO] Squared off {len(trades_to_close)} positions for {session_id}")

paper_service = PaperService()
