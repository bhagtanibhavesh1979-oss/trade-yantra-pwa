"""
Alerts Routes
API endpoints for alert management and High/Low level generation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.services.session_manager import session_manager
from backend.services.alert_service import create_alert

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

# Mapping for technical vs display/strategy labels (Align with UI/Chart/Strategy)
STRATEGY_DISPLAY_MAP = {
    "High": "RANGE_HIGH", "Low": "RANGE_LOW", "M": "MIDPOINT",
    "S1": "TGT_L1", "S2": "TGT_L2", "S3": "TGT_L3",
    "S4": "TGT_L4", "S5": "TGT_L5", "S6": "TGT_L6",
    "R1": "TGT_H1", "R2": "TGT_H2", "R3": "TGT_H3",
    "R4": "TGT_H4", "R5": "TGT_H5", "R6": "TGT_H6",
    # Midpoint-target mappings (between Range High and Target High1/2/3)
    # Use MR*/MS* naming: MR = Mid between Range High and Target High, MS = Mid between Range Low and Target Low
    "MR1": "MID_H1", "MR2": "MID_H2", "MR3": "MID_H3",
    "MS1": "MID_L1", "MS2": "MID_L2", "MS3": "MID_L3"
}

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
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
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
    date: Optional[str] = None    # "YYYY-MM-DD"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
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

from backend.services.alert_service import generate_high_low_alerts


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
    start_date = req.start_date or req.date
    end_date = req.end_date or req.date
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if not start_date or start_date < "2026-01-01":
        print(f"[WARN] Requested start date '{start_date}' is missing or too old. Defaulting to today: {today_str}")
        start_date = today_str
    if not end_date or end_date < "2026-01-01":
        print(f"[WARN] Requested end date '{end_date}' is missing or too old. Defaulting to today: {today_str}")
        end_date = today_str

    print(f"DEBUG: Generating H/L Alerts for {req.symbol} ({exchange}) from {start_date} to {end_date}")
    
    # helper for generation with auto-refresh
    async def _safe_generate():
        return generate_high_low_alerts(
            session.smart_api, 
            req.symbol, 
            token, 
            start_date,
            end_date,
            req.start_time, 
            req.end_time, 
            req.is_custom_range,
            exchange
        )

    new_alert_data = await _safe_generate()
    
    # AUTO-REFRESH LOGIC: If generation failed with no data, try refreshing token ONCE
    if not new_alert_data:
        print(f"[RECOVERY] Alert generation returned nothing for {req.symbol}. Attempting token refresh...")
        if session_manager.refresh_session_tokens(req.session_id):
            print(f"[OK] Token refreshed. Retrying generation...")
            new_alert_data = await _safe_generate()
    
    # REPLACE LOGIC: Clear existing AUTO alerts for this symbol before generating new ones
    session.alerts = [a for a in session.alerts if not (str(a['token']) == str(token) and str(a.get('type', '')).startswith('AUTO_'))]
    
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
            label_display = STRATEGY_DISPLAY_MAP.get(alert_data.get('label'), alert_data.get('label'))
            alert = create_alert(
                req.symbol,
                token,
                alert_data['type'],
                alert_data['price'],
                f"AUTO_{label_display.upper()}"
            )
            session.alerts.append(alert)
            added_alerts.append(alert)
            count += 1
            
    # Persist blueprint inputs on session for Telegram Signal Engine matching
    try:
        session.blueprint_start_date = start_date
        session.blueprint_end_date = end_date
        session.blueprint_start_time = req.start_time
        session.blueprint_end_time = req.end_time
        session.blueprint_is_custom_range = req.is_custom_range
        # Timeframe/strategy/buffer/target/SL are part of Session globals where possible
        session.blueprint_timeframe = 'FIFTEEN_MINUTE'
        session.blueprint_trigger_mode = getattr(session, 'trigger_mode', 'CANDLE_CLOSE')
        session.blueprint_buffer = getattr(session, 'buffer_pct', None)
        session.blueprint_target = getattr(session, 'global_target', None)
        session.blueprint_stop_loss = getattr(session, 'global_stop_loss', None)
    except Exception as _bp_e:
        print(f"[WARN] Failed to persist blueprint metadata for {req.session_id}: {_bp_e}")

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
    from backend.services.persistence_service import persistence_service
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
    start_date = req.start_date or req.date
    end_date = req.end_date or req.date
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if not start_date or start_date < "2026-01-01":
        print(f"[WARN] Bulk Gen: Start date '{start_date}' is invalid/old. Healing to today: {today_str}")
        start_date = today_str
    if not end_date or end_date < "2026-01-01":
        print(f"[WARN] Bulk Gen: End date '{end_date}' is invalid/old. Healing to today: {today_str}")
        end_date = today_str

    print(f"DEBUG: StartDate={start_date}, EndDate={end_date}, Levels={req.levels}")
    
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
        total_duplicates = 0
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
                    start_date=start_date,
                    end_date=end_date,
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
                    
                    # Duplicate check (Robust string and price comparison)
                    is_duplicate = any(
                        str(a['token']) == token and
                        round(a['price'], 2) == round(alert_data['price'], 2) and
                        a['condition'] == alert_data['type']
                        for a in session.alerts
                    )
                    
                    if not is_duplicate:
                        label_display = STRATEGY_DISPLAY_MAP.get(alert_data.get('label'), alert_data.get('label'))
                        alert = create_alert(
                            symbol=symbol,
                            token=token,
                            condition=alert_data['type'],
                            price=alert_data['price'],
                            alert_type=f"AUTO_{label_display.upper()}"
                        )
                        session.alerts.append(alert)
                        stock_alerts_count += 1
                    else:
                        total_duplicates += 1
                
                total_alerts += stock_alerts_count
                results.append({"symbol": symbol, "success": True, "count": stock_alerts_count})
                
            except Exception as e:
                print(f"[ERROR] Bulk gen failed for {stock.get('symbol')}: {e}")
                results.append({"symbol": stock.get('symbol'), "success": False, "error": str(e)})

        return total_alerts, total_duplicates, results

    # Execute in default thread pool executor
    import concurrent.futures
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        total_alerts, total_duplicates, results = await loop.run_in_executor(pool, _run_bulk_logic)
    
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
