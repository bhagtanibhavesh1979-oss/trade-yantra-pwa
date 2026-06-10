"""
Alert Service - High/Low Alert Strategy
Handles calculation of High, Low, Resistance and Support levels
"""
from typing import List, Dict
import datetime
import uuid

def tick_round(price, tick=0.05):
    """Round to nearest 0.05 tick — identical to backtest_service.py"""
    if price is None: return 0.0
    try:
        return round(float(price) * 20) / 20.0
    except:
        return float(price)

from services.angel_service import angel_service
from SmartApi import SmartConnect

def generate_high_low_alerts(smart_api: SmartConnect, symbol: str, token: str, start_date: str, end_date: str, start_time: str, end_time: str, is_custom: bool, exchange: str = "NSE") -> List[Dict]:
    """
    Generate Alerts based on High/Low of a specific period.
    Formula:
    Diff = High - Low
    Resistance = High + Diff
    Support = Low - Diff
    """
    try:
        # Parse Dates
        if not is_custom:
            from_dt = datetime.datetime.strptime(f"{start_date} 09:15", "%Y-%m-%d %H:%M")
            to_dt = datetime.datetime.strptime(f"{end_date} 15:30", "%Y-%m-%d %H:%M")
            interval = "ONE_MINUTE"  # Use minute data to ensure we get the exact date
        else:
            from_dt = datetime.datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            to_dt = datetime.datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
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
                ts = c[0] # "YYYY-MM-DD HH:MM"
                
                try:
                    clean_ts = ts.split('+')[0].split('Z')[0].strip()
                    if 'T' in clean_ts:
                        dt_val = datetime.datetime.strptime(clean_ts[:16], "%Y-%m-%dT%H:%M")
                    else:
                        dt_val = datetime.datetime.strptime(clean_ts[:16], "%Y-%m-%d %H:%M")
                except Exception as parse_err:
                    print(f"Error parsing timestamp {ts}: {parse_err}")
                    continue
                
                # STRICT DATE + TIME FILTER
                if dt_val < from_dt or dt_val > to_dt:
                    continue
                    
                c_high = c[2]
                c_low = c[3]
                if c_high > high: high = c_high
                if low == 0 or c_low < low: low = c_low # Fixed 99999999 init issue
            
            print(f"DEBUG: Calculated High={high}, Low={low} for {symbol}")
        else:
            print(f"DEBUG: API returned no data or error for {symbol}")
            return []
        
        if high <= 0 or low >= 99999999: return []
        
        # Calculate quadrant steps (Matching TradingView exactly)
        diff = high - low
        step = diff / 2.0
        
        levels = []
        # Generate range from S3 (j = -6) to R3 (j = 8)
        for j in range(-6, 9):
            price = tick_round(low + (j * step))
            label = ""
            condition = "ABOVE" # Default
            
            if j == 0:
                label, condition = "Low", "BELOW"
            elif j == 1:
                label, condition = "M", "ABOVE"
            elif j == 2:
                label, condition = "High", "ABOVE"
            elif j > 2:
                if j % 2 == 0:
                    label = f"R{ (j - 2) // 2 }"
                else:
                    label = f"Mid_{j}"
                condition = "ABOVE"
            else: # j < 0
                if j % 2 == 0:
                    label = f"S{ abs(j) // 2 }"
                else:
                    label = f"Mid_{j}"
                condition = "BELOW"
                
            levels.append({"price": price, "type": condition, "label": label})
        
        print(f"Generated {len(levels)} levels for {symbol}: H={high}, L={low}, Diff={diff}")
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
