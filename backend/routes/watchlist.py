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

class AddStockRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    symbol: str
    token: str
    exch_seg: str = "NSE"

class RemoveStockRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    token: str

class RefreshRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None

@router.get("/{session_id}")
async def get_watchlist(session_id: str, client_id: Optional[str] = None):
    try:
        session = session_manager.get_session(session_id, client_id=client_id)
        if not session:
            return {"watchlist": []}
        return {"watchlist": session.watchlist}
    except:
        return {"watchlist": []}

@router.post("/add")
async def add_stock(req: AddStockRequest):
    try:
        session = session_manager.get_session(req.session_id, client_id=req.client_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if any(s['token'] == req.token for s in session.watchlist):
            raise HTTPException(status_code=400, detail="Stock already in watchlist")
        
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
        ws_manager.subscribe_token(req.session_id, req.token, stock_data)
        
        def fetch_data():
            try:
                smart_api = session.smart_api
                if not smart_api: return
                
                ltp = angel_service.fetch_ltp(smart_api, req.symbol, req.token, exchange=req.exch_seg)
                if ltp: stock_data['ltp'] = ltp
                
                pdh, pdl, _ = angel_service.fetch_previous_day_high_low(
                    smart_api, req.token, exchange=req.exch_seg, specific_date=session.selected_date
                )
                _, _, pdc = angel_service.fetch_previous_day_high_low(
                    smart_api, req.token, exchange=req.exch_seg, specific_date=None
                )

                if pdh is not None: stock_data['pdh'] = pdh
                if pdl is not None: stock_data['pdl'] = pdl
                if pdc is not None: stock_data['pdc'] = pdc
                
                stock_data['loading'] = False
                session_manager.save_session(req.session_id)
            except:
                pass
        
        threading.Thread(target=fetch_data, daemon=True).start()
        session_manager.save_session(req.session_id)
        
        return {
            "success": True,
            "message": f"Added {req.symbol} to watchlist",
            "stock": stock_data
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SetDateRequest(BaseModel):
    session_id: str
    client_id: Optional[str] = None
    date: str

@router.post("/set-date")
async def set_watchlist_date(req: SetDateRequest):
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.selected_date = req.date
    session_manager.save_session(req.session_id)
    return {"success": True, "message": f"Watchlist date set to {req.date}"}

@router.post("/remove")
async def remove_stock(req: RemoveStockRequest):
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_len = len(session.watchlist)
    session.watchlist = [s for s in session.watchlist if s['token'] != req.token]
    
    if len(session.watchlist) == initial_len:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    ws_manager.unsubscribe_token(req.session_id, req.token)
    session.alerts = [a for a in session.alerts if a['token'] != req.token]
    session_manager.save_session(req.session_id)
    
    return {"success": True, "message": "Removed stock"}

@router.post("/refresh")
async def refresh_watchlist(req: RefreshRequest):
    session = session_manager.get_session(req.session_id, client_id=req.client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    def refresh_all():
        try:
            smart_api = session.smart_api
            if not smart_api: return
            
            for stock in session.watchlist:
                try:
                    stock['loading'] = True
                    exch = stock.get('exch_seg', 'NSE')
                    ltp = angel_service.fetch_ltp(smart_api, stock['symbol'], stock['token'], exchange=exch)
                    if ltp: stock['ltp'] = ltp
                    
                    pdh, pdl, _ = angel_service.fetch_previous_day_high_low(
                        smart_api, stock['token'], exchange=exch, specific_date=session.selected_date
                    )
                    _, _, pdc = angel_service.fetch_previous_day_high_low(
                        smart_api, stock['token'], exchange=exch, specific_date=None
                    )

                    if pdh is not None: stock['pdh'] = pdh
                    if pdl is not None: stock['pdl'] = pdl
                    if pdc is not None: stock['pdc'] = pdc
                    stock['loading'] = False
                    time.sleep(0.5)
                except:
                    stock['loading'] = False
            session_manager.save_session(req.session_id)
        except:
            pass
    
    threading.Thread(target=refresh_all, daemon=True).start()
    return {"success": True, "message": "Refreshing in background"}

@router.get("/search/{query}")
async def search_symbols(query: str):
    if len(query) < 3: return {"results": []}
    return {"results": angel_service.search_symbols(query)}
