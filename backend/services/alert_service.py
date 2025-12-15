"""
Alert Service - 3-6-9 Trading Logic
"""
from typing import List, Dict
import datetime
import uuid

def generate_369_levels(ltp: float, weekly_close: float) -> List[Dict]:
    """
    Generate 3-6-9 alert levels based on weekly close
    Pattern: [3,6,9] for stocks < 3333, [30,60,90] for stocks > 3333
    """
    if weekly_close <= 0:
        return []
    
    levels = []
    pattern = [30, 60, 90] if weekly_close > 3333 else [3, 6, 9]
    
    # Generate potential UP levels (Resistance flow)
    curr = weekly_close
    for i in range(10):
        curr += pattern[i % 3]
        price = round(curr, 2)
        
        if price > ltp:
            levels.append({"price": price, "type": "ABOVE"})
        elif price < ltp:
            levels.append({"price": price, "type": "BELOW"})
    
    # Generate potential DOWN levels (Support flow)
    curr = weekly_close
    for i in range(10):
        curr -= pattern[i % 3]
        price = round(curr, 2)
        
        # Dynamic typing: If price is ABOVE ltp, it's resistance. If BELOW, it's support.
        if price > ltp:
            levels.append({"price": price, "type": "ABOVE"})
        elif price < ltp:
            levels.append({"price": price, "type": "BELOW"})
    
    return levels

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
