"""
Trade Yantra - FastAPI Backend
Progressive Web App Trading Application Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Import routes
from routes import auth, watchlist, alerts, stream, indices

# Import services
from services.session_manager import session_manager
from services.angel_service import angel_service
from services.websocket_manager import ws_manager

# Load environment variables
load_dotenv()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events
    """
    # Startup
    print("==> Trade Yantra Backend Starting...")
    
    # Load scrip master in background
    import threading
    threading.Thread(target=angel_service.load_scrip_master, daemon=True).start()
    
    print("==> Backend Ready!")
    
    yield
    
    # Shutdown
    print("==> Trade Yantra Backend Shutting Down...")
    
    # Stop all WebSocket connections
    ws_manager.stop_all()

# Create FastAPI app
app = FastAPI(
    title="Trade Yantra API",
    description="Progressive Web App Trading Application Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(watchlist.router)
app.include_router(alerts.router)
app.include_router(stream.router)
app.include_router(indices.router)

# Health check endpoint
@app.get("/")
async def root():
    """
    Health check and API info
    """
    return {
        "service": "Trade Yantra API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "auth": "/api/auth",
            "watchlist": "/api/watchlist",
            "alerts": "/api/alerts",
            "stream": "/ws/stream/{session_id}"
        },
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """
    Health check for monitoring
    """
    return {
        "status": "healthy",
        "active_sessions": len(session_manager.get_all_sessions()),
        "scrip_master_loaded": angel_service.master_loaded
    }

# For Railway deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Disable reload in production
        log_level="info"
    )
