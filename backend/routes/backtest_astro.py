"""Astro backtesting routes.

This route powers the Planet Nakshatra/Pada backtest feature.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.services.session_manager import session_manager
from backend.services.planet_nakshatra_backtest_service import planet_nakshatra_backtest_service


router = APIRouter(prefix="/api/astro/backtest", tags=["Astro Backtest"])


@router.get("/planet-nakshatra")
def backtest_planet_nakshatra(
    years: int = Query(5, ge=1, le=30, description="How many years back to run the backtest"),
    planets: Optional[list[str]] = Query(None, description="Optional list of planets"),
    sidereal_mode: str = Query("lahiri", description="Sidereal mode: lahiri | chitra | true_citra"),
    session_id: str = Query(..., description="Session id"),
    client_id: Optional[str] = Query(None),
):

    """Backtest NIFTY/BANKNIFTY behavior after planet changes in Nakshatra/Pada."""
    session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        smart_api = session.smart_api
        if not smart_api:
            raise HTTPException(status_code=401, detail="SmartAPI session not available")

        requested_planets = planets or ["Sun", "Mars", "Jupiter", "Saturn", "Mercury", "Rahu", "Ketu"]

        result = planet_nakshatra_backtest_service.run(
            smart_api=smart_api,
            years=years,
            planets=requested_planets,
            include_event_types=["NakshatraChange", "PadaChange"],
            horizons=[5, 10, 20],
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest error: {str(e)}")

