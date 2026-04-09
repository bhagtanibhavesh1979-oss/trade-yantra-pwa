"""
Live Trading Routes
API endpoints for live order execution and monitoring
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.session_manager import session_manager
from services.live_service import live_service
from typing import Optional, List

router = APIRouter(prefix="/api/live", tags=["Live Trading"])


class LiveTradeToggleRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    enabled: bool


class SetCapitalRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    capital: float = 0.0
    lot_size: int = 1


class ManualOrderRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    symbol: str
    token: str
    side: str                       # BUY or SELL
    quantity: int = 1
    price: float = 0.0
    order_type: str = "MARKET"      # MARKET or LIMIT
    product_type: str = "INTRADAY"
    exchange: str = "NSE"


class SquareOffRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    order_id: Optional[str] = None  # If None, square off all


@router.get("/status/{session_id}")
async def get_live_status(session_id: str, client_id: Optional[str] = None):
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "enabled": session.auto_live_trade,
        "capital": session.live_capital,
        "lot_size": session.live_lot_size,
        "trade_quantity": getattr(session, 'trade_quantity', session.live_lot_size),
        "orders": session.live_orders,
        "pnl": session.live_pnl
    }


@router.post("/toggle")
async def toggle_live_trading(req: LiveTradeToggleRequest):
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.smart_api and req.enabled:
        raise HTTPException(status_code=400, detail="Angel One not connected. Please login first.")

    session.auto_live_trade = req.enabled
    session_manager.save_session(req.session_id)

    return {
        "success": True,
        "enabled": session.auto_live_trade,
        "message": f"Live trading {'enabled ✅' if req.enabled else 'disabled ⛔'}"
    }


@router.post("/config")
async def set_live_config(req: SetCapitalRequest):
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.live_capital = req.capital
    session.live_lot_size = req.lot_size
    # IMPORTANT: Also sync trade_quantity so websocket_manager uses the correct qty
    session.trade_quantity = req.lot_size
    session.trade_capital = req.capital
    session_manager.save_session(req.session_id)

    return {
        "success": True,
        "capital": session.live_capital,
        "lot_size": session.live_lot_size,
        "trade_quantity": session.trade_quantity,
        "message": "Live trading configuration updated"
    }


@router.post("/order")
async def place_manual_order(req: ManualOrderRequest):
    """Place a manual live order"""
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    stock = {
        "symbol": req.symbol,
        "token": req.token,
        "exch_seg": req.exchange,
        "ltp": req.price
    }

    order_id = live_service.place_live_order(
        session_id=req.session_id,
        stock=stock,
        side=req.side,
        quantity=req.quantity,
        product_type=req.product_type,
        price=req.price,
        order_type=req.order_type,
        tag="MANUAL"
    )

    if order_id:
        return {"success": True, "order_id": order_id, "message": f"Order placed: {req.side} {req.quantity} {req.symbol}"}
    else:
        raise HTTPException(status_code=500, detail="Order placement failed. Check logs.")


@router.post("/square-off")
async def square_off_live(req: SquareOffRequest):
    """Square off live positions"""
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    # Fetch current open positions from Angel One
    try:
        positions = session.smart_api.position()
        if not positions or not positions.get('status'):
            return {"success": False, "message": "No open positions found"}

        pos_data = positions.get('data', [])
        squared = []

        for pos in pos_data:
            net_qty = int(pos.get('netqty', 0))
            if net_qty == 0:
                continue

            # Close the position by placing opposite order
            side = "SELL" if net_qty > 0 else "BUY"
            qty = abs(net_qty)
            stock = {
                "symbol": pos.get('tradingsymbol', ''),
                "token": pos.get('symboltoken', ''),
                "exch_seg": pos.get('exchange', 'NSE'),
                "ltp": 0
            }

            order_id = live_service.place_live_order(
                req.session_id, stock, side, qty,
                product_type=pos.get('producttype', 'INTRADAY'),
                order_type="MARKET", tag="SQUARE_OFF", is_square_off=True
            )
            if order_id:
                squared.append({"symbol": stock['symbol'], "qty": qty, "side": side, "order_id": order_id})

        return {"success": True, "squared_off": squared, "count": len(squared)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance/{session_id}")
async def get_live_balance(session_id: str):
    session = session_manager.get_session(session_id)
    if not session or not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    try:
        balance_data = session.smart_api.rmsLimit()
        if balance_data and balance_data.get('status'):
            return {"balance": balance_data['data']}
        return {"balance": None, "message": "Failed to fetch balance"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{session_id}")
async def get_live_orders(session_id: str, client_id: Optional[str] = None):
    """Fetch live orders from Angel One"""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    try:
        response = session.smart_api.orderBook()
        if response and response.get('status'):
            return {"orders": response.get('data', [])}
        return {"orders": session.live_orders, "source": "cache"}
    except Exception as e:
        return {"orders": session.live_orders, "source": "cache", "error": str(e)}


@router.get("/funds/{session_id}")
async def get_live_funds(session_id: str, client_id: Optional[str] = None):
    """Fetch live funds from Angel One"""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    try:
        from services.angel_service import angel_service
        funds = angel_service.get_rms_limit(session.smart_api)
        if funds:
            return {"net": funds.get('net', 0), "availablecash": funds.get('availablecash', 0), "data": funds}
        return {"net": 0, "availablecash": 0, "error": "Failed to fetch funds"}
    except Exception as e:
        return {"net": 0, "availablecash": 0, "error": str(e)}


@router.get("/positions/{session_id}")
async def get_live_positions(session_id: str, client_id: Optional[str] = None):
    """Fetch live positions from Angel One"""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    try:
        from services.angel_service import angel_service
        positions = angel_service.get_position(session.smart_api)
        if positions:
            return {"positions": positions}
        return {"positions": [], "error": "Failed to fetch positions"}
    except Exception as e:
        return {"positions": [], "error": str(e)}
