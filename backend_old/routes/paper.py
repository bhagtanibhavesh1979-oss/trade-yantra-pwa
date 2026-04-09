from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from services.session_manager import session_manager
from services.paper_service import paper_service

import logging
logger = logging.getLogger("paper_route")

router = APIRouter(prefix="/api/paper", tags=["Paper Trading"])

class TogglePaperRequest(BaseModel):
    enabled: bool
    client_id: Optional[str] = None

@router.post("/toggle/{session_id}")
async def toggle_paper_trading(session_id: str, req: TogglePaperRequest):
    print(f"DEBUG: Toggle Paper Trading for {session_id} to {req.enabled}")
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        print(f"DEBUG: Session {session_id} NOT FOUND for toggle")
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.auto_paper_trade = req.enabled
    print(f"DEBUG: Saving session {session_id} after paper toggle")
    session_manager.save_session(session_id)
    return {"status": "success", "auto_paper_trade": session.auto_paper_trade}

class StrategyModeRequest(BaseModel):
    mode: str
    client_id: Optional[str] = None

@router.post("/strategy/{session_id}")
async def set_strategy_mode(session_id: str, req: StrategyModeRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.strategy_mode = req.mode # 'BOUNCE' or 'SAR'
    session_manager.save_session(session_id)
    return {"status": "success", "strategy_mode": session.strategy_mode}

class TriggerModeRequest(BaseModel):
    mode: str
    client_id: Optional[str] = None

@router.post("/trigger-mode/{session_id}")
async def set_trigger_mode(session_id: str, req: TriggerModeRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.trigger_mode = req.mode # 'CANDLE_CLOSE' or 'INSTANT'
    session_manager.save_session(session_id)
    return {"status": "success", "trigger_mode": session.trigger_mode}

class BufferSettingsRequest(BaseModel):
    buffer: float
    client_id: Optional[str] = None

@router.post("/buffer/{session_id}")
async def set_buffer_pct(session_id: str, req: BufferSettingsRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.buffer_pct = req.buffer 
    session_manager.save_session(session_id)
    return {"status": "success", "buffer_pct": session.buffer_pct}

@router.get("/summary/{session_id}")
async def get_paper_summary(session_id: str, client_id: Optional[str] = None):
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Merge historical trades from permanent storage
    from services.persistence_service import persistence_service
    historical_trades = persistence_service.get_trade_history(session.client_id) or []
    
    # Use a dictionary to avoid duplicates (prioritize memory trades for live updates)
    trades_map = {str(t.get('id')): t for t in historical_trades}
    for t in session.paper_trades:
        trades_map[str(t.get('id', ''))] = t
        
    all_trades = sorted(trades_map.values(), key=lambda x: x.get('created_at', ''), reverse=True)
    
    # --- RIGID AUTO RECOVERY ---
    # If balance is 0, we force it back to 500k baseline IMMEDIATELY
    current_bal = float(getattr(session, 'virtual_balance', 0.0))
    if current_bal == 0:
        session.virtual_balance = 500000.0
        print(f"💰 [RIGID] Forced balance reset to 500,000 for {session.client_id}")
        session_manager.save_session(session_id)
    # ---------------------------

    response_data = {
        "auto_paper_trade": session.auto_paper_trade,
        "strategy_mode": getattr(session, 'strategy_mode', 'BOUNCE'),
        "trigger_mode": getattr(session, 'trigger_mode', 'CANDLE_CLOSE'),
        "buffer_pct": getattr(session, 'buffer_pct', 0.25),
        "virtual_balance": session.virtual_balance,
        "trades": all_trades[:200], # Keep a healthy amount in the UI
        "summary": {
            "total_pnl": sum(t.get('pnl', 0) for t in all_trades),
            "open_trades": len([t for t in all_trades if t.get('status') == 'OPEN']),
            "closed_trades": len([t for t in all_trades if t.get('status') == 'CLOSED'])
        }
    }
    
    # 🔍 RIGID DEBUG TRAP
    print(f"📡 [API] Returning summary for {session.client_id}: Balance = {response_data['virtual_balance']}")
    
    return response_data

class SetBalanceRequest(BaseModel):
    amount: float
    client_id: Optional[str] = None

@router.post("/balance/{session_id}")
async def set_virtual_balance(session_id: str, req: SetBalanceRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    paper_service.set_virtual_balance(session_id, req.amount, client_id=req.client_id)
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

@router.get("/analytics/{session_id}")
async def get_analytics(session_id: str):
    """Get performance analytics for the dashboard"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    from services.persistence_service import persistence_service
    bal = getattr(session, 'virtual_balance', 100000.0)
    return persistence_service.get_performance_stats(session.client_id, bal)

class BacktestRequest(BaseModel):
    symbol: str
    token: str
    exch: str = "NSE"
    start_date: str
    end_date: str
    mode: str # "DISCRETE" or "ZONE"
    high: float
    low: float
    high_zone_buffer: float = 2.0
    low_zone_buffer: float = 2.0
    quantity: int = 100
    target: Optional[float] = None
    target_type: str = "POINTS" # "POINTS" or "AMOUNT"
    stop_loss: Optional[float] = None
    trailing_sl: Optional[float] = None
    blueprint_date: Optional[str] = None
    interval: str = "TEN_MINUTE"
    trade_type: str = "INTRADAY" # "INTRADAY" or "POSITIONAL"
    buffer: float = 0.1
    trigger_mode: str = "CANDLE_CLOSE"
    client_id: Optional[str] = None

@router.post("/backtest/{session_id}")
async def run_backtest(session_id: str, req: BacktestRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session or not session.smart_api:
        raise HTTPException(status_code=401, detail="Angel API session inactive. Please re-login.")
        
    from services.backtest_service import backtest_service
    
    config = {
        "mode": req.mode,
        "high": req.high,
        "low": req.low,
        "high_zone_buffer": req.high_zone_buffer,
        "low_zone_buffer": req.low_zone_buffer,
        "quantity": req.quantity,
        "target": req.target,
        "target_type": req.target_type,
        "stop_loss": req.stop_loss,
        "trailing_sl": req.trailing_sl,
        "blueprint_date": req.blueprint_date,
        "interval": req.interval,
        "trade_type": req.trade_type,
        "buffer": req.buffer,
        "trigger_mode": req.trigger_mode
    }
    
    try:
        result = backtest_service.run_backtest(
            session.smart_api, req.symbol, req.token, req.exch, req.start_date, req.end_date, config
        )
        return result
    except Exception as e:
        import traceback
        print(f"[ERROR] Backtest Failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Backtest Engine Error: {str(e)}")
