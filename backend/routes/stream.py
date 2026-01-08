"""
WebSocket Stream Routes
Handles real-time price updates via WebSocket
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.session_manager import session_manager
from services.websocket_manager import ws_manager
import json
import asyncio

router = APIRouter(tags=["Stream"])

@router.websocket("/ws/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time price updates
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()
    
    # Get session
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return
    
    # Register this WebSocket connection
    if not hasattr(session, 'websocket_clients'):
        session.websocket_clients = []
    session.websocket_clients.append(websocket)
    
    # Broadcast callback for WebSocket manager
    # Uses run_coroutine_threadsafe to safely bridge from Angel's thread to FastAPI's async loop
    def broadcast_callback(sid: str, message: dict):
        if sid == session_id:
            # Broadcast to ALL connected clients for this session (multi-tab support)
            for client in list(session.websocket_clients):
                try:
                    asyncio.run_coroutine_threadsafe(client.send_json(message), loop)
                except:
                    pass
    
    # Start WebSocket if not already running on backend
    if session.watchlist and session.smart_api:
        # Check if already running to avoid duplicate connection attempts
        is_running = False
        with ws_manager.lock:
            if session_id in ws_manager.connections:
                is_running = True
                # Update the callback to the new connection
                ws_manager.broadcast_callbacks[session_id] = broadcast_callback
        
        if not is_running:
            print(f"🚀 Starting new Angel One WebSocket for {session_id}")
            ws_manager.start_websocket(
                session_id,
                session.jwt_token,
                session.api_key,
                session.client_id,
                session.feed_token,
                session.watchlist,
                broadcast_callback
            )
        else:
            print(f"🔄 Reusing existing Angel One WebSocket for {session_id}")
            # Immediately send status and last prices if possible
            await websocket.send_json({"type": "status", "data": {"status": "CONNECTED"}})
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get('type') == 'ping':
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        # Clean up on disconnect
        if websocket in session.websocket_clients:
            session.websocket_clients.remove(websocket)
        # CRITICAL: Don't stop ws_manager here on Cloud Run/Mobile
        # We want the Angel One connection to STAY ALIVE even if tab is closed/refreshed
        print(f"Browser WebSocket disconnected for session {session_id} (Persistent backend WS remains)")
    except Exception as e:
        print(f"WebSocket Error: {e}")
