"""Swiss Ephemeris (pyswisseph) based Astro Engine for planet Nakshatra/Pada.

Given a date range, compute sidereal longitude (Lahiri) for specific planets,
map the longitude to:
- Nakshatra (1..27)
- Pada (1..4)

Also compute day-to-day transitions for Nakshatra and Pada.

Important:
- This file assumes `pyswisseph` is installed in your backend environment.
- If it is not installed, installation is required.

We treat each event on a market day (calendar day). Planet position is computed
at 00:00 IST boundary converted to UTC Julian Day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import math

import swisseph as swe


NAKSHATRAS: List[str] = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishtha",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

NAK_SPAN = 360.0 / 27.0
PADA_SPAN = NAK_SPAN / 4.0


PLANET_TO_SWE = {
    # Swiss Ephemeris planet ids
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,  # Mean node
    "Ketu": swe.MEAN_NODE,  # We'll add 180° to represent Ketu
}


@dataclass(frozen=True)
class PlanetNakPada:
    planet: str
    nakshatra: str
    nakshatra_index_0: int
    pada: int
    lon_deg: float
    entered: bool = True


class AstroBacktestEngine:
    def __init__(self, sidereal_mode: str = "lahiri"):
        """Create an astrology engine.

        sidereal_mode:
          - "lahiri" (SIDM_LAHIRI)
          - "chitra" (Drik-style Chitra Paksha; we map to Swiss Ephemeris SIDM_SS_CITRA by default)
          - "ss_citra" (alias for SIDM_SS_CITRA)
          - "true_citra" (SIDM_TRUE_CITRA)
        """

        mode_map = {
            "lahiri": swe.SIDM_LAHIRI,
            "chitra": swe.SIDM_SS_CITRA,
            "ss_citra": swe.SIDM_SS_CITRA,
            "true_citra": swe.SIDM_TRUE_CITRA,
        }

        if sidereal_mode not in mode_map:
            raise ValueError(f"Unsupported sidereal_mode: {sidereal_mode}")

        swe.set_sid_mode(mode_map[sidereal_mode])


    @staticmethod
    def _utc_datetime_from_ist_date(date_str: str, hour_ist: int = 0) -> datetime:
        # date_str: YYYY-MM-DD in IST calendar
        ist = timezone(timedelta(hours=5, minutes=30))
        dt_ist = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=ist) + timedelta(hours=hour_ist)
        return dt_ist.astimezone(timezone.utc)

    @staticmethod
    def _jd_from_utc(dt_utc: datetime) -> float:
        # Swiss Ephemeris expects JD UT
        # swe.julday takes year, month, day, hour, minute, second, and calendar flag
        return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0)

    @staticmethod
    def _wrap_360(deg: float) -> float:
        return deg % 360.0

    def _sidereal_longitude(self, planet: str, jd_ut: float) -> float:
        if planet not in PLANET_TO_SWE:
            raise ValueError(f"Unsupported planet: {planet}")

        swe_id = PLANET_TO_SWE[planet]

        # Calculate ecliptic longitude
        # Use flags for speed + sidereal (Swiss Ephemeris applies sidereal settings internally with set_sid_mode)
        # We'll request apparent position; for nakshatra/pada level mapping, precision is sufficient.
        lon, lat, dist, speed_lon = swe.calc_ut(jd_ut, swe_id, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][:4]

        lon_sid = self._wrap_360(float(lon))
        if planet == "Ketu":
            lon_sid = self._wrap_360(lon_sid + 180.0)
        return lon_sid

    def _nakshatra_pada_from_lon(self, lon_sid: float) -> Tuple[str, int, int, float]:
        """Map sidereal longitude to nakshatra and pada.

        Uses a small epsilon to make boundary cases numerically stable, so that
        values extremely close to the end of a pada/nakshatra don't flip to the next
        bucket due to floating point rounding.
        """

        eps = 1e-9  # degrees
        # Shift slightly backwards so an exact boundary doesn't round into the next bucket.
        lon_adj = (float(lon_sid) - eps) % 360.0

        nak_idx = int(lon_adj / NAK_SPAN) % 27
        deg_in_nak = lon_adj - nak_idx * NAK_SPAN
        # Clamp to [0, NAK_SPAN) to avoid deg_in_nak == NAK_SPAN due to rounding.
        deg_in_nak = min(max(deg_in_nak, 0.0), NAK_SPAN - eps)

        pada = int(deg_in_nak / PADA_SPAN) + 1
        pada = min(max(pada, 1), 4)
        nak_name = NAKSHATRAS[nak_idx]
        return nak_name, nak_idx, pada, float(deg_in_nak)


    def compute_planet_transitions(
        self,
        start_date: str,
        end_date: str,
        planets: Sequence[str],
        event_types: Sequence[str],
        step_minutes: int = 10,
    ) -> List[Dict]:
        """Compute Nakshatra/Pada transitions by scanning in time.

        The previous implementation sampled only at 00:00 IST for each calendar day.
        That can shift transition dates/padas vs. instant transit times (e.g., Drik Panchang).

        This implementation scans from (start_date 00:00 IST) up to (end_date 23:59 IST)
        with `step_minutes` resolution, and emits events when either:
        - Nakshatra boundary is crossed, or
        - Pada boundary is crossed.

        Event `date` remains the IST calendar day of the detected crossing instant.
        """

        want_nak = "NakshatraChange" in set(event_types)
        want_pada = "PadaChange" in set(event_types)

        if step_minutes <= 0:
            raise ValueError("step_minutes must be > 0")

        d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
        if d0 > d1:
            raise ValueError("start_date must be <= end_date")

        ist_tz = timezone(timedelta(hours=5, minutes=30))
        t_start_ist = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=ist_tz)
        t_end_ist = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=ist_tz) + timedelta(hours=23, minutes=59)

        results: List[Dict] = []

        # Store previous state per planet at previous scan timestamp.
        prev_state: Dict[str, Tuple[str, int, int]] = {}

        def state_at(dt_ist: datetime) -> Dict[str, Tuple[str, int, int, float]]:
            """Return per-planet: (nak_name, nak_idx, pada, lon_sid) at given IST datetime."""
            dt_utc = dt_ist.astimezone(timezone.utc)
            jd_ut = self._jd_from_utc(dt_utc)
            out: Dict[str, Tuple[str, int, int, float]] = {}
            for p in planets:
                lon_sid = self._sidereal_longitude(p, jd_ut)
                nak_name, nak_idx, pada, _deg_in_nak = self._nakshatra_pada_from_lon(lon_sid)
                out[p] = (nak_name, nak_idx, pada, lon_sid)
            return out

        # Initialize previous state at start timestamp.
        current = state_at(t_start_ist)
        for p in planets:
            nak_name, nak_idx, pada, _lon_sid = current[p]
            prev_state[p] = (nak_name, nak_idx, pada)

        # Scan forward
        step = timedelta(minutes=step_minutes)
        t = t_start_ist + step

        # To avoid duplicates, track last-emitted signature per planet for each event day.
        # Signature includes whether we were in a given entered nakshatra/pada.
        last_emitted: Dict[Tuple[str, str, str, int], str] = {}

        while t <= t_end_ist:
            current = state_at(t)
            date_str = t.astimezone(ist_tz).strftime("%Y-%m-%d")

            for p in planets:
                prev_nak, _prev_nak_idx, prev_pada = prev_state[p]
                nak_name, nak_idx, pada, lon_sid = current[p]


                if want_nak and nak_name != prev_nak:
                    key = (p, "NakshatraChange", nak_name, pada)
                    if last_emitted.get(key) != date_str:
                        results.append(
                            {
                                "date": date_str,
                                "planet": p,
                                "event_type": "NakshatraChange",
                                "entered_nakshatra": nak_name,
                                "entered_pada": pada,
                                "prev_nakshatra": prev_nak,
                                "prev_pada": prev_pada,
                                "lon_deg": float(lon_sid),
                            }
                        )
                        last_emitted[key] = date_str

                if want_pada and pada != prev_pada:
                    key = (p, "PadaChange", nak_name, pada)
                    if last_emitted.get(key) != date_str:
                        results.append(
                            {
                                "date": date_str,
                                "planet": p,
                                "event_type": "PadaChange",
                                "entered_nakshatra": nak_name,
                                "entered_pada": pada,
                                "prev_nakshatra": prev_nak,
                                "prev_pada": prev_pada,
                                "lon_deg": float(lon_sid),
                            }
                        )
                        last_emitted[key] = date_str

                prev_state[p] = (nak_name, nak_idx, pada)

            t += step

        return results


