import threading
import time
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict


from backend.services.session_manager import session_manager
from backend.services.backtest_service import backtest_service
from backend.services.telegram_service import telegram_service
from backend.services.signal_state import signal_state


logger = logging.getLogger("live_signal_service")

IST = pytz.timezone("Asia/Kolkata")


def _tick_round(price, tick=0.05):
    if price is None:
        return 0.0
    try:
        return round(float(price) * 20) / 20.0
    except:
        return float(price)


def _signal_to_telegram(side: str, symbol: str, price: float, signal_label: str, timeframe: str, candle_time_ist: datetime):
    hhmm = candle_time_ist.strftime("%H:%M")
    day = candle_time_ist.strftime("%Y-%m-%d")

    if side == "BUY":
        emoji = "🟢"
        return (
            f"{emoji} BUY\n"
            f"Symbol: {symbol} Price: {price:.2f}\n"
            f"Signal: {signal_label}\n"
            f"Timeframe: {timeframe}\n"
            f"Time: {hhmm}"
        )
    if side == "SELL":
        emoji = "🔴"
        return (
            f"{emoji} SELL\n"
            f"Symbol: {symbol} Price: {price:.2f}\n"
            f"Signal: {signal_label}\n"
            f"Timeframe: {timeframe}\n"
            f"Time: {hhmm}"
        )
    # SAR reversal / trap / rejection mapped as SELL/BUY flip by backtest
    if side in ("SAR", "SAR_REVERSAL"):
        # This should be rendered as a dedicated SAR message by caller.
        return ""

    return (
        f"ℹ️ SIGNAL\nSymbol: {symbol} Price: {price:.2f}\n"
        f"Signal: {signal_label}\nTimeframe: {timeframe}\nTime: {hhmm} ({day})"
    )


class TelegramSignalEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._workers: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, threading.Event] = {}

    def start_for_session(self, session_id: str):
        with self._lock:
            if session_id in self._workers and self._workers[session_id].is_alive():
                return {"status": "already_running"}

            stop_evt = threading.Event()
            self._stop_flags[session_id] = stop_evt

            t = threading.Thread(target=self._run_loop, args=(session_id, stop_evt), daemon=True)
            self._workers[session_id] = t
            t.start()
            return {"status": "started"}

    def stop_for_session(self, session_id: str):
        with self._lock:
            if session_id in self._stop_flags:
                self._stop_flags[session_id].set()
                return {"status": "stopping"}
            return {"status": "not_running"}

    def _run_loop(self, session_id: str, stop_evt: threading.Event):
        logger.info(f"[TELEGRAM] Signal engine loop started for {session_id[:8]}")

        last_candle_tag = None

        while not stop_evt.is_set():
            try:
                now = datetime.now(IST)
                # Only CANDLE_CLOSE / 15m as in websocket_manager strategy
                candle_start_minute = (now.minute // 15) * 15
                candle_end = now.replace(minute=candle_start_minute, second=0, microsecond=0) + timedelta(minutes=15)
                candle_tag = candle_end.strftime("%Y-%m-%d %H:%M")


                # Wait a small offset after close so candle range is stable.
                # If we're within [close+0..close+40s], we process once.
                seconds_to_close = (now - (candle_end - timedelta(seconds=15))).total_seconds()  # approx
                # Simpler: process once per tag when second between 10..55
                if now.second >= 10 and now.second < 55:
                    if candle_tag != last_candle_tag:
                        last_candle_tag = candle_tag
                        self._process_candle_close(session_id, candle_end)

            except Exception as e:
                logger.exception(f"[TELEGRAM] Engine error: {e}")

            # Sleep small
            time.sleep(2)

    def _process_candle_close(self, session_id: str, candle_end_ist: datetime):
        session = session_manager.get_session(session_id)
        if not session:
            return
        if getattr(session, "is_paused", False):
            return

        if not session.watchlist:
            return

        # Blueprint inputs (persisted by /api/alerts/generate)
        bp_start = getattr(session, "blueprint_start_date", None)
        bp_end = getattr(session, "blueprint_end_date", None)
        if not bp_start or not bp_end:
            logger.warning(f"[TELEGRAM] Missing blueprint date range for session {session_id[:8]}. Skipping.")
            return

        # Recompute blueprint high/low EXACTLY like BacktestService does.
        # BacktestService.run_backtest() fetches ONE_MINUTE candles for the blueprint range
        # and sets: high_val=max(high) and low_val=min(low) from that window.
        bp_start_time = getattr(session, "blueprint_start_time", '09:15')
        bp_end_time = getattr(session, "blueprint_end_time", '15:30')

        # Fetch blueprint candles once per candle-close invocation (per session).
        # Note: backtest_service applies strict time filtering; we reuse the same filtering logic.
        smart_api = getattr(session, "smart_api", None)
        if not smart_api:
            return

        # We compute inferred high/low by fetching blueprint ONE_MINUTE candles.
        # BacktestService uses exchange & symboltoken; we need those per stock.
        # So we compute per-stock inside the stock loop (but before using cfg).

        # Buffer expected by BacktestService is percent (e.g., 0.45 means 0.45%).
        buffer_pct = getattr(session, "buffer_pct", 0.45)
        buffer_val = float(buffer_pct)


        # timeframe/interval mapping: backtest_service uses interval as configured; websocket_manager uses FIFTEEN_MINUTE
        interval = getattr(session, "blueprint_timeframe", "FIFTEEN_MINUTE") or "FIFTEEN_MINUTE"

        target = getattr(session, "global_target", None)
        target_type = "POINTS"
        stop_loss = getattr(session, "global_stop_loss", None)

        strategy_mode = getattr(session, "strategy_mode", 'SAR')
        trigger_mode = 'CANDLE_CLOSE'

        # Compute inferred_high/inferred_low by querying blueprint range once per session.
        # Note: BacktestService also enforces blueprint candle time filtering; we reuse same params here.
        # We compute per-stock because exchange differs.


        # For each stock, compute the signal using the same logic as backtest_service by running a tiny backtest window ending at candle_end_ist.
        # We use blueprint start/end as-is; set end_date to candle_end day for rolling correctness.
        candle_date_str = candle_end_ist.strftime("%Y-%m-%d")

        for stock in list(session.watchlist):
            try:
                symbol = stock.get('symbol')
                token = str(stock.get('token'))
                exch = stock.get('exch_seg', 'NSE')
                if not symbol or not token or not exch:
                    continue

                # Build the level grid from persisted AUTO levels in the Alerts tab.
                # This avoids re-generating levels from blueprint H/L with any timing drift.
                token_str = str(token)
                auto_lv = []
                for a in getattr(session, "alerts", []) or []:
                    if str(a.get("token")) != token_str:
                        continue
                    atype = str(a.get("type", ""))
                    if not atype.startswith("AUTO_"):
                        continue
                    try:
                        p = float(a.get("price"))
                    except:
                        continue
                    # Backtest level 'n' is label like Low/M/High/R1..R12/S1..S12.
                    # Your alerts route maps display labels like RANGE_HIGH, TGT_H1 etc.
                    # We must reverse-map them to Backtest's n-space.
                    # Minimal mapping by using backtest_service expectations:
                    label = atype.replace("AUTO_", "").strip().upper()
                    # Convert known UI labels back to backtest labels.
                    # Example: RANGE_HIGH -> High, RANGE_LOW -> Low, MIDPOINT -> M,
                    # TGT_H1 -> R1, TGT_L1 -> S1, etc.
                    if label in ("RANGE_HIGH", "HIGH"):
                        n = "High"
                    elif label in ("RANGE_LOW", "LOW"):
                        n = "Low"
                    elif label in ("MIDPOINT", "M"):
                        n = "M"
                    elif label.startswith("TGT_H"):
                        n = "R" + label.replace("TGT_H", "")
                    elif label.startswith("TGT_L"):
                        n = "S" + label.replace("TGT_L", "")
                    elif label.startswith("R") and label[1:].isdigit():
                        n = label
                    elif label.startswith("S") and label[1:].isdigit():
                        n = label
                    else:
                        # Fallback: use the label token as-is.
                        n = label

                    auto_lv.append({"p": p, "n": n})

                if not auto_lv:
                    continue

                # BacktestService level generation is derived from blueprint high/low, but
                # for signal generation we need an equivalent level list.
                levels = sorted(auto_lv, key=lambda x: float(x["p"]))
                inferred_high = max(float(x["p"]) for x in levels)
                inferred_low = min(float(x["p"]) for x in levels)

                # Now run backtest just to reuse its exact decision logic,
                # but feed high/low derived from persisted levels (no blueprint drift).
                cfg = {
                    "mode": "DISCRETE",
                    "high": inferred_high,
                    "low": inferred_low,
                    "quantity": 100,
                    "target": target,
                    "target_type": target_type,
                    "stop_loss": stop_loss,
                    "interval": interval,
                    "trade_type": "INTRADAY",
                    "buffer": buffer_val,
                    "trigger_mode": trigger_mode,
                    "blueprint_start_date": bp_start,
                    "blueprint_end_date": bp_end,
                    "blueprint_start_time": getattr(session, "blueprint_start_time", '09:15'),
                    "blueprint_end_time": getattr(session, "blueprint_end_time", '15:30'),
                }

                result = backtest_service.run_backtest(
                    session.smart_api,
                    symbol,
                    token,
                    exch,
                    bp_start,
                    candle_date_str,
                    cfg,
                )


                if not result or result.get('error'):
                    continue

                trades = result.get('trades') or []
                if not trades:
                    continue

                last_trade = trades[-1]
                # Signal inference:
                # If trade reason is TRAP/REJECTION and side flips in backtest, we interpret as SAR reversal.
                entry_side = last_trade.get('side')
                entry_price = last_trade.get('entry_price')
                exit_reason = str(last_trade.get('reason', ''))
                exit_price = last_trade.get('exit_price')

                # For validation engine we will send BUY/SELL when a position is opened or flipped.
                # backtest_service stores positions with side and entry_price; if last_trade has reason outside, we just emit BUY/SELL based on its side.
                side_for_alert = entry_side
                signal_label = str(exit_reason).replace('SAR_FLIP', '').replace('AUTO_', '')

                if side_for_alert not in ("BUY", "SELL"):
                    # try to map exit reason TRAP/REJECTION to flip direction
                    if "TRAP" in exit_reason or "REJECTION" in exit_reason:
                        side_for_alert = "SELL" if entry_side == "BUY" else "BUY"
                        signal_label = exit_reason

                if side_for_alert not in ("BUY", "SELL"):
                    continue

                price_for_msg = _tick_round(float(exit_price) if exit_price is not None else float(entry_price))
                signature = f"{session_id}|{symbol}|{candle_tag(candle_end_ist)}|{side_for_alert}|{price_for_msg}|{signal_label}"

                st = signal_state.get(session_id, symbol)
                if st.last_alert_signature == signature:
                    continue

                # SAR special message if trap/rejection implied reversal
                if "TRAP" in exit_reason or "REJECTION" in exit_reason:
                    # Required format:
                    new_side = side_for_alert
                    msg = (
                        "🔄 SAR REVERSAL\n"
                        f"Symbol: {symbol}\n"
                        f"Exit {entry_side}: {price_for_msg:.2f}\n"
                        f"New {new_side}: {price_for_msg:.2f}\n"
                        f"Signal: {signal_label}\n"
                        f"Timeframe: {interval.replace('_', ' ')}\n"
                        f"Time: {candle_end_ist.strftime('%H:%M')}"
                    )
                else:
                    msg = _signal_to_telegram(side_for_alert, symbol, price_for_msg, signal_label, interval.replace('_', ' '), candle_end_ist)

                telegram_service.send_text_message(msg)
                signal_state.update_on_alert(
                    session_id,
                    symbol,
                    side=side_for_alert,
                    entry_price=entry_price,
                    signal=signal_label,
                    signature=signature,
                )

            except Exception as e:
                logger.exception(f"[TELEGRAM] Error processing {stock}: {e}")


def candle_tag(candle_end_ist: datetime) -> str:
    return candle_end_ist.strftime("%Y-%m-%d %H:%M")


telegram_signal_engine = TelegramSignalEngine()

