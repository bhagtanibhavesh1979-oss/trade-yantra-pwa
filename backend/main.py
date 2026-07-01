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

# Load .env from project root (so BOT_TOKEN / CHAT_ID are available to services)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()




# Diagnostics for Google Cloud Run
print("--- STARTING TRADE YANTRA BACKEND ---")
# FORCE UTF-8 for Windows Console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

print(f"DEBUG: PATH = {os.getcwd()}")
print(f"DEBUG: PORT ENV = {os.environ.get('PORT', 'Not Set')}")
sys.stdout.flush()

# Load environment variables
load_dotenv()

# Import routers
# Ensure current directory is on sys.path so `backend` package resolves under uvicorn.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.routes import (
    auth_router,
    watchlist_router,
    alerts_router,
    stream_router,
    indices_router,
    paper_router,
    live_router,
    chart_router,
    telegram_signals_router,
)
from backend.routes.astro import router as astro_router
from backend.routes.backtest_astro import router as backtest_astro_router









# Import services (package-qualified)
from backend.services.session_manager import session_manager
from backend.services.websocket_manager import ws_manager


# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Startup and shutdown events """
    import sys
    print("[INFO] Trade Yantra Backend Starting on GCP...")
    sys.stdout.flush()
    
    # Load scrip master in background - Don't let this crash the startup
    try:
        import threading
        from backend.services.angel_service import angel_service
        print("[INFO] Starting Scrip Master background loader...")
        sys.stdout.flush()
        threading.Thread(target=angel_service.load_scrip_master, daemon=True).start()
    except Exception as e:
        print(f"[WARN] Scrip Master loader failed to start: {e}")
        print("[INFO] App will continue without scrip master")
        sys.stdout.flush()
    
    print("[OK] Backend Startup Sequence Complete!")
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

# CORS Configuration
cors_origins_str = os.getenv("CORS_ORIGINS", "*")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXED ROUTER PREFIXES
# We add /api/ prefix here to match exactly what your PWA frontend is calling.
# This fixes the "404 Not Found" errors.
app.include_router(auth_router)
app.include_router(watchlist_router)
app.include_router(alerts_router)
app.include_router(indices_router)
app.include_router(paper_router)
app.include_router(live_router)
app.include_router(chart_router)
app.include_router(astro_router)
app.include_router(backtest_astro_router)
app.include_router(telegram_signals_router)



# Stream usually handles its own /ws prefix inside the router
app.include_router(stream_router)


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
        "environment": "Google Cloud Run",
        "version": "1.1.0-POST-FIX-v4"
    }

@app.get("/debug/session/{session_id}")
async def debug_session(session_id: str):
    """ Debug endpoint to check session status """
    from backend.services.persistence_service import persistence_service
    db_data = persistence_service.get_session_by_session_id(session_id)

    memory_session = session_manager.get_session(session_id)
    
    return {
        "session_id": session_id,
        "in_memory": memory_session is not None,
        "in_database": bool(db_data),
        "client_id": db_data.get('client_id') if db_data else None
    }

@app.get("/debug/heartbeat")
async def debug_heartbeat():
    """ Check if strategy heartbeat thread is running """
    thread = ws_manager.heartbeat_thread
    return {
        "running": ws_manager.running,
        "thread_exists": thread is not None,
        "thread_alive": thread.is_alive() if thread else False,
        "last_strategy_tick": getattr(ws_manager, '_last_strategy_tick', 'N/A'),
        "active_broadcasts": len(ws_manager.broadcast_callbacks),
        "active_connections": len(ws_manager.connections)
    }

if __name__ == '__main__':
    print('About to start uvicorn')
    # Local/GCP Port Configuration
    port = int(os.environ.get("PORT", 8002))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        # WebSocket Optimization for Stable Connections
        # These settings MUST align with application-level heartbeat
        ws_ping_interval=None,  # Disable uvicorn ping, we handle it at app level
        ws_ping_timeout=None,   # Disable uvicorn timeout
        timeout_keep_alive=120, # Keep HTTP connections alive for 2 minutes
        timeout_graceful_shutdown=10
    )
