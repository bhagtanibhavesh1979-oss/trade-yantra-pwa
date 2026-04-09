"""
Trade Yantra - Local Pre-Push Diagnostic Script
Use this to verify your local backend before deploying to Cloud.
"""
import requests
import json
import time

# Local Backend Port (Matches your fixed main.py and api.js)
BASE_URL = "http://localhost:8002"

def test_health():
    print(f"🔍 Testing Health Check at {BASE_URL}/health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is ALIVE and reachable on port 8002!")
            return True
        else:
            print(f"❌ Backend returned error {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("   TIP: Make sure you ran 'python backend/main.py' or similar.")
        return False

def test_search(query="SBI"):
    print(f"\n🔍 Testing Search for '{query}'...")
    try:
        response = requests.get(f"{BASE_URL}/api/watchlist/search/{query}", timeout=5)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                print(f"✅ Search working! Found {len(results)} matches.")
                for r in results[:3]:
                    print(f"   - {r['symbol']} (Token: {r['token']})")
                return results[0]
            else:
                print("⚠️ Search working but returned 0 results. Check scripmaster.json path.")
                return None
        else:
            print(f"❌ Search failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Search error: {e}")
        return None

def main():
    print("="*60)
    print("TRADE YANTRA - LOCAL PRE-PUSH TEST")
    print("="*60)
    
    if not test_health():
        return

    stock = test_search()
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    if stock:
        print("✅ Core systems are working locally.")
        print("👉 You can now safely test 'Add Stock' in the browser.")
        print("👉 Frontend should be on http://localhost:5173")
    else:
        print("❌ Diagnostic found issues. Please check the 'backend_startup.log' if it exists.")

if __name__ == "__main__":
    main()
