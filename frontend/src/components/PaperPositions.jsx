import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getPaperSummary, togglePaperTrading, closePaperTrade, clearPaperTrades, setVirtualBalance, setStopLoss, setTarget } from '../services/api';
import toast from 'react-hot-toast';

const PaperPositions = ({ sessionId, watchlist, trades: propTrades, setTrades: propSetTrades }) => {
    const [summary, setSummary] = useState({
        auto_paper_trade: false,
        virtual_balance: 0.0,
        summary: { total_pnl: 0, open_trades: 0, closed_trades: 0 }
    });
    const [loading, setLoading] = useState(true);
    const [toggling, setToggling] = useState(false);
    const [isAddingMoney, setIsAddingMoney] = useState(false);
    const [addAmount, setAddAmount] = useState('');
    const [slInputs, setSlInputs] = useState({}); // {tradeId: slValue}
    const [targetInputs, setTargetInputs] = useState({}); // {tradeId: targetValue}

    // Use props if available, otherwise local state (for standalone testing)
    const [localTrades, setLocalTrades] = useState([]);
    const trades = propTrades || localTrades;
    const setTrades = propSetTrades || setLocalTrades;

    const fetchSummary = async (showLoading = false) => {
        if (showLoading) setLoading(true);
        try {
            const data = await getPaperSummary(sessionId);
            setSummary(data);
            if (!propTrades && data.trades) setTrades(data.trades);
        } catch (err) {
            console.error('Failed to fetch paper summary:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSummary(true);
        const interval = setInterval(() => fetchSummary(false), 5000);
        return () => clearInterval(interval);
    }, [sessionId]);

    const handleToggle = async () => {
        const nextState = !summary.auto_paper_trade;

        try {
            setToggling(true);
            setSummary(prev => ({ ...prev, auto_paper_trade: nextState }));

            await toast.promise(
                togglePaperTrading(sessionId, nextState),
                {
                    loading: nextState ? 'Enabling Auto Execution...' : 'Disabling Auto Execution...',
                    success: <b>{nextState ? 'Auto Trades Enabled' : 'Auto Trades Disabled'}</b>,
                    error: (err) => {
                        const msg = err.response?.data?.detail || 'Connection Timeout';
                        return <b>Update Failed: {msg}</b>;
                    },
                }
            );
        } catch (err) {
            console.error('Toggle error detailed:', err);
            setSummary(prev => ({ ...prev, auto_paper_trade: !nextState }));
        } finally {
            setToggling(false);
            fetchSummary();
        }
    };

    const handleAddMoney = async () => {
        const amount = parseFloat(addAmount);
        if (isNaN(amount) || amount <= 0) {
            toast.error('Enter a valid amount');
            return;
        }

        try {
            const newBalance = (summary.virtual_balance || 0) + amount;
            await setVirtualBalance(sessionId, newBalance);
            setSummary(prev => ({ ...prev, virtual_balance: newBalance }));
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

    const handleSetTarget = async (trade) => {
        const targetValue = targetInputs[trade.id];
        if (!targetValue || isNaN(parseFloat(targetValue))) {
            toast.error('Enter a valid target price');
            return;
        }

        try {
            await setTarget(sessionId, trade.id, parseFloat(targetValue));
            toast.success(`Target set at ₹${parseFloat(targetValue).toFixed(2)}`);
            setTargetInputs(prev => ({ ...prev, [trade.id]: '' }));
            fetchSummary();
        } catch (err) {
            toast.error('Failed to set target');
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
        if (!window.confirm('Clear all paper trade history?')) return;
        try {
            await clearPaperTrades(sessionId);
            toast.success('History cleared');
            fetchSummary();
        } catch (err) {
            toast.error('Failed to clear history');
        }
    };

    if (loading && !summary) {
        return <div className="p-8 text-center text-gray-400">Loading Paper Trading Data...</div>;
    }

    const openTrades = trades?.filter(t => t.status === 'OPEN') || [];
    const closedTrades = trades?.filter(t => t.status === 'CLOSED') || [];

    return (
        <div className="w-full space-y-4 pb-24 px-4 overflow-x-hidden">
            {/* Wallet Section */}
            <div className="glass-card p-5 rounded-2xl border border-[var(--border-color)] bg-gradient-to-br from-[#1A1F3A] to-[#0A0E27] shadow-xl">
                <div className="flex items-center justify-between">
                    <div>
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-widest mb-1">
                            Virtual Wallet Balance
                        </div>
                        <div className="text-3xl font-bold text-white flex items-baseline gap-1">
                            <span className="text-sm text-[var(--text-muted)] font-normal">₹</span>
                            {(summary?.virtual_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </div>
                    </div>
                    <button
                        onClick={() => setIsAddingMoney(!isAddingMoney)}
                        className="bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] px-4 py-2 rounded-xl text-sm font-bold border border-[var(--accent-blue)]/30 hover:bg-[var(--accent-blue)] hover:text-white transition-all"
                    >
                        {isAddingMoney ? 'Cancel' : '+ Add Money'}
                    </button>
                </div>

                <AnimatePresence>
                    {isAddingMoney && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-[var(--border-color)]/30">
                                <input
                                    type="number"
                                    placeholder="Amount (e.g. 100000)"
                                    value={addAmount}
                                    onChange={(e) => setAddAmount(e.target.value)}
                                    className="flex-1 min-w-0 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-xl px-4 py-2 outline-none focus:border-[var(--accent-blue)] transition-all"
                                />
                                <button
                                    onClick={handleAddMoney}
                                    className="bg-[var(--success-neon)] text-white px-4 py-2 rounded-xl font-bold text-sm shadow-lg shadow-green-500/20 whitespace-nowrap"
                                >
                                    Confirm
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {summary?.virtual_balance <= 0 && !isAddingMoney && (
                    <div className="mt-3 p-2 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center gap-2">
                        <span className="text-lg">⚠️</span>
                        <p className="text-[10px] text-red-400 font-medium uppercase tracking-wider">
                            Balance is 0. Auto-trades are paused.
                        </p>
                    </div>
                )}
            </div>

            {/* Control Panel */}
            <div className="glass-card p-5 rounded-2xl border border-[var(--border-color)]">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            Strategy Trades
                        </h2>
                        <p className="text-xs text-[var(--text-muted)]">Live execution simulation based on your alerts</p>
                    </div>
                    <button
                        onClick={handleToggle}
                        disabled={toggling}
                        className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${summary?.auto_paper_trade
                            ? 'bg-[var(--success-neon)] text-white shadow-[0_0_15px_rgba(72,187,120,0.4)]'
                            : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]'
                            }`}
                    >
                        {summary?.auto_paper_trade ? 'Auto Exec: ON' : 'Auto Exec: OFF'}
                    </button>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    <div className="bg-[var(--bg-secondary)] p-3 rounded-xl border border-[var(--border-color)]/50">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold">Total P&L</div>
                        <div className={`text-lg font-bold ${summary?.summary?.total_pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                            ₹{summary?.summary?.total_pnl?.toFixed(2)}
                        </div>
                    </div>
                    <div className="bg-[var(--bg-secondary)] p-3 rounded-xl border border-[var(--border-color)]/50">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold">Open</div>
                        <div className="text-lg font-bold text-white">{openTrades.length}</div>
                    </div>
                    <div className="bg-[var(--bg-secondary)] p-3 rounded-xl border border-[var(--border-color)]/50">
                        <div className="text-[10px] text-[var(--text-muted)] uppercase font-bold">Closed</div>
                        <div className="text-lg font-bold text-[var(--text-secondary)]">{closedTrades.length}</div>
                    </div>
                </div>
            </div>

            {/* Active Positions */}
            <div className="space-y-3">
                <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider px-1">Active Positions</h3>
                {openTrades.length === 0 ? (
                    <div className="text-center py-8 glass-card rounded-2xl border-dashed border-[var(--border-color)] text-[var(--text-muted)] text-sm">
                        No active positions. Enable "Auto Exec" and hit an alert level.
                    </div>
                ) : (
                    openTrades.map(trade => (
                        <div key={trade.id} className="glass-card p-4 rounded-xl border-l-4 border-l-[var(--accent-blue)]">
                            <div className="flex justify-between items-start mb-3">
                                <div className="flex flex-col">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-white">{trade.symbol}</span>
                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${trade.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                            {trade.side}
                                        </span>
                                    </div>
                                    <div className="text-xs text-[var(--text-muted)] mt-1">
                                        Entry: ₹{trade.entry_price.toFixed(2)} • {trade.trigger_level}
                                    </div>
                                    <div className="flex gap-3 mt-0.5">
                                        {trade.stop_loss && (
                                            <div className="text-[10px] text-red-400/80 font-medium">
                                                🛑 SL: ₹{parseFloat(trade.stop_loss).toFixed(2)}
                                            </div>
                                        )}
                                        {trade.target && (
                                            <div className="text-[10px] text-green-400/80 font-medium">
                                                🎯 TGT: ₹{parseFloat(trade.target).toFixed(2)}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="text-right">
                                        <div className={`font-bold ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                            {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                        </div>
                                        <div className="text-[10px] text-[var(--text-muted)]">Live P&L</div>
                                    </div>
                                    <button
                                        onClick={() => handleCloseTrade(trade)}
                                        className="p-2 bg-[var(--danger-neon)]/10 text-[var(--danger-neon)] rounded-lg hover:bg-[var(--danger-neon)] hover:text-white transition-all"
                                        title="Close Position"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>

                            {/* Control Inputs (SL & Target) */}
                            <div className="space-y-2 pt-3 border-t border-[var(--border-color)]/30">
                                {/* Stop Loss */}
                                <div className="flex gap-2">
                                    <input
                                        type="number"
                                        placeholder="Set SL (e.g., 495.50)"
                                        value={slInputs[trade.id] || ''}
                                        onChange={(e) => setSlInputs(prev => ({ ...prev, [trade.id]: e.target.value }))}
                                        className="flex-1 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg px-3 py-1.5 text-xs outline-none focus:border-red-400 transition-all"
                                    />
                                    <button
                                        onClick={() => handleSetStopLoss(trade)}
                                        disabled={!slInputs[trade.id]}
                                        className="bg-red-500/20 text-red-400 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-red-500 hover:text-white transition-all disabled:opacity-50"
                                    >
                                        Set SL
                                    </button>
                                </div>
                                {/* Target */}
                                <div className="flex gap-2">
                                    <input
                                        type="number"
                                        placeholder="Set Target (e.g., 515.00)"
                                        value={targetInputs[trade.id] || ''}
                                        onChange={(e) => setTargetInputs(prev => ({ ...prev, [trade.id]: e.target.value }))}
                                        className="flex-1 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg px-3 py-1.5 text-xs outline-none focus:border-green-400 transition-all"
                                    />
                                    <button
                                        onClick={() => handleSetTarget(trade)}
                                        disabled={!targetInputs[trade.id]}
                                        className="bg-green-500/20 text-green-400 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-green-500 hover:text-white transition-all disabled:opacity-50"
                                    >
                                        Set TGT
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* History */}
            {closedTrades.length > 0 && (
                <div className="space-y-3">
                    <div className="flex justify-between items-center px-1">
                        <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Recent History</h3>
                        <button onClick={handleClearHistory} className="text-[10px] text-[var(--danger-neon)] hover:underline">Clear History</button>
                    </div>
                    <div className="space-y-2 opacity-70">
                        {closedTrades.slice(0, 10).map(trade => (
                            <div key={trade.id} className="bg-[var(--bg-secondary)] p-3 rounded-lg border border-[var(--border-color)]/30 flex justify-between items-center text-sm">
                                <div>
                                    <div className="font-bold text-white uppercase tracking-tight">{trade.symbol}</div>
                                    <div className="text-[10px] text-[var(--text-muted)]">
                                        {trade.side} @ {trade.entry_price.toFixed(2)} → {trade.exit_price?.toFixed(2)}
                                    </div>
                                </div>
                                <div className={`font-bold ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                    {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PaperPositions;
