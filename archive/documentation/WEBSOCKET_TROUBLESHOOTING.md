# WebSocket Streaming Troubleshooting Guide
## Generated: 2026-02-12 09:50 IST

## Quick Diagnosis Steps

### Step 1: Is the Backend Running?
```powershell
Get-Process -Name python
```
Expected: Should show python.exe process

If not running:
```powershell
cd c:\Users\bhave\Downloads\trade-yantra
.\start_backend.bat
```

### Step 2: Check Backend Logs for WebSocket Initialization
```powershell
Get-Content backend\backend_out.log -Tail 100 -Wait
```

Look for these messages when you refresh the frontend:
- `[WS-INIT] WebSocket connection initiated for session...`
- `[WS-INIT] ✅ Session found. Watchlist: X stocks`
- `[WS-INIT] feed_token present: True`
- `[WS-INIT] 🚀 Starting NEW Angel One WebSocket...`
- `✅ [WS] WebSocket Connected for session...`

**Missing [WS-INIT] messages?**
- Frontend is not connecting to backend WebSocket endpoint
- Check browser console for WebSocket errors
- Verify: `ws://127.0.0.1:8002/ws/stream/{session_id}` is accessible

### Step 3: Check if Angel WebSocket is Receiving Data
```powershell
Get-Content backend\backend_out.log -Tail 100 -Wait
```

Look for:
- `[WS-DEBUG] {session} Data RX: {token} -> {price}`
- `[WS-DEBUG] {session} BINARY RX: {token} -> {price}`

**These messages appear every 5 seconds when data is flowing**

**Not seeing [WS-DEBUG] messages?**
→ Angel One WebSocket is NOT receiving data from broker

**Possible causes:**
1. **Market is closed** (Market hours: 9:15 AM - 3:30 PM IST Monday-Friday)
2. **Token expired** - Need to re-login
3. **Angel API issue** - Check Angel One status
4. **Network/firewall** blocking WebSocket connection to Angel servers

### Step 4: Check Browser Console
Open DevTools (F12) → Console tab

**Expected logs:**
```
Connecting to WebSocket: ws://127.0.0.1:8002/ws/stream/{session_id}
WebSocket connected
[WS] Price update received: SYMBOL 1234.56
[WS] Price update received: SYMBOL 1234.60
```

**Not seeing "WebSocket connected"?**
- Check Network tab → WS subtab
- Should show `/ws/stream/{session_id}` with status 101
- If 403/404/500: Backend routing issue
- If connection closes immediately: Token/auth issue

**Seeing "WebSocket connected" but no price updates?**
- Backend is connected but Angel WebSocket not receiving data
- Go back to Step 3

### Step 5: Check Network Tab
DevTools → Network → WS (WebSocket)

**Expected:**
- Connection to: `ws://127.0.0.1:8002/ws/stream/{session_id}`
- Status: 101 Switching Protocols
- Messages flowing (green up/down arrows)

**Click on the WebSocket connection** to see messages:
- Should see `price_update` messages with token and ltp
- Should see occasional `pong` responses to ping

**No messages flowing?**
- Backend WebSocket connected but no data from Angel
- See "Angel WebSocket Not Receiving Data" section below

---

## Common Issues & Solutions

### Issue 1: Market Hours
**Symptom:** No data streaming
**Solution:** Live market data only available during market hours (9:15 AM - 3:30 PM IST, Mon-Fri)
**Note:** Even during market hours, there may be brief periods with no updates if stocks are not trading

### Issue 2: Token Expired
**Symptom:** WebSocket connects then disconnects, or never connects
**Solution:**
1. Logout from the app
2. Login again with fresh credentials
3. This will generate new JWT and feed tokens

### Issue 3: Angel WebSocket Not Receiving Data
**Symptom:** Backend logs show WebSocket connected but no `[WS-DEBUG]` messages

**Debug Steps:**
1. Check if Angel One API is working:
   ```python
   # Run this in backend directory
   python
   >>> from services.session_manager import session_manager
   >>> # Get your session_id from browser localStorage
   >>> session = session_manager.get_session("your_session_id_here")
   >>> session.smart_api.ltpData("NSE", "SBIN-EQ", "3045")
   ```
   Should return: `{'status': True, 'data': {'ltp': 782.5}}`

2. If LTP works but WebSocket doesn't:
   - Angel One WebSocket servers might be down
   - Network/firewall blocking WebSocket connection
   - Feed token might be invalid (re-login)

### Issue 4: Frontend Not Connecting to Backend
**Symptom:** No `[WS-INIT]` messages in backend logs when you refresh page

**Check:**
1. Is frontend running? Look for browser window with app
2. Check browser console for errors
3. Verify backend URL in frontend:
   - Should auto-detect: `ws://127.0.0.1:8002` for localhost
   - Check DevTools → Console → Look for "Connecting to WebSocket:" message

### Issue 5: Watchlist Empty
**Symptom:** `[WS-INIT] ✅ Session found. Watchlist: 0 stocks`

**Solution:**
- Add stocks to your watchlist first
- WebSocket won't start if watchlist is empty

### Issue 6: Feed Token Missing
**Symptom:** `[WS-INIT] feed_token present: False`

**Solution:**
- Logout and login again
- Feed token is required for WebSocket connection to Angel One

---

## Manual Testing Commands

### Test Backend API is Responding
```powershell
curl http://127.0.0.1:8002/
```
Expected: HTML or JSON response

### Test Session is Valid
```powershell
# Replace {session_id} with your actual session ID
curl http://127.0.0.1:8002/api/auth/verify/{session_id}
```
Expected: `{"active": true, "client_id": "..."}`

### Test Watchlist Endpoint
```powershell
curl http://127.0.0.1:8002/api/watchlist/{session_id}
```
Expected: JSON array of stocks

---

## Emergency Restart Procedure

If nothing works:

1. **Stop Everything:**
   ```powershell
   Get-Process -Name python | Stop-Process -Force
   Get-Process -Name node | Stop-Process -Force
   ```

2. **Clear Browser Data:**
   - Open DevTools (F12)
   - Application tab → Storage → Clear site data
   - Or manually: localStorage → Delete`trade_yantra_session`

3. **Restart Backend:**
   ```powershell
   cd c:\Users\bhave\Downloads\trade-yantra
   .\start_backend.bat
   ```

4. **Restart Frontend:**
   ```powershell
   cd c:\Users\bhave\Downloads\trade-yantra\frontend
   npm run dev
   ```

5. **Re-login to the app**

6. **Add stocks to watchlist**

7. **Check logs** for [WS-DEBUG] messages

---

## What to Report if Issue Persists

If data still not streaming after all above steps, collect this info:

1. **Current time:** [Verify market is open]

2. **Backend logs output:**
   ```powershell
   Get-Content backend\backend_out.log -Tail 200 > ws_issue_backend.txt
   ```

3. **Browser console output:**
   - Take screenshot of console showing WebSocket connection

4. **Network tab:**
   - Screenshot of WS subtab showing connection status

5. **Session info:**
   - Watchlist count: X stocks
   - feed_token present: Yes/No
   - Connection appears in backend logs: Yes/No
   - `[WS-DEBUG]` messages appearing: Yes/No

This will help identify if issue is:
- Frontend → Backend connection
- Backend → Angel One connection
- Angel One → Data feed
