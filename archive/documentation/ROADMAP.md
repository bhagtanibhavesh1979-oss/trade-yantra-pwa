# Trade Yantra Project Roadmap 🚀

This document tracks the long-term vision and upcoming features for the Trade Yantra platform.

## Phase 1: Stock Trading Stability & UI (CURRENT)
- [x] **Dhan-Inspired UI**: High-density, professional, and edge-to-edge layout for mobile.
- [x] **Stock Backtesting**: Blueprint-based SAR & Bounce strategy testing.
- [x] **Virtual Trading (Paper)**: Real-time execution of stock trades with a virtual balance.
- [ ] **Verification**: Ensure virtual results match manual backtesting/simulation 100%.
- [ ] **Real Execution**: Transition to live trading with stocks once verification is complete.

## Phase 2: Index Options Integration (NEXT)
The "Adventure" phase – extending the platform to handle NIFTY/BANKNIFTY options logic.

### 🎯 Objective
Add a dedicated Options module that leverages the existing "Blueprint" (S6-R6) engine but applies it to Option premiums.

### 🛠️ Strategy (The Modular Approach)
- **Shared Core**: Use the same WebSocket streaming and Level Calculation logic used for stocks.
- **Dedicated UI**: Add an "Options" tab or "Option Chain" view in the current app (avoiding project clones).
- **Phased Rollout**: Build as a "Beta Module" that can be toggled on for testing without affecting Stock trading stability.

### 🧪 Technical Requirements
1. **Option Chain Data**: Integrate Angel One's Option Chain API to fetch real-time strikes.
2. **Expiry Management**: Logic to automatically detect the current-week/near-week expiry contracts.
3. **Lot Sizes**: Update the execution engine to handle lot-based quantities (e.g., NIFTY 50/75) instead of single shares.
4. **The Greeks (Optional)**: Visualize Delta/Theta for advanced entry/exit filtering.

### 📊 Verification Flow
1. **Observation**: Watch Option Premium movements against Blueprint levels.
2. **Virtual Trading**: Run the "SAR" strategy on Index Options using virtual money.
3. **Refinement**: Adjust the "Buffer %" – premiums often move faster/volatilely compared to underlying stocks.

## Phase 3: Advanced Automation & Scale
- **Multi-Strategy Mode**: Run "Bounce" on some stocks and "SAR" on others simultaneously.
- **Detailed Analytics**: Profit/Loss Heatmaps and Trade-by-Trade Performance attribution.
- **Telegram/Push Alerts**: Real-time notifications when major levels are broken.

---
*Roadmap created: 2026-01-31*
*Next Sync: Stock Verification & Simulation matching.*
