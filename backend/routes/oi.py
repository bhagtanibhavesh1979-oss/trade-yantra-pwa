"""OI Tracker Routes

Provides an HTTP snapshot for option-chain open interest around ATM.

GET /api/oi/snapshot/{session_id}?client_id=...
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.services.session_manager import session_manager
from backend.services.oi_service import oi_service
from backend.services import oi_history
from pydantic import BaseModel


class AdminSettings(BaseModel):
    agg_method: Optional[str] = None
    trim_alpha: Optional[float] = None
    retention_days: Optional[int] = None

router = APIRouter(prefix="/api/oi", tags=["OI Tracker"])


@router.get("/snapshot/{session_id}")
async def oi_snapshot(session_id: str, client_id: Optional[str] = Query(None)):
    # NOTE: get_session() in this codebase is keyed primarily by session_id,
    # and `client_id` is only used as a heal fallback.
    # Some frontend tabs may not pass the exact client_id, so we avoid
    # coupling OI snapshot to that.
    session = session_manager.get_session(session_id)
    if not session:
        session = session_manager.get_session(session_id, client_id=client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")


    res = oi_service.snapshot(session_id)
    return res


@router.get("/history/{session_id}")
async def oi_history_route(
    session_id: str,
    underlying: Optional[str] = Query("NIFTY 50"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
):
    # validate underlying
    if underlying not in ("NIFTY 50", "SENSEX"):
        raise HTTPException(status_code=400, detail="unsupported underlying")

    try:
        rows = oi_history.get_history(session_id, underlying, from_ts, to_ts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "data": rows}


@router.post("/admin/settings")
async def oi_admin_settings(payload: AdminSettings):
    # apply settings
    try:
        if payload.agg_method is not None:
            oi_history.set_agg_method(payload.agg_method)
        if payload.trim_alpha is not None:
            oi_history.set_trim_alpha(payload.trim_alpha)
        if payload.retention_days is not None:
            oi_history.set_retention_days(int(payload.retention_days))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "success",
        "settings": {
            "agg_method": oi_history.AGG_METHOD,
            "trim_alpha": oi_history.TRIM_ALPHA,
            "retention_days": oi_history.RETENTION_DAYS,
        },
    }


@router.post("/admin/prune")
async def oi_admin_prune():
    try:
        oi_history.trigger_prune()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "detail": "prune triggered"}


@router.get("/admin/settings")
async def oi_admin_get_settings():
    try:
        return {
            "status": "success",
            "settings": {
                "agg_method": oi_history.AGG_METHOD,
                "trim_alpha": oi_history.TRIM_ALPHA,
                "retention_days": oi_history.RETENTION_DAYS,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

