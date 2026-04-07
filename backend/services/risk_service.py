from typing import Dict, Optional

class RiskService:
    def __init__(self):
        self.MAX_DAILY_LOSS = 2000.0 # Default Max Loss limit (hard stop)
        self.MAX_QTY_PER_TRADE = 500 # Default max quantity
        
    def check_safety(self, session_id: str) -> bool:
        """Global Safety Check (Kill Switch)"""
        from services.session_manager import session_manager
        session = session_manager.get_session(session_id)
        if not session: return False
        
        # 1. Kill Switch
        if not getattr(session, 'auto_live_trade', False):
            # Silent return because this is checked frequently in loops
            return False

        return True

    def check_margin(self, session_id: str, symbol: str, quantity: int, price: float, product_type: str = "INTRADAY") -> bool:
        """
        Check if sufficient margin exists.
        Formula:
            Required = Price * Qty * Margin%
            Available = Net Available Funds
        """
        from services.session_manager import session_manager
        from services.angel_service import angel_service
        session = session_manager.get_session(session_id)
        if not session or not session.smart_api: return False

        try:
            # 1. Get Available Funds
            rms = angel_service.get_rms_limit(session.smart_api)
            # rms structure: {'net': '1234.56', ...}
            if not rms: 
                print(f"[ERR] [RISK] Could not fetch RMS limits")
                return False 
            
            available_cash = float(rms.get('net', 0.0))
            
            # 2. Calculate Required Margin
            # Estimate: Intraday (MIS) ~ 20% (5x leverage), Delivery ~ 100%
            leverage = 0.20 if product_type == "INTRADAY" else 1.0
            required_margin = price * quantity * leverage
            
            if available_cash >= required_margin:
                return True
            else:
                print(f"[ERR] [RISK] Insufficient Funds for {symbol}: Req {required_margin:.2f} > Avail {available_cash:.2f}")
                return False
                
        except Exception as e:
            print(f"[ERR] [RISK] Margin Check Error: {e}")
            return False

risk_service = RiskService()
