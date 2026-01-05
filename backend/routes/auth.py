from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.session_manager import session_manager
from services.angel_service import angel_service
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    api_key: str
    client_id: str
    password: str
    totp_secret: str

class LoginResponse(BaseModel):
    session_id: str
    client_id: str
    message: str

class LogoutRequest(BaseModel):
    session_id: str

class LogoutResponse(BaseModel):
    success: bool
    message: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """
    Login to Angel One and create session
    Using synchronous def to run in FastAPI's thread pool (better for blocking requests)
    """
    import time
    start_time = time.time()
    print(f"==> Login attempt for {req.client_id} started")
    
    # 1. Angel One Auth (Synchronous blocking call)
    success, message, smart_api, tokens = angel_service.login(
        req.api_key,
        req.client_id,
        req.password,
        req.totp_secret
    )
    
    auth_time = time.time() - start_time
    print(f"==> Angel Auth took {auth_time:.2f}s")
    
    if not success:
        print(f"==> Login failed: {message}")
        raise HTTPException(status_code=401, detail=message)
    
    # 2. Create local session
    create_start = time.time()
    session = session_manager.create_session(
        client_id=req.client_id,
        jwt_token=tokens['jwt_token'],
        feed_token=tokens['feed_token'],
        api_key=req.api_key
    )
    session.refresh_token = tokens['refresh_token']
    session.smart_api = smart_api
    
    create_time = time.time() - create_start
    print(f"==> Session creation took {create_time:.2f}s")
    
    total_time = time.time() - start_time
    print(f"==> Total login response time: {total_time:.2f}s")
    
    return LoginResponse(
        session_id=session.session_id,
        client_id=session.client_id,
        message="Login successful"
    )

@router.post("/logout", response_model=LogoutResponse)
async def logout(req: LogoutRequest):
    """
    Logout and clear session
    """
    session = session_manager.get_session(req.session_id)
    if session and session.smart_api:
        angel_service.logout(session.smart_api)
        
    success = session_manager.delete_session(req.session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return LogoutResponse(
        success=True,
        message="Logged out successfully"
    )

@router.get("/session/{session_id}")
async def check_session(session_id: str):
    """
    Check if session is valid
    """
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "valid": True,
        "client_id": session.client_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat()
    }
