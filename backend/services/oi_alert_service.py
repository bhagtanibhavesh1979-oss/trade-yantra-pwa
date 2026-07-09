"""OI Alert Engine

Sends Telegram alerts when open interest (OI) increases by a threshold.

Currently triggers for the strike rows produced by `oi_service.snapshot(session_id)`.
That snapshot already includes near-ATM strike list and computes:
- ce_delta_oi
- pe_delta_oi

We trigger when:
- CE: ce_delta_oi >= threshold
- PE: pe_delta_oi >= threshold

Deduplication:
- One alert per session + underlying + strike + CE/PE between cooldown window.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from backend.services.oi_service import oi_service
from backend.services.session_manager import session_manager
from backend.services.telegram_service import telegram_service


@dataclass
class OIAlertConfig:
    threshold: int = 100000
    poll_interval_seconds: float = 4.0
    cooldown_seconds: int = 120


class OIAlertEngine:
    def __init__(self, config: Optional[OIAlertConfig] = None):
        self.config = config or OIAlertConfig()
        self._lock = threading.RLock()

        # session_id -> underlying -> strike -> {CE/PE: last_alert_ts}
        # keys: (underlying, strike, side)
        self._last_alert_ts: Dict[str, Dict[Tuple[str, int, str], float]] = {}

        self._workers: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, threading.Event] = {}

    def start_for_session(self, session_id: str):
        with self._lock:
            if session_id in self._workers and self._workers[session_id].is_alive():
                return {"status": "already_running"}

            stop_evt = threading.Event()
            self._stop_flags[session_id] = stop_evt

            t = threading.Thread(
                target=self._run_loop,
                args=(session_id, stop_evt),
                daemon=True,
            )
            self._workers[session_id] = t
            t.start()
            return {"status": "started"}

    def stop_for_session(self, session_id: str):
        with self._lock:
            evt = self._stop_flags.get(session_id)
            if evt:
                evt.set()
                return {"status": "stopping"}
            return {"status": "not_running"}

    def _should_alert(self, session_id: str, underlying: str, strike: int, side: str, now_ts: float) -> bool:
        cooldown = self.config.cooldown_seconds
        with self._lock:
            sess_map = self._last_alert_ts.setdefault(session_id, {})
            key = (underlying, strike, side)
            last = sess_map.get(key, 0)
            if now_ts - last < cooldown:
                return False
            sess_map[key] = now_ts
            return True

    def _send(self, text: str):
        try:
            telegram_service.send_text_message(text)
        except Exception:
            # Never crash alert worker
            pass

    def _run_loop(self, session_id: str, stop_evt: threading.Event):
        # Worker runs until stop_evt is set
        while not stop_evt.is_set():
            try:
                session = session_manager.get_session(session_id)
                if not session or getattr(session, "is_paused", False):
                    time.sleep(self.config.poll_interval_seconds)
                    continue

                res = oi_service.snapshot(session_id)
                if not res or res.get("status") != "success":
                    time.sleep(self.config.poll_interval_seconds)
                    continue

                data = res.get("data") or {}
                now_ts = time.time()
                threshold = int(self.config.threshold)

                # data: {"NIFTY 50": [rows...], "SENSEX": [rows...]}
                for underlying, rows in data.items():
                    if not rows:
                        continue

                    for r in rows:
                        strike = int(r.get("strike"))

                        ce_delta = r.get("ce_delta_oi")
                        pe_delta = r.get("pe_delta_oi")
                        ce_oi = r.get("ce_oi")
                        pe_oi = r.get("pe_oi")

                        # CE
                        if ce_delta is not None and float(ce_delta) >= threshold:
                            if self._should_alert(session_id, underlying, strike, "CE", now_ts):
                                msg = (
                                    f"⚡ OI Alert\n"
                                    f"Underlying: {underlying}\n"
                                    f"Strike: {strike} CE\n"
                                    f"ΔOI: {float(ce_delta):,.0f}\n"
                                    f"CE OI: {float(ce_oi or 0):,.0f}"
                                )
                                self._send(msg)

                        # PE
                        if pe_delta is not None and float(pe_delta) >= threshold:
                            if self._should_alert(session_id, underlying, strike, "PE", now_ts):
                                msg = (
                                    f"⚡ OI Alert\n"
                                    f"Underlying: {underlying}\n"
                                    f"Strike: {strike} PE\n"
                                    f"ΔOI: {float(pe_delta):,.0f}\n"
                                    f"PE OI: {float(pe_oi or 0):,.0f}"
                                )
                                self._send(msg)

            except Exception:
                # never crash worker
                pass

            # sleep at the end so we keep stable cadence
            time.sleep(self.config.poll_interval_seconds)


# Global engine instance
oi_alert_engine = OIAlertEngine()

