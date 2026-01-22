# Progress Checkpoint - 2026-01-20

## ✅ Completed Tasks
1. **Deployment Architecture**
   - Verified `deploy-gcp.ps1` for Google Cloud Run (Backend).
   - Validated Vercel deployment flow for Frontend.
   - **Status**: Ready for production push.

2. **Virtual Balance Persistence**
   - **Issue**: Paper trading balance was resetting on server restart.
   - **Fix**: Added `virtual_balance` column to `UserSession` model in `models.py`.
   - **Status**: Balance is now persistent across restarts.

3. **Auto Square-Off Implementation**
   - **Feature**: Automatically close open positions at end of day.
   - **Implementation**: 
     - Added `check_and_square_off` in `PaperService`.
     - Integrated check into `WebSocketManager` heartbeat loop (runs every 10s).
     - **Trigger Time**: 15:15 IST (3:15 PM).
   - **Status**: Implemented and active.

## 🚧 Pending Tasks (For Next Session)
1. **Indices Cards Optimization**
   - **Issue**: Top 4 index cards (NIFTY 50, BANKNIFTY, etc.) delay the page load and sometimes show negative 100% change.
   - **Cause**: Synchronous loop in `backend/routes/indices.py` blocks the thread; wrong symbol format causes `ltpData` to return 0.
   - **Plan**: 
     - Convert to parallel async fetching or rely purely on WebSocket.
     - Fix symbol mapping for Angel One API.

## 📝 How to Resume
1. **Start Backend**: `cd backend` -> `python -m uvicorn main:app --host 0.0.0.0 --port 8002`
2. **Start Frontend**: `cd frontend` -> `npm run dev`
3. **Verify**: Check if "Virtual Wallet Balance" persists after a backend restart.
