from datetime import datetime
from typing import Optional
import threading

class PaperService:
    def __init__(self):
        self.lock = threading.Lock()

    def create_virtual_trade(self, session_id: str, stock: dict, side: str, alert_name: str, quantity: int = 100):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
        
        with self.lock:
            # Check balance
            if getattr(session, 'virtual_balance', 0.0) <= 0:
                print(f"[WARN] SKIPPING TRADE: Virtual balance is 0 or negative for {session_id}")
                return

            # Check if there's already an open trade for this stock
            open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
            
            if open_trade:
                # Basic SAR (Stop and Reverse) logic: Close if signal is opposite
                if open_trade['side'] != side:
                    self.close_virtual_trade(session_id, open_trade['id'], stock['ltp'])
                return

            # Determine trade parameters
            # Quantity is passed from argument (default 100) or override logic
            entry_price = float(stock['ltp'])
            required_margin = entry_price * quantity
            
            # Check for insufficient funds
            current_balance = getattr(session, 'virtual_balance', 0.0)
            if current_balance < required_margin:
                print(f"[WARN] INSUFFICIENT FUNDS: Need {required_margin}, have {current_balance}")
                # Optional: Log this failure
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
                "status": "OPEN",
                "pnl": 0.0,
                "created_at": datetime.now().isoformat(),
                "closed_at": None,
                "trigger_level": alert_name
            }
            
            # DEDUCT MARGIN FROM BALANCE IMMEDIATELY
            session.virtual_balance = current_balance - required_margin
            
            session.paper_trades.insert(0, trade)
            
            # Add a log entry
            log_msg = f"Virtual {side} Order for {quantity} Qty of {stock['symbol']} executed at ₹{stock['ltp']} ({alert_name})"
            session.logs.insert(0, {
                "timestamp": datetime.now().isoformat(),
                "symbol": stock['symbol'],
                "message": log_msg,
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
                    # Because we deducted the full margin on entry, we add back the full exit value
                    # For SELL orders (shorting), the math is: Margin + PnL
                    # Long: Balance + (Exit * Qty)
                    # Short: Balance + (Entry * Qty) + (Entry - Exit)*Qty = Balance + (2*Entry - Exit)*Qty -> This is complex for simple spots.
                    # Simplified Cash Model:
                    # We just add the PNL back to the balance? NO. We deducted margin.
                    # So New Balance = Old Balance (which already has margin deducted) + Margin + PnL
                    
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
                                    # Use a separate thread or handle carefully to avoid recursion/deadlock
                                    # Since we are already in self.lock, we need to be careful.
                                    # close_virtual_trade also uses self.lock.
                                    # Let's use a list of trades to close after the loop.
                                    trades_to_close.append((trade['id'], ltp, "STOPLOSS"))
                                elif trade['side'] == 'SELL' and ltp >= float(sl):
                                    trades_to_close.append((trade['id'], ltp, "STOPLOSS"))
            
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
            session.virtual_balance = amount
            session_manager.save_session(session_id)
            print(f"[BALANCE] Virtual Balance set to {amount} for {session_id}")

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

paper_service = PaperService()
