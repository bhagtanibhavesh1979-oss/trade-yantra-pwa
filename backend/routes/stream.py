"""
WebSocket Streaming Route
Real-time data stream to frontend
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.session_manager import session_manager
from services.websocket_manager import ws_manager
from services.alert_service import check_alert_trigger, create_alert_log
import json
import asyncio
from typing import Dict

router = APIRouter(tags=["WebSocket"])

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

@router.websocket("/ws/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time data streaming
    Broadcasts: price updates, alert triggers, status changes
    """
    await websocket.accept()
    
    # Verify session
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Invalid session"}
        })
        await websocket.close()
        return
    
    # Store connection
    active_connections[session_id] = websocket
    session.websocket_clients.append(websocket)
    
    print(f"WebSocket connected for session {session_id}")
    
    # Capture running loop for thread-safe broadcasting from background thread
    loop = asyncio.get_running_loop()
    
    # Broadcast callback for Angel One WebSocket
    def broadcast_to_client(sid: str, message: Dict):
        """Broadcast message to frontend WebSocket"""
        if sid == session_id and sid in active_connections:
            try:
                # Use threadsafe call since this runs in Angel One's thread
                asyncio.run_coroutine_threadsafe(
                    active_connections[sid].send_json(message), 
                    loop
                )
            except Exception as e:
                print(f"Broadcast error: {e}")

    # Start Angel One WebSocket if not already started
    if session_id not in ws_manager.connections:
        success = ws_manager.start_websocket(
            session_id=session_id,
            jwt_token=session.jwt_token,
            api_key=session.api_key,
            client_id=session.client_id,
            feed_token=session.feed_token,
            watchlist=session.watchlist,
            broadcast_callback=broadcast_to_client
        )
        
        if not success:
            print(f"Warning: Failed to start Angel One WebSocket for session {session_id}")
            # Don't close the WebSocket, allow connection for alerts and other features
            # await websocket.send_json({
            #     "type": "error",
            #     "data": {"message": "Failed to start Angel One WebSocket"}
            # })
            # await websocket.close()
            # return
    
    # Send initial status
    await websocket.send_json({
        "type": "connected",
        "data": {
            "session_id": session_id,
            "client_id": session.client_id,
            "watchlist_count": len(session.watchlist),
            "alerts_count": len(session.alerts)
        }
    })
    
    # Heartbeat task
    async def send_heartbeat():
        while session_id in active_connections:
            try:
                await asyncio.sleep(15) # Heartbeat every 15s (was 30s)
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"timestamp": asyncio.get_event_loop().time()}
                })
            except:
                break
    
    heartbeat_task = asyncio.create_task(send_heartbeat())
    
    # Alert checking task
    async def check_alerts_task():
        while session_id in active_connections:
            try:
                await asyncio.sleep(1)  # Check every second
                
                if session.is_paused:
                    continue
                
                # Check all alerts
                triggered_alerts = []
                for alert in list(session.alerts):
                    stock = next((s for s in session.watchlist if s['token'] == alert['token']), None)
                    if stock and check_alert_trigger(alert, stock):
                        triggered_alerts.append((alert, stock))
                        session.alerts.remove(alert)
                
                # Broadcast triggered alerts
                for alert, stock in triggered_alerts:
                    log_entry = create_alert_log(stock, alert)
                    session.logs.insert(0, log_entry)
                    
                    await websocket.send_json({
                        "type": "alert_triggered",
                        "data": {
                            "alert": alert,
                            "stock": stock,
                            "log": log_entry
                        }
                    })
            except:
                break
    
    alerts_task = asyncio.create_task(check_alerts_task())
    
    try:
        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            # For now, just echo back
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {"timestamp": asyncio.get_event_loop().time()}
                })
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Cleanup
        heartbeat_task.cancel()
        alerts_task.cancel()
        
        if session_id in active_connections:
            del active_connections[session_id]
        
        if websocket in session.websocket_clients:
            session.websocket_clients.remove(websocket)
        
        print(f"WebSocket cleanup completed for session {session_id}")
