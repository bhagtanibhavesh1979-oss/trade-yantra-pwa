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
        
        # TradingView-matching main ladder (from the shared Pine script)
        # Main definitions:
        # diff = rangeHigh - rangeLow
        # midpoint = (rangeHigh + rangeLow) / 2
        # Target highs:  High + n*diff  (n=1..6)
        # Target lows:   Low  - n*diff  (n=1..6)
        diff = high - low
        midpoint = (high + low) / 2.0

        # Generate levels for n = 1..6 (R1..R6, S1..S6), plus Low/M/High
        # NOTE: We keep the condition mapping consistent with existing trigger logic:
        # - Resistance side levels trigger when price goes ABOVE => condition="ABOVE"
        # - Support side levels trigger when price goes BELOW => condition="BELOW"
        #
        # TradingView ladder logic uses alternating sides around the midpoint:
        #   Low (support) is BELOW
        #   Midpoint (R/S boundary) is treated as ABOVE in the Pine you shared
        #   High (top resistance) is ABOVE
        #
        # IMPORTANT: Your Telegram "side" is computed from alert.condition in
        # websocket_manager.py. So if we label a level as support, it must be
        # emitted with type="BELOW".
        levels = [
            {"price": tick_round(low), "type": "BELOW", "label": "Low"},
            {"price": tick_round(midpoint), "type": "ABOVE", "label": "M"},
            {"price": tick_round(high), "type": "ABOVE", "label": "High"},
        ]

        # Pine (main ladder) defines:
        # targetHigh1 = rangeHigh + diff
        # targetHigh2 = rangeHigh + 2*diff
        # targetHigh3 = rangeHigh + 3*diff
        # and similarly for lows (rangeLow - diff, -2*diff, -3*diff).
        # Your UI expects R1..R6 / S1..S6. We therefore extend using:
        # R{2}=High+2*diff, R{3}=High+3*diff ... (i.e., Rn = High + n*diff)
        # BUT TradingView also shows intermediate levels at 0.5*diff steps.
        # The requested 1499.20 BETWEEN 1478.50 and 1519.90 corresponds to:
        #   midBetween = midpoint + diff/4  (or equivalently High - 3*diff/4)
        # That value is NOT Rn for integer n.
        # To match TradingView’s visible ladder, we generate 0.5*diff steps as well
        # and label them with the existing R/S slots by choosing the nearest integer step.

        # Generate R1..R6 as High + k*(diff/2) where k=1..6.
        # This yields: R1=High+diff/2 (the "between" level), R2=High+diff, R3=High+1.5diff, ...
        for k in range(1, 7):
            r_price = high + (k * diff / 2.0)
            levels.append({"price": tick_round(r_price), "type": "ABOVE", "label": f"R{k}"})

        # Generate S1..S6 as Low - k*(diff/2) where k=1..6.
        for k in range(1, 7):
            s_price = low - (k * diff / 2.0)
            levels.append({"price": tick_round(s_price), "type": "BELOW", "label": f"S{k}"})


        # Stable ordering: Supports (S6..S1), Low, M, High, Resistances (R1..R6)
        def sort_key(lv):
            lab = str(lv.get('label',''))
            if lab == 'Low': return 100
            if lab == 'M': return 101
            if lab == 'High': return 102
            if lab.startswith('R'):
                try: return 200 + int(lab[1:])
                except: return 9999
            if lab.startswith('S'):
                try: return 50 - int(lab[1:])  # S6 first
                except: return 9999
            return 9999

        levels.sort(key=sort_key)

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
