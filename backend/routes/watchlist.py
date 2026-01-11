"""
Watchlist Routes
CRUD operations for stock watchlist
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from services.session_manager import session_manager
from services.angel_service import angel_service
from services.websocket_manager import ws_manager
import threading
import time

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])

@router.get("/debug/all")
async def debug_all():
    """
    Debug: Return all sessions and their watchlists
    """
    sessions = session_manager.get_all_sessions()
    debug_data = {}
    for sid, s in sessions.items():
        debug_data[sid] = {
            "client_id": s.client_id,
            "watchlist": s.watchlist,
            "alerts_count": len(s.alerts)
        }
    return debug_data

class AddStockRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None # For robust Self-Healing
    symbol: str
    token: str
    exch_seg: str = "NSE"

class RemoveStockRequest(BaseModel):
    session_id: str
    token: str

class RefreshRequest(BaseModel):
    session_id: str

@router.get("/{session_id}")
async def get_watchlist(session_id: str, client_id: Optional[str] = None):
    """
    Get user's watchlist
    """
    print(f"🔍 Getting watchlist for session {session_id} (Client: {client_id})")
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        print(f"❌ Session {session_id} not found for watchlist")
        # Return empty watchlist but with error info to help frontend
        return {
            "error": "Session not found",
            "session_id": session_id,
            "watchlist": []
        }
    
    return {
        "watchlist": session.watchlist
    }

@router.post("/add")
async def add_stock(req: AddStockRequest):
    """
    Add stock to watchlist
    Fetches initial LTP and weekly close, then subscribes to WebSocket
    """
    # Use client_id for robust self-healing during add
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if already exists
    if any(s['token'] == req.token for s in session.watchlist):
        raise HTTPException(status_code=400, detail="Stock already in watchlist")
    
    # Create stock entry
    stock_data = {
        "symbol": req.symbol,
        "token": req.token,
        "exch_seg": req.exch_seg,
        "ltp": 0.0,
        "pdc": 0.0,
        "pdh": 0.0,
        "pdl": 0.0,
        "loading": True
    }
    
    session.watchlist.append(stock_data)
    
    # Subscribe to WebSocket if connected
    ws_manager.subscribe_token(req.session_id, req.token, stock_data)
    
    # Fetch data in background
    def fetch_data():
        # Use the authenticated SmartAPI instance from session
        smart_api = session.smart_api
        if not smart_api:
            print(f"No SmartAPI instance in session for {req.symbol}")
            stock_data['loading'] = False
            return
        
        # Fetch LTP
        ltp = angel_service.fetch_ltp(smart_api, req.symbol, req.token)
        if ltp:
            stock_data['ltp'] = ltp
        
        # Fetch High/Low/Close for the session's selected date
        # If no selected_date, it falls back to previous trading day
        print(f"DEBUG: Background fetch for {req.symbol} started (Date: {session.selected_date})...")
        pdh, pdl, pdc = angel_service.fetch_previous_day_high_low(
            smart_api, req.token, specific_date=session.selected_date
        )
        print(f"DEBUG: Background fetch for {req.symbol} result: PDH={pdh}, PDL={pdl}, PDC={pdc}")
        if pdh is not None: stock_data['pdh'] = pdh
        if pdl is not None: stock_data['pdl'] = pdl
        if pdc is not None: stock_data['pdc'] = pdc
        
        stock_data['loading'] = False
        # Save session after update
        session_manager.save_session(req.session_id)
    
    threading.Thread(target=fetch_data, daemon=True).start()
    
    # Save session
    session_manager.save_session(req.session_id)
    print(f"✅ Watchlist modification saved for {req.session_id}")
    
    return {
        "success": True,
        "message": f"Added {req.symbol} to watchlist",
        "stock": stock_data
    }

class SetDateRequest(BaseModel):
    session_id: str
    date: str # YYYY-MM-DD

@router.post("/set-date")
async def set_watchlist_date(req: SetDateRequest):
    """
    Set the reference date for High/Low calculations in the watchlist
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.selected_date = req.date
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Watchlist date set to {req.date}"
    }

@router.delete("/remove")
async def remove_stock(req: RemoveStockRequest):
    """
    Remove stock from watchlist
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Remove from watchlist
    initial_len = len(session.watchlist)
    session.watchlist = [s for s in session.watchlist if s['token'] != req.token]
    
    if len(session.watchlist) == initial_len:
        raise HTTPException(status_code=404, detail="Stock not found in watchlist")
    
    # Unsubscribe from WebSocket
    ws_manager.unsubscribe_token(req.session_id, req.token)
    
    # Remove related alerts
    session.alerts = [a for a in session.alerts if a['token'] != req.token]
    
    # Save session
    session_manager.save_session(req.session_id)
    
    return {
        "success": True,
        "message": f"Removed stock from watchlist"
    }

@router.post("/refresh")
async def refresh_watchlist(req: RefreshRequest):
    """
    Refresh LTP and weekly close for all stocks
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    def refresh_all():
        smart_api = session.smart_api
        if not smart_api:
            print("No SmartAPI instance in session for refresh")
            return
        
        for stock in session.watchlist:
            stock['loading'] = True
            
            # Fetch LTP
            ltp = angel_service.fetch_ltp(smart_api, stock['symbol'], stock['token'])
            if ltp:
                stock['ltp'] = ltp
            
            # Fetch High/Low/Close for the session's selected date
            pdh, pdl, pdc = angel_service.fetch_previous_day_high_low(
                smart_api, stock['token'], specific_date=session.selected_date
            )
            if pdh is not None: stock['pdh'] = pdh
            if pdl is not None: stock['pdl'] = pdl
            if pdc is not None: stock['pdc'] = pdc
            
            stock['loading'] = False
            # Small sleep to respect rate limits during bulk refresh
            time.sleep(0.5)
            
        # Save session after all updates
        session_manager.save_session(req.session_id)
    
    threading.Thread(target=refresh_all, daemon=True).start()
    
    return {
        "success": True,
        "message": "Refreshing watchlist data in background"
    }

@router.get("/search/{query}")
async def search_symbols(query: str):
    """
    Search for stock symbols
    """
    if len(query) < 3:
        return {"results": []}
    
    results = angel_service.search_symbols(query)
    
    return {
        "results": results
    }

