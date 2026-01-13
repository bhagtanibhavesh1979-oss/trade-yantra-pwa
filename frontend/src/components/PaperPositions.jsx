import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getPaperSummary, togglePaperTrading, closePaperTrade, clearPaperTrades } from '../services/api';
import toast from 'react-hot-toast';

const PaperPositions = ({ sessionId, watchlist, trades: propTrades, setTrades: propSetTrades }) => {
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [toggling, setToggling] = useState(false);

    // Use props if available, otherwise local state (for standalone testing)
    const [localTrades, setLocalTrades] = useState([]);
    const trades = propTrades || localTrades;
    const setTrades = propSetTrades || setLocalTrades;

    const fetchSummary = async () => {
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
        fetchSummary();
        const interval = setInterval(fetchSummary, 5000);
        return () => clearInterval(interval);
    }, [sessionId]);

    const handleToggle = async () => {
        if (!summary) return;
        try {
            setToggling(true);
            const nextState = !summary.auto_paper_trade;
            await togglePaperTrading(sessionId, nextState);
            setSummary(prev => ({ ...prev, auto_paper_trade: nextState }));
            toast.success(nextState ? 'Auto Paper Trading Enabled' : 'Auto Paper Trading Disabled');
        } catch (err) {
            toast.error('Failed to toggle paper trading');
        } finally {
            setToggling(false);
        }
    };

    const handleCloseTrade = async (trade) => {
        try {
            // Find current LTP from watchlist
            const stock = watchlist.find(s => s.token === trade.token);
            const ltp = stock ? stock.ltp : trade.entry_price; // Fallback to entry if not found

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
        <div className="w-full space-y-4 pb-24 px-4">
            {/* Control Panel */}
            <div className="glass-card p-5 rounded-2xl border border-[var(--border-color)]">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            Virtual Trading (Paper)
                        </h2>
                        <p className="text-xs text-[var(--text-muted)]">Test your Support/Resistance technique without real money</p>
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
                        No active virtual positions. Enable "Auto Exec" and hit an alert level to enter.
                    </div>
                ) : (
                    openTrades.map(trade => (
                        <div key={trade.id} className="glass-card p-4 rounded-xl border-l-4 border-l-[var(--accent-blue)] flex justify-between items-center group">
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
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="text-right">
                                    <div className={`font-bold ${trade.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                                    </div>
                                    <div className="text-[10px] text-[var(--text-muted)]">Live P&L</div>
                                </div>
                                <button
                                    onClick={() => handleCloseTrade(trade)}
                                    className="p-2 bg-[var(--danger-neon)]/10 text-[var(--danger-neon)] rounded-lg hover:bg-[var(--danger-neon)] hover:text-white transition-all opacity-0 group-hover:opacity-100"
                                    title="Close Position"
                                >
                                    ✕
                                </button>
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
                                    <div className="font-bold text-white">{trade.symbol}</div>
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
