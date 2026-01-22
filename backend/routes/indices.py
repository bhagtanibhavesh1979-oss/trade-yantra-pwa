"""
Indices Routes
Fetch live data for major NSE indices
"""
from fastapi import APIRouter, HTTPException
from services.session_manager import session_manager
from services.angel_service import angel_service
import datetime
import traceback

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

# PDC Cache to avoid redundant history calls
pdc_cache = {}

# Global cache for indices to prevent mobile timeouts
indices_cache = {
    "data": None,
    "last_updated": 0
}
CACHE_DURATION = 300 # 5 minutes

@router.get("/{session_id}")
async def get_indices(session_id: str):
    try:
        # 1. Return cached data if available and fresh
        now = time.time()
        if indices_cache["data"] and (now - indices_cache["last_updated"]) < CACHE_DURATION:
            return {"indices": indices_cache["data"]}

        session = session_manager.get_session(session_id)
        if not session:
            # If no sessions, we can still show cached data as it's generic index data
            if indices_cache["data"]:
                return {"indices": indices_cache["data"]}
            return {"indices": []}
        
        smart_api = session.smart_api
        if not smart_api:
            # Fallback to cache
            if indices_cache["data"]:
                return {"indices": indices_cache["data"]}
            return {"indices": []}
        
        indices_data = []
        
        # 2. Fetch data ( Angel One rates limit applies, so caching is critical )
        for index in INDICES:
            try:
                # Fetch LTP
                exchange = index.get("exch", "NSE")
                ltp_data = smart_api.ltpData(exchange, index["symbol"], index["token"])
                ltp = 0
                if ltp_data and ltp_data.get('status'):
                    ltp = ltp_data['data']['ltp']
                
                # Fetch previous day close
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                cached = pdc_cache.get(index["token"])
                
                pdc = 0
                if cached and cached["date"] == today_str:
                    pdc = cached["pdc"]
                else:
                    try:
                        pdc = angel_service.fetch_previous_day_close(smart_api, index["token"], exchange)
                        if pdc:
                            pdc_cache[index["token"]] = {"pdc": pdc, "date": today_str}
                    except:
                        pass
                
                indices_data.append({
                    "symbol": index["symbol"],
                    "token": index["token"],
                    "ltp": ltp,
                    "pdc": pdc or 0,
                })
            except:
                indices_data.append({
                    "symbol": index["symbol"],
                    "token": index["token"],
                    "ltp": 0,
                    "pdc": 0,
                })
        
        # 3. Update global cache
        if indices_data:
            indices_cache["data"] = indices_data
            indices_cache["last_updated"] = now

        return {
            "indices": indices_data
        }
    except Exception as e:
        print(f"[ERROR] Indices route failed: {e}")
        # Return empty safe response instead of 500
        return {"indices": []}
