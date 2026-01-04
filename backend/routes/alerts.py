"""
Alerts Routes
API endpoints for alert management and High/Low level generation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from services.session_manager import session_manager
from services.alert_service import create_alert
import uuid
import datetime

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

class CreateAlertRequest(BaseModel):
    session_id: str
    symbol: str
    token: str
    condition: str  # "ABOVE" or "BELOW"
    price: float

class GenerateAlertsRequest(BaseModel):
    session_id: str
    symbol: str  # Required now
    date: str    # "YYYY-MM-DD"
    start_time: str = "09:15"
    end_time: str = "15:30"
    is_custom_range: bool = False
    levels: List[str] = ["High", "Low"] # Default targets
    token: str = None  # Optional: manually provide token (for indices)
    exchange: str = None # Optional: manually provide exchange (for indices)

class DeleteAlertRequest(BaseModel):
    session_id: str
    alert_id: str

class PauseRequest(BaseModel):
    session_id: str
    paused: bool

class GenerateBulkAlertsRequest(BaseModel):
    session_id: str
    date: str    # "YYYY-MM-DD"
    start_time: str = "09:15"
    end_time: str = "15:30"
    is_custom_range: bool = False
    levels: List[str] = ["High", "Low", "R1", "S1"]  # Default targets

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
    
    # Check if stock exists in watchlist (legacy check, maybe relax for manual index alerts too?)
    # For now, let's allow if token is passed or if it's in watchlist
    # But manual alert creation UI likely still uses watchlist context. This is about auto-generation.
    stock = next((s for s in session.watchlist if s['token'] == req.token), None)
    
    # Relaxed check: Only enforce watchlist if req.token implies it came from there? 
    # Actually manual alerts usually come from click ACTIONS on a specific stock.
    # If we want manual alerts for indices, we need similar logic.
    # But for now, let's focus on auto-generation.
    if not stock: 
        # Bypass if it looks like an index (we can't easily verify w/o token lookup, but CreateAlertRequest has token)
        # Let's just assume valid token for now if coming from UI.
        pass

    # Create alert
    alert = create_alert(req.symbol, req.token, req.condition, req.price, "MANUAL")
    session.alerts.append(alert)
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": "Alert created",
        "alert": alert
    }

from services.alert_service import generate_high_low_alerts

@router.post("/generate")
async def generate_auto_alerts(req: GenerateAlertsRequest):
    """
    Generate High/Low alerts for a specific stock
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    token = req.token
    exchange = req.exchange or "NSE"

    # If token not provided, look up in watchlist
    if not token:
        stock = next((s for s in session.watchlist if s['symbol'] == req.symbol), None)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not in watchlist and no token provided")
        token = stock['token']

    print(f"DEBUG: Generating H/L Alerts for {req.symbol} ({exchange}) on {req.date}")
    print(f"DEBUG: Levels requested: {req.levels}")
    
    new_alert_data = generate_high_low_alerts(
        session.smart_api, 
        req.symbol, 
        token, 
        req.date, 
        req.start_time, 
        req.end_time, 
        req.is_custom_range,
        exchange
    )
    
    count = 0
    added_alerts = []
    
    for alert_data in new_alert_data:
        # Filter by selected levels
        if alert_data.get('label') not in req.levels:
            continue

        # Check duplicate
        is_duplicate = any(
            a['token'] == token and 
            a['price'] == alert_data['price'] and 
            a['condition'] == alert_data['type']
            for a in session.alerts
        )
        
        if not is_duplicate:
            alert = create_alert(
                req.symbol,
                token,
                alert_data['type'],
                alert_data['price'],
                f"AUTO_{alert_data.get('label', 'HL').upper()}"
            )
            session.alerts.append(alert)
            added_alerts.append(alert)
            count += 1
    
    print(f"DEBUG: Successfully added {count} alerts: {[a['price'] for a in added_alerts]}")
    
    # Create log entry
    if count > 0:
        log_entry = {
            "time": datetime.datetime.utcnow().isoformat() + "Z",
            "symbol": req.symbol,
            "msg": f"Generated {count} H/L alerts"
        }
        session.logs.insert(0, log_entry)
        session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Generated {count} new alerts",
        "count": count,
        "alerts": added_alerts
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
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": "Alert deleted"
    }

class ClearAllAlertsRequest(BaseModel):
    session_id: str

@router.delete("/clear-all")
async def clear_all_alerts(req: ClearAllAlertsRequest):
    """
    Delete all alerts at once
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    count = len(session.alerts)
    session.alerts = []
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Cleared {count} alerts",
        "count": count
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
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "is_paused": session.is_paused,
        "message": f"Alerts {'paused' if req.paused else 'resumed'}"
    }

@router.post("/generate-bulk")
async def generate_bulk_alerts(req: GenerateBulkAlertsRequest):
    """
    Generate High/Low alerts for ALL stocks in watchlist
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")
    
    if not session.watchlist or len(session.watchlist) == 0:
        raise HTTPException(status_code=400, detail="Watchlist is empty")
    
    print(f"DEBUG: Bulk generating alerts for {len(session.watchlist)} stocks")
    print(f"DEBUG: Date={req.date}, Levels={req.levels}")
    
    total_alerts = 0
    results = []
    
    for stock in session.watchlist:
        try:
            symbol = stock['symbol']
            token = stock['token']
            
            new_alert_data = generate_high_low_alerts(
                session.smart_api,
                symbol,
                token,
                req.date,
                req.start_time,
                req.end_time,
                req.is_custom_range
            )
            
            stock_alerts_count = 0
            added_alerts = []
            
            for alert_data in new_alert_data:
                # Filter by selected levels
                if alert_data.get('label') not in req.levels:
                    continue
                
                # Check duplicate
                is_duplicate = any(
                    a['token'] == token and
                    a['price'] == alert_data['price'] and
                    a['condition'] == alert_data['type']
                    for a in session.alerts
                )
                
                if not is_duplicate:
                    alert = create_alert(
                        symbol,
                        token,
                        alert_data['type'],
                        alert_data['price'],
                        f"AUTO_{alert_data.get('label', 'HL').upper()}"
                    )
                    session.alerts.append(alert)
                    added_alerts.append(alert)
                    stock_alerts_count += 1
            
            total_alerts += stock_alerts_count
            results.append({
                "symbol": symbol,
                "success": True,
                "count": stock_alerts_count
            })
            
            print(f"DEBUG: {symbol} - Generated {stock_alerts_count} alerts")
            
        except Exception as e:
            print(f"ERROR: Failed to generate alerts for {stock['symbol']}: {e}")
            results.append({
                "symbol": stock['symbol'],
                "success": False,
                "error": str(e)
            })
    
    # Create log entry
    if total_alerts > 0:
        log_entry = {
            "time": datetime.datetime.utcnow().isoformat() + "Z",
            "symbol": "BULK",
            "msg": f"Generated {total_alerts} alerts for {len(session.watchlist)} stocks"
        }
        session.logs.insert(0, log_entry)
        session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Generated {total_alerts} alerts for {len(session.watchlist)} stocks",
        "total_alerts": total_alerts,
        "total_stocks": len(session.watchlist),
        "results": results
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
