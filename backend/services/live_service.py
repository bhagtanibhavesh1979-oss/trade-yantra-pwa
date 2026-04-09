from typing import Optional, Dict, List
import threading
from datetime import datetime, timezone
from services.angel_service import angel_service, TokenExpiredException


class LiveService:
    def __init__(self):
        self.lock = threading.RLock()
        self.LIVE_ENABLED = False # Master Kill Switch (Hardcoded Safety first)

    def toggle_live_trading(self, enabled: bool):
        self.LIVE_ENABLED = enabled
        print(f"⚠️ [LIVE] Master Switch Toggled: {'ON' if enabled else 'OFF'}")

    def place_live_order(self, session_id: str, stock: dict, side: str, 
                         quantity: int, product_type: str = "INTRADAY", 
                         price: float = 0.0, order_type: str = "MARKET",
                         tag: str = "MANUAL"):
        from services.session_manager import session_manager

        
        # 1. Check Safety Switches
        if not self.LIVE_ENABLED:
            print(f"🛑 [LIVE] Order Blocked: Master Switch is OFF")
            return {"status": "error", "message": "Live Trading Disabled (Safety Switch)"}

        session = session_manager.get_session(session_id)
        if not session or not session.smart_api:
            print(f"❌ [LIVE] No active session/API for {session_id}")
            return {"status": "error", "message": "Session Inactive"}

        # 2. Prepare Order Params
        transaction_type = "BUY" if side.upper() == "BUY" else "SELL"
        
        # Normalize Exchange (sometimes comes as NSE-EQ) early for LTP fetching
        exchange = stock.get('exch_seg', 'NSE')
        
        # 2a. [SMARTAPI 2026 COMPLIANCE] Convert MARKET to LIMIT
        if order_type.upper() == "MARKET":
            try:
                # Need LTP to set a competitive limit price
                current_ltp = price
                if current_ltp <= 0:
                    # Fetch fresh LTP if not provided
                    ltp_res = angel_service.get_ltp_data(session.smart_api, exchange, stock['symbol'], str(stock['token']))
                    if ltp_res and 'ltp' in ltp_res:
                        current_ltp = float(ltp_res['ltp'])
                
                if current_ltp > 0:
                    # Apply fixed paise offset (e.g. 0.30) to get filled like a market order
                    # BUY at LTP + offset | SELL at LTP - offset
                    offset = getattr(session, 'market_offset', 0.30)
                    if transaction_type == "BUY":
                        limit_price = current_ltp + offset
                    else:
                        limit_price = current_ltp - offset
                    
                    # Round to nearest 0.05 tick size
                    price = round(limit_price * 20) / 20.0
                    order_type = "LIMIT"
                    print(f"🔄 [LIVE] Market-to-Limit Conversion: {stock['symbol']} @ {price} (LTP: {current_ltp})")
            except Exception as le:
                 print(f"⚠️ [LIVE] LTP fetch failed for Market conversion: {le}")
        
        # Normalize Product Type
        # Angel SmartAPI Types: "INTRADAY", "CARRYFORWARD", "DELIVERY", "MARGIN", "BO"
        # "INTRADAY" gives max leverage (MIS)
        # "DELIVERY" is Cash (CNC)
        # "MARGIN" is Margin (NRML)
        p_type = product_type.upper()
        if p_type == "CNC": p_type = "DELIVERY"
        if p_type == "MIS": p_type = "INTRADAY"
        if p_type == "NRML": p_type = "MARGIN"

        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": stock['symbol'],
            "symboltoken": str(stock['token']),
            "transactiontype": transaction_type,
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": p_type, 
            "duration": "DAY",
            "price": str(price) if order_type == "LIMIT" else "0",
            "quantity": str(quantity),
            "ordertag": tag[:20] 
        }
        
        def _place():
            # 3. Call Broker API
            order_id = angel_service.place_order(session.smart_api, order_params)
            
            if order_id:
                # Log success
                log_msg = f"🚀 [LIVE] {side} Order Placed: {stock['symbol']} x {quantity} ({p_type})"
                session.logs.insert(0, {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "symbol": stock['symbol'],
                    "msg": log_msg,
                    "type": "live_trade",
                    "details": order_id
                })
                session_manager.save_session(session_id)
                return {"status": "success", "order_id": order_id}
            return {"status": "error", "message": "No order ID returned"}
        
        try:
            return _place()
        except TokenExpiredException:
            print(f"🔄 [LIVE] Token expired during ORDER for {session.client_id}. Attempting auto-refresh...")
            if session_manager.refresh_session_tokens(session_id):
                # Retry once with new token
                return _place()
            else:
                return {"status": "error", "message": "Session Expired during order. Please re-login."}
        except Exception as e:
            # Catch REJECTED orders and log specific reason
            err_msg = str(e)
            print(f"❌ [LIVE] Order Rejected: {err_msg}")
            
            log_msg = f"❌ [LIVE] Order Failed: {err_msg}"
            session.logs.insert(0, {
                "time": datetime.now(timezone.utc).isoformat(),
                "symbol": stock['symbol'],
                "msg": log_msg,
                "type": "error"
            })
            session_manager.save_session(session_id)
            return {"status": "error", "message": err_msg}

    def get_live_positions(self, session_id: str):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session or not session.smart_api: return []
        
        try:
            return angel_service.get_position(session.smart_api) or []
        except TokenExpiredException:
            print(f"🔄 [LIVE] Token expired for {session.client_id}. Attempting auto-refresh...")
            if session_manager.refresh_session_tokens(session_id):
                # Retry once with new token
                return angel_service.get_position(session.smart_api) or []
            else:
                print(f"❌ [LIVE] Auto-refresh failed for {session.client_id}")
                return []

    def get_live_orders(self, session_id: str):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session or not session.smart_api: return []
        
        try:
            return angel_service.get_order_book(session.smart_api) or []
        except TokenExpiredException:
            print(f"🔄 [LIVE] Token expired (orders) for {session.client_id}. Attempting auto-refresh...")
            if session_manager.refresh_session_tokens(session_id):
                return angel_service.get_order_book(session.smart_api) or []
            else:
                return []
        
    def get_funds(self, session_id: str):
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session or not session.smart_api:
            print(f"[DEBUG] get_funds: No session or API for {session_id}")
            return {"error": "No active session"}
        
        def _fetch():
            rms_data = angel_service.get_rms_limit(session.smart_api)
            if not rms_data: return {"net": 0, "error": "Empty RMS data"}
            
            net_balance = 0
            if isinstance(rms_data, dict):
                if 'data' in rms_data and isinstance(rms_data['data'], dict):
                    net_balance = float(rms_data['data'].get('net', 0))
                elif 'net' in rms_data:
                    net_balance = float(rms_data.get('net', 0))
                elif 'availablecash' in rms_data:
                    net_balance = float(rms_data.get('availablecash', 0))
            return {'net': net_balance, 'raw': rms_data}

        try:
            return _fetch()
        except TokenExpiredException:
            print(f"🔄 [LIVE] Token expired (funds) for {session.client_id}. Attempting auto-refresh...")
            if session_manager.refresh_session_tokens(session_id):
                return _fetch()
            else:
                return {"net": 0, "error": "Session Expired", "code": "AG8001"}
        except Exception as e:
            print(f"[ERROR] get_funds failed: {e}")
            return {"net": 0, "error": str(e)}

    def close_all_live_positions(self, session_id: str):
        """Fetches and squares off all open intraday positions at the broker"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session or not session.smart_api: 
            print(f"❌ [LIVE-SQ] No session for {session_id[:8]}")
            return

        print(f"🚀 [LIVE-SQ] Starting Auto Square-off for {session.client_id}...")
        
        try:
            positions = self.get_live_positions(session_id)
            if not positions:
                print(f"✅ [LIVE-SQ] No open positions found for {session.client_id}")
                return

            closed_count = 0
            for pos in positions:
                # Angel positions use 'netqty' (string)
                qty = int(pos.get('netqty', 0))
                if qty == 0: continue
                
                symbol = pos.get('tradingsymbol')
                token = pos.get('symboltoken')
                exch = pos.get('exchange', 'NSE')
                p_type = pos.get('producttype', 'INTRADAY')
                
                # We typically only square off INTRADAY (MIS) or MARGIN (NRML) positions for day trading
                # But let's be safe and only square off what the user expects.
                if p_type not in ['INTRADAY', 'MARGIN', 'MIS', 'NRML']:
                    print(f"ℹ️ [LIVE-SQ] Skipping {symbol} ({p_type}) - Not an intraday product")
                    continue

                side = "SELL" if qty > 0 else "BUY"
                abs_qty = abs(qty)
                
                print(f"📡 [LIVE-SQ] Squaring off {symbol} x {abs_qty} ({side})")
                
                stock_dict = {
                    "symbol": symbol,
                    "token": token,
                    "exch_seg": exch
                }
                
                res = self.place_live_order(
                    session_id, stock_dict, side, abs_qty, 
                    product_type=p_type, 
                    tag="EOD_SQUARE_OFF"
                )
                
                if res.get('status') == 'success':
                    closed_count += 1
                else:
                    print(f"❌ [LIVE-SQ] Failed to square off {symbol}: {res.get('message')}")

            print(f"🏁 [LIVE-SQ] Finished. Closed {closed_count} live positions.")
            
        except Exception as e:
            print(f"❌ [LIVE-SQ] Error during square-off: {e}")

live_service = LiveService()
