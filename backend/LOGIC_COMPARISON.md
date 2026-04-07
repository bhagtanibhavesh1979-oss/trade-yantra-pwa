# Logic Parity Reference (Lab vs Paper/Live)

This document records the exact logic verification performed on 2026-03-10 to ensure the Paper and Live trading systems perfectly match the Lab (Backtest) results.

## 1. SAR Trap / Rejection Logic
Verified against Havells trade on 03-10 (First Trade):
- **Level (High)**: 1383.60
- **Buffer (0.45%)**: 6.2262 (Buffer Calculation: `Level * 0.0045`)
- **Trap Mark (Sell Trigger)**: `1383.60 - 6.2262 = 1377.3738`
- **Logic Output (Tick Rounded)**: **1377.35**
- **Lab Match**: Confirmed. Lab's **OUT** price was exactly 1377.35.

### Implementation Rule
The system now uses the following for all TRAP/REJECTION reversals:
- **BUY -> SELL (Trap)**: Exit at `Level - (Level * Buffer%)`, rounded to 0.05.
- **SELL -> BUY (Trap)**: Exit at `Level + (Level * Buffer%)`, rounded to 0.05.

## 2. 9:30 AM Opening Candle
- **Reference Price**: At 9:30 AM, the `prev_close_ref` is strictly set to the **9:15 AM Open price**.
- **Execution Type**: Level-based (Instant entry if 9:30 Close is above/below the level), matching Lab.

## 3. Data Synchronization
- **Trigger Offset**: Checks run at **HH:MM:10** to allow broker data to finalize.
- **Targeted Fetch**: Specifically searches for the "09:15" candle in raw API data to avoid using partial current candles.
- **Catch-up Window**: 15 minutes (to handle late server starts).

## 4. Pending (Deferred) Parity Adjustments
The following items are identified but not yet implemented (awaiting user approval after 9:30 AM verification):
- **SL/TGT Base Price**: Use theoretical entry (e.g., Level price) instead of Market Close as the starting point for SL/TGT.
- **Intra-candle High/Low Hits**: Check for SL/TGT using High/Low instead of Close-only.
