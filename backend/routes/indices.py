"""
Indices Routes
Fetch live data for major NSE indices
"""
from fastapi import APIRouter, HTTPException
from services.session_manager import session_manager
from services.angel_service import angel_service

router = APIRouter(prefix="/api/indices", tags=["Indices"])

# Major Indices with tokens
INDICES = [
    {"symbol": "NIFTY 50", "token": "99926000", "exch": "NSE"},
    {"symbol": "NIFTY BANK", "token": "99926009", "exch": "NSE"},
    {"symbol": "SENSEX", "token": "99919000", "exch": "BSE"},
    {"symbol": "NIFTY IT", "token": "99926013", "exch": "NSE"},
    {"symbol": "NIFTY PHARMA", "token": "99926023", "exch": "NSE"},
    {"symbol": "NIFTY AUTO", "token": "99926003", "exch": "NSE"},
    {"symbol": "NIFTY FMCG", "token": "99926011", "exch": "NSE"},
    {"symbol": "NIFTY METAL", "token": "99926015", "exch": "NSE"},
    {"symbol": "NIFTY REALTY", "token": "99926024", "exch": "NSE"},
    {"symbol": "NIFTY ENERGY", "token": "99926010", "exch": "NSE"},
    {"symbol": "NIFTY FIN SERVICE", "token": "99926012", "exch": "NSE"},
]

@router.get("/{session_id}")
async def get_indices(session_id: str):
    """
    Get live data for major indices
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    smart_api = session.smart_api
    if not smart_api:
        raise HTTPException(status_code=500, detail="SmartAPI not initialized")
    
    indices_data = []
    
    for index in INDICES:
        try:
            # Fetch LTP
            exchange = index.get("exch", "NSE")
            ltp_data = smart_api.ltpData(exchange, index["symbol"], index["token"])
            ltp = 0
            if ltp_data and ltp_data.get('status'):
                ltp = ltp_data['data']['ltp']
            
            # Fetch previous day close using historical data
            pdc = angel_service.fetch_previous_day_close(smart_api, index["token"], exchange)
            
            indices_data.append({
                "symbol": index["symbol"],
                "token": index["token"],
                "ltp": ltp,
                "pdc": pdc or 0,
            })
        except Exception as e:
            print(f"Error fetching {index['symbol']}: {e}")
            indices_data.append({
                "symbol": index["symbol"],
                "token": index["token"],
                "ltp": 0,
                "pdc": 0,
            })
    
    return {
        "indices": indices_data
    }
