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
    CRITICAL for Cloud Run: Session must be committed to database BEFORE returning
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
        client_id=req.client_id.upper(),
        jwt_token=tokens['jwt_token'],
        feed_token=tokens['feed_token'],
        api_key=req.api_key
    )
    session.refresh_token = tokens['refresh_token']
    session.smart_api = smart_api
    
    create_time = time.time() - create_start
    print(f"==> Session creation took {create_time:.2f}s")
    
    # 3. CRITICAL: Verify session was saved to database
    # Optimized: Single retry with short delay for better UX
    from services.persistence_service import persistence_service
    max_retries = 1  # Reduced from 3 for faster login
    retry_delay = 0.2  # Reduced from 0.5 seconds
    
    for attempt in range(max_retries):
        try:
            db_session = persistence_service.get_session_by_session_id(session.session_id)
            if db_session and db_session.get('client_id') == req.client_id:
                print(f"[OK] Session {session.session_id} verified in database")
                print(f"[OK] Restored {len(session.watchlist)} watchlist items, {len(session.alerts)} alerts")
                break
            elif attempt < max_retries - 1:
                print(f"[WARN] Session not found in database, retry {attempt + 1}/{max_retries}")
                time.sleep(retry_delay)
                session_manager.save_session(session.session_id)
        except Exception as e:
            print(f"[WARN] Database verification warning (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                # Don't fail login - session is in memory
                print(f"[WARN] Proceeding with in-memory session (database save will retry in background)")
                pass
    
    total_time = time.time() - start_time
    print(f"==> Total login response time: {total_time:.2f}s")
    
    return LoginResponse(
        session_id=session.session_id,
        client_id=session.client_id,
        message="Login successful"
    )

@router.post("/logout", response_model=LogoutResponse)
def logout(req: LogoutRequest):
    """
    Logout and clear session
    """
    session = session_manager.get_session(req.session_id)
    if session:
        # Final save to persist any recent P&L or logs
        session_manager.save_session(req.session_id)
        if session.smart_api:
            angel_service.logout(session.smart_api)
        
    success = session_manager.delete_session(req.session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return LogoutResponse(
        success=True,
        message="Logged out successfully"
    )

@router.get("/verify/{session_id}")
def verify_session(session_id: str, client_id: Optional[str] = None):
    """
    Check if session is valid and restore from DB if needed.
    Enhanced with client_id for robust Self-Healing.
    """
    print(f"[INFO] Verifying session: {session_id} (Client: {client_id})")
    
    # get_session handles self-healing using client_id if provided
    session = session_manager.get_session(session_id, client_id=client_id)
    
    if not session:
        # One last desperate attempt to heal from persistence directly
        if client_id:
             from services.persistence_service import persistence_service
             restored = persistence_service.get_latest_session_by_client_id(client_id)
             if restored:
                 # Manually trigger healing logic if session_manager missed it
                 session = session_manager.get_session(session_id, client_id) 
        
    if not session:
        print(f"[ERROR] Session {session_id} could not be healed")
        raise HTTPException(status_code=404, detail="Session expired or invalid")
    
    print(f"[OK] Verified session for client {session.client_id}")
    return {
        "success": True,
        "valid": True,
        "client_id": session.client_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat()
    }
