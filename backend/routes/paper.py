from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.session_manager import session_manager
from services.paper_service import paper_service

import logging
logger = logging.getLogger("paper_route")

router = APIRouter(prefix="/api/paper", tags=["Paper Trading"])

class TogglePaperRequest(BaseModel):
    enabled: bool

@router.post("/toggle/{session_id}")
async def toggle_paper_trading(session_id: str, req: TogglePaperRequest):
    print(f"DEBUG: Toggle Paper Trading for {session_id} to {req.enabled}")
    session = session_manager.get_session(session_id)
    if not session:
        print(f"DEBUG: Session {session_id} NOT FOUND for toggle")
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.auto_paper_trade = req.enabled
    print(f"DEBUG: Saving session {session_id} after paper toggle")
    session_manager.save_session(session_id)
    return {"status": "success", "auto_paper_trade": session.auto_paper_trade}

@router.get("/summary/{session_id}")
async def get_paper_summary(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "auto_paper_trade": session.auto_paper_trade,
        "virtual_balance": getattr(session, 'virtual_balance', 0.0),
        "trades": session.paper_trades, 
        "summary": {
            "total_pnl": sum(t.get('pnl', 0) for t in session.paper_trades),
            "open_trades": len([t for t in session.paper_trades if t.get('status') == 'OPEN']),
            "closed_trades": len([t for t in session.paper_trades if t.get('status') == 'CLOSED'])
        }
    }

class SetBalanceRequest(BaseModel):
    amount: float

@router.post("/balance/{session_id}")
async def set_virtual_balance(session_id: str, req: SetBalanceRequest):
    paper_service.set_virtual_balance(session_id, req.amount)
    return {"status": "success", "virtual_balance": req.amount}

@router.post("/close/{session_id}/{trade_id}")
async def close_trade(session_id: str, trade_id: str, ltp: float):
    paper_service.close_virtual_trade(session_id, trade_id, ltp)
    return {"status": "success"}

@router.post("/clear/{session_id}")
async def clear_trades(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.paper_trades = []
    session_manager.save_session(session_id)
    return {"status": "success"}

class SetStopLossRequest(BaseModel):
    sl_price: float

@router.post("/stoploss/{session_id}/{trade_id}")
async def set_stop_loss(session_id: str, trade_id: str, req: SetStopLossRequest):
    paper_service.set_stop_loss(session_id, trade_id, req.sl_price)
    return {"status": "success", "stop_loss": req.sl_price}

class SetTargetRequest(BaseModel):
    target_price: float

@router.post("/target/{session_id}/{trade_id}")
async def set_target(session_id: str, trade_id: str, req: SetTargetRequest):
    paper_service.set_target(session_id, trade_id, req.target_price)
    return {"status": "success", "target_price": req.target_price}

# --- NEW FEATURES ---

class ManualTradeRequest(BaseModel):
    symbol: str
    token: str
    ltp: float
    side: str # "BUY" or "SELL"
    quantity: int = 100

@router.post("/trade/{session_id}")
async def manual_trade(session_id: str, req: ManualTradeRequest):
    """Manually place a virtual trade"""
    stock = {
        "symbol": req.symbol,
        "token": req.token,
        "ltp": req.ltp
    }
    
    # We use "MANUAL" as the alert name to indicate user action
    paper_service.create_virtual_trade(session_id, stock, req.side, "MANUAL", quantity=req.quantity)
    return {"status": "success", "message": f"Manual {req.side} order placed for {req.symbol}"}

@router.get("/export/{session_id}")
async def export_trades(session_id: str):
    """Export trades to CSV"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Combine active session trades with historical ones
    from services.persistence_service import persistence_service
    historical_trades = persistence_service.get_trade_history(session.client_id)
    
    # Merge logic: use trade ID to avoid duplicates
    trades_map = {t['id']: t for t in historical_trades}
    for t in session.paper_trades:
        trades_map[t['id']] = t
        
    # Sort by created_at descending
    trades = sorted(trades_map.values(), key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["ID", "Time", "Symbol", "Side", "Entry Price", "Exit Price", "Quantity", "Status", "PnL", "Reason"])
    
    for t in trades:
        writer.writerow([
            t['id'], 
            t['created_at'], 
            t['symbol'], 
            t['side'], 
            t['entry_price'], 
            t.get('exit_price', ''), 
            t.get('quantity', 100), 
            t['status'], 
            t.get('pnl', 0.0), 
            t.get('trigger_level', 'AUTO')
        ])
        
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_report.csv"}
    )
