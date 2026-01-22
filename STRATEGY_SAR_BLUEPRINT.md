# Future Strategy: SAR (Stop and Reverse) Breakdown Logic

This document outlines the blueprint for implementing the "Candle-Close Breakdown/Breakout" strategy to be used if the current "Mean Reversion" technique needs an upgrade.

## 1. Core Logic Shift
*   **Current (Mean Reversion)**: Price touches Support -> **BUY** (Expect Bounce).
*   **SAR Strategy (Breakdown)**: 5min/15min Candle Closes **BELOW** Support -> **SELL/SHORT** (Expect Momentum).

## 2. Technical Requirements
### A. Candle Aggregator Service
Create a new `CandleManager` in the backend to:
- Subscribe to the 1-second Tick Stream.
- Aggregate ticks into OHLC (Open, High, Low, Close) buckets.
- Track current candle progress (e.g., "Current 9:15-9:20 candle is at ₹450.20").

### B. Level Scanning Logic
Modify `check_and_trigger_alerts` in `websocket_manager.py`:
- Use the `Close` of the completed candle instead of the raw `ltp`.
- If `Candle.Close < Support_Level`:
    1. Close any existing Long positions.
    2. Open a **SHORT** position.
    3. Find the *next* support level in the `alerts` list to set as the `target_price`.

## 3. Implementation Steps (To be executed upon request)
1. **Frontend**: Add a "Strategy Type" toggle in Dashboard (Bounce vs. Momentum).
2. **Backend**:
    - Implement `CandleService` to store OHLC in memory.
    - Update `PaperService.create_virtual_trade` to handle "Next-Level" target logic.
    - Add a "Candle Timeout" to ensure triggers only happens at the *end* of the time bucket (e.g., at 04m:59s).

## 4. Key Benefit
This strategy avoids "False Touches" where a price briefly spikes through support and then recovers. It ensures we only trade when the market has firmly broken the level.
