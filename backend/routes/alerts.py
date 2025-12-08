"""
Alerts Routes
Alert management and 3-6-9 level generation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from services.session_manager import session_manager
from services.alert_service import generate_369_levels, create_alert
import uuid

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

class CreateAlertRequest(BaseModel):
    session_id: str
    symbol: str
    token: str
    condition: str  # "ABOVE" or "BELOW"
    price: float

class GenerateAlertsRequest(BaseModel):
    session_id: str

class DeleteAlertRequest(BaseModel):
    session_id: str
    alert_id: str

class PauseRequest(BaseModel):
    session_id: str
    paused: bool

@router.get("/{session_id}")
async def get_alerts(session_id: str):
    """
    Get all alerts for session
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "alerts": session.alerts,
        "is_paused": session.is_paused
    }

@router.post("/create")
async def create_manual_alert(req: CreateAlertRequest):
    """
    Create a manual alert
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Validate condition
    if req.condition not in ["ABOVE", "BELOW"]:
        raise HTTPException(status_code=400, detail="Condition must be ABOVE or BELOW")
    
    # Check if stock exists in watchlist
    stock = next((s for s in session.watchlist if s['token'] == req.token), None)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not in watchlist")
    
    # Create alert
    alert = create_alert(req.symbol, req.token, req.condition, req.price, "MANUAL")
    session.alerts.append(alert)
    
    return {
        "success": True,
        "message": "Alert created",
        "alert": alert
    }

@router.post("/generate")
async def generate_auto_alerts(req: GenerateAlertsRequest):
    """
    Auto-generate 3-6-9 alerts for all watchlist stocks
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    count = 0
    new_alerts = []
    
    for stock in session.watchlist:
        wc = stock.get('wc', 0)
        ltp = stock.get('ltp', 0)
        
        if wc > 0 and ltp > 0:
            print(f"Generating 3-6-9 for {stock['symbol']}: LTP={ltp}, WC={wc}")
            levels = generate_369_levels(ltp, wc)
            
            for level in levels:
                # Check for duplicates
                is_duplicate = any(
                    a['token'] == stock['token'] and 
                    a['price'] == level['price'] and 
                    a['condition'] == level['type']
                    for a in session.alerts
                )
                
                if not is_duplicate:
                    alert = create_alert(
                        stock['symbol'],
                        stock['token'],
                        level['type'],
                        level['price'],
                        "AUTO"
                    )
                    session.alerts.append(alert)
                    new_alerts.append(alert)
                    count += 1
    
    # Create log entry
    if count > 0:
        log_entry = {
            "time": "SYS",
            "symbol": "AUTO",
            "msg": f"Generated {count} alerts"
        }
        session.logs.insert(0, log_entry)
    
    return {
        "success": True,
        "message": f"Generated {count} new alerts",
        "count": count,
        "alerts": new_alerts
    }

@router.delete("/delete")
async def delete_alert(req: DeleteAlertRequest):
    """
    Delete an alert
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_len = len(session.alerts)
    session.alerts = [a for a in session.alerts if a['id'] != req.alert_id]
    
    if len(session.alerts) == initial_len:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {
        "success": True,
        "message": "Alert deleted"
    }

@router.post("/pause")
async def toggle_pause(req: PauseRequest):
    """
    Pause or resume alert monitoring
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.is_paused = req.paused
    
    return {
        "success": True,
        "is_paused": session.is_paused,
        "message": f"Alerts {'paused' if req.paused else 'resumed'}"
    }

@router.get("/logs/{session_id}")
async def get_logs(session_id: str):
    """
    Get alert logs
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "logs": session.logs
    }
