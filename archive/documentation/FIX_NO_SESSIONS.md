# WebSocket Streaming - Step-by-Step Fix
## Current Issue: Sessions: 0

## The Problem
- Backend is running ✅
- BUT no sessions are loaded (Sessions: 0) ❌
- This means no frontend is connected OR user not logged in
- Without a session, WebSocket cannot start

## STEP-BY-STEP SOLUTION

### Step 1: Check if Frontend is Running
```powershell
# Check if any Node process is running (frontend)
Get-Process -Name node -ErrorAction SilentlyContinue
```

**If nothing shows up**, start the frontend:
```powershell
cd frontend
npm run dev
```

Look for output like:
```
VITE ready in XXX ms
➜ Local: http://localhost:5173/
```

---

### Step 2: Open the App in Browser
1. Open browser
2. Go to: `http://localhost:5173` (or whatever port Vite shows)
3. You should see the login page

---

### Step 3: Login with Angel One Credentials
1. Enter your:
   - API Key
   - Client ID
   - Password
   - TOTP Secret (if using 2FA)

2. Click "Login"

3. **Watch backend console for messages:**
   ```
   Session manager initialized
   ✅ Login successful for client: XXXXXX
   [WS-INIT] WebSocket connection initiated...
   ✅ [WS] WebSocket Connected for session...
   ```

---

### Step 4: Add Stocks to Watchlist (if empty)
1. After login, go to Watchlist tab
2. Search and add at least 2-3 stocks
3. Backend should show:
   ```
   [WS] Watchlist size: X tokens
   ```

---

### Step 5: Wait for Data (15-30 seconds)
- After login + adding stocks, wait ~30 seconds
- Market must be OPEN (9:15 AM - 3:30 PM IST, Mon-Fri)

**Check backend logs for data reception:**
```powershell
Get-Content backend\backend_out.log -Tail 50 -Wait
```

Look for:
```
[WS-DEBUG] {session} Data RX: {token} -> {price}
```

---

### Step 6: Verify in Browser
1. Open DevTools (F12) → Console tab
2. Should see:
   ```
   WebSocket connected
   [WS] Price update received: SBIN 782.50
   [WS] Price update received: RELIANCE 1234.56
   ```

3. Prices should update in the UI

---

### Step 7: Run Status Check Again
```powershell
python ws_status.py
```

**Expected output:**
```
Sessions: 1
Session: abc12345-1234-1234...
  Watchlist: 5
  Feed Token: True
  JWT Token: True
  WS Connected: True
  Last tick: 3s ago
```

---

## If Still Not Working After All Steps

### Check 1: Is Market Open?
```
Current time: 10:01 AM IST ✅ (Market is OPEN 9:15-15:30)
```
Market is open NOW, so data SHOULD be flowing.

### Check 2: Backend Logs
```powershell
Get-Content backend\backend_out.log -Tail 100
```

Look for:
- ❌ "Token expired" → Re-login required
- ❌ "max retry attempts" → Angel API connection issue
- ❌ Any traceback/error → Share with me

### Check 3: Browser Console
F12 → Console tab

Look for:
- ❌ "WebSocket connection failed"
- ❌ "403 Forbidden" or "401 Unauthorized"
- ❌ Any red errors → Share with me

### Check 4: Network Tab
F12 → Network → WS tab

- Should show: `/ws/stream/{session_id}`
- Status should be: 101 (Switching Protocols)
- Messages should be flowing

---

## Quick Diagnostic Commands

### Is frontend running?
```powershell
Get-Process node
```

### Is backend running?
```powershell
Get-Process python
```

### Backend recent logs:
```powershell
Get-Content backend\backend_out.log -Tail 30
```

### Session status:
```powershell
python ws_status.py
```

---

## If You Need to Restart Everything

```powershell
# Stop all processes
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force

# Start backend
.\start_backend.bat

# Wait 5 seconds, then start frontend
cd frontend
npm run dev

# Open browser → http://localhost:5173
# Login
# Add stocks to watchlist
# Wait 30 seconds
# Check: python ws_status.py
```

---

## WHAT TO DO RIGHT NOW

1. ✅ Backend is running (you confirmed this)
2. ⏭️ **START FRONTEND** if not running
3. ⏭️ **OPEN BROWSER** → http://localhost:5173
4. ⏭️ **LOGIN** to the app
5. ⏭️ **RUN**: `python ws_status.py` again
6. ⏭️ **REPORT**: What Sessions count shows then

The Sessions: 0 is because no one is logged in yet!
