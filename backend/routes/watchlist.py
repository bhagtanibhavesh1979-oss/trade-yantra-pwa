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

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])

class AddStockRequest(BaseModel):
    session_id: str
    symbol: str
    token: str
    exch_seg: str = "NSE"

class RemoveStockRequest(BaseModel):
    session_id: str
    token: str

class RefreshRequest(BaseModel):
    session_id: str

@router.get("/{session_id}")
async def get_watchlist(session_id: str):
    """
    Get user's watchlist
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "watchlist": session.watchlist
    }

@router.post("/add")
async def add_stock(req: AddStockRequest):
    """
    Add stock to watchlist
    Fetches initial LTP and weekly close, then subscribes to WebSocket
    """
    session = session_manager.get_session(req.session_id)
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
        "wc": 0.0,
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
        
        # Fetch previous day close
        pdc = angel_service.fetch_previous_day_close(smart_api, req.token)
        if pdc:
            stock_data['pdc'] = pdc
        
        # Fetch weekly close
        wc = angel_service.fetch_historical_data(smart_api, req.token)
        if wc:
            stock_data['wc'] = wc
        
        stock_data['loading'] = False
    
    threading.Thread(target=fetch_data, daemon=True).start()
    
    return {
        "success": True,
        "message": f"Added {req.symbol} to watchlist",
        "stock": stock_data
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
            
            # Fetch previous day close
            pdc = angel_service.fetch_previous_day_close(smart_api, stock['token'])
            if pdc:
                stock['pdc'] = pdc
            
            # Fetch weekly close
            wc = angel_service.fetch_historical_data(smart_api, stock['token'])
            if wc:
                stock['wc'] = wc
            
            stock['loading'] = False
    
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
