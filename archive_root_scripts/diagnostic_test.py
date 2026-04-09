"""
Quick diagnostic script to test session and alert persistence
Run this to verify database connectivity and data persistence
"""
import requests
import json

# IMPORTANT: Update this URL based on your deployment
BASE_URL = "https://trade-yantra-api-ibynqazflq-ue.a.run.app"

def test_health():
    """Test if API is reachable"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Health Check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def test_login(api_key, client_id, password, totp_secret):
    """Test login and session creation"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "api_key": api_key,
                "client_id": client_id,
                "password": password,
                "totp_secret": totp_secret
            },
            timeout=30
        )
        print(f"\n📝 Login Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            session_id = data.get('session_id')
            print(f"✅ Login successful!")
            print(f"   Session ID: {session_id}")
            print(f"   Client ID: {data.get('client_id')}")
            return session_id
        else:
            print(f"❌ Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_session_check(session_id):
    """Test if session persists"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/auth/session/{session_id}",
            timeout=10
        )
        print(f"\n🔍 Session Check: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Session is valid!")
            print(f"   Data: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"❌ Session check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Session check error: {e}")
        return False

def test_get_alerts(session_id):
    """Test fetching alerts"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/alerts/{session_id}",
            timeout=10
        )
        print(f"\n🔔 Get Alerts: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            alerts = data.get('alerts', [])
            print(f"✅ Found {len(alerts)} alerts")
            if alerts:
                print(f"   First alert: {json.dumps(alerts[0], indent=2)}")
            return alerts
        else:
            print(f"❌ Failed to get alerts: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Get alerts error: {e}")
        return []

def main():
    print("=" * 60)
    print("Trade Yantra - Database Persistence Diagnostic Test")
    print("=" * 60)
    
    # Step 1: Health check
    if not test_health():
        print("\n❌ Cannot reach API. Check your internet connection and API URL.")
        return
    
    print("\n" + "=" * 60)
    print("Please provide your Angel One credentials:")
    print("=" * 60)
    api_key = input("API Key: ").strip()
    client_id = input("Client ID: ").strip()
    password = input("Password: ").strip()
    totp_secret = input("TOTP Secret: ").strip()
    
    # Step 2: Test login
    session_id = test_login(api_key, client_id, password, totp_secret)
    if not session_id:
        print("\n❌ Login failed. Cannot proceed with tests.")
        return
    
    # Step 3: Test session persistence
    import time
    print("\n⏳ Waiting 2 seconds before session check...")
    time.sleep(2)
    
    if not test_session_check(session_id):
        print("\n❌ Session not persisting to database!")
        print("   This is the root cause of logout-on-refresh issue.")
        return
    
    # Step 4: Test alert retrieval
    alerts = test_get_alerts(session_id)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ API accessible: YES")
    print(f"✅ Login working: YES")
    print(f"✅ Session persists: YES")
    print(f"📊 Alerts count: {len(alerts)}")
    
    if len(alerts) > 0:
        print(f"\n✅ ALERTS ARE PERSISTING - Database is working correctly!")
        print(f"   If you're not seeing alerts in the frontend:")
        print(f"   1. Make sure you rebuilt the frontend: npm run build")
        print(f"   2. Clear browser cache and localStorage")
        print(f"   3. Check browser console for errors")
    else:
        print(f"\n⚠️  No alerts found. This could mean:")
        print(f"   1. You haven't generated any alerts yet")
        print(f"   2. Alerts are not being saved to database")
        print(f"   3. Database was recently cleaned/reset")

if __name__ == "__main__":
    main()
