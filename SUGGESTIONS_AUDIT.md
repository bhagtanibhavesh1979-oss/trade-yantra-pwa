# Trade Yantra: Brutal Honest Suggestions & Project Audit
**Generated on: 2026-01-23 02:45 AM IST**

This document tracks the "no-nonsense" technical and product improvements required to turn Trade Yantra into a professional-grade execution platform.

## 🔴 CRITICAL (Immediate Review Needed)

| Suggestion | Status | Why it's brutal |
| :--- | :--- | :--- |
| **Kill Localhost Data Overwrite** | ✅ FIXED | Before today, if your server crashed, your entire local watchlist/trades were deleted by the code. Absolute amateur hour. Now it preserves local state if fetch fails. |
| **Fix Broken Backend Logic** | ✅ FIXED | Alert generation was failing with `NameError`. You can't run a strategy if the math is wrong. Fixed the `async` loop and duplicate tracking. |
| **Sanitize Paper Trading PnL** | ⏳ PENDING | Current PnL calculation relies on the frontend staying active. If the tab is closed, the PnL might "freeze" until reopened. Need a backend worker for background PnL sync. |
| **WebSocket Resilience** | ⚠️ PARTIAL | The "Red Dot" tonight proved that we need better UI messaging for "Market Closed" vs "Connection Error". |

## 🟡 HIGH PRIORITY (Performance & Stability)

| Suggestion | Status | Why it's brutal |
| :--- | :--- | :--- |
| **Scrip Master Bloat** | ⏳ PENDING | The `scripmaster.json` is huge. Loading it on every startup is slow. Need to move to a SQLite cache or Redis for instant search. |
| **Charting Experience** | ⚠️ PARTIAL | The localhost restriction on charts is a pain. The current "Click-to-Pro-Chart" is a band-aid; real fix is deploying to the live domain. |
| **Strategy Execution Latency** | ⏳ PENDING | Ticks are processed in Python. For high-speed SAR strategies, we need to ensure the processing loop stays under 50ms. |

## 🟢 PRODUCT & UX (Wowed User)

| Suggestion | Status | Why it's brutal |
| :--- | :--- | :--- |
| **The "SAR" Switch** | 📜 PLANNED | The blueprint exists. We need a one-button toggle between "Reversion" (Bounce) and "Breakout" (Momentum). |
| **Daily PnL Reporting** | ⏳ PENDING | Traders need to see a "Daily Equity Curve", not just a list of trades. Need an "Overview" chart for the Trades tab. |
| **Bulk Management** | ✅ FIXED | Added "Delete Selected" and "Clear All" with better UI feedback. Management is now fast. |

---

## 🛠️ THE ARCHITECT'S FINAL WORD
The app is currently a **"Reactive"** tool (it reacts to price). To be a **"Pro"** tool, it must become **"Predictive"** (Candle Analysis) and **"Persistent"** (Background Workers). 

**Next Session Goal:** Implement the **SAR Candle Aggregator** to stop trading on "shaky" raw ticks and start trading on "confirmed" candle closes.
