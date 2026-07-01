from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.session_manager import session_manager
from backend.services.live_service import live_service
from backend.services.risk_service import risk_service
from backend.services.angel_service import angel_service

router = APIRouter(prefix="/api/live", tags=["Live Trading"])

class ToggleLiveRequest(BaseModel):
    enabled: bool

@router.post("/toggle/{session_id}")
async def toggle_live_trading(session_id: str, req: ToggleLiveRequest):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update Session State
    session.auto_live_trade = req.enabled
    
    # Update Service Master Switch
    live_service.toggle_live_trading(req.enabled)
    
    session_manager.save_session(session_id)
    return {"status": "success", "auto_live_trade": session.auto_live_trade}

class TradeSettingsRequest(BaseModel):
    trade_quantity: Optional[int] = 100
    trade_capital: Optional[float] = 0.0

@router.post("/settings/{session_id}")
async def update_live_settings(session_id: str, req: TradeSettingsRequest):
    """
    Update Trade Settings (Quantity OR Capital per trade)
    """
    session = session_manager.get_session(session_id)
    if not session:
         raise HTTPException(status_code=404, detail="Session not found")
    
    # Update Session State
    if req.trade_quantity is not None:
        session.trade_quantity = req.trade_quantity
    
    if req.trade_capital is not None:
        session.trade_capital = req.trade_capital
        
    session_manager.save_session(session_id)
    return {
        "status": "success", 
        "trade_quantity": session.trade_quantity,
        "trade_capital": getattr(session, 'trade_capital', 0)
    }

class ManualOrderRequest(BaseModel):
    symbol: str
    token: str
    exch_seg: str = "NSE"
    side: str # "BUY" or "SELL"
    quantity: int
    product_type: str = "INTRADAY"
    order_type: str = "MARKET"
    price: float = 0.0

@router.post("/order/{session_id}")
async def place_manual_order(session_id: str, req: ManualOrderRequest):
    """
    Manually place a REAL order via LiveService.
    Includes Risk Checks.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 1. Risk Check (Master Switch)
    # We allow manual API orders even if auto-trade is off? 
    # Usually safer to require Master Switch ON, but for manual maybe optional?
    # Let's enforce it for safety consistency
    if not session.auto_live_trade:
         raise HTTPException(status_code=400, detail="Live Execution is DISABLED. Toggle 'GO LIVE' first.")

    # 2. Margin Check
    price = req.price
    if price <= 0:
        # Fetch LTP for Margin Check
        try:
            ltp_res = angel_service.get_ltp_data(session.smart_api, req.exch_seg, req.symbol, req.token)
            if ltp_res and 'ltp' in ltp_res:
                price = float(ltp_res['ltp'])
        except Exception as e:
            print(f"⚠️ [LIVE] LTP fetch failed for manual order: {e}")

    # Only check margin if we have a valid price
    if price > 0:
        if not risk_service.check_margin(session_id, req.symbol, req.quantity, price, req.product_type):
             raise HTTPException(status_code=400, detail="Insufficient Funds / Margin")

    # 3. Place Order
    result = live_service.place_live_order(
        session_id, 
        {"symbol": req.symbol, "token": req.token, "exch_seg": req.exch_seg}, 
        req.side, 
        req.quantity, 
        req.product_type,
        req.price,
        req.order_type,
        tag="MANUAL_API"
    )
    
    if result and result.get("status") == "success":
        return result
    else:
        raise HTTPException(status_code=400, detail=result.get("message", "Order Placement Failed"))

@router.get("/status/{session_id}")
async def get_live_status(session_id: str):
    """
    Get current Live Trading Status and Settings for a session.
    Used by frontend to sync UI state on load.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "status": "success",
        "auto_live_trade": getattr(session, 'auto_live_trade', False),
        "trade_quantity": getattr(session, 'trade_quantity', 100),
        "trade_capital": getattr(session, 'trade_capital', 0.0)
    }

@router.get("/positions/{session_id}")
async def get_positions(session_id: str):
    return live_service.get_live_positions(session_id)

@router.get("/orders/{session_id}")
async def get_orders(session_id: str):
    return live_service.get_live_orders(session_id)

@router.get("/funds/{session_id}")
async def get_funds(session_id: str):
    return live_service.get_funds(session_id)
