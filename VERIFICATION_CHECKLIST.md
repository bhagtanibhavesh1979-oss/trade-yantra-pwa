## Quick Verification Checklist

### ✅ Check 1: Connection Stability
- [ ] Open the app on mobile
- [ ] Watch the connection indicator (top-right)
- [ ] Switch to another app for 60 seconds
- [ ] Return to Trade Yantra
- [ ] **Expected**: Connection should recover within 2-5 seconds (green indicator)

### ✅ Check 2: Trade Persistence  
- [ ] Open Trades tab
- [ ] Add ₹100,000 to virtual wallet
- [ ] Enable "Auto Exec" toggle
- [ ] Go to Alerts tab and generate some support/resistance alerts
- [ ] Wait for a trade to execute
- [ ] **Test 2A**: Refresh the browser/app
  - [ ] Trade should still be visible
- [ ] **Test 2B**: Close app completely, reopen, login
  - [ ] All trades (open + closed) should be restored

### ✅ Check 3: Download Trades
- [ ] Go to Trades tab
- [ ] Ensure you have at least 1 executed trade
- [ ] Click "Download CSV" button (next to "Performance Today")
- [ ] **Expected**: 
  - [ ] Toast notification "Download started!"
  - [ ] CSV file downloads with name `trade_report.csv`
  - [ ] File contains all your trades with columns: ID, Time, Symbol, Side, Entry, Exit, Qty, Status, PnL, Reason

---

## What Changed?

### Backend
```diff
websocket_manager.py:
- time.sleep(5)  # Heartbeat every 5s
+ time.sleep(30) # Heartbeat every 30s - More stable!

- max_errors = 5  # Reconnect after 5 errors
+ max_errors = 10 # More lenient - prevents premature disconnects
```

### Frontend  
```diff
websocket.js:
- pingInterval: 5000  // Ping every 5s
+ pingInterval: 30000 // Ping every 30s - matches backend

- idleTime > 15000  // Reconnect if stalled 15s
+ idleTime > 60000  // Reconnect if stalled 60s - more patient!

- this.checkAndRecover()
+ setTimeout(() => this.checkAndRecover(), 2000) 
  // Wait 2s before reconnecting - prevents race conditions
```

### TradesTab.jsx
```diff
handleDownloadReport:
- const url = `/api/paper/export/...`
- window.open(url, '_blank')
+ const API_URL = import.meta.env.VITE_API_URL || ...
+ const url = `${API_URL}/api/paper/export/...`
+ Error handling + toast notifications
```

---

## Already Working (No Changes Needed)

✅ **Trade Persistence System**:
- Trades saved to: `backend/data/sessions.json`
- Also synced to Google Cloud Storage (if configured)
- Restored on login via `client_id`

✅ **Download Endpoint**:
- Backend route already exists: `/api/paper/export/{session_id}`
- Generates CSV with all trade details

---

## Common Issues & Solutions

### "Connection keeps disconnecting"
- ✅ **Fixed**: Increased timeouts from 5s→30s and 15s→60s
- If still happening: Check your internet connection stability

### "My trades disappeared!"  
- ✅ **Already working**: Trades are persisted to JSON file
- **Action**: Just login again with the same credentials
- Trades are tied to your `client_id`, not session

### "Download button does nothing"
- ✅ **Fixed**: Updated to use correct API URL
- If still failing: Check if popup blocker is enabled
- Alternative: Copy trades manually from the UI

---

## How to Deploy These Changes

### Local Development:
```bash
# Backend
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8002

# Frontend  
cd frontend
npm run dev
```

### Production (Google Cloud Run):
```bash
# Deploy backend
gcloud run deploy trade-yantra-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated

# Deploy frontend (if needed)
npm run build
# Upload dist/ to your hosting service
```

---

## Next Steps

1. Test the connection stability improvements
2. Verify trades persist across refresh/logout
3. Test the download feature
4. Monitor for any new issues
5. Enjoy a more stable trading experience! 📈
