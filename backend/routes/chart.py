"""
Chart Routes
Historical data for charts
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services.session_manager import session_manager
from services.angel_service import angel_service
import datetime

router = APIRouter(prefix="/api/chart", tags=["Chart"])

# Mapping from UI timeframe to Angel One interval string
TIMEFRAME_TO_INTERVAL = {
    "1m": "ONE_MINUTE",
    "3m": "THREE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1H": "ONE_HOUR",
    "4H": "FOUR_HOUR",
    "1D": "ONE_DAY",
    "1W": "ONE_WEEK",
    "1M": "ONE_MONTH"
}

@router.get("/history")
def get_chart_history(
    symbol: str = Query(None),
    token: str = Query(None),
    exchange: str = Query(None),
    interval: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    session_id: str = Query(None),
    client_id: Optional[str] = Query(None)
):
    """
    Get historical candle data for a symbol.
    """
    try:
        # Validate session
        session = session_manager.get_session(session_id, client_id=client_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Validate required parameters
        if not all([symbol, token, exchange, interval, from_date, to_date]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # Map interval to Angel One format
        angel_interval = TIMEFRAME_TO_INTERVAL.get(interval)
        if not angel_interval:
            raise HTTPException(status_code=400, detail=f"Unsupported interval: {interval}")
        
        # Convert dates to Angel One format: YYYY-MM-DD HH:MM
        # We assume the input dates are in YYYY-MM-DD format.
        # We'll set the time to market open and close for the given date.
        # For simplicity, we use 09:15 to 15:30 (Indian market hours).
        from_date_full = f"{from_date} 09:15"
        to_date_full = f"{to_date} 15:30"
        
        # Prepare request for Angel One
        req = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": angel_interval,
            "fromdate": from_date_full,
            "todate": to_date_full
        }
        
        # Fetch data from Angel One
        # We need a smart_api instance for the session
        smart_api = session_manager.get_smart_api(session_id, client_id)
        if not smart_api:
            raise HTTPException(status_code=404, detail="SmartAPI session not found")
        
        res = angel_service.fetch_candle_data(smart_api, req, priority='low')
        
        if not res or not res.get('status'):
            # If no data or error, return empty array
            return {"data": []}
        
        # Angel One returns data in the format:
        # {
        #   "status": True,
        #   "message": "SUCCESS",
        #   "data": [
        #       ["2024-06-01 09:15", 100, 110, 90, 105, 1000],
        #       ...
        #   ]
        # }
        # We need to convert to TradingView format: array of [timestamp, open, high, low, close]
        # where timestamp is Unix seconds.
        
        tv_data = []
        for candle in res.get('data', []):
            try:
                # Angel One can return "YYYY-MM-DDTHH:MM:SS+05:30" or "YYYY-MM-DD HH:MM"
                date_str = candle[0]
                if 'T' in date_str:
                    # Strip timezone for simple timestamp conversion
                    clean_str = date_str.split('+')[0]
                    dt = datetime.datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
                else:
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                timestamp = int(dt.timestamp())
            except Exception as e:
                print(f"Skipping candle due to date parse error: {candle[0]} - {e}")
                continue
            open_price = float(candle[1])
            high_price = float(candle[2])
            low_price = float(candle[3])
            close_price = float(candle[4])
            # We ignore volume (candle[5]) for now
            tv_data.append([timestamp, open_price, high_price, low_price, close_price])
        
        return {"data": tv_data}
    
    except Exception as e:
        # Log the error for debugging
        print(f"Error in chart history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")