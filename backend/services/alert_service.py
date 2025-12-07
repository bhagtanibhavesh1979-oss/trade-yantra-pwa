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
    
    # Generate resistance levels (ABOVE current price)
    curr = weekly_close
    for i in range(10):
        curr += pattern[i % 3]
        if curr > ltp:
            levels.append({
                "price": round(curr, 2),
                "type": "ABOVE"
            })
    
    # Generate support levels (BELOW current price)
    curr = weekly_close
    for i in range(10):
        curr -= pattern[i % 3]
        if curr < ltp:
            levels.append({
                "price": round(curr, 2),
                "type": "BELOW"
            })
    
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
    return {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "symbol": stock['symbol'],
        "msg": f"{stock['symbol']} hit {alert['price']} ({alert['condition']})",
        "price": stock['ltp'],
        "alert_id": alert['id']
    }

def create_alert(symbol: str, token: str, condition: str, price: float, alert_type: str = "MANUAL") -> Dict:
    """
    Create a new alert
    """
    return {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "token": token,
        "condition": condition,
        "price": price,
        "active": True,
        "type": alert_type,
        "created_at": datetime.datetime.now().isoformat()
    }
