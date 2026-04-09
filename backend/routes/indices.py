"""
Indices Routes
Fetch live data for major NSE indices
"""
from fastapi import APIRouter, HTTPException
from services.session_manager import session_manager
from services.angel_service import angel_service
from typing import Optional
import datetime
import traceback
import time

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
CACHE_DURATION = 60 # Reduced to 1 minute for better responsiveness

@router.get("/{session_id}")
async def get_indices(session_id: str, client_id: Optional[str] = None):
    try:
        # 1. Return cached data if available and fresh
        now = time.time()
        if indices_cache["data"] and (now - indices_cache["last_updated"]) < CACHE_DURATION:
            return {"indices": indices_cache["data"]}

        session = session_manager.get_session(session_id, client_id=client_id)
        if not session:
            # Check disk if not in memory (Recovery)
            if indices_cache["data"]: return {"indices": indices_cache["data"]}
            return {"indices": []}
        
        smart_api = session.smart_api
        if not smart_api:
            # Try to restore smart_api if missing
            if indices_cache["data"]: return {"indices": indices_cache["data"]}
            return {"indices": []}
        
        indices_data = []
        
        # 2. Fetch data
        for index in INDICES:
            try:
                exchange = index.get("exch", "NSE")
                
                # USE SAFE WRAPPER
                ltp = angel_service.fetch_ltp(smart_api, index["symbol"], index["token"], exchange)
                
                # Fetch previous day close
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                cached = pdc_cache.get(index["token"])
                
                pdc = 0
                if cached and cached["date"] == today_str:
                    pdc = cached["pdc"]
                else:
                    try:
                        pdc = angel_service.fetch_previous_day_close(smart_api, index["token"], exchange)
                    except: pass
                    
                    if pdc:
                        pdc_cache[index["token"]] = {"pdc": pdc, "date": today_str}
                
                indices_data.append({
                    "symbol": index["symbol"],
                    "token": index["token"],
                    "ltp": ltp or 0,
                    "pdc": pdc or 0,
                    "exch": exchange
                })
            except Exception as e:
                print(f"[ERROR] failed index {index['symbol']}: {e}")
                # Append cleanup
                indices_data.append({
                    "symbol": index["symbol"],
                    "token": index["token"],
                    "ltp": 0,
                    "pdc": 0,
                    "exch": exchange
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
        return {"indices": []}
