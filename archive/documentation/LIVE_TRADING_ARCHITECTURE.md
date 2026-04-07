# Live Trading Architecture (Implemented)

## 1. Overview
The Live Trading system runs parallel to the Paper Trading engine, utilizing the same strategy logic but executing real orders via the Angel One SmartAPI. It features a strict "Red Zone" UI to distinguish it from the simulation environment and includes a robust "Risk Service" layer to prevent accidental wealth destruction.

## 2. Key Components

### A. Frontend (Red Zone)
- **Component**: `LiveOrdersTab.jsx`
- **Route**: New tab in Dashboard (`activeTab === 'live_orders'`)
- **UI Theme**: 
    - Red Borders/Backgrounds
    - "Master Kill Switch" (Toggle Button)
    - Real "Available Margin" display (Not Virtual Balance)
    - Live PnL from Angel One positions

### B. Backend Services
1. **`LiveService`** (`services/live_service.py`)
    - Handles `place_order`, `get_positions`, `get_funds`.
    - Manages the "Master Live Switch" (Global variable `LIVE_ENABLED` acts as a hard server-side gate).
    - Normalizes product types (MIS/Intraday).

2. **`RiskService`** (`services/risk_service.py`)
    - **Kill Switch**: Checks `session.auto_live_trade` flag.
    - **Margin Check**: Pre-calculates required margin before placing order.
    - **Quantity Limit**: (Future) Max quantity per trade.

3. **`SessionManager`** (`services/session_manager.py`)
    - Extended `Session` model with `auto_live_trade` (bool).
    - Persists this state to disk/GCS.

### C. Execution Logic (`websocket_manager.py`)
- **Hybrid Engine**: The `_process_candle_trades` loop now checks **both** Paper and Live flags.
- **Fail-Safe**: Added explicit Stop-Loss/Target checks for open trades every 15 minutes to catch "missed" signals.
- **Routing**:
    - **Paper**: Calls `paper_service.create_virtual_trade`
    - **Live**: Calls `live_service.place_live_order` (Wrapped in Risk Checks)

## 3. Safety Mechanisms
1. **Double Confirmation**: User must confirm "Enable Real Money Trading" with a browser prompt.
2. **Server-Side Gate**: Even if UI sends a request, `LiveService` checks `LIVE_ENABLED` (Master Switch).
3. **Margin Protection**: Orders are rejected locally if funds are insufficient, preventing broker rejection errors.
4. **SL Enforcement**: Hard Stop-Loss check added to the strategy loop.

## 4. Workflows

### Auto-Trading (Live)
1. User generates Alerts (Levels).
2. User toggles "GO LIVE" in Live Tab.
3. System monitors 15m candles.
4. Signal Triggered (e.g. SAR Buy).
5. `RiskService` checks Margin & Kill Switch.
6. `LiveService` places Order.
7. Order appears in "Live Positions".

### Manual Trading (Live)
1. User clicks "Square Off" in Live Tab.
2. `placeLiveOrder` API called with opposite side.
3. Market Order executes immediately.

## 5. Deployment
- **Backend**: Python FastAPI (Google Cloud Run)
- **Frontend**: React/Vite PWA (Vercel)
- **Database**: JSON/GCS Persistence

## 6. Future Improvements
- [ ] Sync "Auto-Live" state with "Auto-Paper" state if desired (Unified Toggle).
- [ ] Add "Max Daily Loss" hard stop triggered by `LiveService`.
- [ ] Implement "Trailing Stop Loss" in `RiskService`.
