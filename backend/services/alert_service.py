"""
Alert Service - High/Low Alert Strategy
Handles calculation of High, Low, Resistance and Support levels
"""
from typing import List, Dict
import datetime
import uuid

from services.angel_service import angel_service
from SmartApi import SmartConnect

def generate_high_low_alerts(smart_api: SmartConnect, symbol: str, token: str, date: str, start_time: str, end_time: str, is_custom: bool, exchange: str = "NSE") -> List[Dict]:
    """
    Generate Alerts based on High/Low of a specific period.
    Formula:
    Diff = High - Low
    Resistance = High + Diff
    Support = Low - Diff
    """
    try:
        # Parse Dates
        base_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        
        # For non-custom range, we want ONLY the selected date's High/Low
        # Set both from and to as the same date to get only that day's data
        if not is_custom:
            # Use the full day range for the selected date
            from_dt = datetime.datetime.strptime(f"{date} 09:15", "%Y-%m-%d %H:%M")
            to_dt = datetime.datetime.strptime(f"{date} 15:30", "%Y-%m-%d %H:%M")
            interval = "ONE_MINUTE"  # Use minute data to ensure we get the exact date
        else:
            # Custom time range within the selected date
            from_dt = datetime.datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            to_dt = datetime.datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
            interval = "ONE_MINUTE"
        
        api_from = from_dt.strftime('%Y-%m-%d %H:%M')
        api_to = to_dt.strftime('%Y-%m-%d %H:%M')
        
        req = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": api_from,
            "todate": api_to
        }
        
        print(f"DEBUG: Fetching candles for {symbol} from {api_from} to {api_to}")
        data = angel_service.fetch_candle_data(smart_api, req)
        
        high = -1.0
        low = 99999999.0
        
        if data and data.get('status') and data.get('data'):
            candles = data['data']
            if not candles: 
                print(f"DEBUG: No candle data returned for {symbol}")
                return []
            
            print(f"DEBUG: Received {len(candles)} candles for {symbol}")
            
            # Calculate High/Low from all candles in the range
            for c in candles:
                c_high = c[2]
                c_low = c[3]
                if c_high > high: high = c_high
                if c_low < low: low = c_low
            
            print(f"DEBUG: Calculated High={high}, Low={low} for {symbol}")
        else:
            print(f"DEBUG: API returned no data or error for {symbol}")
            return []
        
        if high <= 0 or low >= 99999999: return []
        
        # Calculate half-difference for multi-level support/resistance
        diff = (high - low) / 2
        
        # Generate 4 resistance levels: R1, R2, R3, R4
        r1 = round(high + diff, 2)
        r2 = round(high + (2 * diff), 2)
        r3 = round(high + (3 * diff), 2)
        r4 = round(high + (4 * diff), 2)
        
        # Generate 4 support levels: S1, S2, S3, S4
        s1 = round(low - diff, 2)
        s2 = round(low - (2 * diff), 2)
        s3 = round(low - (3 * diff), 2)
        s4 = round(low - (4 * diff), 2)
        
        # Return 10 levels: High, Low, R1-R4, S1-S4
        levels = [
            {"price": high, "type": "ABOVE", "label": "High"},
            {"price": low, "type": "BELOW", "label": "Low"},
            {"price": r1, "type": "ABOVE", "label": "R1"},
            {"price": r2, "type": "ABOVE", "label": "R2"},
            {"price": r3, "type": "ABOVE", "label": "R3"},
            {"price": r4, "type": "ABOVE", "label": "R4"},
            {"price": s1, "type": "BELOW", "label": "S1"},
            {"price": s2, "type": "BELOW", "label": "S2"},
            {"price": s3, "type": "BELOW", "label": "S3"},
            {"price": s4, "type": "BELOW", "label": "S4"}
        ]
        
        print(f"Generated Levels for {symbol}: H={high}, L={low}, Diff={diff}")
        print(f"  Resistance: R1={r1}, R2={r2}, R3={r3}, R4={r4}")
        print(f"  Support: S1={s1}, S2={s2}, S3={s3}, S4={s4}")
        return levels
        
    except Exception as e:
        print(f"Gen Alert Error: {e}")
        return []

def check_alert_trigger(alert: Dict, stock: Dict) -> bool:
    """
    Check if alert should be triggered
    Returns: True if triggered
    """
    ltp = stock.get('ltp', 0)
    condition = alert.get('condition')
    price = alert.get('price', 0)
    
    if condition == "ABOVE" and ltp >= price:
        return True
    elif condition == "BELOW" and ltp <= price:
        return True
    
    return False

def create_alert_log(stock: Dict, alert: Dict) -> Dict:
    """
    Create alert log entry
    """
    # Use IST (UTC+5:30)
    ist_time = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    
    return {
        "time": datetime.datetime.utcnow().isoformat() + "Z", # Send UTC ISO string
        "symbol": stock['symbol'],
        "msg": f"{stock['symbol']} hit {alert['price']} ({alert['condition']})",
        "price": stock['ltp'],
        "alert_id": alert['id']
    }

def create_alert(symbol: str, token: str, condition: str, price: float, alert_type: str = "MANUAL") -> Dict:
    """
    Create a new alert
    """
    # Use IST (UTC+5:30)
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    
    return {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "token": token,
        "condition": condition,
        "price": price,
        "active": True,
        "type": alert_type,
        "created_at": ist_now.isoformat()
    }
