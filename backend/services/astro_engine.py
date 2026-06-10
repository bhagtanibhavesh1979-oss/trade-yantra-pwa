"""
Astrology Engine
----------------
Calculates Moon position and Nakshatra transitions using the Jean Meeus
algorithm (Astronomical Algorithms, 2nd Ed.) with Lahiri ayanamsha.

No external astronomy library required — pure Python math.
Accuracy: ~0.3° (sufficient for Nakshatra determination, which spans 13.33°).

Install note: No pip install needed. Uses only Python stdlib (math, datetime).
If you later want higher precision, install: pip install ephem
and replace moon_longitude_tropical() with an ephem-based calculation.
"""

import math
import datetime
from typing import List, Tuple, Optional


# ── Constants ──────────────────────────────────────────────────────────────────

NAKSHATRAS: List[str] = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

NAK_SPAN        = 360.0 / 27        # 13.3333° per nakshatra
PADA_SPAN       = NAK_SPAN / 4      # 3.3333° per pada

# Lahiri ayanamsha at J2000.0 and annual precession rate
LAHIRI_J2000    = 23.85028          # degrees
PRECESSION_RATE = 50.2388475 / 3600 # degrees per year


# ── Julian Day ─────────────────────────────────────────────────────────────────

def julian_day(dt: datetime.datetime) -> float:
    """Convert a UTC datetime to Julian Day Number (fractional)."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = (
        dt.day
        + (153 * m + 2) // 5
        + 365 * y
        + y // 4
        - y // 100
        + y // 400
        - 32045
    )
    return jdn + (dt.hour - 12) / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0


def datetime_from_julian(jd: float) -> datetime.datetime:
    """Convert Julian Day Number back to UTC datetime."""
    jd = jd + 0.5
    z  = int(jd)
    f  = jd - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)

    day    = b - d - int(30.6001 * e)
    month  = e - 1 if e < 14 else e - 13
    year   = c - 4716 if month > 2 else c - 4715

    total_seconds = f * 86400
    hour   = int(total_seconds // 3600)
    minute = int((total_seconds % 3600) // 60)
    second = int(total_seconds % 60)
    return datetime.datetime(year, month, day, hour, minute, second)


# ── Ayanamsha ──────────────────────────────────────────────────────────────────

def lahiri_ayanamsha(jd: float) -> float:
    """Return Lahiri ayanamsha in degrees for the given Julian Day."""
    years_since_j2000 = (jd - 2451545.0) / 365.25
    return LAHIRI_J2000 + PRECESSION_RATE * years_since_j2000


# ── Moon Longitude ─────────────────────────────────────────────────────────────

def _r(deg: float) -> float:
    """Degrees → radians (normalised to 0–360 first)."""
    return math.radians(deg % 360)


def moon_longitude_tropical(jd: float) -> float:
    """
    Tropical Moon longitude (degrees) using Jean Meeus Chapter 47.
    Accuracy ~0.3° — well within the 13.33° nakshatra span.
    """
    T = (jd - 2451545.0) / 36525.0

    # Fundamental arguments
    L0      = 218.3164477  + 481267.88123421 * T - 0.0015786 * T**2 + T**3 / 538841    - T**4 / 65194000
    M       = 357.5291092  +  35999.0502909  * T - 0.0001536 * T**2 + T**3 / 24490000
    M_prime = 134.9633964  + 477198.8675055  * T + 0.0087414 * T**2 + T**3 / 69699     - T**4 / 14712000
    F       =  93.2720950  + 483202.0175233  * T - 0.0036539 * T**2 - T**3 / 3526000   + T**4 / 863310000
    omega   = 125.0445479  -   1934.1362608  * T + 0.0020755 * T**2 + T**3 / 467441    - T**4 / 60616000

    # Periodic corrections in longitude (degrees)
    sigma_l = (
         6.288774 * math.sin(_r(M_prime))
        + 1.274027 * math.sin(_r(2 * L0 - M_prime))
        + 0.658314 * math.sin(_r(2 * L0))
        + 0.213618 * math.sin(_r(2 * M_prime))
        - 0.185116 * math.sin(_r(M))
        - 0.114332 * math.sin(_r(2 * F))
        + 0.058793 * math.sin(_r(2 * L0 - 2 * M_prime))
        + 0.057066 * math.sin(_r(2 * L0 - M - M_prime))
        + 0.053322 * math.sin(_r(2 * L0 + M_prime))
        + 0.045758 * math.sin(_r(2 * L0 - M))
        - 0.040923 * math.sin(_r(M - M_prime))
        - 0.034720 * math.sin(_r(L0))
        - 0.030383 * math.sin(_r(M + M_prime))
        + 0.015327 * math.sin(_r(2 * (L0 - F)))
        - 0.012528 * math.sin(_r(M_prime + 2 * F))
        + 0.010980 * math.sin(_r(M_prime - 2 * F))
        + 0.010675 * math.sin(_r(4 * L0 - M_prime))
        + 0.010034 * math.sin(_r(3 * M_prime))
        + 0.008548 * math.sin(_r(4 * L0 - 2 * M_prime))
        - 0.007888 * math.sin(_r(2 * L0 + M - M_prime))
        - 0.006766 * math.sin(_r(2 * L0 + M))
        - 0.005163 * math.sin(_r(M_prime - M))
        + 0.004987 * math.sin(_r(L0 + M))
        + 0.004036 * math.sin(_r(2 * L0 - M + M_prime))
        + 0.003994 * math.sin(_r(2 * (L0 + M_prime)))
        + 0.003861 * math.sin(_r(4 * L0))
        + 0.003665 * math.sin(_r(2 * L0 - 3 * M_prime))
        - 0.002689 * math.sin(_r(M - 2 * M_prime))
        - 0.002602 * math.sin(_r(2 * (L0 - M_prime - F)))
        + 0.002390 * math.sin(_r(2 * (L0 - M_prime) - M))
        - 0.002348 * math.sin(_r(L0 + M_prime))
        + 0.002236 * math.sin(_r(2 * (L0 - M)))
        - 0.002120 * math.sin(_r(M + 2 * M_prime))
        - 0.002069 * math.sin(_r(2 * M))
        + 0.002048 * math.sin(_r(2 * (L0 - M) - M_prime))
        - 0.001773 * math.sin(_r(2 * L0 + M_prime - 2 * F))
        - 0.001595 * math.sin(_r(2 * (L0 + F)))
        + 0.001215 * math.sin(_r(4 * L0 - M - M_prime))
        - 0.001110 * math.sin(_r(2 * (M_prime + F)))
        - 0.000892 * math.sin(_r(3 * L0 - M_prime))
        - 0.000811 * math.sin(_r(L0 + M + M_prime))
        + 0.000761 * math.sin(_r(4 * L0 - M - 2 * M_prime))
        + 0.000717 * math.sin(_r(M_prime - 2 * M))
        + 0.000704 * math.sin(_r(M_prime - 2 * (M + F)))
        + 0.000693 * math.sin(_r(M - 2 * (M_prime - L0)))
        + 0.000598 * math.sin(_r(2 * (L0 - M) - F))
        + 0.000550 * math.sin(_r(M_prime + 4 * L0))
        + 0.000537 * math.sin(_r(4 * M_prime))
        + 0.000521 * math.sin(_r(4 * L0 - M))
        + 0.000500 * math.sin(_r(M_prime - M + 2 * L0))
        # Nutation correction (simplified)
        - 0.000170 * math.sin(_r(omega))
    )

    return (L0 + sigma_l) % 360


def moon_longitude_sidereal(jd: float) -> float:
    """Sidereal Moon longitude (degrees) with Lahiri ayanamsha correction."""
    tropical  = moon_longitude_tropical(jd)
    ayanamsha = lahiri_ayanamsha(jd)
    return (tropical - ayanamsha) % 360


# ── Nakshatra Lookup ──────────────────────────────────────────────────────────

def get_nakshatra_info(sidereal_lon: float) -> dict:
    """
    Returns nakshatra name, index (0-26), pada (1-4), and degree within nakshatra.
    """
    idx    = int(sidereal_lon / NAK_SPAN) % 27
    deg_in = sidereal_lon - idx * NAK_SPAN
    pada   = int(deg_in / PADA_SPAN) + 1
    return {
        "nakshatra": NAKSHATRAS[idx],
        "index":     idx,
        "pada":      min(pada, 4),
        "degree":    round(sidereal_lon, 4),
        "deg_in_nak": round(deg_in, 4),
    }


# ── Transition Finder ─────────────────────────────────────────────────────────

def find_nakshatra_transitions(
    timestamps: List[int],
    step_minutes: int = 10,
) -> List[dict]:
    """
    Given a list of Unix timestamps (seconds), find each moment the Moon
    crosses into a new Nakshatra between min(timestamps) and max(timestamps).

    Scans at `step_minutes` resolution (default 10 min).
    Moon moves ~0.09° per 10 min — well under the 13.33° nakshatra span,
    so no transitions are missed.

    Returns list of transition dicts:
    {
        "timestamp":      <unix_seconds of transition>,
        "nakshatra":      "Rohini",
        "index":          3,          # 0-based
        "pada":           1,
        "degree":         40.12,      # sidereal Moon longitude
        "deg_in_nak":     0.45,
        "prev_nakshatra": "Krittika",
    }
    """
    if not timestamps:
        return []

    J2000_UNIX = 946728000.0
    SEC_PER_JD = 86400.0
    step_sec   = step_minutes * 60

    from_ts = min(timestamps)
    to_ts   = max(timestamps)

    def nak_idx_at(ts: int) -> int:
        jd  = 2451545.0 + (ts - J2000_UNIX) / SEC_PER_JD
        lon = moon_longitude_sidereal(jd)
        return int(lon / NAK_SPAN) % 27

    def info_at(ts: int, prev_idx: int) -> dict:
        jd   = 2451545.0 + (ts - J2000_UNIX) / SEC_PER_JD
        lon  = moon_longitude_sidereal(jd)
        info = get_nakshatra_info(lon)
        info["timestamp"]      = ts
        info["prev_nakshatra"] = NAKSHATRAS[prev_idx]
        return info

    results  = []
    prev_idx = nak_idx_at(from_ts)
    ts       = from_ts + step_sec

    while ts <= to_ts:
        idx = nak_idx_at(ts)
        if idx != prev_idx:
            results.append(info_at(ts, prev_idx))
            prev_idx = idx
        ts += step_sec

    return results


def get_nakshatra_for_timestamps(timestamps: List[int]) -> List[dict]:
    """
    For each timestamp in the list, return the Moon's Nakshatra.
    Used to annotate candle data.
    """
    J2000_UNIX = 946728000.0
    SEC_PER_JD = 86400.0

    results = []
    for ts in timestamps:
        jd  = 2451545.0 + (ts - J2000_UNIX) / SEC_PER_JD
        lon = moon_longitude_sidereal(jd)
        info = get_nakshatra_info(lon)
        info["timestamp"] = ts
        results.append(info)
    return results