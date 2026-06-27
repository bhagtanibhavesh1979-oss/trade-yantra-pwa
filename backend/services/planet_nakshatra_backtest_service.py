"""Planet Nakshatra/Pada backtest service.

Fetches daily historical candles for NIFTY50 spot and BANKNIFTY spot from Angel One,
computes planetary sidereal Nakshatra/Pada transitions (using Swiss Ephemeris), and
measures subsequent returns/drawdown/win-rate on trading days.

The output is designed for a FastAPI route:
- grouped summary table
- (optional) event list can be added later

NOTE:
- This implementation assumes Angel One SmartConnect is authenticated and provided
  as `smart_api`.
- Date alignment is done by matching ISO date strings from market candles.
- Returns windows are measured on the next N trading days (not calendar days).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from services.angel_service import angel_service
from services.astro_backtest_engine import AstroBacktestEngine


@dataclass(frozen=True)
class MarketSpec:
    name: str
    token: str
    exch: str


class PlanetNakshatraBacktestService:
    def __init__(self):
        self.astro_engine = AstroBacktestEngine()

        # Market specs
        self.nifty = MarketSpec(name="NIFTY", token="99926037", exch="NSE")
        self.banknifty = MarketSpec(name="BANKNIFTY", token="99926009", exch="NSE")

    @staticmethod
    def _years_ago_midnight_ist(years: int) -> datetime:
        # Backtest from (now - years) in UTC, but we will use IST date strings for matching.
        now = datetime.now(timezone.utc)
        target = now - timedelta(days=365 * years)
        # normalize to midnight UTC for stable ISO date conversion
        target = target.replace(hour=0, minute=0, second=0, microsecond=0)
        return target

    @staticmethod
    def _candles_to_df(candles: List[list]) -> pd.DataFrame:
        """Convert Angel One candle list to DataFrame.

        Expected candle schema (SmartAPI): [ts, open, high, low, close, volume]
        ts could be ISO or "YYYY-MM-DD HH:MM:SS".

        We keep:
        - date (YYYY-MM-DD) derived from ts
        - close
        - high, low, open
        """
        if not candles:
            return pd.DataFrame()

        rows = []
        for c in candles:
            if not c or len(c) < 5:
                continue
            ts = c[0]
            open_p, high_p, low_p, close_p = map(float, c[1:5])

            dt = None
            if isinstance(ts, (int, float)):
                # unix seconds
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            else:
                ts_str = str(ts)
                # SmartAPI usually returns: "YYYY-MM-DD HH:MM:SS" for ONE_DAY sometimes.
                # If ISO: "YYYY-MM-DDTHH:MM:SS".
                if "T" in ts_str:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    # Try common format
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            dt = datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
                            break
                        except ValueError:
                            continue

            if dt is None:
                continue

            # Convert to IST date string for matching across all candles/events.
            dt_ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
            date_str = dt_ist.strftime("%Y-%m-%d")

            rows.append(
                {
                    "date": date_str,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Keep one row per date (ONE_DAY should already be unique, but keep stable)
        df = df.sort_values("date").groupby("date", as_index=False).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        })
        return df

    @staticmethod
    def _prepare_next_horizon_returns(df: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
        """Given market df with chronological rows and a close column,
        compute next-N trading-day returns and drawdowns.

        Adds columns:
        - ret_{N}d: (close[t+N]/close[t]-1)
        - dd_{N}d: max drawdown within (t+1 .. t+N) relative to close[t] peak.

        Drawdown definition:
        - compute path of closes over next N days (inclusive t+1..t+N)
        - peak = max(closes)
        - trough = min(closes)
        - dd = (trough/peak - 1)
        """
        df = df.sort_values("date").reset_index(drop=True)
        closes = df["close"].astype(float).to_numpy()

        n = len(df)
        for N in horizons:
            ret_col = f"ret_{N}d"
            dd_col = f"dd_{N}d"
            win = np.full(n, np.nan, dtype=float)
            dd = np.full(n, np.nan, dtype=float)

            for i in range(n):
                j = i + N
                if j >= n:
                    continue
                # returns using close at j
                win[i] = (closes[j] / closes[i]) - 1.0

                # drawdown during window (t+1..t+N)
                segment = closes[i + 1 : j + 1]
                if segment.size == 0:
                    continue
                peak = float(np.max(segment))
                trough = float(np.min(segment))
                if peak == 0:
                    dd[i] = np.nan
                else:
                    dd[i] = (trough / peak) - 1.0

            df[ret_col] = win
            df[dd_col] = dd

        return df

    @staticmethod
    def _win_rate_from_returns(ret_series: pd.Series) -> float:
        s = ret_series.dropna()
        if s.empty:
            return 0.0
        return float((s > 0).mean() * 100.0)

    def run(
        self,
        smart_api,
        years: int,
        planets: List[str],
        include_event_types: List[str],
        horizons: List[int],
    ) -> Dict:
        # Date range: from years back to today (UTC)
        start_dt_utc = self._years_ago_midnight_ist(years)
        end_dt_utc = datetime.now(timezone.utc)

        # Convert to strings for Angel API
        start_str = start_dt_utc.strftime("%Y-%m-%d")
        end_str = end_dt_utc.strftime("%Y-%m-%d")

        # Fetch ONE_DAY candles
        def fetch_one_day(token: str, exch: str) -> pd.DataFrame:
            req = {
                "exchange": exch,
                "symboltoken": str(token),
                "interval": "ONE_DAY",
                "fromdate": f"{start_str} 00:00",
                "todate": f"{end_str} 23:59",
            }
            res = angel_service.fetch_candle_data(smart_api, req)
            if not res or res.get("status") is False:
                raise RuntimeError(res.get("message") if isinstance(res, dict) else "Market fetch failed")
            candles = res.get("data") or []
            return self._candles_to_df(candles)

        nifty_df = fetch_one_day(self.nifty.token, self.nifty.exch).rename(
            columns={"close": "nifty_close", "high": "nifty_high", "low": "nifty_low", "open": "nifty_open"}
        )
        bank_df = fetch_one_day(self.banknifty.token, self.banknifty.exch).rename(
            columns={"close": "bn_close", "high": "bn_high", "low": "bn_low", "open": "bn_open"}
        )

        if nifty_df.empty or bank_df.empty:
            raise RuntimeError("No market candle data available for the requested period")

        market = nifty_df.merge(bank_df[["date", "bn_close"]], on="date", how="inner")
        if market.empty:
            raise RuntimeError("No overlapping trading dates between NIFTY and BANKNIFTY")

        # Compute horizon metrics for each trading day
        nifty_metrics_base = self._prepare_next_horizon_returns(
            market[["date", "nifty_close"]].rename(columns={"nifty_close": "close"}),
            horizons,
        )

        bn_metrics_base = self._prepare_next_horizon_returns(
            market[["date", "bn_close"]].rename(columns={"bn_close": "close"}),
            horizons,
        )

        # Rename metric columns and merge back
        nifty_cols = ["date"]
        bn_cols = ["date"]
        for h in horizons:
            nifty_cols += [f"ret_{h}d", f"dd_{h}d"]
            bn_cols += [f"ret_{h}d", f"dd_{h}d"]

        nifty_metrics = nifty_metrics_base[nifty_cols].rename(columns={
            **{f"ret_{h}d": f"nifty_ret_{h}d" for h in horizons},
            **{f"dd_{h}d": f"nifty_dd_{h}d" for h in horizons},
        })

        bn_metrics = bn_metrics_base[bn_cols].rename(columns={
            **{f"ret_{h}d": f"bn_ret_{h}d" for h in horizons},
            **{f"dd_{h}d": f"bn_dd_{h}d" for h in horizons},
        })

        merged = market.merge(nifty_metrics, on="date", how="left")
        merged = merged.merge(bn_metrics, on="date", how="left")


        # Astro events per planet day-by-day (use same IST date strings)
        astro_events = self.astro_engine.compute_planet_transitions(
            start_date=start_str,
            end_date=end_str,
            planets=planets,
            event_types=include_event_types,
        )
        # astro_events: list of dicts with date + planet + event_type + entered_nakshatra/pada

        events_df = pd.DataFrame(astro_events)
        if events_df.empty:
            return {
                "meta": {
                    "start_date": start_str,
                    "end_date": end_str,
                    "years": years,
                    "event_count": 0,
                },
                "summary": [],
            }

        # Align to trading days by merging on date
        aligned = events_df.merge(merged, on="date", how="inner")
        if aligned.empty:
            return {
                "meta": {
                    "start_date": start_str,
                    "end_date": end_str,
                    "years": years,
                    "event_count": len(events_df),
                },
                "summary": [],
            }

        group_cols = [
            "planet",
            "event_type",
            "entered_nakshatra",
            "entered_pada",
        ]

        agg_rows = []
        for keys, g in aligned.groupby(group_cols):
            # keys is tuple in same order as group_cols
            row_base = dict(zip(group_cols, keys))
            # For each horizon compute:
            # - avg nifty_ret
            # - avg bn_ret
            # - avg drawdown (use dd columns)
            # - win rate
            for h in horizons:
                nifty_ret = g[f"nifty_ret_{h}d"]
                bn_ret = g[f"bn_ret_{h}d"]
                row_base[f"nifty_avg_ret_{h}d"] = float(nifty_ret.mean()) if nifty_ret.dropna().shape[0] else 0.0
                row_base[f"bn_avg_ret_{h}d"] = float(bn_ret.mean()) if bn_ret.dropna().shape[0] else 0.0

                nifty_dd = g[f"nifty_dd_{h}d"]
                bn_dd = g[f"bn_dd_{h}d"]
                row_base[f"nifty_avg_dd_{h}d"] = float(nifty_dd.mean()) if nifty_dd.dropna().shape[0] else 0.0
                row_base[f"bn_avg_dd_{h}d"] = float(bn_dd.mean()) if bn_dd.dropna().shape[0] else 0.0

                row_base[f"nifty_win_rate_{h}d"] = self._win_rate_from_returns(nifty_ret)
                row_base[f"bn_win_rate_{h}d"] = self._win_rate_from_returns(bn_ret)

            row_base["event_count"] = int(len(g))
            agg_rows.append(row_base)

        summary_df = pd.DataFrame(agg_rows)
        if not summary_df.empty:
            # Sort by combined performance: nifty avg 20d + bn avg 20d
            sort_key = summary_df.get("nifty_avg_ret_20d", 0) + summary_df.get("bn_avg_ret_20d", 0)
            summary_df = summary_df.assign(_sort=sort_key).sort_values("_sort", ascending=False).drop(columns=["_sort"], errors="ignore")

        return {
            "meta": {
                "start_date": start_str,
                "end_date": end_str,
                "years": years,
                "event_count": int(len(events_df)),
                "aligned_event_count": int(len(aligned)),
                "horizons": horizons,
                "markets": ["NIFTY", "BANKNIFTY"],
            },
            "summary": summary_df.to_dict(orient="records"),
        }


planet_nakshatra_backtest_service = PlanetNakshatraBacktestService()

