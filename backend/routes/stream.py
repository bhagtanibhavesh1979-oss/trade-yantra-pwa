"""
WebSocket Stream Routes
Handles real-time price updates via WebSocket
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
from backend.services.session_manager import session_manager
from backend.services.websocket_manager import ws_manager
import json
import asyncio

router = APIRouter(tags=["Stream"])

@router.websocket("/ws/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, client_id: Optional[str] = None):
    """
    WebSocket endpoint for real-time price updates
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()
    
    # Get session
    session = session_manager.get_session(session_id, client_id=client_id)
    print(f"[WS-INIT] WebSocket connection initiated for session {session_id[:8]}...")
    
    if not session:
        print(f"[WS-INIT] [ERR] Session not found for {session_id}")
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return
    
    print(f"[WS-INIT] [OK] Session found. Watchlist: {len(session.watchlist)} stocks")
    print(f"[WS-INIT] feed_token present: {bool(session.feed_token)}")
    print(f"[WS-INIT] jwt_token present: {bool(session.jwt_token)}")
    
    # Register this WebSocket connection
    if not hasattr(session, 'websocket_clients'):
        session.websocket_clients = []
    session.websocket_clients.append(websocket)
    print(f"[WS-INIT] Registered client. Total clients: {len(session.websocket_clients)}")
    
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
    # FIX: Allow starting if we have a feed_token, even if smart_api object is missing (persisted session)
    if session.watchlist and session.feed_token:
        print(f"[WS-INIT] Conditions met for WebSocket start (watchlist + feed_token)")
        # Check if already running to avoid duplicate connection attempts
        is_running = False
        with ws_manager.lock:
            if session_id in ws_manager.connections:
                is_running = True
                # Update the callback to the new connection
                ws_manager.broadcast_callbacks[session_id] = broadcast_callback
                print(f"[WS-INIT]   Reusing existing Angel WebSocket connection")
        
        if not is_running:
            print(f"[WS-INIT] [EXEC] Starting NEW Angel One WebSocket...")
            success = ws_manager.start_websocket(
                session_id,
                session.jwt_token,
                session.data_api_key,
                session.client_id,
                session.feed_token,
                session.watchlist,
                broadcast_callback
            )
            print(f"[WS-INIT] WebSocket start result: {success}")
            if success:
                # Notify frontend that connection was established
                await websocket.send_json({"type": "connected", "data": {"session_id": session_id, "status": "started"}})
        else:
            # Immediately send connected message so frontend light turns green
            await websocket.send_json({"type": "connected", "data": {"session_id": session_id, "status": "reused"}})
    
        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get('type') == 'ping':
                    await websocket.send_json({"type": "pong"})
                 
                elif message.get('type') == 'subscribe_token':
                    token = message.get('token')
                    if not token:
                        await websocket.send_json({"type": "error", "message": "Token is required"})
                        continue
                    # Get session
                    session = session_manager.get_session(session_id, client_id=client_id)
                    if not session:
                        await websocket.send_json({"type": "error", "message": "Session not found"})
                        continue
                    # Try to get stock data from session's watchlist
                    stock_data = None
                    for s in session.watchlist:
                        if s['token'] == token:
                            stock_data = s
                            break
                    # If not in watchlist, try to get from scrip master
                    if not stock_data:
                        from backend.services.angel_service import angel_service
                        # Ensure scrip master is loaded
                        if not angel_service.master_loaded:
                            angel_service.load_scrip_master()
                        for s in angel_service.scrips:
                            if s['token'] == token:
                                stock_data = s
                                break
                    # If still not found, create a minimal stock_data
                    if not stock_data:
                        stock_data = {'symbol': token, 'token': token, 'exch_seg': 'NSE'}
                    # Subscribe via websocket manager
                    success = ws_manager.subscribe_chart_token(session_id, token, stock_data)
                    if success:
                        await websocket.send_json({"type": "subscription_confirmation", "token": token})
                    else:
                        await websocket.send_json({"type": "error", "message": "Failed to subscribe to token"})
                 
                elif message.get('type') == 'unsubscribe_token':
                    token = message.get('token')
                    if not token:
                        await websocket.send_json({"type": "error", "message": "Token is required"})
                        continue
                    success = ws_manager.unsubscribe_chart_token(session_id, token)
                    if success:
                        await websocket.send_json({"type": "unsubscription_confirmation", "token": token})
                    else:
                        await websocket.send_json({"type": "error", "message": "Failed to unsubscribe from token"})
                 
                elif message.get('type') == 'pong':
                    # Server responded to our ping -- keep the websocket alive
                    continue
                 
                elif message.get('type') == 'status':
                    # Status update from server
                    print('Server status:', data)
                 
                elif message.get('type') == 'error':
                    print('WebSocket error message:', data)
                 
                else:
                    print('Unknown message type:', type, data)
        except WebSocketDisconnect:
            # Clean up on disconnect
            if websocket in session.websocket_clients:
                session.websocket_clients.remove(websocket)
            # CRITICAL: Don't stop ws_manager here on Cloud Run/Mobile
            # We want the Angel One connection to STAY ALIVE even if tab is closed/refreshed
            print(f"Browser WebSocket disconnected for session {session_id} (Persistent backend WS remains)")
        except Exception as e:
            print(f"WebSocket Error: {e}")
