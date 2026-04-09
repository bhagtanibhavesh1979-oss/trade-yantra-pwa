from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

def tick_round(price, tick=0.05):
    if price is None: return 0.0
    try:
        return round(float(price) * 20) / 20.0
    except:
        return float(price)

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
                    valid_candles = []
                    for c in bp_data['data']:
                        ts = c[0]
                        # Match Date (Ignore Leakage from previous day)
                        if blueprint_date not in ts: continue
                        # Match Time (Ignore Opening Noise)
                        time_val = ts.split(' ')[1] if ' ' in ts else (ts.split('T')[1] if 'T' in ts else "")
                        if time_val < "09:15": continue
                        valid_candles.append(c)
                        
                    if valid_candles:
                        high_val = max(float(c[2]) for c in valid_candles)
                        low_val = min(float(c[3]) for c in valid_candles)
                        print(f"[OK] Blueprint loaded from {blueprint_date}: H={high_val} L={low_val}")
            except Exception as e: 
                print(f"[WARN] Failed to fetch Blueprint for {blueprint_date}: {e}. Using Watchlist H/L.")
        
        # Fallback if 0
        if high_val <= 0 or low_val <= 0:
            return {"error": "Invalid Levels. Please ensure the Blueprint Date has data or Watchlist High/Low is set."}

        diff = high_val - low_val
        step = diff / 2.0 # Major Step (Red to Green, Green to Black)
        half_step = step / 2.0 # Half-Step (Purple lines)
        
        levels = []
        for j in range(-12, 25): 
            price = tick_round(low_val + (j * half_step))
            name = ""
            if j % 2 == 0:
                idx = j // 2
                if idx == 0: name = "Low"
                elif idx == 1: name = "M"
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
                    
                    # STRICT TIME FILTER: Ignore 9:00 - 9:14:59 candles (Opening noise / Pre-market)
                    time_val = ts.split(' ')[1] if ' ' in ts else (ts.split('T')[1] if 'T' in ts else "")
                    if time_val and time_val < "09:15":
                        continue
                        
                    final_price, last_timestamp = close_p, ts
                    
                    # Track previous close to detect gaps
                    prev_c_ref = last_close_p if last_close_p is not None else open_p

                    # --- OUTER BOUNDARY CHECK: No trades outside S6/R6 range ---
                    min_lv_p = levels[0]['p']
                    max_lv_p = levels[-1]['p']
                    if close_p < min_lv_p or close_p > max_lv_p:
                        if current_position:
                            exit_price = tick_round(close_p)
                            pnl = (exit_price - current_position['entry_price']) * quantity if current_position['side'] == "BUY" else (current_position['entry_price'] - exit_price) * quantity
                            all_trades.append({**current_position, "exit_price": exit_price, "exit_time": ts, "pnl": round(pnl, 2), "reason": "OUTSIDE_BOUNDS"})
                            running_balance += pnl
                            total_pnl += pnl
                            current_position = None
                        last_close_p = close_p
                        continue

                    # 1. POSITION MONITORING (SAR)
                    if current_position:
                        side, entry_p, entry_lv_p = current_position['side'], current_position['entry_price'], current_position.get('level_p', 0)
                        exit_price, reason = None, ""
                        
                        test_p_up = high_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        test_p_down = low_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        
                        # A. Target Check
                        if target_val:
                            if target_type == "POINTS":
                                if side == "BUY" and high_p >= (entry_p + target_val): exit_price, reason = entry_p + target_val, "TARGET_PTS"
                                elif side == "SELL" and low_p <= (entry_p - target_val): exit_price, reason = entry_p - target_val, "TARGET_PTS"
                            elif target_type == "AMOUNT":
                                # Profit = (Exit - Entry) * Qty
                                # Required Exit = Entry + (Target / Qty)
                                target_pts = target_val / quantity
                                if side == "BUY" and high_p >= (entry_p + target_pts): exit_price, reason = entry_p + target_pts, "TARGET_AMT"
                                elif side == "SELL" and low_p <= (entry_p - target_pts): exit_price, reason = entry_p - target_pts, "TARGET_AMT"

                        # B. Stop Loss Check (Missing in original logic)
                        sl_val = strategy_config.get('stop_loss')
                        if not exit_price and sl_val:
                            if side == "BUY" and low_p <= (entry_p - sl_val): exit_price, reason = entry_p - sl_val, "STOP_LOSS"
                            elif side == "SELL" and high_p >= (entry_p + sl_val): exit_price, reason = entry_p + sl_val, "STOP_LOSS"

                        # C. SAR Logic (Trap/Rejection)
                        if not exit_price:
                            for lv in levels:
                                b = lv['p'] * buffer_pct
                                if side == "BUY":
                                    # Trap: Price goes below any level it should have held (Prev Close support)
                                    if test_p_down < (lv['p'] - b) and prev_c_ref >= (lv['p'] - b):
                                        exit_price, reason = lv['p'] - b, f"TRAP_{lv['n']}"
                                        break
                                    # Rejection: Hit higher level and failed
                                    elif high_p >= (lv['p'] + b) and close_p < lv['p']:
                                        exit_price, reason = tick_round(close_p), f"REJECTION_{lv['n']}"
                                        break
                                else:
                                    # Trap: Price breaks above resistance
                                    if test_p_up > (lv['p'] + b) and prev_c_ref <= (lv['p'] + b):
                                        exit_price, reason = lv['p'] + b, f"TRAP_{lv['n']}"
                                        break
                                    # Rejection: Hit lower level and failed
                                    elif low_p <= (lv['p'] - b) and close_p > lv['p']: 
                                        exit_price, reason = tick_round(close_p), f"REJECTION_{lv['n']}"
                                        break

                        if exit_price:
                            exit_price = tick_round(exit_price)
                            pnl = (exit_price - entry_p) * quantity if side == "BUY" else (entry_p - exit_price) * quantity
                            all_trades.append({**current_position, "exit_price": exit_price, "exit_time": ts, "pnl": round(pnl, 2), "reason": reason})
                            running_balance += pnl
                            total_pnl += pnl
                            
                            # STOP-AND-REVERSE: If reason was a TRAP or REJECTION, flip the position
                            if "TRAP" in reason or "REJECTION" in reason:
                                new_side = "SELL" if side == "BUY" else "BUY"
                                current_position = {"side": new_side, "entry_price": exit_price, "time": ts, "level": "SAR_FLIP", "level_p": exit_price}
                            else:
                                # Normal exit (Target or SL)
                                current_position = None

                    # 2. ENTRY MONITORING (SAR Hysteresis)
                    if current_position is None:
                        found_lv, side, entry_p_fixed = None, None, None
                        
                        trigger_p_up = high_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        trigger_p_down = low_p if trigger_mode == 'INSTANT_TOUCH' else close_p
                        
                        for lv in reversed(levels):
                            b = lv['p'] * buffer_pct
                            # Breakout UP (LONG ENTRY)
                            # Logic: Close > Level
                            if trigger_p_up > lv['p'] and (prev_c_ref <= lv['p'] or idx_c == 0):
                                side = "BUY"
                                if trigger_mode == 'CANDLE_CLOSE':
                                    entry_p_fixed = tick_round(close_p)
                                else:
                                    entry_p_fixed = tick_round(max(open_p, lv['p']))

                                found_lv = lv
                                break
                            # Rejection DOWN (SHORT SAR from Buy Level?) 
                            # Logic: Close < Level - Buffer
                            elif high_p >= (lv['p'] + b) and close_p < (lv['p'] - b):
                                # This is a specific Trap/Rejection case, but main SAR is below
                                pass 

                        if not found_lv:
                            for lv in levels:
                                b = lv['p'] * buffer_pct
                                # Breakout DOWN (SHORT ENTRY)
                                # Logic: Close < (Level - Buffer)
                                if trigger_p_down < (lv['p'] - b) and (prev_c_ref >= (lv['p'] - b) or idx_c == 0):
                                    side = "SELL"
                                    if trigger_mode == 'CANDLE_CLOSE':
                                        entry_p_fixed = tick_round(close_p)
                                    else:
                                        entry_p_fixed = tick_round(min(open_p, lv['p'] - b))
                                    found_lv = lv
                                    break
                                # Rejection UP (LONG SAR from Sell Level?)
                                # Logic: Close > (Level + Buffer)
                                elif low_p <= (lv['p'] - b) and close_p > (lv['p'] + b):
                                     # Covered by Breakout UP loop
                                     pass

                        if found_lv:
                            current_position = {"side": side, "entry_price": entry_p_fixed, "time": ts, "level": found_lv['n'], "level_p": found_lv['p'], "type": trigger_mode}
                    
                    last_close_p = close_p
                except Exception as e:
                    print(f"[DEBUG] Candle Error at {candle[0]}: {e}")
                    continue

            # Intraday Square Off at Day End
            if trade_mode == "INTRADAY" and current_position:
                exit_p = tick_round(final_price)
                pnl = (exit_p - current_position['entry_price']) * quantity if current_position['side'] == "BUY" else (current_position['entry_price'] - exit_p) * quantity
                all_trades.append({**current_position, "exit_price": exit_p, "exit_time": last_timestamp, "pnl": round(pnl, 2), "reason": "EOD_SQUARE_OFF"})
                running_balance += pnl
                total_pnl += pnl
                current_position = None

            equity_curve.append({"time": date, "balance": round(running_balance, 2)})

        # Terminal Cleanup for Positional
        if current_position:
            exit_p = tick_round(final_price)
            pnl = (exit_p - current_position['entry_price']) * quantity if current_position['side'] == "BUY" else (current_position['entry_price'] - exit_p) * quantity
            all_trades.append({**current_position, "exit_price": exit_p, "exit_time": last_timestamp, "pnl": round(pnl, 2), "reason": "TERMINATED"})
            running_balance += pnl
            total_pnl += pnl

        wins = len([t for t in all_trades if t['pnl'] > 0])
        total_brokerage = len(all_trades) * 50.0 # Estimate 50 per trade (Brokerage + STT + Taxes)
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


