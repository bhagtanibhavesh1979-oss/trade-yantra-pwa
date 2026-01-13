from datetime import datetime
from typing import Optional
import threading

class PaperService:
    def __init__(self):
        self.lock = threading.Lock()

    def create_virtual_trade(self, session_id: str, stock: dict, side: str, alert_name: str):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
        
        with self.lock:
            # Check if there's already an open trade for this stock
            open_trade = next((t for t in session.paper_trades if str(t['token']) == str(stock['token']) and t['status'] == 'OPEN'), None)
            
            if open_trade:
                # Basic SAR (Stop and Reverse) logic: Close if signal is opposite
                if open_trade['side'] != side:
                    self.close_virtual_trade(session_id, open_trade['id'], stock['ltp'])
                return

            trade_id = f"v{int(datetime.now().timestamp())}_{stock['token']}"
            trade = {
                "id": trade_id,
                "symbol": stock['symbol'],
                "token": stock['token'],
                "side": side,
                "entry_price": stock['ltp'],
                "exit_price": None,
                "quantity": 100,
                "status": "OPEN",
                "pnl": 0.0,
                "created_at": datetime.now().isoformat(),
                "closed_at": None,
                "trigger_level": alert_name
            }
            
            session.paper_trades.insert(0, trade)
            
            # Add a log entry
            log_msg = f"Virtual {side} Order for {stock['symbol']} executed at ₹{stock['ltp']} ({alert_name})"
            session.logs.insert(0, {
                "timestamp": datetime.now().isoformat(),
                "symbol": stock['symbol'],
                "message": log_msg,
                "type": "paper_trade",
                "current_price": stock['ltp']
            })
            
            session_manager.save_session(session_id)
            print(f"💰 PAPER TRADE OPENED: {side} {stock['symbol']} at {stock['ltp']} via {alert_name}")

    def close_virtual_trade(self, session_id: str, trade_id: str, exit_price: float):
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
                    
                    # Calculate PNL
                    if trade['side'] == 'BUY':
                        trade['pnl'] = (float(exit_price) - float(trade['entry_price'])) * int(trade['quantity'])
                    else:
                        trade['pnl'] = (float(trade['entry_price']) - float(exit_price)) * int(trade['quantity'])
                        
                    log_msg = f"Virtual position for {trade['symbol']} CLOSED at ₹{exit_price}. PNL: ₹{trade['pnl']:.2f}"
                    session.logs.insert(0, {
                        "timestamp": datetime.now().isoformat(),
                        "symbol": trade['symbol'],
                        "message": log_msg,
                        "type": "paper_trade_close",
                        "current_price": exit_price,
                        "pnl": trade['pnl']
                    })
                    
                    session_manager.save_session(session_id)
                    print(f"📉 PAPER TRADE CLOSED: {trade['symbol']} at {exit_price}. PNL: {trade['pnl']}")
                    break

    def update_live_pnl(self, session_id: str, token_map: dict):
        """Calculates floating PNL for all open virtual positions"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        with self.lock:
            for trade in session.paper_trades:
                if trade['status'] == 'OPEN':
                    stock_info = token_map.get(str(trade['token']))
                    if stock_info and stock_info.get('ltp'):
                        ltp = float(stock_info['ltp'])
                        entry = float(trade['entry_price'])
                        qty = int(trade['quantity'])
                        if trade['side'] == 'BUY':
                            trade['pnl'] = (ltp - entry) * qty
                        else:
                            trade['pnl'] = (entry - ltp) * qty

paper_service = PaperService()
