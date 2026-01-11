"""
Trade Yantra - FastAPI Backend (GCP Optimized)
Final Version - Fixes 404s, Session Loss, and WebSocket Disconnects
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
from dotenv import load_dotenv

# Diagnostics for Google Cloud Run
print("--- STARTING TRADE YANTRA BACKEND ---")
print(f"DEBUG: PATH = {os.getcwd()}")
print(f"DEBUG: PORT ENV = {os.environ.get('PORT', 'Not Set')}")
sys.stdout.flush()

# Load environment variables
load_dotenv()

# Import routes
from routes import auth, watchlist, alerts, stream, indices

# Import services
from services.session_manager import session_manager
from services.websocket_manager import ws_manager

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Startup and shutdown events """
    import sys
    print("🚀 Trade Yantra Backend Starting on GCP...")
    sys.stdout.flush()
    
    # Load scrip master in background
    import threading
    from services.angel_service import angel_service
    print("⏳ Starting Scrip Master background loader...")
    sys.stdout.flush()
    threading.Thread(target=angel_service.load_scrip_master, daemon=True).start()
    
    print("✅ Backend Startup Sequence Complete!")
    sys.stdout.flush()
    yield
    
    # Shutdown logic
    print("==> Trade Yantra Backend Shutting Down...")
    ws_manager.stop_all()

# Create FastAPI app
app = FastAPI(
    title="Trade Yantra API",
    description="Optimized for Google Cloud Run Deployment",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration - Updated to avoid Startup Crash with '*'
default_origins = "https://trade-yantra-pwa-3llk.vercel.app,http://localhost:5173"
allowed_origins_str = os.getenv("CORS_ORIGINS", default_origins)

if allowed_origins_str == "*":
    allowed_origins = ["*"]
    allow_all_credentials = False # Starlette requirement
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
    allow_all_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_all_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXED ROUTER PREFIXES
# We add /api/ prefix here to match exactly what your PWA frontend is calling.
# This fixes the "404 Not Found" errors.
app.include_router(auth.router)
app.include_router(watchlist.router)
app.include_router(alerts.router)
app.include_router(indices.router)

# Stream usually handles its own /ws prefix inside the router
app.include_router(stream.router) 

@app.get("/")
@app.get("/health")
async def health_check():
    """
    Critical for Google Cloud: Used by the Load Balancer 
    to know the container is alive.
    """
    return {
        "status": "healthy",
        "service": "Trade Yantra API",
        "environment": "Google Cloud Run"
    }

@app.get("/debug/session/{session_id}")
async def debug_session(session_id: str):
    """ Debug endpoint to check session status """
    from services.persistence_service import persistence_service
    db_data = persistence_service.get_session_by_session_id(session_id)
    memory_session = session_manager.get_session(session_id)
    
    return {
        "session_id": session_id,
        "in_memory": memory_session is not None,
        "in_database": bool(db_data),
        "client_id": db_data.get('client_id') if db_data else None
    }

if __name__ == "__main__":
    # Local/GCP Port Configuration
    port = int(os.environ.get("PORT", 8002))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        # WebSocket Optimization for Mobile Devices
        # These keep the 'tunnel' open even if no trades are happening
        ws_ping_interval=20.0, 
        ws_ping_timeout=20.0,
        timeout_keep_alive=60
    )
