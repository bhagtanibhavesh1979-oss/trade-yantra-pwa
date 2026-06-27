from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from services.session_manager import session_manager
from services.paper_service import paper_service
from datetime import datetime, timedelta

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

class PaperSarTestModeRequest(BaseModel):
    mode: str  # STANDARD | SAR_MATCH_NO_CLOSE_AFTER_FIRST
    client_id: Optional[str] = None

@router.post("/sar-test-mode/{session_id}")
async def set_paper_sar_test_mode(session_id: str, req: PaperSarTestModeRequest):
    session = session_manager.get_session(session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    allowed = {"STANDARD", "SAR_MATCH_NO_CLOSE_AFTER_FIRST"}
    if req.mode not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Allowed: {sorted(allowed)}")

    session.paper_sar_test_mode = req.mode
    session_manager.save_session(session_id)
    return {"status": "success", "paper_sar_test_mode": session.paper_sar_test_mode}

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
    
    # Use a dictionary to avoid duplicates
    # CRITICAL: Build with HISTORICAL first, then OVERRIDE with in-memory (live) state.
    # This ensures that a trade closed in memory is NOT resurrected by the old history file.
    trades_map = {str(t.get('id')): t for t in historical_trades}
    for t in session.paper_trades:
        trades_map[str(t.get('id', ''))] = t  # In-memory is always the source of truth
        
    all_trades = sorted(trades_map.values(), key=lambda x: x.get('created_at', ''), reverse=True)
    
    # --- RIGID AUTO RECOVERY ---
    # Disabled in favor of Session Init default 500k
    # current_bal = float(getattr(session, 'virtual_balance', 0.0))
    # if current_bal == 0:
    #     session.virtual_balance = 500000.0
    #     print(f"[MONEY] [RIGID] Forced balance reset to 500,000 for {session.client_id}")
    #     session_manager.save_session(session_id)
    # ---------------------------

    response_data = {
        "auto_paper_trade": session.auto_paper_trade,
        "is_paused": getattr(session, 'is_paused', False),
        "strategy_mode": getattr(session, 'strategy_mode', 'BOUNCE'),
        "trigger_mode": getattr(session, 'trigger_mode', 'CANDLE_CLOSE'),
        "buffer_pct": getattr(session, 'buffer_pct', 0.25),
        "global_target": getattr(session, 'global_target', None),
        "global_stop_loss": getattr(session, 'global_stop_loss', None),
        "virtual_balance": session.virtual_balance,
        "trades": all_trades[:200], # Keep a healthy amount in the UI
        "summary": {
            "total_pnl": sum(t.get('pnl', 0) for t in all_trades),
            "open_trades": len([t for t in all_trades if t.get('status') == 'OPEN']),
            "closed_trades": len([t for t in all_trades if t.get('status') == 'CLOSED'])
        }
    }
    
    #  RIGID DEBUG TRAP
    print(f" [API] Returning summary for {session.client_id}: Balance = {response_data['virtual_balance']}")
    
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
async def close_trade(session_id: str, trade_id: str, ltp: float, client_id: Optional[str] = None):
    """Manually close a single trade, with explicit disk flush"""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    paper_service.close_virtual_trade(session_id, trade_id, ltp, reason="MANUAL_CLOSE")
    
    # CRITICAL: Also update in permanent trade history so merged view shows CLOSED
    from services.persistence_service import persistence_service
    closed_trade = next((t for t in session.paper_trades if t['id'] == trade_id), None)
    if closed_trade:
        persistence_service.add_to_trade_history(session.client_id, closed_trade)
    
    return {"status": "success"}

@router.post("/clear/{session_id}")
async def clear_trades(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 1. Filter In-Memory Trades: KEEP OPEN positions
    open_trades = [t for t in session.paper_trades if t.get('status') == 'OPEN']
    session.paper_trades = open_trades
    
    # 2. Clear Permanent Store but PRESERVE OPEN trades
    from services.persistence_service import persistence_service
    # Fetch historical trades to see if any are OPEN (should be synced with memory but safety first)
    history = persistence_service.get_trade_history(session.client_id) or []
    historical_open = [t for t in history if t.get('status') == 'OPEN']
    
    # Fully clear the history file/GCS blob
    persistence_service.clear_trade_history(session.client_id)
    
    # Re-populate with preserved OPEN trades (merge from memory and history to be safe)
    trades_map = {str(t.get('id')): t for t in open_trades}
    for t in historical_open:
        trades_map[str(t.get('id', ''))] = t
        
    for t in trades_map.values():
        persistence_service.add_to_trade_history(session.client_id, t)
    
    session_manager.save_session(session_id)
    print(f" [CLEAR] History cleared for {session.client_id}. Preserved {len(trades_map)} open trades.")
    
    return {"status": "success", "preserved_count": len(trades_map)}

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

@router.post("/square-off/{session_id}")
async def square_off_positions(session_id: str):
    paper_service.close_all_open_trades(session_id, reason="MANUAL_SQUARE_OFF")
    return {"status": "success"}

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
    
    # Fetch current session strategy mode
    session = session_manager.get_session(session_id)
    strategy_mode = getattr(session, 'strategy_mode', 'MANUAL') if session else "MANUAL"
    
    # We use "MANUAL" as the alert name to indicate user action
    paper_service.create_virtual_trade(session_id, stock, req.side, "MANUAL", quantity=req.quantity, strategy_mode=strategy_mode)
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
    trades_map = {}
    if historical_trades:
        for t in historical_trades:
            tid = t.get('id')
            if tid: trades_map[tid] = t

    for t in session.paper_trades:
        tid = t.get('id')
        if tid: trades_map[tid] = t
        
    # Sort by created_at descending
    trades = sorted(trades_map.values(), key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    try:
        # Header
        writer.writerow(["Symbol", "Side", "Quantity", "Entry Price", "Exit Price", "Entry Time", "Exit Time", "Status", "PnL", "Execution Reason"])
        
        for t in trades:
            # Format times for easier reading in Excel
            entry_time = t.get('created_at', '')
            if entry_time:
                try:
                    dt = datetime.fromisoformat(str(entry_time).replace('Z', ''))
                    # Convert to IST (+5:30)
                    dt_ist = dt + timedelta(hours=5, minutes=30)
                    entry_time = dt_ist.strftime('%Y-%m-%d %H:%M:%S')
                except: pass
                
            exit_time = t.get('closed_at', '')
            if exit_time:
                try:
                    dt = datetime.fromisoformat(str(exit_time).replace('Z', ''))
                    # Convert to IST (+5:30)
                    dt_ist = dt + timedelta(hours=5, minutes=30)
                    exit_time = dt_ist.strftime('%Y-%m-%d %H:%M:%S')
                except: pass

            # Robust helper for rounding
            def safe_round(val, default=''):
                try:
                    v = float(val)
                    # If it's a 0.05 tick, we want to see it clearly
                    return round(v, 2)
                except (TypeError, ValueError):
                    return default

            writer.writerow([
                t.get('symbol', 'N/A'), 
                t.get('side', 'N/A'), 
                t.get('quantity', 100), 
                safe_round(t.get('entry_price')), 
                safe_round(t.get('exit_price')), 
                entry_time,
                exit_time,
                t.get('status', 'N/A'), 
                safe_round(t.get('pnl', 0.0), 0.0), 
                f"{t.get('trigger_level', 'MANUAL')} ({t.get('exit_reason', 'OPEN')})"
            ])
            
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=trade_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    except Exception as e:
        logger.error(f"Export Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export Error: {str(e)}")

@router.get("/analytics/{session_id}")
async def get_analytics(session_id: str):
    """Get performance analytics for the dashboard"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    from services.persistence_service import persistence_service
    bal = getattr(session, 'virtual_balance', 100000.0)
    extra_trades = getattr(session, 'paper_trades', [])
    return persistence_service.get_performance_stats(session.client_id, bal, extra_trades)

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
    blueprint_date: Optional[str] = None          # Legacy single-date support
    blueprint_start_date: Optional[str] = None    # New: start of blueprint range
    blueprint_end_date: Optional[str] = None      # New: end of blueprint range
    blueprint_start_time: str = "09:15"           # New: start time of blueprint range
    blueprint_end_time: str = "15:30"             # New: end time of blueprint range
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
    
    # Resolve blueprint date range: prefer explicit start/end, fallback to legacy single date
    bp_start = req.blueprint_start_date or req.blueprint_date
    bp_end = req.blueprint_end_date or req.blueprint_date

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
        "blueprint_date": req.blueprint_date,          # Legacy
        "blueprint_start_date": bp_start,
        "blueprint_end_date": bp_end,
        "blueprint_start_time": req.blueprint_start_time,
        "blueprint_end_time": req.blueprint_end_time,
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
