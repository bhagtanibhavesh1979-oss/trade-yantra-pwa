"""
Astrology Routes
Nakshatra transitions and Moon position for chart markers.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import datetime

from backend.services.session_manager import session_manager
from backend.services.astro_engine import (
    find_nakshatra_transitions,
    get_nakshatra_for_timestamps,
    get_nakshatra_info,
    moon_longitude_sidereal,
    julian_day,
    lahiri_ayanamsha,
    NAKSHATRAS,
)

router = APIRouter(prefix="/api/astro", tags=["Astrology"])


@router.get("/nakshatras")
def get_nakshatra_transitions(
    from_ts: int  = Query(..., description="Start Unix timestamp (seconds, IST)"),
    to_ts:   int  = Query(..., description="End Unix timestamp (seconds, IST)"),
    session_id: str = Query(...),
    client_id:  Optional[str] = Query(None),
):
    """
    Returns Moon Nakshatra transition events for the given time range.
    Timestamps should be in the same format as the chart candles (IST-adjusted Unix seconds).

    Response:
    {
        "transitions": [
            {
                "timestamp":      1717123800,
                "nakshatra":      "Rohini",
                "index":          3,
                "pada":           2,
                "degree":         40.84,
                "deg_in_nak":     1.51,
                "prev_nakshatra": "Krittika"
            },
            ...
        ],
        "current": { nakshatra info for to_ts },
        "ayanamsha": 24.12
    }
    """
    # Validate session
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if from_ts >= to_ts:
        raise HTTPException(status_code=400, detail="from_ts must be less than to_ts")

    # The frontend sends IST-adjusted timestamps (UTC + 19800).
    # Convert to true UTC for astronomical calculations by subtracting IST offset.
    IST_OFFSET = 19800  # 5h30m in seconds

    utc_from = from_ts - IST_OFFSET
    utc_to   = to_ts   - IST_OFFSET

    try:
        transitions = find_nakshatra_transitions(
            [utc_from, utc_to],
            step_minutes=10,
        )

        # Shift transition timestamps back to IST for the frontend
        for t in transitions:
            t["timestamp"] = t["timestamp"] + IST_OFFSET

        # Current Moon position at to_ts
        J2000_UNIX = 946728000.0
        SEC_PER_JD = 86400.0
        jd_now     = 2451545.0 + (utc_to - J2000_UNIX) / SEC_PER_JD
        lon_now    = moon_longitude_sidereal(jd_now)
        current    = get_nakshatra_info(lon_now)
        ayanamsha  = lahiri_ayanamsha(jd_now)

        return {
            "transitions": transitions,
            "current":     current,
            "ayanamsha":   round(ayanamsha, 4),
            "count":       len(transitions),
        }

    except Exception as e:
        print(f"[AstroRoute] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Astro calculation error: {str(e)}")


@router.get("/moon/now")
def get_moon_now(
    session_id: str = Query(...),
    client_id:  Optional[str] = Query(None),
):
    """Returns current Moon Nakshatra position."""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    import time
    now_utc    = int(time.time())
    J2000_UNIX = 946728000.0
    SEC_PER_JD = 86400.0
    jd         = 2451545.0 + (now_utc - J2000_UNIX) / SEC_PER_JD
    lon        = moon_longitude_sidereal(jd)
    info       = get_nakshatra_info(lon)
    info["ayanamsha"] = round(lahiri_ayanamsha(jd), 4)
    info["timestamp"] = now_utc
    return info


@router.get("/nakshatras/list")
def list_nakshatras():
    """Returns all 27 Nakshatra names with their degree ranges."""
    span = 360 / 27
    return {
        "nakshatras": [
            {
                "index":      i,
                "name":       name,
                "start_deg":  round(i * span, 4),
                "end_deg":    round((i + 1) * span, 4),
            }
            for i, name in enumerate(NAKSHATRAS)
        ]
    }