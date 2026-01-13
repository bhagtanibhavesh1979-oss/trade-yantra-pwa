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
        "trades": session.paper_trades, 
        "summary": {
            "total_pnl": sum(t.get('pnl', 0) for t in session.paper_trades),
            "open_trades": len([t for t in session.paper_trades if t.get('status') == 'OPEN']),
            "closed_trades": len([t for t in session.paper_trades if t.get('status') == 'CLOSED'])
        }
    }

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
