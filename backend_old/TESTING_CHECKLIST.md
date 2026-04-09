# Post-Deployment Testing Checklist

Use this checklist to verify your Google Cloud Run deployment works correctly.

---

## 1. Basic Health Checks ✅

### Test API Health Endpoint
```bash
# Replace with your actual Cloud Run URL
curl https://your-service-url.run.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "active_sessions": 0,
  "scrip_master_loaded": true
}
```

- [ ] Status is "healthy"
- [ ] Response time < 2 seconds

---

### Test Root Endpoint
```bash
curl https://your-service-url.run.app/
```

**Expected Response:**
```json
{
  "service": "Trade Yantra API",
  "version": "1.0.0",
  "status": "running",
  ...
}
```

- [ ] Service returns correct info
- [ ] All endpoints listed

---

## 2. Frontend Integration ✅

### Update Frontend URL

**Production (.env.production):**
```env
VITE_API_URL=https://your-service-url.run.app
```

**Local Testing (.env.local):**
```env
VITE_API_URL=https://your-service-url.run.app
```

- [ ] Environment variable updated
- [ ] Frontend rebuilt
- [ ] Frontend deployed (if production)

---

## 3. Authentication Flow ✅

### Test Login
1. Open your frontend application
2. Enter Angel One credentials
3. Submit login form

**Verify:**
- [ ] Login completes successfully
- [ ] No CORS errors in browser console
- [ ] Session created
- [ ] Dashboard loads

---

## 4. WebSocket Connection ✅

### Test Real-Time Connection

**After login:**
- [ ] WebSocket connects (check browser DevTools → Network → WS)
- [ ] Connection shows as "connected"
- [ ] No immediate disconnections

### Test Connection Stability
**Monitor for 5+ minutes:**
- [ ] Connection stays open (no dropouts)
- [ ] Heartbeat messages received every 15 seconds
- [ ] No "reconnecting" messages

**This is the KEY TEST** - Render had frequent dropouts, Google Cloud should be stable.

---

## 5. Watchlist Features ✅

### Add Stock to Watchlist
1. Search for a stock (e.g., "RELIANCE")
2. Add to watchlist

**Verify:**
- [ ] Stock added successfully
- [ ] Price data fetched
- [ ] PDH/PDL values displayed

### Live Price Updates
**Wait 30-60 seconds:**
- [ ] LTP (Last Traded Price) updates automatically
- [ ] Updates continue without manual refresh
- [ ] No connection interruptions

---

## 6. Alert System ✅

### Generate Alerts
1. Select a stock from watchlist
2. Generate High/Low alerts for a date
3. View generated alerts

**Verify:**
- [ ] Alerts generated successfully
- [ ] Support/Resistance levels calculated
- [ ] Alerts appear in alerts tab

### Test Alert Triggering
**If live price reaches alert level:**
- [ ] Alert triggers automatically
- [ ] Browser notification appears
- [ ] Alert moves to logs
- [ ] Alert removed from active alerts

---

## 7. Performance Testing ✅

### Response Times
Measure and verify:
- [ ] Login: < 3 seconds
- [ ] Add stock: < 2 seconds
- [ ] Refresh prices: < 2 seconds
- [ ] Generate alerts: < 3 seconds

### Cold Start (only if min-instances=0)
1. Wait 15 minutes (service should scale to zero)
2. Open frontend and login

**Verify:**
- [ ] First request completes (may take 2-5 seconds)
- [ ] Subsequent requests are fast (< 1 second)

---

## 8. Long-Running Stability ✅

### 30-Minute Test
**Leave application running for 30 minutes:**
- [ ] WebSocket stays connected
- [ ] Live prices continue updating
- [ ] No errors in browser console
- [ ] No reconnection attempts

### 2-Hour Test (Optional but Recommended)
**If possible, monitor for 2 hours:**
- [ ] Connection remains stable
- [ ] Memory usage doesn't grow (check Cloud Run metrics)
- [ ] No crashes or restarts

---

## 9. Error Handling ✅

### Test Graceful Failures
**Simulate errors:**
1. Manually disconnect internet for 5 seconds
2. Reconnect

**Verify:**
- [ ] WebSocket reconnects automatically
- [ ] Frontend shows reconnecting state
- [ ] Data syncs after reconnection

---

## 10. Google Cloud Monitoring ✅

### Check Cloud Run Dashboard
Visit: [Google Cloud Console](https://console.cloud.google.com/run)

**Verify:**
- [ ] Service shows as "healthy"
- [ ] No errors in logs
- [ ] Request count increasing
- [ ] CPU/Memory usage normal (< 50%)

### View Logs
```bash
gcloud run services logs read trade-yantra-api \
  --region us-central1 \
  --limit 50
```

**Check for:**
- [ ] No error messages
- [ ] Successful WebSocket connections
- [ ] Normal startup messages

---

## 11. Comparison with Render ✅

### Side-by-Side Test (Optional)
**Keep both running and compare:**

**Render:**
- Connection stability: ___
- Average response time: ___
- Dropout frequency: ___

**Google Cloud Run:**
- Connection stability: ___
- Average response time: ___
- Dropout frequency: ___

**Winner:** ___

---

## 12. Final Decision ✅

### After 48 Hours of Testing

**If Google Cloud Run is better:**
- [ ] Update production frontend URL permanently
- [ ] Monitor for 1 more week
- [ ] Delete Render deployment (or keep as backup)

**If Render is still better (unlikely):**
- [ ] Rollback to Render (see ROLLBACK.md)
- [ ] Delete Google Cloud deployment
- [ ] Report issues (contact support)

---

## Troubleshooting

### WebSocket Still Dropping?
- Check timeout setting: `--timeout 3600`
- Verify frontend uses `wss://` (not `ws://`)
- Check CORS_ORIGINS environment variable

### CORS Errors?
```bash
gcloud run services update trade-yantra-api \
  --region us-central1 \
  --set-env-vars CORS_ORIGINS=https://your-frontend.com
```

### Service Offline?
```bash
# Check logs
gcloud run services logs read trade-yantra-api --region us-central1 --limit 50

# Redeploy if needed
cd backend
./deploy-gcp.ps1  # or ./deploy-gcp.sh
```

---

## Success Criteria ✅

**Migration is successful if:**
- ✅ WebSocket stays connected for 30+ minutes
- ✅ Zero dropouts/reconnections
- ✅ Response times < 3 seconds
- ✅ All features work identically to Render
- ✅ **Better stability than Render**

**If all criteria met:** Migration SUCCESS! 🎉
