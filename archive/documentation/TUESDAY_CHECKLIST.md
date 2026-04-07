# Pre-Trading Day Checklist
**Date: Tuesday, January 28, 2026**

## ✅ Current Status (January 25, 2026)

### Working Configuration:
- ✅ Backend: `https://trade-yantra-api-ibynqazflq-uc.a.run.app`
- ✅ Frontend: `https://trade-yantra-pwa-3llk.vercel.app` (or `https://frontend-eight-chi-33.vercel.app`)
- ⚠️ CORS: Currently set to `"*"` (allows all origins - INSECURE)

### Why Mobile App Works Now:
The backend defaults to allowing all origins when `CORS_ORIGINS` is not set. This is convenient but **not secure for live trading**.

---

## 🔒 Monday Night / Tuesday Morning (Before 9:00 AM)

### Step 1: Secure the Backend
Run this PowerShell command:
```powershell
cd C:\Users\bhave\Downloads\trade-yantra
.\secure-for-production.ps1
```

### Step 2: Verify Mobile Access
1. Open your mobile browser
2. Navigate to: `https://trade-yantra-pwa-3llk.vercel.app`
3. Login with Angel One credentials
4. Verify you can see your watchlist
5. Add a test stock and verify live prices update

### Step 3: Test Auto-Trade Setup
1. Go to **Trades Tab**
2. Click **"Auto-Generate Level Alerts"** for one stock (like AXISBANK)
3. Verify you see all **25 levels** (Red, Green, Black + Purple mid-pivots)
4. Enable **"Auto Paper Trade"**
5. Check that the toggle shows "ON"

### Step 4: Verify Strategy Settings
In the **Lab Tab**, confirm these settings are saved:
- ✅ Trigger Mode: **CANDLE CLOSE**
- ✅ Wick Sensitivity: **0.25%**
- ✅ Quantity: **100** (or your preferred quantity)

---

## 📊 During Market Hours (Tuesday 9:15 AM - 3:30 PM)

### First 15 Minutes (9:15 - 9:30 AM)
- [ ] Verify WebSocket connection is active (prices updating)
- [ ] Check that Auto-Trade is still enabled
- [ ] Monitor **Logs Tab** for any errors

### Throughout the Day
- [ ] Check **Trades Tab** for new paper trades
- [ ] Verify each trade shows:
  - Entry Level (e.g., "S1", "Mid_Pivot")
  - Side (BUY/SELL)
  - Entry Price
  - Reason (e.g., "CANDLE_CLOSE", "REJECTION")

### End of Day (3:15 PM)
- [ ] All positions should auto-square-off
- [ ] Check **Net P&L** in the dashboard
- [ ] Review the **Simulated Journey** to see all trades

---

## 🔍 Troubleshooting Guide

### Issue: "Failed to connect to backend"
**Solution:**
```powershell
# Check if backend is healthy
curl https://trade-yantra-api-ibynqazflq-uc.a.run.app/health
```
Expected response: `{"status":"healthy",...}`

### Issue: "CORS error" after securing
**Solution:**
Your Vercel URL might have changed. Run:
```powershell
cd frontend
npx vercel ls
# Note down the production URL, then update:
gcloud run services update trade-yantra-api --region us-central1 --set-env-vars "CORS_ORIGINS=YOUR_VERCEL_URL,http://localhost:5173"
```

### Issue: "No trades triggered even though price hit levels"
**Possible causes:**
1. Auto-Trade is OFF (check the toggle)
2. Alerts were not generated (click "Auto-Generate Level Alerts" again)
3. The 15-minute candle hasn't closed yet (wait for :00, :15, :30, :45 marks)

---

## 📞 Emergency Rollback

If anything goes wrong during market hours:

### Option 1: Disable Auto-Trading
1. Go to **Trades Tab**
2. Turn OFF **"Auto Paper Trade"**
3. Continue monitoring manually

### Option 2: Re-enable Permissive CORS (Temporary)
```powershell
gcloud run services update trade-yantra-api --region us-central1 --set-env-vars "CORS_ORIGINS=*"
```
**Note:** Only use this temporarily if you have urgent access issues.

---

## 📈 Post-Market Analysis

After 3:30 PM, check:
1. **Total Trades**: How many round-trips?
2. **Gross P&L**: Raw profit from trades
3. **Est. Brokerage**: ₹50 × number of trades
4. **Net P&L**: Final profit after costs
5. **Win Rate**: Percentage of profitable trades

**Decision Point:**
- If Net P&L > 0 with 60%+ win rate → Consider Sahi (₹10 brokerage)
- If Net P&L < 0 → Adjust sensitivity buffer or review levels

---

**Created:** January 25, 2026, 12:33 AM IST
**Last Updated:** Before secure-for-production.ps1 execution
