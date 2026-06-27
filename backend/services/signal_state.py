from dataclasses import dataclass
from typing import Dict, Optional
import threading
import time


@dataclass
class SymbolSignalState:
    side: Optional[str] = None
    entry_price: Optional[float] = None
    current_signal: Optional[str] = None
    last_alert_signature: Optional[str] = None
    last_alert_time: Optional[float] = None


class SignalState:
    """In-memory dedupe + current position state (per session & symbol)."""

    def __init__(self):
        self._lock = threading.RLock()
        # session_id -> symbol -> state
        self._by_session: Dict[str, Dict[str, SymbolSignalState]] = {}

    def get(self, session_id: str, symbol: str) -> SymbolSignalState:
        with self._lock:
            if session_id not in self._by_session:
                self._by_session[session_id] = {}
            if symbol not in self._by_session[session_id]:
                self._by_session[session_id][symbol] = SymbolSignalState()
            return self._by_session[session_id][symbol]

    def update_on_alert(
        self,
        session_id: str,
        symbol: str,
        *,
        side: Optional[str],
        entry_price: Optional[float],
        signal: Optional[str],
        signature: str,
    ):
        with self._lock:
            st = self.get(session_id, symbol)
            st.side = side
            st.entry_price = entry_price
            st.current_signal = signal
            st.last_alert_signature = signature
            st.last_alert_time = time.time()
            return st


signal_state = SignalState()

