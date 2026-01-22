"""
Alerts Routes
API endpoints for alert management and High/Low level generation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.session_manager import session_manager
from services.alert_service import create_alert
import uuid
import datetime
import time
import asyncio

import logging

# Configure logging to a file
logging.basicConfig(
    filename="backend_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("alerts_route")

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

class CreateAlertRequest(BaseModel):
    session_id: str
    symbol: str
    token: str
    condition: str  # "ABOVE" or "BELOW"
    price: float

class GenerateAlertsRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    symbol: str
    date: str
    start_time: str = "09:15"
    end_time: str = "15:30"
    is_custom_range: bool = False
    levels: List[str] = ["High", "Low"]
    token: Optional[str] = None
    exchange: Optional[str] = None

class DeleteAlertRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    alert_id: str

class PauseRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    paused: bool

class GenerateBulkAlertsRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    date: str    # "YYYY-MM-DD"
    start_time: str = "09:15"
    end_time: str = "15:30"
    is_custom_range: bool = False
    levels: List[str] = ["High", "Low", "R1", "S1"]  # Default targets


@router.get("/{session_id}")
async def get_alerts(session_id: str, client_id: Optional[str] = None):
    """
    Get all alerts for session
    """
    session = session_manager.get_session(session_id, client_id=client_id)
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
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")

    token = req.token
    exchange = req.exchange or "NSE"
    
    # 1. Date Validation/Healing
    gen_date = req.date
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if not gen_date or gen_date < "2026-01-01":
        print(f"[WARN] Requested date '{gen_date}' is missing or too old. Defaulting to today: {today_str}")
        gen_date = today_str

    print(f"DEBUG: Generating H/L Alerts for {req.symbol} ({exchange}) on {gen_date}")
    print(f"DEBUG: Levels requested: {req.levels}")
    
    new_alert_data = generate_high_low_alerts(
        session.smart_api, 
        req.symbol, 
        token, 
        gen_date, 
        req.start_time, 
        req.end_time, 
        req.is_custom_range,
        exchange
    )
    
    # REPLACE LOGIC: Clear existing AUTO alerts for this symbol before generating new ones
    # This prevents old and new levels from being mixed as requested by the user.
    initial_alerts_count = len(session.alerts)
    session.alerts = [a for a in session.alerts if not (str(a['token']) == str(token) and str(a.get('type', '')).startswith('AUTO_'))]
    cleared_count = initial_alerts_count - len(session.alerts)
    if cleared_count > 0:
        print(f"DEBUG: Cleared {cleared_count} old auto-alerts for {req.symbol}")
    
    count = 0
    added_alerts = []
    
    for alert_data in new_alert_data:
        # Filter by selected levels
        if alert_data.get('label') not in req.levels:
            continue

        # Check duplicate (Robust string and price comparison)
        is_duplicate = any(
            str(a['token']) == str(token) and 
            round(a['price'], 2) == round(alert_data['price'], 2) and 
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
            
    # CRITICAL: Save session to database after generating alerts
    if count > 0:
        session_manager.save_session(req.session_id)
        print(f"[OK] Saved {count} new alerts to database for session {req.session_id}")
            
    print(f"DEBUG: Successfully added {count} alerts: {[a['price'] for a in added_alerts]}")
    
    # Create log entry
    if count > 0:
        log_entry = {
            "time": datetime.datetime.utcnow().isoformat() + "Z",
            "symbol": req.symbol,
            "msg": f"Generated {count} H/L alerts"
        }
        session.logs.insert(0, log_entry)
        # The session is already saved above, no need to save again just for logs
        # session_manager.save_session(req.session_id) 
    
    return {
        "success": True,
        "message": f"Generated {count} new alerts",
        "count": count,
        "alerts": session.alerts  # Return FULL list for instant sync as requested by user
    }

@router.post("/delete")
async def delete_alert(req: DeleteAlertRequest):
    """
    Delete an alert
    """
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
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
    client_id: Optional[str] = None

class DeleteMultipleAlertsRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    alert_ids: List[str]

@router.post("/delete-multiple")
async def delete_multiple_alerts(req: DeleteMultipleAlertsRequest):
    """
    Delete multiple alerts at once
    """
    print(f"[DEBUG] Delete Multiple Alerts Request: SID={req.session_id}, CID={req.client_id}, Count={len(req.alert_ids)}")
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_len = len(session.alerts)
    session.alerts = [a for a in session.alerts if a['id'] not in req.alert_ids]
    deleted_count = initial_len - len(session.alerts)
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Deleted {deleted_count} alerts",
        "count": deleted_count
    }

@router.post("/clear-all")
async def clear_all_alerts(req: ClearAllAlertsRequest):
    """
    Delete all alerts at once
    """
    print(f"[DEBUG] Clear All Alerts Request: SID={req.session_id}, CID={req.client_id}")
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        print(f"[ERROR] Clear All: Session {req.session_id} not found (Client: {req.client_id})")
        raise HTTPException(status_code=404, detail="Session not found")
    
    count = len(session.alerts)
    session.alerts = []
    
    # CRITICAL: Also clear in persistence directly to prevent "Ghost Healing"
    # where the session manager might pick up an old record with alerts.
    from services.persistence_service import persistence_service
    all_data = persistence_service.load_sessions()
    if req.session_id in all_data:
        all_data[req.session_id]['alerts'] = []
        persistence_service._write_all(all_data)
        print(f"[OK] Persistence: Cleared alerts for {req.session_id} in database")

    # Save session (Normal background save)
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
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
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
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.smart_api:
        raise HTTPException(status_code=400, detail="Angel One not connected")
    
    if not session.watchlist or len(session.watchlist) == 0:
        raise HTTPException(status_code=400, detail="Watchlist is empty")
    
    logger.debug(f"Bulk generating alerts for {len(session.watchlist)} stocks. Session: {req.session_id}")
    print(f"DEBUG: Bulk generating alerts for {len(session.watchlist)} stocks")
    
    # 0. Date Validation
    gen_date = req.date
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if not gen_date or gen_date < "2026-01-01":
        print(f"[WARN] Bulk Gen: Date '{gen_date}' is invalid/old. Healing to today: {today_str}")
        gen_date = today_str

    print(f"DEBUG: Date={gen_date}, Levels={req.levels}")
    
    # 1. REPLACE LOGIC: Clear ALL existing AUTO alerts before bulk generation
    # This ensures a clean slate as requested by the user.
    initial_alerts_count = len(session.alerts)
    session.alerts = [a for a in session.alerts if not str(a.get('type', '')).startswith('AUTO_')]
    print(f"DEBUG: Cleared {initial_alerts_count - len(session.alerts)} existing auto-alerts for bulk generation")

    # 2. RUN IN EXECUTOR: Bulk generation (Historical data fetch) is CPU/Network intensive
    # and synchronous. We run it in a thread pool to avoid blocking the event loop
    # so that WebSocket PING/PONG continues to work on mobile devices.
    def _run_bulk_logic():
        total_alerts = 0
        results = []
        
        for stock in session.watchlist:
            try:
                symbol = stock['symbol']
                token = str(stock['token'])
                
                # Small sleep to stay within Angel's rate limit
                time.sleep(0.45) 
                
                new_alert_data = generate_high_low_alerts(
                    smart_api=session.smart_api,
                    symbol=symbol,
                    token=token,
                    date=gen_date,
                    start_time=req.start_time,
                    end_time=req.end_time,
                    is_custom=req.is_custom_range,
                    exchange=stock.get('exch_seg', 'NSE')
                )
                
                if not new_alert_data:
                    results.append({"symbol": symbol, "success": False, "error": "No data returned"})
                    continue

                stock_alerts_count = 0
                for alert_data in new_alert_data:
                    # Filter by selected levels
                    if alert_data.get('label') not in req.levels:
                        continue
                    
                    # Duplicate check (redundant but safe)
                    is_duplicate = any(
                        str(a['token']) == token and
                        round(a['price'], 2) == round(alert_data['price'], 2) and
                        a['condition'] == alert_data['type']
                        for a in session.alerts
                    )
                    
                    if not is_duplicate:
                        alert = create_alert(
                            symbol=symbol,
                            token=token,
                            condition=alert_data['type'],
                            price=alert_data['price'],
                            alert_type=f"AUTO_{alert_data.get('label', 'HL').upper()}"
                        )
                        session.alerts.append(alert)
                        stock_alerts_count += 1
                
                total_alerts += stock_alerts_count
                results.append({"symbol": symbol, "success": True, "count": stock_alerts_count})
                
            except Exception as e:
                print(f"[ERROR] Bulk gen failed for {stock.get('symbol')}: {e}")
                results.append({"symbol": stock.get('symbol'), "success": False, "error": str(e)})

        return total_alerts, results

    # Execute in default thread pool executor
    import concurrent.futures
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        total_alerts, results = await loop.run_in_executor(pool, _run_bulk_logic)
    
    # Create log entry
    if total_alerts > 0:
        log_entry = {
            "time": datetime.datetime.utcnow().isoformat() + "Z",
            "symbol": "BULK",
            "msg": f"Generated {total_alerts} alerts for {len(session.watchlist)} stocks"
        }
        session.logs.insert(0, log_entry)
        session_manager.save_session(req.session_id)
    else:
        print(f"[INFO] Bulk generation finished: 0 new alerts created (Likely all duplicates or no data)")
    
    return {
        "success": True,
        "message": f"Generated {total_alerts} alerts ({total_duplicates} skipped as duplicates)",
        "total_alerts": total_alerts,
        "total_duplicates": total_duplicates,
        "total_stocks": len(session.watchlist),
        "alerts": session.alerts, # Return FULL list for instant sync
        "results": results
    }



@router.get("/logs/{session_id}")
async def get_logs(session_id: str, client_id: Optional[str] = None):
    """
    Get alert logs
    """
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "logs": session.logs
    }
