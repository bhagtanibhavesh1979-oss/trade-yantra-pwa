import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    toggleLiveTrading,
    getLivePositions,
    getLiveFunds,
    placeLiveOrder,
    updateLiveSettings,
    getSession,
    API_BASE_URL
} from '../services/api';
import toast from 'react-hot-toast';

const LiveOrdersTab = ({
    clientId,
    sessionId,
    watchlist,
    isPaused,
    liveAutoExec,
    setLiveAutoExec,
    liveTradeQty,
    setLiveTradeQty,
    liveTradeCap,
    setLiveTradeCap
}) => {
    // Internal State
    const [balance, setBalance] = useState(0);
    // REMOVED internal states (autoExec, tradesQty, tradesCap) in favor of props

    const [trades, setTrades] = useState([]);
    const [saveLoading, setSaveLoading] = useState(false);
    const [apiError, setApiError] = useState(null);

    // UI State
    const [loading, setLoading] = useState(true);
    const [selectedOrder, setSelectedOrder] = useState(null);

    // Derived Live State using Watchlist Prices for smooth updates
    const processedTrades = trades.map(t => {
        const stock = watchlist.find(s => String(s.token) === String(t.token));
        if (!stock) return t;

        const currentLtp = parseFloat(stock.ltp);
        const qty = parseInt(t.quantity);
        let livePnl = 0;

        // Angel PnL in position is snapshot. Recalculate based on live LTP for better UX
        // Formula: (LTP - AvgPrice) * Qty * (Side == BUY ? 1 : -1)
        if (t.side === 'BUY') {
            livePnl = (currentLtp - t.entry_price) * qty;
        } else {
            livePnl = (t.entry_price - currentLtp) * qty;
        }

        return { ...t, pnl: livePnl, current_price: currentLtp };
    });

    const liveTotalPnl = processedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);

    const fetchLiveData = async (showLoader = false) => {
        const sid = sessionId || getSession()?.sessionId;
        if (!sid) return;

        if (showLoader) setLoading(true);
        try {
            const [positions, funds] = await Promise.all([
                getLivePositions(sid),
                getLiveFunds(sid)
            ]);

            // Map Angel Positions to UI Format
            // Angel returns all positions (including squared off ones with netqty=0)
            const mappedPositions = (positions || []).filter(p => parseInt(p.netqty) !== 0).map(p => {
                const netQty = parseInt(p.netqty);
                const isBuy = netQty > 0;
                // For Net Position, Entry Price is usually BuyAvg for Long, SellAvg for Short?
                // Angel API provides 'avgnetprice' which is weighted.
                // Let's use 'avgnetprice' or fallback to buyavg/sellavg
                const entryPrice = parseFloat(p.avgnetprice || (isBuy ? p.buyavgprice : p.sellavgprice));

                return {
                    id: p.symboltoken,
                    symbol: p.tradingsymbol,
                    token: p.symboltoken,
                    side: isBuy ? 'BUY' : 'SELL',
                    quantity: Math.abs(netQty),
                    entry_price: entryPrice,
                    pnl: parseFloat(p.pnl), // Snapshot PnL
                    product: p.producttype,
                    exchange: p.exchange
                };
            });

            setTrades(mappedPositions);
            setBalance(parseFloat(funds?.net || 0));
            
            if (funds?.error || (Array.isArray(positions) && positions.length === 0 && funds?.net === 0)) {
                // If backend explicitly says session expired
                if (funds?.code === 'AG8001' || funds?.error === 'Session Expired') {
                    setApiError('SESSION_EXPIRED');
                } else if (funds?.error) {
                    setApiError(funds.error);
                } else {
                    setApiError(null);
                }
            } else {
                setApiError(null);
            }

        } catch (err) {
            console.error('Failed to fetch live data:', err);
            setApiError('CONNECTION_ERROR');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLiveData(true);
        const interval = setInterval(() => fetchLiveData(false), 5000);
        return () => clearInterval(interval);
    }, [sessionId]);

    const handleToggleAuto = async () => {
        if (!liveAutoExec && !confirm("⚠️ DANGER: Enable REAL MONEY Auto-Trading?")) return;

        try {
            const newState = !liveAutoExec;
            setLiveAutoExec(newState);
            // We assume toggleLiveTrading returns updated status
            await toggleLiveTrading(sessionId, newState);
            toast.success(`LIVE Auto-Trading ${newState ? 'ENABLED' : 'DISABLED'}`);
        } catch (err) {
            toast.error('Failed to toggle live trading');
            setLiveAutoExec(!liveAutoExec); // Revert on failure
        }
    };

    const handleSaveSettings = async () => {
        setSaveLoading(true);
        try {
            // Validate inputs
            const q = parseInt(liveTradeQty);
            const c = parseFloat(liveTradeCap);
            if (isNaN(q) || q < 1) { toast.error("Quantity must be at least 1"); return; }
            if (isNaN(c) || c < 0) { toast.error("Capital cannot be negative"); return; }

            const res = await updateLiveSettings(sessionId, {
                trade_quantity: q,
                trade_capital: c
            });

            toast.success("Settings Saved!");
        } catch (e) {
            toast.error("Failed to save settings");
            console.error(e);
        } finally {
            setSaveLoading(false);
        }
    };

    const handleClosePosition = async (trade) => {
        if (!confirm(`Exiting ${trade.symbol}. Confirm?`)) return;

        try {
            // Place Counter Order
            const order = {
                symbol: trade.symbol,
                token: trade.token,
                exch_seg: trade.exchange || "NSE",
                side: trade.side === "BUY" ? "SELL" : "BUY",
                quantity: trade.quantity,
                product_type: trade.product || "INTRADAY",
                order_type: "MARKET",
                price: 0
            };

            await placeLiveOrder(sessionId, order);
            toast.success('Exit Order Placed');
            // Optimistic update or wait for refresh
            setTimeout(fetchLiveData, 1000);
        } catch (e) {
            toast.error('Exit Failed: ' + e.message);
        }
    };

    if (loading && trades.length === 0) {
        return <div className="p-10 text-center text-red-500 animate-pulse font-bold">Connecting to Exchange...</div>;
    }

    return (
        <div className="w-full space-y-4 pb-24 px-4 overflow-x-hidden border-t-4 border-red-600 bg-red-950/10 min-h-screen">
            <div className="bg-red-600/20 border border-red-500/50 p-2 text-center rounded-b-xl mb-4">
                <h2 className="text-red-500 font-black tracking-widest uppercase text-xs animate-pulse">🔴 LIVE TRADING ENVIRONMENT - REAL MONEY</h2>
            </div>
            
            {/* API ERROR ALERT */}
            <AnimatePresence>
                {apiError === 'SESSION_EXPIRED' && (
                    <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        className="bg-red-600 text-white p-4 rounded-xl shadow-lg border-2 border-white/20 mb-4 overflow-hidden"
                    >
                        <div className="flex items-center gap-4">
                            <span className="text-3xl">⚠️</span>
                            <div className="flex-1">
                                <h4 className="font-black text-sm uppercase">Angel One Session Expired</h4>
                                <p className="text-[10px] font-bold opacity-90">Your broker connection has timed out. Automated trades will NOT execute until you re-login.</p>
                            </div>
                            <button 
                                onClick={() => window.location.reload()}
                                className="bg-white text-red-600 px-4 py-2 rounded-lg font-black text-[10px] uppercase shadow-md active:scale-95 transition-all"
                            >
                                Re-Login Now
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 1. FUNDS & PNL */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-5 rounded-xl border border-red-500/30 shadow-[0_0_30px_rgba(220,38,38,0.1)] relative overflow-hidden">
                    <div className="relative z-10 flex justify-between items-center">
                        <div>
                            <h3 className="text-[10px] text-red-400 uppercase font-bold tracking-widest mb-1">Real Funds</h3>
                            <div className="text-white flex items-baseline gap-1">
                                <span className="text-lg">₹</span>
                                <span className="text-4xl font-black tabular-nums">{(balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="glass-card p-5 rounded-xl border border-red-500/30 flex items-center justify-around">
                    <div className="text-center">
                        <div className="text-[10px] text-red-400 uppercase mb-1">Real PnL</div>
                        <div className={`text-2xl font-black ${liveTotalPnl >= 0 ? 'text-green-400' : 'text-red-500'}`}>
                            {liveTotalPnl >= 0 ? '+' : ''}{liveTotalPnl.toFixed(2)}
                        </div>
                    </div>
                </div>
            </div>

            {/* 2. LIVE SETTINGS & CONTROLS */}
            <h3 className="text-xs font-bold text-red-400 uppercase px-1 mt-4 tracking-widest">Execution Settings</h3>
            <div className="glass-card p-4 rounded-xl border border-red-500/30 mb-4 space-y-4">

                {/* SETTINGS FORM */}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Fixed Quantity</label>
                        <input
                            type="number"
                            className="w-full bg-black/30 border border-gray-700 rounded p-2 text-white text-sm font-bold disabled:opacity-50"
                            value={liveTradeQty}
                            onChange={(e) => setLiveTradeQty(e.target.value)}
                            disabled={liveTradeCap > 0}
                            placeholder="100"
                        />
                        {liveTradeCap > 0 && <p className="text-[9px] text-yellow-500 mt-1">Disabled (Using Capital)</p>}
                    </div>
                    <div>
                        <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Max Capital (₹) <span className="text-[9px] text-green-500">Auto-Calc Qty</span></label>
                        <input
                            type="number"
                            className="w-full bg-black/30 border border-gray-700 rounded p-2 text-white text-sm font-bold"
                            value={liveTradeCap}
                            onChange={(e) => setLiveTradeCap(e.target.value)}
                            placeholder="0 (Disabled)"
                        />
                    </div>
                </div>

                <button
                    onClick={handleSaveSettings}
                    disabled={saveLoading}
                    className="w-full py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-bold text-gray-300 transition-all border border-gray-700"
                >
                    {saveLoading ? 'Saving...' : 'SAVE SETTINGS'}
                </button>

                <div className="h-px bg-red-500/20 my-2"></div>

                {/* MASTER SWITCH */}
                <div className="flex justify-between items-center gap-4">
                    <div className="flex-1">
                        <h3 className="text-xs font-bold text-white mb-1">Master Kill Switch</h3>
                        <p className="text-[10px] text-gray-400">Controls all automated live execution</p>
                    </div>
                    <button
                        onClick={handleToggleAuto}
                        className={`px-8 py-3 rounded-xl font-black text-xs uppercase tracking-wider transition-all shadow-lg ${liveAutoExec ? 'bg-red-600 text-white animate-pulse' : 'bg-gray-800 text-gray-500 border border-gray-700'}`}
                    >
                        {liveAutoExec ? '🔴 LIVE EXECUTION ON' : 'STOPPED'}
                    </button>
                </div>
            </div>

            {/* 3. POSITIONS */}
            <h3 className="text-xs font-bold text-red-400 uppercase px-1 mt-6 tracking-widest">Open Market Positions</h3>
            <div className="space-y-3">
                {processedTrades.length === 0 ? (
                    <div className="py-12 text-center border-2 border-dashed border-red-500/20 rounded-2xl text-red-400/50 text-sm font-bold">
                        NO OPEN POSITIONS
                    </div>
                ) : (
                    processedTrades.map(trade => (
                        <div key={trade.id} onClick={() => setSelectedOrder(trade)} className="bg-black/40 backdrop-blur-md p-4 rounded-xl border-l-4 border-l-red-500 border border-white/5 shadow-lg cursor-pointer">
                            <div className="flex justify-between items-center">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-black text-lg text-white">{trade.symbol}</span>
                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${trade.side === 'BUY' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'}`}>{trade.side}</span>
                                        <span className="text-[9px] font-bold text-gray-500 border border-gray-700 px-1 rounded">{trade.product}</span>
                                    </div>
                                    <div className="text-[11px] text-gray-400">
                                        {trade.quantity} Qty @ {trade.entry_price.toFixed(2)} → {trade.current_price?.toFixed(2)}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className={`text-xl font-black tabular-nums ${trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* MODAL */}
            <AnimatePresence>
                {selectedOrder && (
                    <div className="fixed inset-0 bg-black/95 flex items-center justify-center p-4 z-[100] backdrop-blur-sm" onClick={() => setSelectedOrder(null)}>
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className="bg-gray-900 w-full max-w-sm rounded-3xl p-6 border border-red-500/30 shadow-[0_0_50px_rgba(220,38,38,0.2)]"
                            onClick={e => e.stopPropagation()}
                        >
                            <h2 className="text-2xl font-black text-white mb-2">{selectedOrder.symbol}</h2>
                            <div className="space-y-4">
                                <div className="flex justify-between text-sm">
                                    <span className="text-gray-400">Entry</span>
                                    <span className="font-bold text-white">₹{selectedOrder.entry_price.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-gray-400">Current</span>
                                    <span className="font-bold text-white">₹{selectedOrder.current_price?.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-lg border-t border-white/10 pt-2">
                                    <span className="text-gray-400 font-bold">PnL</span>
                                    <span className={`font-black ${selectedOrder.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                        {selectedOrder.pnl >= 0 ? '+' : ''}{selectedOrder.pnl.toFixed(2)}
                                    </span>
                                </div>

                                <button
                                    onClick={() => { handleClosePosition(selectedOrder); setSelectedOrder(null); }}
                                    className="w-full py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-black uppercase text-sm mt-4 shadow-lg shadow-red-600/30"
                                >
                                    SQUARE OFF (MARKET)
                                </button>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default LiveOrdersTab;
