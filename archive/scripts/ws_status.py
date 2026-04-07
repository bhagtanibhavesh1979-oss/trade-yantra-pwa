"""Comprehensive WebSocket & Session Status Check (ASCII Only)"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.session_manager import session_manager
from services.websocket_manager import ws_manager

print("="*60)
print("TRADE YANTRA - COMPREHENSIVE STATUS")
print("="*60)

print(f"Sessions in memory: {len(session_manager.sessions)}")

for i, (sid, sess) in enumerate(session_manager.sessions.items()):
    print(f"\n[{i+1}] Session: {sid[:16]}...")
    print(f"    Client ID: {sess.client_id}")
    print(f"    Watchlist: {len(sess.watchlist)} stocks")
    print(f"    SmartAPI:  {'OK' if sess.smart_api else 'MISSING'}")
    print(f"    JWT Token: {'PRESENT' if sess.jwt_token else 'MISSING'}")
    print(f"    Feed Token: {'PRESENT' if sess.feed_token else 'MISSING'}")
    
    with ws_manager.lock:
        connected = sid in ws_manager.connections
        last_tick = ws_manager.last_tick_times.get(sid, 0)
    
    print(f"    WS Connection (Angel): {'CONNECTED' if connected else 'NOT CONNECTED'}")
    
    if last_tick > 0:
        age = int(time.time() - last_tick)
        print(f"    Last Ticker Activity: {age}s ago")
    else:
        print(f"    Last Ticker Activity: NEVER")

print("\n" + "="*60)
print("DIAGNOSIS")
print("="*60)

if len(session_manager.sessions) > 0:
    for sid, sess in session_manager.sessions.items():
        issues = []
        if not sess.smart_api: issues.append("SmartAPI object missing")
        if not sess.jwt_token: issues.append("JWT token missing")
        if not sess.feed_token: issues.append("Feed token missing")
        
        with ws_manager.lock:
            if sid not in ws_manager.connections:
                issues.append("Not connected to Angel WebSocket")
        
        if issues:
            print(f"Session {sid[:8]} Issues: {', '.join(issues)}")
        else:
            print(f"Session {sid[:8]} Status: OK (Memory)")
else:
    print("No active sessions in memory.")

print("="*60)
