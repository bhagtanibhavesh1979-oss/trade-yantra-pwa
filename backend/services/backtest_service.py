from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

class BacktestService:
    def __init__(self):
        pass

    def run_backtest(self, smart_api, symbol: str, token: str, exch: str, start_date: str, end_date: str, strategy_config: Dict):
        from services.angel_service import angel_service

        # 1. Level Calculation (Full Difference Logic)
        blueprint_date = strategy_config.get('blueprint_date')
        high_val = float(strategy_config.get('high', 0))
        low_val = float(strategy_config.get('low', 0))

        if blueprint_date:
            try:
                req_bp = {"exchange": exch, "symboltoken": str(token), "interval": "ONE_MINUTE", "fromdate": f"{blueprint_date} 09:15", "todate": f"{blueprint_date} 15:30"}
                bp_data = angel_service.fetch_candle_data(smart_api, req_bp)
                if bp_data and bp_data.get('data'):
                    high_val = max(float(c[2]) for c in bp_data['data'])
                    low_val = min(float(c[3]) for c in bp_data['data'])
                    print(f"[OK] Blueprint loaded from {blueprint_date}: H={high_val} L={low_val}")
            except: 
                print(f"[WARN] Failed to fetch Blueprint for {blueprint_date}. Using Watchlist H/L.")
        
        # Fallback if 0
        if high_val <= 0 or low_val <= 0:
            return {"error": "Invalid Levels. Please ensure the Blueprint Date has data or Watchlist High/Low is set."}

        diff = high_val - low_val
        step = diff / 2.0 # Major Step (Red to Green, Green to Black)
        half_step = step / 2.0 # Half-Step (Purple lines)
        
        levels = []
        for j in range(-12, 25): 
            price = round(low_val + (j * half_step), 2)
            name = ""
            if j % 2 == 0:
                idx = j // 2
                if idx == 0: name = "Low"
                elif idx == 1: name = "Mid-Pivot"
                elif idx == 2: name = "High"
                elif idx > 2: name = f"R{idx-2}"
                else: name = f"S{abs(idx)}"
            else:
                name = f"Mid_{j}"
            levels.append({"p": price, "n": name})
        
        levels = sorted(levels, key=lambda x: x['p'])
        buffer_pct = strategy_config.get('buffer', 0.1) / 100.0
        trigger_mode = strategy_config.get('trigger_mode', 'CANDLE_CLOSE')
        
        target_val = strategy_config.get('target')
        target_type = strategy_config.get('target_type', 'POINTS') 
        interval = strategy_config.get('interval', 'FIFTEEN_MINUTE')
        quantity = strategy_config.get('quantity', 100)
        trade_mode = strategy_config.get('trade_type', 'INTRADAY')

        # Dates to simulate
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        dates = [(start_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_dt - start_dt).days + 1)]

        all_trades, total_pnl, running_balance = [], 0.0, 0.0
        equity_curve, current_position, final_price, last_timestamp = [{"time": start_date, "balance": 0.0}], None, 0.0, ""
        last_close_p = None

        for date in dates:
            if datetime.strptime(date, '%Y-%m-%d').weekday() >= 5: continue
            hist_data = angel_service.fetch_candle_data(smart_api, {"exchange": exch, "symboltoken": str(token), "interval": interval, "fromdate": f"{date} 09:15", "todate": f"{date} 15:30"})
            
            if not hist_data:
                 print(f"[WARN] No response from API for {date}")
                 continue
            
            if hist_data.get('status') is False:
                print(f"[ERROR] API Error on {date}: {hist_data.get('message')}")
                if "Invalid Session" in str(hist_data.get('message')) or "Authorization" in str(hist_data.get('message')):
                     raise Exception("Session Expired. Please Re-Login.")
                continue

            if not hist_data.get('data'): 
                print(f"[INFO] No candle data found for {date}")
                continue
                
            data_list = hist_data.get('data')
            for idx_c, candle in enumerate(data_list):
                try:
                    ts, open_p, high_p, low_p, close_p = candle[0], float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4])
                    final_price, last_timestamp = close_p, ts
                    
                    # Track previous close to detect gaps
                    prev_c_ref = last_close_p if last_close_p is not None else open_p

                    # 1. POSITION MONITORING (SAR)
                    if current_position:
                        side, entry_p, entry_lv_p = current_position['side'], current_position['entry_price'], current_position.get('level_p', 0)
                        exit_price, reason = None, ""
                        
                        test_p_up = high_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        test_p_down = low_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        
                        if target_val and target_type == "POINTS":
                            if side == "BUY" and high_p >= (entry_p + target_val): exit_price, reason = entry_p + target_val, "TARGET_PTS"
                            elif side == "SELL" and low_p <= (entry_p - target_val): exit_price, reason = entry_p - target_val, "TARGET_PTS"

                        if not exit_price:
                            for lv in levels:
                                b = lv['p'] * buffer_pct
                                if side == "BUY":
                                    # Trap: Price goes below any level it should have held
                                    if test_p_down < (lv['p'] - b) and prev_c_ref >= (lv['p'] - b):
                                        exit_price, reason = lv['p'] - b, "trap_reverse"
                                        break
                                    # Rejection: Hit higher level and failed
                                    elif high_p >= (lv['p'] + b) and close_p < lv['p']:
                                        exit_price, reason = close_p, "rejection_reverse"
                                        break
                                else:
                                    # Trap: Price breaks above resistance
                                    if test_p_up > (lv['p'] + b) and prev_c_ref <= (lv['p'] + b):
                                        exit_price, reason = lv['p'] + b, "trap_reverse"
                                        break
                                    # Rejection: Hit lower level and failed
                                    elif low_p <= (lv['p'] - b) and close_p > lv['p']: 
                                        exit_price, reason = close_p, "rejection_reverse"
                                        break

                        if exit_price:
                            pnl = (exit_price - entry_p) * quantity if side == "BUY" else (entry_p - exit_price) * quantity
                            all_trades.append({**current_position, "exit_price": exit_price, "exit_time": ts, "pnl": round(pnl, 2), "reason": reason})
                            running_balance += pnl
                            total_pnl += pnl
                            new_side = "SELL" if side == "BUY" else "BUY"
                            current_position = {"side": new_side, "entry_price": exit_price, "time": ts, "level": "SAR_FLIP", "level_p": exit_price}

                    # 2. ENTRY MONITORING (If flat)
                    if current_position is None:
                        found_lv, side, entry_p_fixed = None, None, None
                        
                        # Use high/low for Instant, close for Candle
                        trigger_p_up = high_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        trigger_p_down = low_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        
                        for lv in reversed(levels):
                            b = lv['p'] * buffer_pct
                            # Breakout UP (Or started above)
                            if trigger_p_up > (lv['p'] + b) and (prev_c_ref <= (lv['p'] + b) or idx_c == 0):
                                found_lv, side, entry_p_fixed = lv, "BUY", max(open_p, lv['p'] + b)
                                break
                            # Rejection DOWN
                            elif high_p >= (lv['p'] + b) and close_p < lv['p']:
                                found_lv, side, entry_p_fixed = lv, "SELL", close_p
                                break
                                
                        if not found_lv:
                            for lv in levels:
                                b = lv['p'] * buffer_pct
                                # Breakout DOWN (Or started below)
                                if trigger_p_down < (lv['p'] - b) and (prev_c_ref >= (lv['p'] - b) or idx_c == 0):
                                    found_lv, side, entry_p_fixed = lv, "SELL", min(open_p, lv['p'] - b)
                                    break
                                # Rejection UP
                                elif low_p <= (lv['p'] - b) and close_p > lv['p']:
                                    found_lv, side, entry_p_fixed = lv, "BUY", close_p
                                    break

                        if found_lv:
                            current_position = {"side": side, "entry_price": entry_p_fixed, "time": ts, "level": found_lv['n'], "level_p": found_lv['p'], "type": trigger_mode}
                    
                    last_close_p = close_p
                except Exception as e:
                    print(f"[DEBUG] Candle Error at {candle[0]}: {e}")
                    continue

            # Intraday Square Off at Day End
            if trade_mode == "INTRADAY" and current_position:
                pnl = (final_price - current_position['entry_price']) * quantity if current_position['side'] == "BUY" else (current_position['entry_price'] - final_price) * quantity
                all_trades.append({**current_position, "exit_price": final_price, "exit_time": last_timestamp, "pnl": pnl, "reason": "EOD_SQUARE_OFF"})
                running_balance += pnl
                total_pnl += pnl
                current_position = None

            equity_curve.append({"time": date, "balance": round(running_balance, 2)})

        # Terminal Cleanup for Positional
        if current_position:
            pnl = (final_price - current_position['entry_price']) * quantity if current_position['side'] == "BUY" else (current_position['entry_price'] - final_price) * quantity
            all_trades.append({**current_position, "exit_price": final_price, "exit_time": last_timestamp, "pnl": pnl, "reason": "TERMINATED"})
            running_balance += pnl
            total_pnl += pnl

        wins = len([t for t in all_trades if t['pnl'] > 0])
        total_brokerage = len(all_trades) * 50.0 # Estimate ₹50 per trade (Brokerage + STT + Taxes)
        net_pnl = total_pnl - total_brokerage
        
        return {
            "summary": {
                "total_pnl": round(total_pnl, 2),
                "total_brokerage": round(total_brokerage, 2),
                "net_pnl": round(net_pnl, 2),
                "total_trades": len(all_trades),
                "win_rate": round(wins/len(all_trades)*100, 1) if all_trades else 0,
                "wins": wins,
                "losses": len(all_trades)-wins,
                "period": f"{start_date} to {end_date}"
            },
            "trades": all_trades,
            "equity_curve": equity_curve
        }

backtest_service = BacktestService()


