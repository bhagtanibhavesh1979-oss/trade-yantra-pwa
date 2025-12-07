# Trade Yantra - Testing Guide

## Backend Testing

### 1. Start Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8002
```

Verify server is running:
- Open `http://localhost:8002` - should show API info
- Open `http://localhost:8002/docs` - Swagger UI
- Open `http://localhost:8002/health` - Health check

### 2. Test Endpoints (Optional)

Using Swagger UI at `http://localhost:8002/docs`, test:
1. **POST /api/auth/login** - Enter your Angel One credentials
2. Copy the `session_id` from response
3. **GET /api/watchlist/{session_id}** - Should return empty watchlist
4. **GET /api/alerts/{session_id}** - Should return empty alerts

---

## Frontend Testing

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Backend URL

Create `.env.local` file in `frontend/` directory:

```env
VITE_API_URL=http://localhost:8002
```

> **Note:** `.env.local` is gitignored. You need to create this file manually for local development.

### 3. Start Frontend

```bash
npm run dev
```

Open `http://localhost:5173`

### 4. Test Login Flow

1. Enter your Angel One credentials:
   - SmartAPI Key
   - Client ID
   - Password
   - TOTP Secret

2. Click "Login"

3. Should redirect to Dashboard

### 5. Test Watchlist

1. Click in search box
2. Type "TATA" or "RELIANCE"
3. Click on a result to add stock
4. Stock should appear in watchlist with LTP initially 0.00
5. Click "Refresh" button
6. LTP should update from backend

### 6. Test WebSocket

1. Open browser DevTools → Console
2. Look for "WebSocket connected" message
3. Watch for price updates in console (if market is open)
4. LTP should auto-update in UI

### 7. Test Filters & Sorting

1. Add multiple stocks to watchlist
2. Try filtering by symbol name
3. Try min/max price filters
4. Try different sort options (A-Z, price low/high)

### 8. Test Alerts

1. Navigate to Alerts tab
2. Click "Generate Levels" button
3. Alerts should appear (3-6-9 levels)
4. Try deleting an alert
5. Toggle "Pause Monitoring"

### 9. Test Logs

1. Navigate to Logs tab
2. Should show "Generated X alerts" message
3. If an alert triggers (price crosses threshold), it appears here

---

## Common Issues

### Backend not accessible
- Check backend is running on port 8002
- Check for port conflicts: `netstat -ano | findstr :8002`

### Frontend can't connect to backend
- Verify `.env.local` has correct VITE_API_URL
- Check browser console for CORS errors
- Restart frontend dev server after changing `.env.local`

### WebSocket not connecting
- Check browser console for WebSocket errors
- Verify session_id is valid
- Check backend logs for WebSocket connection attempts

### Prices not updating
- Check if market is open (9:15 AM - 3:30 PM IST, Mon-Fri)
- Verify WebSocket status shows "Live" (green dot)
- Check backend logs for Angel One API errors
