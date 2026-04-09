import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    toggleLiveTrading,
    getLivePositions,
    getLiveFunds,
    placeLiveOrder,
    updateLiveSettings,
    getSession,
} from '../services/api';
import toast from 'react-hot-toast';

const LiveOrdersTab = ({
    sessionId,
    watchlist,
    liveAutoExec,
    setLiveAutoExec,
    liveTradeQty,
    setLiveTradeQty,
    liveTradeCap,
    setLiveTradeCap
}) => {
    // Internal State
    const [balance, setBalance] = useState(0);
    const [trades, setTrades] = useState([]);
    const [saveLoading, setSaveLoading] = useState(false);
    const [apiError, setApiError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedOrder, setSelectedOrder] = useState(null);

    // Derived Live State using Watchlist Prices
    const processedTrades = trades.map(t => {
        const stock = watchlist.find(s => String(s.token) === String(t.token));
        if (!stock) return t;
        const currentLtp = parseFloat(stock.ltp);
        const qty = parseInt(t.quantity);
        const livePnl = t.side === 'BUY' ? (currentLtp - t.entry_price) * qty : (t.entry_price - currentLtp) * qty;
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

            const mappedPositions = (positions || []).filter(p => parseInt(p.netqty) !== 0).map(p => {
                const netQty = parseInt(p.netqty);
                const isBuy = netQty > 0;
                const entryPrice = parseFloat(p.avgnetprice || (isBuy ? p.buyavgprice : p.sellavgprice));
                return {
                    id: p.symboltoken,
                    symbol: p.tradingsymbol,
                    token: p.symboltoken,
                    side: isBuy ? 'BUY' : 'SELL',
                    quantity: Math.abs(netQty),
                    entry_price: entryPrice,
                    pnl: parseFloat(p.pnl),
                    product: p.producttype,
                    exchange: p.exchange
                };
            });

            setTrades(mappedPositions);
            setBalance(parseFloat(funds?.net || 0));
            
            if (funds?.code === 'AG8001' || funds?.error === 'Session Expired') {
                setApiError('SESSION_EXPIRED');
            } else {
                setApiError(null);
            }
        } catch (err) {
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
            await toggleLiveTrading(sessionId, newState);
            toast.success(`Execution Control: ${newState ? 'ACTIVE' : 'IDLE'}`);
        } catch (err) {
            toast.error('Failed to update execution state');
            setLiveAutoExec(!liveAutoExec);
        }
    };

    const handleSaveSettings = async () => {
        setSaveLoading(true);
        try {
            const q = parseInt(liveTradeQty);
            const c = parseFloat(liveTradeCap);
            if (isNaN(q) || q < 1) { toast.error("Quantity must be at least 1"); return; }
            await updateLiveSettings(sessionId, { trade_quantity: q, trade_capital: c });
            toast.success("Settings Synchronized");
        } catch (e) {
            toast.error("Sync Failed");
        } finally {
            setSaveLoading(false);
        }
    };

    const handleClosePosition = async (trade) => {
        if (!confirm(`Immediate Market Exit for ${trade.symbol}?`)) return;
        try {
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
            toast.success('Exit Order Transmitted');
            setTimeout(fetchLiveData, 1000);
        } catch (e) {
            toast.error('Exit Refused: ' + e.message);
        }
    };

    if (loading && trades.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <div className="w-12 h-12 border-4 border-red-500/20 border-t-red-600 rounded-full animate-spin"></div>
                <p className="text-gray-400 font-medium animate-pulse">Establishing Broker Uplink...</p>
            </div>
        );
    }

    return (
        <div className="w-full max-w-4xl mx-auto space-y-6 pb-32 px-4">
            
            {/* 1. PREMIUM HEADER SECTION */}
            <div className="flex justify-between items-end mt-4 px-1">
                <div>
                    <h1 className="text-2xl font-black text-white tracking-tight">Market Exposure</h1>
                    <p className="text-[10px] text-gray-500 font-bold uppercase tracking-[0.2em]">Institutional Grade Execution</p>
                </div>
                <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-full backdrop-blur-md">
                    <div className={`w-2 h-2 rounded-full ${liveAutoExec ? 'bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-gray-600'}`}></div>
                    <span className="text-[10px] font-black text-white uppercase tracking-wider">
                        {liveAutoExec ? 'Live Engine Active' : 'System Idle'}
                    </span>
                </div>
            </div>

            {/* 2. OVERVIEW CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* BALANCE CARD */}
                <div className="glass-card p-6 rounded-2xl border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent relative group overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-red-600/5 blur-[50px] rounded-full -mr-10 -mt-10 group-hover:bg-red-600/10 transition-all duration-700"></div>
                    <h3 className="text-[10px] text-gray-400 uppercase font-bold tracking-widest mb-4">Available Liquidity</h3>
                    <div className="flex items-baseline gap-2">
                        <span className="text-xl text-gray-400 font-light">₹</span>
                        <span className="text-4xl font-black text-white tabular-nums tracking-tight">{(balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="mt-4 flex items-center gap-2">
                        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-tighter bg-white/5 px-2 py-0.5 rounded">Broker: Angel One</span>
                    </div>
                </div>

                {/* PNL CARD */}
                <div className="glass-card p-6 rounded-2xl border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent">
                    <h3 className="text-[10px] text-gray-400 uppercase font-bold tracking-widest mb-4">Unrealized Performance</h3>
                    <div className={`text-4xl font-black tabular-nums tracking-tight ${liveTotalPnl >= 0 ? 'text-green-400' : 'text-red-500'}`}>
                        {liveTotalPnl >= 0 ? '+' : ''}{liveTotalPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </div>
                    <p className="text-[10px] text-gray-500 mt-4 font-bold uppercase">Real-time valuation</p>
                </div>
            </div>

            {/* 3. SESSION ERROR ALERT */}
            <AnimatePresence>
                {apiError === 'SESSION_EXPIRED' && (
                    <motion.div 
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-red-950/40 border border-red-500/50 p-4 rounded-xl flex items-center justify-between gap-4 backdrop-blur-xl"
                    >
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 bg-red-600 rounded-full flex items-center justify-center text-xl shadow-[0_0_20px_rgba(220,38,38,0.4)]">⚠️</div>
                            <div>
                                <h4 className="text-white text-sm font-black uppercase tracking-wider">Authentication Required</h4>
                                <p className="text-[10px] text-red-300 font-bold uppercase opacity-80">Your secure session has expired. Action needed.</p>
                            </div>
                        </div>
                        <button 
                            onClick={() => window.location.reload()}
                            className="bg-white text-black px-4 py-2 rounded-lg font-black text-[10px] uppercase hover:bg-gray-200 transition-all shadow-xl"
                        >
                            Reconnect
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 4. EXECUTION CONTROL PANEL */}
            <div className="glass-card rounded-2xl border border-white/5 overflow-hidden">
                <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                    <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em]">Execution Control</h3>
                </div>
                <div className="p-6 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <label className="text-[10px] text-gray-500 uppercase font-black block mb-2 tracking-widest">Trade Allocation</label>
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="relative group">
                                        <input
                                            type="number"
                                            className="w-full bg-black/40 border border-white/10 rounded-xl p-3 text-white text-sm font-black focus:outline-none focus:border-red-500/50 transition-all disabled:opacity-30"
                                            value={liveTradeQty}
                                            onChange={(e) => setLiveTradeQty(e.target.value)}
                                            disabled={liveTradeCap > 0}
                                            placeholder="QTY"
                                        />
                                        <span className="absolute right-3 top-3.5 text-[8px] font-black text-gray-600 uppercase">Qty</span>
                                    </div>
                                    <div className="relative group">
                                        <input
                                            type="number"
                                            className="w-full bg-black/40 border border-white/10 rounded-xl p-3 text-white text-sm font-black focus:outline-none focus:border-red-500/50 transition-all"
                                            value={liveTradeCap}
                                            onChange={(e) => setLiveTradeCap(e.target.value)}
                                            placeholder="CAPITAL"
                                        />
                                        <span className="absolute right-3 top-3.5 text-[8px] font-black text-gray-600 uppercase">INR</span>
                                    </div>
                                </div>
                                {liveTradeCap > 0 && <p className="text-[9px] text-yellow-500/70 mt-2 font-bold uppercase italic">Dynamic quantity based on capital allocation</p>}
                            </div>
                            <button
                                onClick={handleSaveSettings}
                                disabled={saveLoading}
                                className="w-full py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl text-[10px] font-black uppercase tracking-[0.2em] transition-all border border-white/10 active:scale-95"
                            >
                                {saveLoading ? 'Synchronizing...' : 'Sychronize Configuration'}
                            </button>
                        </div>

                        <div className="flex flex-col justify-between bg-black/40 p-5 rounded-2xl border border-white/5">
                            <div>
                                <h4 className="text-white text-xs font-black uppercase mb-1 tracking-wider">Master Execution Switch</h4>
                                <p className="text-[10px] text-gray-500 font-medium">When active, the system will execute real market orders based on strategy signals.</p>
                            </div>
                            <button
                                onClick={handleToggleAuto}
                                className={`w-full mt-4 py-4 rounded-xl font-black text-xs uppercase tracking-[0.2em] transition-all relative overflow-hidden group ${liveAutoExec ? 'bg-red-600 text-white shadow-[0_10px_30px_rgba(220,38,38,0.3)]' : 'bg-gray-800 text-gray-500'}`}
                            >
                                <span className="relative z-10">{liveAutoExec ? 'Live Trading Active' : 'Go Live'}</span>
                                {liveAutoExec && (
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_2s_infinite]"></div>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* 5. POSITIONS LIST */}
            <div>
                <div className="flex items-center justify-between px-1 mb-4">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em]">Open Market Exposure</h3>
                    <span className="text-[10px] font-bold text-gray-600 uppercase">{processedTrades.length} Positions</span>
                </div>
                
                <div className="space-y-3">
                    {processedTrades.length === 0 ? (
                        <div className="py-20 text-center border border-white/5 rounded-3xl bg-black/20 flex flex-col items-center justify-center gap-2">
                            <div className="text-4xl opacity-10">📉</div>
                            <p className="text-[10px] text-gray-600 font-black uppercase tracking-widest">No Active Market Exposure</p>
                        </div>
                    ) : (
                        processedTrades.map(trade => (
                            <motion.div 
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                key={trade.id} 
                                onClick={() => setSelectedOrder(trade)} 
                                className="glass-card p-5 rounded-2xl border border-white/5 hover:border-white/10 bg-black/40 cursor-pointer group"
                            >
                                <div className="flex justify-between items-center">
                                    <div className="flex items-center gap-4">
                                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-black text-xs ${trade.side === 'BUY' ? 'bg-green-950/40 text-green-500 border border-green-500/20' : 'bg-red-950/40 text-red-500 border border-red-500/20'}`}>
                                            {trade.side === 'BUY' ? 'LONG' : 'SHRT'}
                                        </div>
                                        <div>
                                            <h4 className="font-black text-lg text-white leading-none mb-1">{trade.symbol}</h4>
                                            <div className="flex items-center gap-3">
                                                <span className="text-[11px] text-gray-400 font-bold tabular-nums">
                                                    {trade.quantity} @ ₹{trade.entry_price.toFixed(2)}
                                                </span>
                                                <span className="w-1 h-1 bg-gray-700 rounded-full"></span>
                                                <span className="text-[10px] text-gray-600 font-bold uppercase tracking-widest">{trade.product}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className={`text-2xl font-black tabular-nums tracking-tighter ${trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                        </div>
                                        <div className="text-[10px] font-bold text-gray-500 uppercase">Live PnL</div>
                                    </div>
                                </div>
                            </motion.div>
                        ))
                    )}
                </div>
            </div>

            {/* 6. MODAL OVERLAY */}
            <AnimatePresence>
                {selectedOrder && (
                    <div className="fixed inset-0 bg-black/90 flex items-center justify-center p-4 z-[100] backdrop-blur-md" onClick={() => setSelectedOrder(null)}>
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0, y: 20 }}
                            animate={{ scale: 1, opacity: 1, y: 0 }}
                            exit={{ scale: 0.95, opacity: 0, y: 20 }}
                            className="bg-zinc-900 w-full max-w-sm rounded-[2rem] p-8 border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)]"
                            onClick={e => e.stopPropagation()}
                        >
                            <div className="flex flex-col items-center text-center mb-8">
                                <div className={`px-4 py-1 rounded-full text-[9px] font-black uppercase mb-3 ${selectedOrder.side === 'BUY' ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                                    {selectedOrder.side === 'BUY' ? 'Long Position' : 'Short Position'}
                                </div>
                                <h2 className="text-4xl font-black text-white tracking-tighter">{selectedOrder.symbol}</h2>
                                <p className="text-gray-500 text-[10px] font-bold uppercase tracking-[0.2em] mt-2">Active Execution</p>
                            </div>

                            <div className="space-y-4 bg-black/40 p-6 rounded-2xl border border-white/5">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="text-gray-500 font-bold uppercase tracking-wider">Entry Avg</span>
                                    <span className="font-black text-white tabular-nums">₹{selectedOrder.entry_price.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between items-center text-xs">
                                    <span className="text-gray-500 font-bold uppercase tracking-wider">Last Price</span>
                                    <span className="font-black text-white tabular-nums">₹{selectedOrder.current_price?.toFixed(2)}</span>
                                </div>
                                <div className="h-px bg-white/5"></div>
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-500 font-black uppercase text-[10px] tracking-widest">Net Realization</span>
                                    <span className={`text-2xl font-black tabular-nums tracking-tighter ${selectedOrder.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                        {selectedOrder.pnl >= 0 ? '+' : ''}{selectedOrder.pnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>

                            <button
                                onClick={() => { handleClosePosition(selectedOrder); setSelectedOrder(null); }}
                                className="w-full py-5 bg-red-600 hover:bg-red-500 text-white rounded-2xl font-black uppercase text-xs tracking-[0.2em] mt-8 shadow-[0_10px_30px_rgba(220,38,38,0.3)] transition-all active:scale-95"
                            >
                                Liquidate Position
                            </button>
                            
                            <button 
                                onClick={() => setSelectedOrder(null)}
                                className="w-full mt-4 py-3 text-gray-500 text-[10px] font-black uppercase tracking-widest hover:text-white transition-all"
                            >
                                Dismiss
                            </button>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default LiveOrdersTab;
