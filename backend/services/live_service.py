from typing import Optional, Dict, List
import threading
from datetime import datetime, timezone

class LiveService:
    def __init__(self):
        self.lock = threading.RLock()

    def place_live_order(self, session_id: str, stock: dict, side: str, 
                         quantity: int, product_type: str = "INTRADAY", 
                         price: float = 0.0, order_type: str = "MARKET",
                         tag: str = "MANUAL", is_square_off: bool = False,
                         client_id: Optional[str] = None):
        from services.session_manager import session_manager
        from services.angel_service import angel_service

        # 1. Check Safety Switches
        session = session_manager.get_session(session_id, client_id=client_id)
        if not session or not session.smart_api:
            return None
        
        try:
            # 2. Risk Check (Optional: Placeholder)
            from services.risk_service import risk_service
            if not risk_service.check_safety(session_id):
                print(f"[LIVE] [ORDER] Safety Switch BLOCKED trade for {stock['symbol']}")
                return None

            # 3. Handle Square Off
            if is_square_off:
                # Square off logic usually sends opposite side
                pass
            
            # 4. Angel One API Order Placement
            # Simplified for restoration parity
            order_params = {
                "exchange": stock.get('exch_seg', 'NSE'),
                "symboltoken": stock['token'],
                "transactiontype": side.upper(),
                "quantity": quantity,
                "disclosedquantity": 0,
                "price": price if order_type == "LIMIT" else 0,
                "ordertype": order_type.upper(),
                "producttype": product_type.upper(),
                "duration": "DAY",
                "variety": "NORMAL",
                "trading_symbol": stock['symbol']
            }
            
            print(f"[LIVE] [ORDER] Placing {side} {quantity} {stock['symbol']} at {order_type}")
            order_id = angel_service.place_order(session.smart_api, order_params)
            
            if order_id:
                # 5. Log Order
                order_log = {
                    "time": datetime.utcnow().isoformat() + "Z",
                    "symbol": stock['symbol'],
                    "side": side,
                    "qty": quantity,
                    "price": price or stock.get('ltp', 0),
                    "id": order_id,
                    "tag": tag,
                    "type": order_type
                }
                session.live_orders.insert(0, order_log)
                session_manager.save_session(session_id)
                return order_id
            
            return None
            
        except Exception as e:
            print(f"[LIVE] [ERROR] Order Placement Failed: {e}")
            return None

live_service = LiveService()
