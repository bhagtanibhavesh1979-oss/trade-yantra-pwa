"""
WebSocket Diagnostic Script
Checks the state of WebSocket connections and sessions
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8002"

# Get session from localStorage (you'll need to paste your session_id)
print("=" * 60)
print("WEBSOCKET DIAGNOSTIC TOOL")
print("=" * 60)

# First, let's check if backend is responding
try:
    resp = requests.get(f"{BASE_URL}/", timeout=5)
    print(f"✅ Backend is responding: {resp.status_code}")
except Exception as e:
    print(f"❌ Backend connection failed: {e}")
    exit(1)

# Ask for session ID
session_id = input("\nEnter your session_id (from browser localStorage): ").strip()

if not session_id:
    print("❌ Session ID required")
    exit(1)

print(f"\n🔍 Checking session: {session_id[:8]}...\n")

# Check session validity
try:
    resp = requests.get(f"{BASE_URL}/api/auth/verify/{session_id}", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Session is valid")
        print(f"   Client ID: {data.get('client_id', 'N/A')}")
        print(f"   Active: {data.get('active', False)}")
    else:
        print(f"❌ Session invalid or expired: {resp.status_code}")
        print(f"   Response: {resp.text}")
        exit(1)
except Exception as e:
    print(f"❌ Failed to verify session: {e}")
    exit(1)

# Check watchlist
try:
    resp = requests.get(f"{BASE_URL}/api/watchlist/{session_id}", timeout=10)
    if resp.status_code == 200:
        watchlist = resp.json()
        print(f"\n📊 Watchlist: {len(watchlist)} stocks")
        if watchlist:
            print(f"   Sample: {watchlist[0].get('symbol', 'N/A')}")
    else:
        print(f"\n❌ Failed to fetch watchlist: {resp.status_code}")
except Exception as e:
    print(f"\n❌ Watchlist check failed: {e}")

# Instructions for WebSocket test
print("\n" + "=" * 60)
print("WEBSOCKET CONNECTION TEST")
print("=" * 60)
print("\n1. Open browser DevTools (F12)")
print("2. Go to Network tab > WS (WebSocket)")
print("3. Refresh the page")
print("4. Look for connection to: /ws/stream/{session_id}")
print("\nExpected:")
print("  ✅ Status: 101 Switching Protocols")
print("  ✅ Messages flowing with 'price_update' type")
print("\nIf you see:")
print("  ❌ 403/404/500 - Check backend logs")
print("  ❌ Connection closes immediately - Token issue")
print("  ❌ No messages - Angel WebSocket not receiving data")
print("\n" + "=" * 60)
print("BACKEND LOG COMMANDS")
print("=" * 60)
print("\nRun these in PowerShell:")
print(f"  Get-Content backend\\backend_out.log -Tail 50 -Wait")
print(f"  Get-Content backend\\backend_debug.log -Tail 50 -Wait")
print("\nLook for:")
print("  [WS-INIT] messages - Shows WebSocket initialization")
print("  [WS-DEBUG] messages - Shows data reception from Angel")
print("  ✅ [WS] WebSocket Connected - Angel connection successful")
print("  ❌ errors or exceptions - Problem indicators")
