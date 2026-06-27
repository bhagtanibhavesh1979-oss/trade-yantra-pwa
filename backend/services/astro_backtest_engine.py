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
    def __init__(self):
        # Lahiri sidereal mode
        swe.set_sid_mode(swe.SIDM_LAHIRI)

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
        lon, lat, dist, speed_lon = swe.calc_ut(jd_ut, swe_id, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]

        lon_sid = self._wrap_360(float(lon))
        if planet == "Ketu":
            lon_sid = self._wrap_360(lon_sid + 180.0)
        return lon_sid

    def _nakshatra_pada_from_lon(self, lon_sid: float) -> Tuple[str, int, int, float]:
        nak_idx = int(lon_sid / NAK_SPAN) % 27
        deg_in_nak = lon_sid - nak_idx * NAK_SPAN
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
    ) -> List[Dict]:
        """Compute daily transitions between consecutive days.

        Returns rows for each transition day (where nakshatra or pada differs from previous day).
        Each row:
        {
          date: YYYY-MM-DD (IST)
          planet: str
          event_type: "NakshatraChange" | "PadaChange"
          entered_nakshatra: str
          entered_pada: int
          prev_nakshatra: str
          prev_pada: int
          lon_deg: float
        }
        """

        want_nak = "NakshatraChange" in set(event_types)
        want_pada = "PadaChange" in set(event_types)

        d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
        if d0 > d1:
            raise ValueError("start_date must be <= end_date")

        # We need previous day info; start at start_date - 1
        prev_date = d0 - timedelta(days=1)

        def info_for(date_obj) -> Dict[str, Tuple[str, int, int]]:
            date_str = date_obj.strftime("%Y-%m-%d")
            jd_ut = self._jd_from_utc(self._utc_datetime_from_ist_date(date_str, hour_ist=0))

            out: Dict[str, Tuple[str, int, int]] = {}
            for p in planets:
                lon_sid = self._sidereal_longitude(p, jd_ut)
                nak_name, nak_idx, pada, _deg_in_nak = self._nakshatra_pada_from_lon(lon_sid)
                out[p] = (nak_name, nak_idx, pada)
            return out

        prev_info = info_for(prev_date)

        results: List[Dict] = []
        for i in range((d1 - d0).days + 1):
            curr_date = d0 + timedelta(days=i)
            date_str = curr_date.strftime("%Y-%m-%d")

            jd_ut = self._jd_from_utc(self._utc_datetime_from_ist_date(date_str, hour_ist=0))

            for p in planets:
                lon_sid = self._sidereal_longitude(p, jd_ut)
                nak_name, nak_idx, pada, deg_in_nak = self._nakshatra_pada_from_lon(lon_sid)

                prev_nak, _prev_nak_idx, prev_pada = prev_info[p]

                if want_nak and nak_name != prev_nak:
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

                if want_pada and pada != prev_pada:
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

                # update prev_info for this planet
                prev_info[p] = (nak_name, nak_idx, pada)

        return results

