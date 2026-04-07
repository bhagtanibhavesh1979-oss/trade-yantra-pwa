import requests
import sys

# Change to the appropriate session ID if needed
SESSION_ID = "fe856cec-63bb-4862-be34-433ef1314646" 
BASE_URL = "http://localhost:8002"

def trigger_manual_check():
    print(f"Triggering manual strategy check for session {SESSION_ID}...")
    try:
        # Based on routes/alerts.py, the endpoint is /api/alerts/generate-bulk
        response = requests.post(f"{BASE_URL}/api/alerts/generate-bulk", json={
            "session_id": SESSION_ID,
            "date": "2026-03-19" # Today's date for levels
        })
        print(f"Response: {response.status_code}")
        print(response.json())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    trigger_manual_check()
