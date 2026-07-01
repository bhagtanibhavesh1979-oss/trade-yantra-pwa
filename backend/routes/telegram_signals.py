from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.live_signal_service import telegram_signal_engine

router = APIRouter(prefix="/api/signals/telegram", tags=["Telegram Signals"])


class SessionIdRequest(BaseModel):
    session_id: str


@router.post("/start/{session_id}")
async def start_engine(session_id: str):
    return telegram_signal_engine.start_for_session(session_id)


@router.post("/stop/{session_id}")
async def stop_engine(session_id: str):
    return telegram_signal_engine.stop_for_session(session_id)

