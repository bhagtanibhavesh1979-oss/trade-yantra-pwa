"""Option-chain Open Interest (OI) snapshot service.

Computes a compact OI view for NIFTY + SENSEX around ATM.

Rule:
- NIFTY 50: ATM ± 5 strikes, step = 50
- SENSEX: ATM ± 5 strikes, step = 100
- Expiry: nearest weekly expiry

Output per strike:
- CE OI, PE OI
- delta vs previous snapshot (increasing/decreasing)

Implementation approach:
- Determine ATM from underlying LTP.
- Build NFO option contract tokens for CE/PE for the strikes and nearest
  weekly expiry by using `scripmaster` loaded in `angel_service`.
- Pull live LTP+OI using SmartConnect `getMarketData(mode="FULL")`.

NOTE: Token mapping is required; if scripmaster lacks required fields, the
endpoint will return a structured error.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re


from backend.services.session_manager import session_manager
from backend.services.angel_service import angel_service
from backend.services import oi_history


@dataclass
class OIStrikeRow:
    strike: int
    ce_oi: float
    pe_oi: float
    ce_delta_oi: float
    pe_delta_oi: float


class OIService:
    def __init__(self):
        self._lock = threading.RLock()
        # session_id -> underlying -> last snapshot
        # prev rows_by_strike: {strike: (ce_oi, pe_oi)}
        self._prev: Dict[str, Dict[str, Dict]] = {}

        self._underlyings = {
            "NIFTY 50": {"step": 50, "token": "99926000", "exchange": "NSE", "idx_suffix": "NIFTY"},
            "SENSEX": {"step": 100, "token": "99919000", "exchange": "BSE", "idx_suffix": "SENSEX"},
        }

    def _get_session(self, session_id: str):
        return session_manager.get_session(session_id)

    def _tick_round_to_step(self, price: float, step: int) -> int:
        if step <= 0:
            return int(round(price))
        return int(round(price / step) * step)

    def _strike_list(self, atm: int, step: int, span: int = 5) -> List[int]:
        """Legacy deterministic strike list.

        Kept for fallback if scripmaster strike extraction fails.
        """
        return [int(atm + i * step) for i in range(-span, span + 1)]

    def _extract_strikes_from_scrips(
        self, underlying: str, expiry_date: str
    ) -> List[int]:
        """Extract all available strikes for the given underlying+expiry from scripmaster."""
        self._ensure_scrip_master()

        # NIFTY options use prefix `NIFTY`, while your Sensex options in scripmaster use `BSE`.
        prefix = "NIFTY" if underlying == "NIFTY 50" else "BSE"

        expiry = re.escape(str(expiry_date))

        # Match: <PREFIX><EXPIRY><STRIKE><CE/PE>
        sym_re = re.compile(rf"^{prefix}{expiry}(\d+)(CE|PE)$")

        strikes_set = set()
        for s in angel_service.scrips:
            sym = s.get("symbol") or ""
            m = sym_re.match(sym)
            if not m:
                continue
            strikes_set.add(int(m.group(1)))

        strikes = sorted(strikes_set)
        return strikes

    def _pick_nearest_11_strikes(self, strikes: List[int], atm_value: float, span: int = 5) -> List[int]:
        if not strikes:
            return []

        # find nearest strike index
        # prefer exact/closest numeric distance
        atm_int = int(atm_value)
        nearest_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - atm_int))

        start = nearest_idx - span
        end = nearest_idx + span

        # clamp to available indices
        start = max(0, start)
        end = min(len(strikes) - 1, end)

        picked = strikes[start : end + 1]
        # if we got less than 11 due to clamping, pad from the other side if possible
        if len(picked) < (2 * span + 1):
            # expand forward/backward to reach 11
            need = (2 * span + 1) - len(picked)
            # try left
            left = start - 1
            while need > 0 and left >= 0:
                picked.insert(0, strikes[left])
                left -= 1
                need -= 1
            # try right
            right = end + 1
            while need > 0 and right < len(strikes):
                picked.append(strikes[right])
                right += 1
                need -= 1
        return picked

    def _ensure_scrip_master(self):
        # Angel scrip master is required for token resolution.
        # Your cached scrip master sometimes contains only core indices/equities
        # (no NFO option symbols). In that case, expiry detection and token lookup
        # will fail. Force a re-load when option contracts are missing.

        scrips = getattr(angel_service, "scrips", None) or []
        has_options = any((s.get("symbol") or "").endswith("CE") or (s.get("symbol") or "").endswith("PE") for s in scrips)

        if (not getattr(angel_service, "master_loaded", False)) or (not scrips) or (not has_options):
            angel_service.load_scrip_master()

        # Re-check after load
        scrips = getattr(angel_service, "scrips", None) or []
        has_options = any((s.get("symbol") or "").endswith("CE") or (s.get("symbol") or "").endswith("PE") for s in scrips)
        if not has_options:
            # Last resort: we still can't proceed reliably.
            # Let downstream logic return a structured error.
            pass



    def _fetch_underlying_ltp(self, smart_api, underlying: str) -> Optional[float]:
        cfg = self._underlyings[underlying]
        exch = cfg["exchange"]
        token = cfg["token"]
        res = angel_service.get_ltp_data(smart_api, exch, underlying, token)
        if not res:
            return None
        ltp = res.get("ltp")
        return float(ltp) if ltp is not None else None

    def _nearest_expiry_from_scrips(self, underlying: str) -> Optional[str]:
        """Return nearest expiry code for given underlying from scripmaster."""
        self._ensure_scrip_master()
        if underlying not in ("NIFTY 50", "SENSEX"):
            return None

        from datetime import datetime

        prefix = "NIFTY" if underlying == "NIFTY 50" else "BSE"

        expiries: List[Tuple[datetime, str]] = []
        # Parse from symbol: <PREFIX><DDMMMYY><STRIKE><CE/PE>
        # (Your cached scripmaster may not reliably provide an `expiry` field.)
        pattern = re.compile(rf"^{prefix}(\d{{1,2}}[A-Z]{{3}}\d{{2}})(\d+)(CE|PE)$")
        for s in angel_service.scrips:
            sym = s.get("symbol") or ""
            if not sym:
                continue
            m = pattern.match(sym)
            if not m:
                continue
            exp_code = m.group(1)
            try:
                exp_dt = datetime.strptime(exp_code, "%d%b%y")
                expiries.append((exp_dt, exp_code))
            except Exception:
                continue


        if not expiries:
            angel_service.load_scrip_master()
            return self._nearest_expiry_from_scrips(underlying)

        # Prefer the nearest expiry that is today or in the future (options expiry).
        # Fall back to the nearest by absolute date if none are in the future.
        expiries.sort(key=lambda x: x[0])
        from datetime import datetime

        today = datetime.now().date()
        future = [e for e in expiries if e[0].date() >= today]
        if future:
            # earliest future expiry
            return future[0][1]

        # no future expiries found in scripmaster; return the most recent past expiry
        # (closest to today)
        expiries.sort(key=lambda x: x[0], reverse=True)
        return expiries[0][1]



    def _contract_token(self, underlying: str, expiry_date: str, strike: int, opt_type: str) -> Optional[str]:
        """Find CE/PE token for given contract."""
        self._ensure_scrip_master()

        if not expiry_date:
            return None

        # NIFTY options use prefix `NIFTY`, while your Sensex options in scripmaster use `BSE`.
        prefix = "NIFTY" if underlying == "NIFTY 50" else "BSE"
        strike_str = str(int(strike))


        # Robust symbol match:
        # Your cached symbols look like:
        # - NIFTY14JUL2623950CE (NIFTY)
        # - BSE28JUL2623950CE (SENSEX)
        # We'll match based on the prefix + embedded expiry + strike digits.

        expiry = re.escape(str(expiry_date))
        # Match: <PREFIX><EXPIRY><STRIKE><CE/PE>
        sym_any_strike = re.compile(rf"^{prefix}{expiry}(\d+)(CE|PE)$")

        for s in angel_service.scrips:
            sym = s.get("symbol") or ""
            m = sym_any_strike.match(sym)
            if not m:
                continue
            sym_strike = int(m.group(1))
            sym_opt = m.group(2)
            if sym_opt != opt_type:
                continue
            if sym_strike != int(strike):
                continue
            tok = s.get("token")
            return str(tok) if tok is not None else None

        # Final fallback: containment checks.
        for s in angel_service.scrips:
            sym = s.get("symbol") or ""
            if not sym.endswith(opt_type):
                continue
            if prefix not in sym:
                continue
            if str(expiry_date) not in sym:
                continue
            if str(int(strike)) not in sym:
                continue
            tok = s.get("token")
            return str(tok) if tok is not None else None

        return None



    def _fetch_marketdata_full_oi(self, smart_api, tokens: List[str]) -> Dict[str, Dict]:
        """Fetch market data (mode FULL) and return mapping token->fields.

        The SmartAPI SDK variants differ slightly in how `getMarketData` wants
        the exchangeTokens payload. We try multiple call shapes and merge
        results.
        """
        if not tokens:
            return {}

        def _extract(res: object) -> Dict[str, Dict]:
            if not res or not isinstance(res, dict):
                return {}
            data = res.get("data") or {}
            fetched = data.get("fetched") or []
            out: Dict[str, Dict] = {}

            for item in fetched or []:
                try:
                    # SmartAPI FULL payload uses either:
                    # - `token` (common)
                    # - `symbolToken` (seen in your diagnostics)
                    tok = item.get("token")
                    if tok is None:
                        tok = item.get("symbolToken")
                    if tok is None:
                        continue
                    out[str(tok)] = item
                except Exception:
                    continue
            return out


        # 1) Current/expected call shape (use provided exchange if present)
        try:
            # default to NFO if not specified in tokens wrapper
            res1 = smart_api.getMarketData("FULL", {"NFO": tokens})
            # Diagnostic: if we get something back, log available keys for first few tokens
            try:
                if isinstance(res1, dict):
                    data = res1.get("data") or {}
                    fetched = data.get("fetched") or []
                    sample = fetched[:3] if isinstance(fetched, list) else []
                    print(f"[OI] FULL payload sample size={len(sample)} for tokens={tokens[:6]}")
                    if sample:
                        for it in sample:
                            print(f"[OI] FULL item token={it.get('token')} keys={list(it.keys())}")
            except Exception:
                pass
            out1 = _extract(res1)
            if out1:
                return out1
        except Exception:
            pass


        # 2) Alternate call shape (exchangeTokens wrapper)
        try:
            res2 = smart_api.getMarketData("FULL", {"exchangeTokens": {"NFO": tokens}})
            out2 = _extract(res2)
            if out2:
                return out2
        except Exception:
            pass

        # 3) Fallback to previous implementation
        try:
            res3 = smart_api.getMarketData("FULL", {"NFO": tokens})
            out3 = _extract(res3)
            if out3:
                return out3
        except Exception:
            pass

        return {}


    def snapshot(self, session_id: str) -> Dict:
        session = self._get_session(session_id)
        if not session or not getattr(session, "smart_api", None):
            return {"status": "error", "detail": "Session inactive"}

        smart_api = session.smart_api

        self._ensure_scrip_master()

        with self._lock:
            self._prev.setdefault(session_id, {})

        final: Dict[str, List[Dict]] = {}
        updated_at = time.time()

        # Pull OI per underlying
        for underlying in ["NIFTY 50", "SENSEX"]:
            step = int(self._underlyings[underlying]["step"])

            ltp = self._fetch_underlying_ltp(smart_api, underlying)
            if ltp is None:
                continue

            atm = self._tick_round_to_step(ltp, step)

            # Pick nearest expiry from scripmaster (NIFTY and SENSEX-supported).
            expiry_date = self._nearest_expiry_from_scrips(underlying)
            if expiry_date:
                all_strikes = self._extract_strikes_from_scrips(underlying, expiry_date)
                strikes = self._pick_nearest_11_strikes(all_strikes, ltp, span=5)
                if not strikes:
                    strikes = self._strike_list(atm, step)
            else:
                # If expiry scanning fails, fall back to deterministic strikes.
                strikes = self._strike_list(atm, step)
                expiry_date = None




            # Build token list to fetch CE+PE OI.
            token_rows: List[Tuple[int, str, str]] = []
            tokens: List[str] = []
            # If we somehow picked strikes not present in scripmaster for this expiry,
            # this will fail; surface detail in error.
            missing_tokens = []
            for strike in strikes:

                ce_tok = self._contract_token(underlying, expiry_date, strike, "CE")
                pe_tok = self._contract_token(underlying, expiry_date, strike, "PE")
                if not ce_tok or not pe_tok:
                    missing_tokens.append((strike, ce_tok, pe_tok))
                token_rows.append((strike, ce_tok, pe_tok))
                if ce_tok:
                    tokens.append(ce_tok)
                if pe_tok:
                    tokens.append(pe_tok)

            if missing_tokens:
                # Do not fail hard when one side is missing for a strike (common for some scrips).
                print(f"[OI] Warning: missing tokens for some strikes: {missing_tokens}")

            # Fetch market data in one call (to reduce rate-limit)
            md = self._fetch_marketdata_full_oi(smart_api, list(dict.fromkeys(tokens)))

            rows_by_strike_prev: Dict[int, Tuple[float, float]] = (
                self._prev.get(session_id, {}).get(underlying, {}).get("rows_by_strike", {})
            )

            rows_out: List[Dict] = []
            rows_by_strike_now: Dict[int, Tuple[float, float]] = {}

            for strike, ce_tok, pe_tok in token_rows:
                ce_item = md.get(str(ce_tok), {}) if ce_tok else {}
                pe_item = md.get(str(pe_tok), {}) if pe_tok else {}

                # SmartAPI field name for OI in FULL mode varies: openInterest / open_interest / oi
                def _get_oi(item: Dict) -> Optional[float]:
                    # SmartAPI FULL payload naming variants observed in logs:
                    # - `opnInterest`
                    # - `openInterest` / `open_interest`
                    # - `oi` / `openInterestValue`
                    for k in [
                        "opnInterest",
                        "openInterest",
                        "open_interest",
                        "oi",
                        "openInterestValue",
                        "openInterestVal",
                    ]:
                        if k in item and item[k] is not None:
                            try:
                                return float(item[k])
                            except Exception:
                                pass
                    return None


                ce_oi = _get_oi(ce_item) if ce_tok else 0.0
                pe_oi = _get_oi(pe_item) if pe_tok else 0.0

                if ce_oi is None:
                    print(f"[OI] Warning: CE OI missing in payload for {underlying} strike={strike} expiry={expiry_date} tok={ce_tok}")
                    ce_oi = 0.0
                if pe_oi is None:
                    print(f"[OI] Warning: PE OI missing in payload for {underlying} strike={strike} expiry={expiry_date} tok={pe_tok}")
                    pe_oi = 0.0

                prev_ce, prev_pe = rows_by_strike_prev.get(strike, (ce_oi, pe_oi))
                ce_delta = ce_oi - prev_ce
                pe_delta = pe_oi - prev_pe

                def _dir_from_delta(d: float) -> str:
                    if d > 0:
                        return "increased"
                    if d < 0:
                        return "decreased"
                    return "nochange"

                def _pct(delta: float, prev: float) -> Optional[float]:
                    try:
                        if prev == 0:
                            return None
                        return (delta / prev) * 100.0
                    except Exception:
                        return None

                ce_pct = _pct(ce_delta, prev_ce)
                pe_pct = _pct(pe_delta, prev_pe)

                rows_out.append(
                    {
                        "strike": strike,
                        "ce_oi": ce_oi,
                        "pe_oi": pe_oi,
                        "ce_delta_oi": ce_delta,
                        "pe_delta_oi": pe_delta,
                        "ce_delta_pct": ce_pct,
                        "pe_delta_pct": pe_pct,
                        "ce_dir": _dir_from_delta(ce_delta),
                        "pe_dir": _dir_from_delta(pe_delta),
                    }
                )
                rows_by_strike_now[strike] = (ce_oi, pe_oi)

            # persist snapshot
            with self._lock:
                self._prev[session_id][underlying] = {
                    "atm": atm,
                    "expiry": expiry_date,
                    "rows_by_strike": rows_by_strike_now,
                    "updated_at": updated_at,
                }

            # persist aggregate totals for history (CE total, PE total)
            try:
                ce_total = sum(v[0] for v in rows_by_strike_now.values())
                pe_total = sum(v[1] for v in rows_by_strike_now.values())
                oi_history.save_sample(session_id, underlying, updated_at, ce_total, pe_total)
            except Exception:
                # non-fatal
                pass

        final[underlying] = rows_out

        # lightweight debug for tracing update frequency
        # (avoid huge payload logs)
        try:
            first_row = rows_out[0] if rows_out else None
            print(f"[OI] snapshot underlying={underlying} updated_at={updated_at} first_strike={first_row.get('strike') if first_row else None} ce_oi={first_row.get('ce_oi') if first_row else None} pe_oi={first_row.get('pe_oi') if first_row else None}")
        except Exception:
            pass

        return {"status": "success", "updated_at": updated_at, "data": final}


oi_service = OIService()

