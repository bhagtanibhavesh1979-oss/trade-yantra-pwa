import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getPaperSummary, togglePaperTrading, setStrategyMode, setBufferPct, closePaperTrade, clearPaperTrades, setVirtualBalance, setStopLoss, getPaperAnalytics, getSession } from '../services/api';
import toast from 'react-hot-toast';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

const TradesTab = ({
    clientId,
    sessionId,
    watchlist,
    trades: propTrades,
    setTrades: propSetTrades,
    paperBalance,
    setPaperBalance,
    autoExec,
    setAutoExec,
    strategyMode,
    setStrategyMode: updateStrategyModeState,
    bufferPct,
    setBufferPct: updateBufferPctState,
    isPaused
}) => {
    // Local fallback state (optional, mainly for initial render safety)
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [toggling, setToggling] = useState(false);
    const [isAddingMoney, setIsAddingMoney] = useState(false);
    const [addAmount, setAddAmount] = useState('');
    const [slInputs, setSlInputs] = useState({}); // {tradeId: slValue}

    // Use props if available, otherwise local state (for standalone testing)
    const [localTrades, setLocalTrades] = useState([]);
    const trades = propTrades || localTrades;
    const setTrades = propSetTrades || setLocalTrades;

    // COMPACT SUMMARY: Derived from live trades list to ensure it's always in sync with WebSocket
    const openTrades = trades?.filter(t => t.status === 'OPEN') || [];
    const closedTrades = trades?.filter(t => t.status === 'CLOSED') || [];
    const liveTotalPnl = trades?.reduce((sum, t) => sum + (t.pnl || 0), 0) || 0;

    const fetchSummary = async (showLoading = false) => {
        const sessionData = getSession();
        const sid = sessionId || sessionData?.session_id || sessionData?.sessionId;
        if (!sid) return;

        const cid = clientId || sessionData?.client_id || sessionData?.clientId;

        if (showLoading) setLoading(true);
        try {
            const [summaryData, analyticsData] = await Promise.all([
                getPaperSummary(sid, cid),
                getPaperAnalytics(sid, cid).catch(() => null)
            ]);

            console.log('💰 [DEBUG] TradesTab Paper Summary:', summaryData);

            // Sync all lifted states
            // Sync all lifted states
            console.log('🔄 [DEBUG] Syncing State -> Balance:', summaryData.virtual_balance, 'AutoExec:', summaryData.auto_paper_trade);
            if (setPaperBalance) setPaperBalance(summaryData.virtual_balance);
            if (setAutoExec) setAutoExec(summaryData.auto_paper_trade);
            if (updateStrategyModeState) updateStrategyModeState(summaryData.strategy_mode);
            if (updateBufferPctState) updateBufferPctState(summaryData.buffer_pct);

            if (analyticsData) setAnalytics(analyticsData);

            if (summaryData.trades) {
                setTrades(summaryData.trades);
            }
        } catch (err) {
            console.error('Failed to fetch trades summary:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSummary(true);
        const interval = setInterval(() => fetchSummary(false), 5000);
        return () => clearInterval(interval);
    }, [sessionId]);

    const handleBufferChange = async (buffer) => {
        const sid = sessionId;
        const cid = clientId;
        if (!sid) {
            toast.error('Session ID missing.');
            return;
        }

        try {
            if (updateBufferPctState) updateBufferPctState(buffer);
            await toast.promise(
                setBufferPct(sid, buffer, cid),
                {
                    loading: 'Updating Sensitivity...',
                    success: <b>Buffer set to {buffer}%</b>,
                    error: (err) => {
                        console.error('Buffer fetch error:', err);
                        fetchSummary();
                        return <b>Failed to update buffer</b>;
                    }
                }
            );
        } catch (err) {
            console.error('Buffer update error:', err);
        }
    };

    const handleStrategyChange = async (mode) => {
        const sid = sessionId;
        const cid = clientId;
        if (!sid) {
            toast.error('Session ID missing.');
            return;
        }

        try {
            if (updateStrategyModeState) updateStrategyModeState(mode);
            await toast.promise(
                setStrategyMode(sid, mode, cid),
                {
                    loading: 'Updating Strategy...',
                    success: <b>Strategy set to {mode === 'BOUNCE' ? 'Mean Reversion' : 'Momentum (SAR)'}</b>,
                    error: (err) => {
                        console.error('Strategy fetch error:', err);
                        fetchSummary();
                        return <b>Failed to update strategy</b>;
                    }
                }
            );
        } catch (err) {
            console.error('Strategy update error:', err);
        }
    };

    const handleToggle = async () => {
        const nextState = !autoExec;
        const sid = sessionId;
        const cid = clientId;
        if (!sid) {
            toast.error('Session ID missing.');
            return;
        }

        try {
            setToggling(true);
            if (setAutoExec) setAutoExec(nextState);
            await toast.promise(
                togglePaperTrading(sid, nextState, cid),
                {
                    loading: nextState ? 'Enabling Auto Execution...' : 'Disabling Auto Execution...',
                    success: <b>{nextState ? 'Auto Trades Enabled' : 'Auto Trades Disabled'}</b>,
                    error: (err) => {
                        fetchSummary();
                        return <b>Update Failed</b>;
                    }
                }
            );
        } catch (err) {
            console.error('Toggle update error:', err);
            if (setAutoExec) setAutoExec(!nextState);
        } finally {
            setToggling(false);
        }
    };

    const handleAddMoney = async () => {
        const amount = parseFloat(addAmount);
        if (isNaN(amount) || amount <= 0) {
            toast.error('Enter a valid amount');
            return;
        }

        const sid = sessionId;
        const cid = clientId;
        if (!sid) {
            toast.error('Session ID missing.');
            return;
        }

        try {
            const newBalance = (paperBalance || 0) + amount;
            await setVirtualBalance(sid, newBalance, cid);
            if (setPaperBalance) setPaperBalance(newBalance);
            setAddAmount('');
            setIsAddingMoney(false);
            toast.success(`Added ₹${amount} to Virtual Wallet`);
        } catch (err) {
            toast.error('Failed to update balance');
        }
    };

    const handleSetStopLoss = async (trade) => {
        const slValue = slInputs[trade.id];
        if (!slValue || isNaN(parseFloat(slValue))) {
            toast.error('Enter a valid stop loss price');
            return;
        }

        try {
            await setStopLoss(sessionId, trade.id, parseFloat(slValue));
            toast.success(`Stop Loss set at ₹${parseFloat(slValue).toFixed(2)}`);
            setSlInputs(prev => ({ ...prev, [trade.id]: '' }));
            fetchSummary();
        } catch (err) {
            toast.error('Failed to set stop loss');
        }
    };

    const handleCloseTrade = async (trade) => {
        try {
            const stock = watchlist.find(s => s.token === trade.token);
            const ltp = stock ? stock.ltp : trade.entry_price;

            await closePaperTrade(sessionId, trade.id, ltp);
            toast.success('Position closed');
            fetchSummary();
        } catch (err) {
            toast.error('Failed to close position');
        }
    };

    const handleClearHistory = async () => {
        if (!window.confirm('Clear trade history? Open positions will be kept.')) return;
        try {
            await clearPaperTrades(sessionId);
            toast.success('History cleared');
            fetchSummary();
        } catch (err) {
            toast.error('Failed to clear history');
        }
    };

    const handleDownloadReport = async () => {
        try {
            const API_URL = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 'https://trade-yantra-api-ibynqazflq-el.a.run.app');
            const url = `${API_URL}/api/paper/export/${sessionId}`;
            const newWindow = window.open(url, '_blank');
            if (!newWindow) toast.error('Please allow popups to download');
            else toast.success('Download started!');
        } catch (err) {
            toast.error('Failed to download');
        }
    };

    if (loading && (!trades || trades.length === 0) && !paperBalance) {
        return <div className="p-8 text-center text-gray-400">Loading Trades Data...</div>;
    }

    return (
        <div className="w-full space-y-4 pb-24 px-4 overflow-x-hidden">
            {/* 1. WALLET & STATS GRID */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Wallet Card */}
                <div className="glass-card p-5 rounded-2xl border border-[var(--border-color)] shadow-xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent-blue)]/5 rounded-full -mr-16 -mt-16 blur-3xl"></div>
                    <div className="flex items-center justify-between relative z-10">
                        <div>
                            <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-widest mb-1">Account Balance</div>
                            <div className="text-3xl font-black text-[var(--text-primary)] flex items-baseline gap-1">
                                <span className="text-sm text-[var(--text-muted)] font-normal">₹</span>
                                {(paperBalance || 0).toLocaleString('en-IN', { minimumFractionDigits: 0 })}
                            </div>
                        </div>
                        <button
                            onClick={() => setIsAddingMoney(!isAddingMoney)}
                            className="bg-[var(--accent-blue)]/10 text-[var(--accent-blue)] px-4 py-2 rounded-xl text-xs font-bold border border-[var(--accent-blue)]/20 hover:bg-[var(--accent-blue)] hover:text-white transition-all"
                        >
                            {isAddingMoney ? 'Cancel' : 'Add Funds'}
                        </button>
                    </div>

                    <AnimatePresence>
                        {isAddingMoney && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-[var(--border-color)]/20">
                                    <input
                                        type="number"
                                        placeholder="Amount"
                                        value={addAmount}
                                        onChange={(e) => setAddAmount(e.target.value)}
                                        className="flex-1 min-w-0 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-xl px-4 py-2 outline-none focus:border-[var(--accent-blue)]"
                                    />
                                    <button onClick={handleAddMoney} className="bg-[var(--success-neon)] text-white px-4 py-2 rounded-xl font-bold text-xs">Confirm</button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Quick Performance Metrics */}
                <div className="glass-card p-5 rounded-2xl border border-[var(--border-color)]">
                    <div className="flex justify-between items-center mb-3">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-widest">Key Insights</div>
                        <div className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${liveTotalPnl >= 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                            Today: {liveTotalPnl >= 0 ? '+' : ''}{liveTotalPnl.toFixed(0)}
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                        <div className="p-4 rounded-xl bg-[var(--bg-secondary)]/50 border border-[var(--border-color)]/10">
                            <div className="text-2xl font-black text-[var(--accent-blue)]">{analytics?.stats?.win_rate || 0}%</div>
                            <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Win Rate</div>
                        </div>
                        <div className="p-4 rounded-xl bg-[var(--bg-secondary)]/50 border border-[var(--border-color)]/10">
                            <div className="text-2xl font-black text-[var(--success-neon)]">{analytics?.stats?.profit_factor || 0}</div>
                            <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Profit Factor</div>
                        </div>
                        <div className="p-4 rounded-xl bg-[var(--bg-secondary)]/50 border border-[var(--border-color)]/10">
                            <div className="text-2xl font-black text-gray-300">{analytics?.stats?.total_trades || 0}</div>
                            <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Total Trades</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* 2. EQUITY CURVE (The "Premium" Look) */}
            {analytics?.equity_curve?.length > 1 && (
                <div className="glass-card p-4 rounded-2xl border border-[var(--border-color)] overflow-hidden">
                    <div className="flex justify-between items-center mb-4 px-2">
                        <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Growth Curve</h3>
                        <button onClick={handleDownloadReport} className="text-[10px] flex items-center gap-1 text-[var(--accent-blue)] hover:underline">
                            Export Detailed History
                        </button>
                    </div>
                    <div className="h-40 w-full mt-2">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={analytics.equity_curve}>
                                <defs>
                                    <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#667EEA" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#667EEA" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis
                                    dataKey="time"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 9, fill: '#718096' }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    hide
                                    domain={['auto', 'auto']}
                                />
                                <Tooltip
                                    contentStyle={{ background: '#1A202C', border: '1px solid #2D3748', borderRadius: '12px', fontSize: '12px' }}
                                    itemStyle={{ color: '#667EEA' }}
                                    formatter={(value) => [`₹${value}`, 'Balance']}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="balance"
                                    stroke="#667EEA"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorBalance)"
                                    animationDuration={2000}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* 3. STRATEGY CONTROL */}
            <div className="glass-card p-4 rounded-2xl border border-[var(--border-color)] space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-sm font-bold text-[var(--text-primary)]">Automated Execution</h2>
                        <p className="text-[10px] text-[var(--text-muted)] transition-all">
                            {autoExec
                                ? (isPaused ? <span className="text-red-400 font-bold">⚠️ SYSTEM PAUSED: Alerts are OFF. Unpause in Alerts Tab.</span> : 'Strategy is monitoring live alerts')
                                : 'Manual monitoring only'}
                        </p>
                    </div>
                    <button
                        onClick={handleToggle}
                        disabled={toggling}
                        className={`px-6 py-2 rounded-xl text-xs font-black transition-all ${autoExec
                            ? 'bg-[var(--success-neon)] text-white shadow-[0_0_20px_rgba(72,187,120,0.3)]'
                            : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]'
                            }`}
                    >
                        {autoExec ? 'ON' : 'OFF'}
                    </button>
                </div>

                {/* Strategy & Buffer Control */}
                <div className="pt-3 border-t border-[var(--border-color)]/20 space-y-4">
                    <div>
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-widest mb-2 px-1">Logic Pattern</div>
                        <div className="grid grid-cols-2 gap-2 bg-[var(--bg-primary)] p-1 rounded-xl border border-[var(--border-color)]/20">
                            <button
                                onClick={() => handleStrategyChange('BOUNCE')}
                                className={`py-2 rounded-lg text-[10px] font-black transition-all ${strategyMode === 'BOUNCE'
                                    ? 'bg-[var(--accent-blue)] text-white shadow-lg'
                                    : 'text-[var(--text-muted)] hover:text-white'
                                    }`}
                            >
                                MEAN REVERSION
                            </button>
                            <button
                                onClick={() => handleStrategyChange('SAR')}
                                className={`py-2 rounded-lg text-[10px] font-black transition-all ${strategyMode === 'SAR'
                                    ? 'bg-orange-500 text-white shadow-lg'
                                    : 'text-[var(--text-muted)] hover:text-white'
                                    }`}
                            >
                                MOMENTUM (SAR)
                            </button>
                        </div>
                    </div>

                    <div>
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-widest mb-2 px-1">Sensitivity (Buffer)</div>
                        <div className="flex bg-[var(--bg-primary)] p-1 rounded-xl border border-[var(--border-color)]/20 gap-1 overflow-x-auto scrollbar-hide">
                            {[0.10, 0.15, 0.25, 0.45, 0.50, 0.63, 0.72, 0.81, 0.90].map(val => (
                                <button
                                    key={val}
                                    onClick={() => handleBufferChange(val)}
                                    className={`px-3 py-1.5 rounded-lg text-[9px] font-black transition-all whitespace-nowrap ${Number(bufferPct || 0.45).toFixed(2) === val.toFixed(2)
                                        ? 'bg-yellow-500 text-black shadow-lg'
                                        : 'text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]'
                                        }`}
                                >
                                    {val.toFixed(2)}%
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <p className="text-[8px] text-[var(--text-muted)] mt-2 px-1 italic">
                    {strategyMode === 'BOUNCE'
                        ? '• Logic: Rejection at levels. Buy on supports, Sell on resistances.'
                        : '• Logic: Breakdown/Breakout at levels. Sell on support breaks, Buy on resistance breaks.'}
                    {' Confirmation: Waiting for 15m candle close.'}
                </p>
            </div>

            {/* 4. ACTIVE POSITIONS */}
            <div className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest px-1">Live Positions</h3>
                {openTrades.length === 0 ? (
                    <div className="text-center py-12 glass-card rounded-2xl border-dashed border-[var(--border-color)]/50 text-[var(--text-muted)] text-sm italic">
                        No active trades. System is ready.
                    </div>
                ) : (
                    openTrades.map(trade => (
                        <div key={trade.id} className="glass-card p-4 rounded-2xl border-l-[6px] border-l-[var(--accent-blue)] shadow-lg">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-black text-lg text-[var(--text-primary)] tracking-tight">
                                            {trade.symbol}
                                        </span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-black ${trade.side === 'BUY' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                            {trade.side}
                                        </span>
                                        <span className={`text-[8px] px-1.5 py-0.5 rounded border font-bold uppercase ${trade.strategy_mode === 'BOUNCE' ? 'border-blue-500/50 text-blue-400' : 'border-orange-500/50 text-orange-400'}`}>
                                            {trade.strategy_mode === 'BOUNCE' ? 'Reversal' : 'Momentum'}
                                        </span>
                                    </div>
                                    <div className="text-[10px] font-medium text-[var(--text-muted)] line-clamp-1 uppercase">
                                        {trade.quantity} QTY • ₹{trade.entry_price.toFixed(2)} • {trade.trigger_level}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className={`text-xl font-black ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                    </div>
                                    <div className="text-[9px] font-bold text-[var(--text-muted)] uppercase">Live Profit</div>

                                    {/* --- Target and SL Display --- */}
                                    <div className="mt-2 flex flex-col gap-0.5 items-end">
                                        {trade.target && (
                                            <div className="text-[10px] text-[var(--success-neon)] font-bold flex items-center gap-1">
                                                <span className="opacity-50 text-[8px]">TGT:</span> ₹{trade.target.toFixed(2)}
                                            </div>
                                        )}
                                        {trade.stop_loss && (
                                            <div className="text-[10px] text-[var(--danger-neon)] font-bold flex items-center gap-1">
                                                <span className="opacity-50 text-[8px]">SL:</span> ₹{trade.stop_loss.toFixed(2)}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-2">
                                <div className="flex-1 relative flex items-center">
                                    <span className="absolute left-3 text-[10px] text-gray-500 font-bold">SL</span>
                                    <input
                                        type="number"
                                        placeholder="Price"
                                        value={slInputs[trade.id] || ''}
                                        onChange={(e) => setSlInputs(prev => ({ ...prev, [trade.id]: e.target.value }))}
                                        className="w-full bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-xl pl-9 pr-3 py-2 text-xs outline-none focus:border-red-400"
                                    />
                                </div>
                                <button
                                    onClick={() => handleSetStopLoss(trade)}
                                    className="bg-red-500/10 text-red-400 px-4 py-2 rounded-xl text-xs font-black border border-red-500/20"
                                >
                                    Update
                                </button>
                                <button
                                    onClick={() => handleCloseTrade(trade)}
                                    className="bg-[var(--danger-neon)] text-white px-4 py-2 rounded-xl text-xs font-black shadow-lg shadow-red-500/20"
                                >
                                    Close
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* 5. HISTORY */}
            {closedTrades.length > 0 && (
                <div className="space-y-3 pb-8">
                    <div className="flex justify-between items-center px-1">
                        <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest">Day Log</h3>
                        <button onClick={handleClearHistory} className="text-[10px] text-red-400 font-bold opacity-50 hover:opacity-100 uppercase">Clear</button>
                    </div>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 scrollbar-hide">
                        {closedTrades.slice(0, 50).map(trade => (
                            <div key={trade.id} className="bg-[var(--bg-secondary)]/30 backdrop-blur-sm p-3 rounded-xl border border-[var(--border-color)]/20 flex justify-between items-center transition-all hover:bg-[var(--bg-secondary)]/50">
                                <div>
                                    <div className="font-bold text-xs text-[var(--text-primary)] uppercase tracking-tighter">{trade.symbol}</div>
                                    <div className="text-[9px] text-[var(--text-muted)] font-medium">
                                        {trade.side} • {trade.entry_price.toFixed(2)} → {trade.exit_price?.toFixed(2)}
                                        {trade.exit_reason && <span className="ml-2 text-[8px] bg-[var(--bg-primary)] px-1 rounded border border-[var(--border-color)]/20 text-[var(--accent-blue)]">{trade.exit_reason}</span>}
                                    </div>
                                    <div className="text-[7px] text-gray-500 font-mono mt-0.5">{new Date(trade.closed_at).toLocaleString()}</div>
                                </div>
                                <div className={`font-black text-sm ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                    {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(0)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TradesTab;