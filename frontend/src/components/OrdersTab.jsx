import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getPaperSummary, togglePaperTrading, setStrategyMode, setBufferPct, closePaperTrade, clearPaperTrades, setVirtualBalance, setStopLoss, setTarget, getPaperAnalytics, getSession, setTriggerMode, squareOffPositions, API_BASE_URL } from '../services/api';
import toast from 'react-hot-toast';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

const OrdersTab = ({
    clientId,
    sessionId,
    watchlist,
    isPaused
}) => {
    // Internal State
    const [balance, setBalance] = useState(0);
    const [autoExec, setAutoExec] = useState(false);
    const [trades, setTrades] = useState([]);
    const [analytics, setAnalytics] = useState(null);
    const [strategyMode, setInternalStrategyMode] = useState('BOUNCE');
    const [triggerMode, setInternalTriggerMode] = useState('CANDLE_CLOSE');
    const [bufferPct, setInternalBufferPct] = useState(0.25);

    // UI State
    const [loading, setLoading] = useState(true);
    const [isAddingMoney, setIsAddingMoney] = useState(false);
    const [addAmount, setAddAmount] = useState('');
    const [slInputs, setSlInputs] = useState({});
    const [targetInputs, setTargetInputs] = useState({});
    const [selectedOrder, setSelectedOrder] = useState(null);

    // Derived State
    const processedTrades = trades.map(t => {
        if (t.status === 'CLOSED') return t;
        const stock = watchlist.find(s => String(s.token) === String(t.token));
        if (!stock) return t;
        const currentLtp = parseFloat(stock.ltp);
        const entry = parseFloat(t.entry_price);
        const qty = parseInt(t.quantity);
        let livePnl = t.pnl;
        if (t.side === 'BUY') {
            livePnl = (currentLtp - entry) * qty;
        } else {
            livePnl = (entry - currentLtp) * qty;
        }
        return { ...t, pnl: livePnl, current_price: currentLtp };
    });

    const openTrades = processedTrades.filter(t => t.status === 'OPEN');
    const closedTrades = processedTrades.filter(t => t.status === 'CLOSED');
    const liveTotalPnl = processedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);

    const fetchOrdersData = async (showLoader = false) => {
        const sid = sessionId || getSession()?.sessionId;
        if (!sid) return;
        if (showLoader) setLoading(true);
        try {
            const [summaryData, analyticsData] = await Promise.all([
                getPaperSummary(sid, clientId),
                getPaperAnalytics(sid).catch(() => null)
            ]);
            if (summaryData) {
                setBalance(summaryData.virtual_balance);
                setAutoExec(summaryData.auto_paper_trade);
                setTrades(summaryData.trades || []);
                setInternalStrategyMode(summaryData.strategy_mode || 'BOUNCE');
                setInternalTriggerMode(summaryData.trigger_mode || 'CANDLE_CLOSE');
                setInternalBufferPct(summaryData.buffer_pct || 0.25);
            }
            if (analyticsData) setAnalytics(analyticsData);
        } catch (err) {
            console.error('Failed to fetch orders data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOrdersData(true);
        const interval = setInterval(() => fetchOrdersData(false), 5000);
        return () => clearInterval(interval);
    }, [sessionId]);

    const handleToggleAuto = async () => {
        try {
            const newState = !autoExec;
            setAutoExec(newState);
            await togglePaperTrading(sessionId, newState, clientId);
            toast.success(`Automated Trading ${newState ? 'ON' : 'OFF'}`);
        } catch (err) {
            toast.error('Failed to toggle trading');
            setAutoExec(!autoExec);
        }
    };

    const handleStrategyChange = async (mode) => {
        try {
            setInternalStrategyMode(mode);
            await setStrategyMode(sessionId, mode, clientId);
            toast.success(`Strategy: ${mode}`);
        } catch (err) {
            toast.error('Failed to change strategy');
        }
    };

    const handleTriggerModeChange = async (mode) => {
        try {
            setInternalTriggerMode(mode);
            await setTriggerMode(sessionId, mode, clientId);
            toast.success(`Mode: ${mode === 'INSTANT' ? 'Instant' : '15m Candle'}`);
        } catch (err) {
            toast.error('Failed to change trigger mode');
        }
    };

    const handleBufferChange = async (val) => {
        try {
            setInternalBufferPct(val);
            await setBufferPct(sessionId, val, clientId);
            toast.success(`Buffer: ${val}%`);
        } catch (err) {
            toast.error('Failed to update buffer');
        }
    };

    const handleUpdateBalance = async (type) => {
        try {
            const amount = parseFloat(addAmount);
            if (isNaN(amount)) return;
            const newBalance = type === 'ADD' ? balance + amount : amount;
            setBalance(newBalance);
            await setVirtualBalance(sessionId, newBalance, clientId);
            setAddAmount('');
            setIsAddingMoney(false);
            toast.success('Balance Updated');
        } catch (err) {
            toast.error('Failed to update balance');
        }
    };

    const handleSquareOff = async () => {
        if (!confirm("Close all open positions?")) return;
        try {
            await squareOffPositions(sessionId);
            toast.success('All positions squared off');
            fetchOrdersData();
        } catch (e) { toast.error('Square off failed'); }
    };

    const handleExport = () => {
        const url = `${API_BASE_URL}/api/paper/export/${sessionId}`;
        window.open(url, '_blank');
        toast.success('Downloading trade report...');
    };

    const handleSetStopLoss = async (trade) => {
        const slVal = slInputs[trade.id];
        if (!slVal) return;
        try {
            await setStopLoss(sessionId, trade.id, parseFloat(slVal));
            toast.success('SL Updated');
            setSlInputs(prev => ({ ...prev, [trade.id]: '' }));
            fetchOrdersData();
        } catch (e) { toast.error('Failed to set SL'); }
    };

    const handleSetTarget = async (trade) => {
        const tgtVal = targetInputs[trade.id];
        if (!tgtVal) return;
        try {
            await setTarget(sessionId, trade.id, parseFloat(tgtVal));
            toast.success('Target Updated');
            setTargetInputs(prev => ({ ...prev, [trade.id]: '' }));
            fetchOrdersData();
        } catch (e) { toast.error('Failed to set Target'); }
    };

    const handleCloseTrade = async (trade) => {
        try {
            const stock = watchlist.find(s => String(s.token) === String(trade.token));
            const ltp = stock ? stock.ltp : trade.entry_price;
            await closePaperTrade(sessionId, trade.id, ltp);
            toast.success('Trade Closed');
            fetchOrdersData();
        } catch (e) { toast.error('Close failed'); }
    };

    const handleClearHistory = async () => {
        if (confirm("Clear all history?")) {
            await clearPaperTrades(sessionId);
            fetchOrdersData();
        }
    };

    if (loading && !balance && trades.length === 0) {
        return <div className="p-10 text-center text-gray-500 animate-pulse">Loading Orders System...</div>;
    }

    return (
        <div className="w-full space-y-2 md:space-y-4 pb-24 px-0 md:px-4 overflow-x-hidden">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-4">
                <div className="glass-card p-3 md:p-5 rounded-xl border border-[var(--border-color)] shadow-xl relative overflow-hidden">
                    <div className="relative z-10 flex justify-between items-center">
                        <div className="flex flex-col">
                            <h3 className="text-[9px] text-[var(--text-muted)] uppercase font-bold tracking-widest mb-0.5">Available Margin</h3>
                            <div className="text-[var(--text-primary)] flex items-baseline gap-1">
                                <span className="text-lg">₹</span>
                                <span className="text-4xl font-black tabular-nums">{(balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                            </div>
                        </div>
                        <button onClick={() => setIsAddingMoney(!isAddingMoney)} className="p-2 rounded-xl bg-[var(--bg-secondary)] hover:bg-[var(--accent-blue)] transition-all">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 6v6m0 0v6m0-6h6m-6 0H6" strokeWidth={2} strokeLinecap="round" /></svg>
                        </button>
                    </div>
                    {isAddingMoney && (
                        <div className="mt-3 pt-3 border-t border-white/5 flex flex-col gap-2">
                            <input type="number" placeholder="Amount" value={addAmount} onChange={e => setAddAmount(e.target.value)} className="bg-[var(--bg-primary)] border border-white/10 rounded-xl px-3 py-2 text-xs" />
                            <div className="flex gap-2">
                                <button onClick={() => handleUpdateBalance('ADD')} className="flex-1 bg-white/5 py-2 text-[10px] font-bold rounded-lg border border-white/10">(+) ADD</button>
                                <button onClick={() => handleUpdateBalance('SET')} className="flex-1 bg-[var(--accent-blue)] py-2 text-[10px] font-bold rounded-lg shadow-lg">SET BALANCE (=)</button>
                            </div>
                        </div>
                    )}
                </div>

                <div className="glass-card p-3 md:p-6 rounded-xl border border-[var(--border-color)] flex items-center justify-around">
                    <div className="text-center">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">PnL Today</div>
                        <div className={`text-xl font-black ${liveTotalPnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                            {liveTotalPnl >= 0 ? '+' : ''}{liveTotalPnl.toFixed(0)}
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase mb-1">Win Rate</div>
                        <div className="text-xl font-black text-[var(--accent-blue)]">{analytics?.stats?.win_rate || 0}%</div>
                    </div>
                </div>
            </div>

            <div className="glass-card p-4 rounded-xl border border-[var(--border-color)]">
                <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                    <button onClick={handleToggleAuto} className={`w-full md:w-auto px-8 py-3 rounded-xl font-black text-xs uppercase tracking-wider transition-all ${autoExec ? 'bg-[var(--success-neon)] text-white' : 'bg-[var(--bg-secondary)] text-[var(--text-muted)]'}`}>
                        {autoExec ? 'System Active' : 'System Offline'}
                    </button>

                    <div className="flex flex-wrap gap-2">
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl">
                            {['BOUNCE', 'SAR'].map(m => (
                                <button key={m} onClick={() => handleStrategyChange(m)} className={`px-4 py-1.5 rounded-lg text-[10px] font-bold ${strategyMode === m ? 'bg-[var(--accent-blue)] text-white' : 'text-[var(--text-muted)]'}`}>
                                    {m === 'BOUNCE' ? 'Reversal' : 'Momentum'}
                                </button>
                            ))}
                        </div>
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl">
                            {['CANDLE_CLOSE', 'INSTANT'].map(m => (
                                <button key={m} onClick={() => handleTriggerModeChange(m)} className={`px-4 py-1.5 rounded-lg text-[10px] font-bold ${triggerMode === m ? 'bg-orange-500 text-white' : 'text-[var(--text-muted)]'}`}>
                                    {m === 'CANDLE_CLOSE' ? '15m Candle' : 'Instant'}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="mt-4 flex flex-col gap-1">
                    <div className="text-[8px] uppercase tracking-tighter text-yellow-500 font-bold ml-1">Sensitivity Buffer</div>
                    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
                        {[0.10, 0.15, 0.25, 0.45, 0.50, 0.63, 0.72, 0.81, 0.90].map(b => (
                            <button key={b} onClick={() => handleBufferChange(b)} className={`px-4 py-2 rounded-lg text-[11px] font-bold flex-shrink-0 ${Number(bufferPct || 0.45).toFixed(2) === b.toFixed(2) ? 'bg-yellow-500 text-black' : 'bg-white/5 text-gray-400'}`}>
                                {b.toFixed(2)}%
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex gap-2 mt-4">
                    <button onClick={handleSquareOff} className="flex-1 py-3 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all">Square Off All</button>
                    <button onClick={handleExport} className="flex-1 py-3 bg-blue-500/10 hover:bg-blue-500 text-blue-500 hover:text-white border border-blue-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all">Export CSV</button>
                </div>
            </div>

            <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase px-1 mt-6 tracking-widest">Open Orders</h3>
            <div className="space-y-3">
                {openTrades.length === 0 ? (
                    <div className="py-8 text-center border-2 border-dashed border-[var(--border-color)]/30 rounded-2xl text-[var(--text-muted)] text-sm">No open positions</div>
                ) : (
                    openTrades.map(trade => (
                        <div key={trade.id} onClick={() => setSelectedOrder(trade)} className="glass-card p-4 rounded-xl border-l-4 border-l-[var(--accent-blue)] shadow-md hover:bg-white/5 transition-all cursor-pointer group">
                            <div className="flex justify-between items-center">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-black text-base">{trade.symbol}</span>
                                        <span className={trade.side === 'BUY' ? 'text-green-400 text-[10px] font-bold' : 'text-red-400 text-[10px] font-bold'}>{trade.side}</span>
                                        <span className={`text-[8px] px-1.5 py-0.5 rounded border font-bold uppercase ${trade.strategy_mode === 'BOUNCE' ? 'border-blue-500/50 text-blue-400' : 'border-orange-500/50 text-orange-400'}`}>
                                            {trade.strategy_mode === 'BOUNCE' ? 'Reversal' : 'Momentum'}
                                        </span>
                                    </div>
                                    <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-tight">
                                        {trade.quantity} Qty @ {trade.entry_price.toFixed(2)} → {trade.current_price?.toFixed(2)}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className={`text-lg font-black tabular-nums ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                    </div>
                                    <div className="text-[8px] text-[var(--text-muted)] font-bold group-hover:text-[var(--accent-blue)] transition-colors">DETAILS →</div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {closedTrades.length > 0 && (
                <div className="mt-8">
                    <div className="flex justify-between items-center mb-3">
                        <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Order History</h3>
                        <button onClick={handleClearHistory} className="text-[9px] text-red-400 font-bold uppercase">Clear All</button>
                    </div>
                    <div className="space-y-2">
                        {closedTrades.slice(0, 50).map(trade => (
                            <div
                                key={trade.id}
                                onClick={() => setSelectedOrder(trade)}
                                className="bg-white/5 p-3 rounded-xl border border-white/10 flex justify-between items-center cursor-pointer hover:bg-white/10 transition-all border-l-2 border-l-gray-600"
                            >
                                <div className="text-[10px] text-gray-400">
                                    <div className="flex items-center gap-1.5 mb-0.5">
                                        <span className="font-bold text-gray-200">{trade.symbol} {trade.side}</span>
                                        <span className={`text-[7px] px-1 rounded-sm border opacity-70 ${trade.strategy_mode === 'BOUNCE' ? 'border-blue-500 text-blue-400' : 'border-orange-500 text-orange-400'}`}>
                                            {trade.strategy_mode === 'BOUNCE' ? 'REV' : 'MOM'}
                                        </span>
                                    </div>
                                    <div className="opacity-60">{new Date(trade.created_at).toLocaleTimeString()} @ {trade.entry_price.toFixed(1)}</div>
                                </div>
                                <div className={`font-black text-sm ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                    {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(0)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <AnimatePresence>
                {selectedOrder && (
                    <div className="fixed inset-0 bg-black/90 flex items-center justify-center p-4 z-[100] backdrop-blur-md" onClick={() => setSelectedOrder(null)}>
                        <motion.div
                            initial={{ scale: 0.9, y: 20, opacity: 0 }}
                            animate={{ scale: 1, y: 0, opacity: 1 }}
                            className="bg-[var(--bg-card)] w-full max-w-sm rounded-3xl p-6 space-y-6 border border-white/10 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.5)]"
                            onClick={e => e.stopPropagation()}
                        >
                            {/* Modal Header */}
                            <div className="flex justify-between items-start">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <h2 className="text-2xl font-black text-white">{selectedOrder.symbol}</h2>
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${selectedOrder.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                            {selectedOrder.side}
                                        </span>
                                    </div>
                                    <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">
                                        Executed via {selectedOrder.strategy_mode === 'BOUNCE' ? 'Reversal' : 'Momentum'} Logic
                                    </p>
                                </div>
                                <div className="text-right">
                                    <div className={`text-2xl font-black ${selectedOrder.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                        {selectedOrder.pnl >= 0 ? '+' : ''}{selectedOrder.pnl.toFixed(2)}
                                    </div>
                                    <p className="text-[9px] text-gray-500 font-bold uppercase">Total P&L</p>
                                </div>
                            </div>

                            {/* Execution Blueprint */}
                            <div className="space-y-4 py-4 border-y border-white/5">
                                <div className="flex justify-between">
                                    <div className="space-y-1">
                                        <p className="text-[9px] text-gray-500 font-bold uppercase">Entry Execution</p>
                                        <p className="text-xs font-bold text-white">₹{selectedOrder.entry_price.toFixed(2)}</p>
                                        <p className="text-[10px] text-gray-400">{new Date(selectedOrder.created_at).toLocaleTimeString()}</p>
                                        <p className="text-[10px] text-[var(--accent-blue)] bg-[var(--accent-blue)]/10 px-2 py-0.5 rounded inline-block font-bold">
                                            {selectedOrder.trigger_level || 'MANUAL'}
                                        </p>
                                    </div>
                                    <div className="text-right space-y-1">
                                        <p className="text-[9px] text-gray-500 font-bold uppercase">Exit Execution</p>
                                        {selectedOrder.status === 'CLOSED' ? (
                                            <>
                                                <p className="text-xs font-bold text-white">₹{selectedOrder.exit_price?.toFixed(2)}</p>
                                                <p className="text-[10px] text-gray-400">{new Date(selectedOrder.closed_at).toLocaleTimeString()}</p>
                                                <p className="text-[10px] text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded inline-block font-bold">
                                                    {selectedOrder.exit_reason || 'CLOSED'}
                                                </p>
                                            </>
                                        ) : (
                                            <>
                                                <p className="text-xs font-bold text-gray-600 italic">Position Open</p>
                                                <p className="text-[10px] text-gray-500">Live: ₹{selectedOrder.current_price?.toFixed(2)}</p>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* SL/TGT Controls (Only for Open Trades) */}
                            {selectedOrder.status === 'OPEN' ? (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-gray-500 font-bold uppercase ml-1">Stop Loss</label>
                                            <div className="flex gap-1.5">
                                                <input
                                                    type="number"
                                                    placeholder="Price"
                                                    value={slInputs[selectedOrder.id] || ''}
                                                    onChange={e => setSlInputs({ ...slInputs, [selectedOrder.id]: e.target.value })}
                                                    className="w-full bg-white/5 p-3 rounded-xl text-xs border border-white/10 outline-none focus:border-red-500"
                                                />
                                                <button onClick={() => handleSetStopLoss(selectedOrder)} className="bg-red-500/20 text-red-400 p-3 rounded-xl hover:bg-red-500 hover:text-white transition-all">
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" /></svg>
                                                </button>
                                            </div>
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-gray-500 font-bold uppercase ml-1">Target</label>
                                            <div className="flex gap-1.5">
                                                <input
                                                    type="number"
                                                    placeholder="Price"
                                                    value={targetInputs[selectedOrder.id] || ''}
                                                    onChange={e => setTargetInputs({ ...targetInputs, [selectedOrder.id]: e.target.value })}
                                                    className="w-full bg-white/5 p-3 rounded-xl text-xs border border-white/10 outline-none focus:border-green-500"
                                                />
                                                <button onClick={() => handleSetTarget(selectedOrder)} className="bg-green-500/20 text-green-400 p-3 rounded-xl hover:bg-green-500 hover:text-white transition-all">
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" /></svg>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => { handleCloseTrade(selectedOrder); setSelectedOrder(null); }}
                                        className="w-full py-4 bg-red-600 hover:bg-red-700 text-white rounded-2xl font-black uppercase text-xs shadow-lg shadow-red-600/20 transition-all flex items-center justify-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" /></svg>
                                        Exit Position Now
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setSelectedOrder(null)}
                                    className="w-full py-4 bg-white/5 hover:bg-white/10 text-gray-300 rounded-2xl font-bold uppercase text-xs border border-white/5 transition-all"
                                >
                                    Close Details
                                </button>
                            )}
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default OrdersTab;
