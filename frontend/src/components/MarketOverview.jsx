import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skeleton } from './Skeleton';

const MarketOverview = ({ sessionId, onAlertClick }) => {
    const [indices, setIndices] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedChartIndex, setSelectedChartIndex] = useState(null);

    const getTradingViewSymbol = (symbol, exchange = 'NSE') => {
        if (symbol === 'SENSEX' || symbol === 'BSE SENSEX') return 'BSE:SENSEX';
        if (symbol === 'NIFTY 50') return 'NSE:NIFTY';
        if (symbol === 'NIFTY BANK') return 'NSE:BANKNIFTY';
        if (symbol === 'NIFTY FIN SERVICE') return 'NSE:CNXFINANCE'; // CNXFINANCE is standard for FinNifty

        // Fallback
        return `${exchange}:${symbol.replace(' ', '')}`;
    };

    // Filter to only keep the 4 keys we care about
    const TARGET_INDICES = ['NIFTY 50', 'NIFTY BANK', 'SENSEX', 'NIFTY FIN SERVICE', 'BSE SENSEX'];

    const fetchIndices = async () => {
        // Only set loading true if we don't have data yet to prevent flickering
        if (indices.length === 0) setLoading(true);

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/api/indices/${sessionId}`);
            if (response.ok) {
                const data = await response.json();
                if (data.indices) {
                    // We need to map data carefully. 
                    const latestIndices = data.indices.filter(idx => TARGET_INDICES.includes(idx.symbol.toUpperCase()) || (idx.symbol === 'BSE Sensex' && TARGET_INDICES.includes('SENSEX')));

                    setIndices(prevIndices => {
                        return prevIndices.map(prev => {
                            const found = data.indices.find(d =>
                                d.token === prev.token ||
                                d.symbol === prev.symbol ||
                                (prev.symbol === 'SENSEX' && d.symbol === 'SENSEX') // Match generic SENSEX
                            );
                            return found ? { ...prev, ...found } : prev;
                        });
                    });

                    // Initialize if empty
                    if (indices.length === 0) {
                        const initialSet = [
                            { symbol: 'NIFTY 50', token: '99926000', ltp: 0, pdc: 0, exch: 'NSE' },
                            { symbol: 'NIFTY BANK', token: '99926009', ltp: 0, pdc: 0, exch: 'NSE' },
                            { symbol: 'SENSEX', token: '99919000', ltp: 0, pdc: 0, exch: 'BSE' },
                            { symbol: 'NIFTY FIN SERVICE', token: '99926012', ltp: 0, pdc: 0, exch: 'NSE' },
                        ];
                        // Merge with fetched data
                        setIndices(initialSet.map(init => {
                            const found = data.indices.find(d =>
                                d.token === init.token ||
                                (d.symbol === 'BSE Sensex' && init.symbol === 'SENSEX') ||
                                d.symbol === init.symbol
                            );
                            return found ? { ...init, ...found, symbol: init.symbol } : init;
                        }));
                    }
                }
            }
        } catch (err) {
            console.error('Failed to fetch market overview:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (sessionId) {
            // Initial load
            setIndices([
                { symbol: 'NIFTY 50', token: '99926000', ltp: 0, pdc: 0, exch: 'NSE' },
                { symbol: 'NIFTY BANK', token: '99926009', ltp: 0, pdc: 0, exch: 'NSE' },
                { symbol: 'SENSEX', token: '99919000', ltp: 0, pdc: 0, exch: 'BSE' },
                { symbol: 'NIFTY FIN SERVICE', token: '99926012', ltp: 0, pdc: 0, exch: 'NSE' },
            ]);

            fetchIndices();
            const interval = setInterval(fetchIndices, 10000); // Update every 10s for header
            return () => clearInterval(interval);
        }
    }, [sessionId]);

    return (
        <>
            <div className="w-full overflow-x-auto pb-4 pt-2 px-1 scrollbar-hide">
                <div className="flex space-x-4 min-w-max">
                    {(loading && indices.length === 0) ? (
                        // Skeleton Loaders
                        Array(4).fill(0).map((_, i) => (
                            <div key={i} className="min-w-[160px] p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]/50">
                                <div className="flex justify-between items-center mb-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-4 w-4 rounded-full" />
                                </div>
                                <Skeleton className="h-8 w-24 mb-2" />
                                <Skeleton className="h-4 w-16" />
                            </div>
                        ))
                    ) : (
                        indices.map((index, i) => {
                            const change = index.ltp - index.pdc;
                            const changePercent = index.pdc > 0
                                ? ((index.ltp - index.pdc) / index.pdc * 100)
                                : 0;
                            const isPositive = change >= 0;

                            return (
                                <motion.div
                                    key={index.symbol}
                                    initial={{ opacity: 0, y: -20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.1 }}
                                    onClick={() => setSelectedChartIndex(index)}
                                    className="glass-card min-w-[160px] p-3 rounded-lg border border-[var(--glass-border)] flex flex-col justify-between cursor-pointer hover:border-[#667EEA]/50 active:scale-95 transition-all"
                                >
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider truncate mr-2">
                                            {index.symbol.replace('NIFTY', '').trim() || index.symbol}
                                        </span>
                                        <div className="flex items-center gap-1">
                                            {loading && i === 0 && <div className="w-1.5 h-1.5 bg-[var(--accent-blue)] rounded-full animate-ping" />}
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onAlertClick && onAlertClick(index.symbol, index.token, index.exch);
                                                }}
                                                className="p-1 hover:bg-[var(--bg-primary)] rounded-full text-[var(--text-muted)] hover:text-[var(--accent-blue)] transition-colors z-10 relative"
                                                title="Create Alert"
                                            >
                                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>

                                    <div className="flex items-baseline gap-2">
                                        <span className={`text-lg font-bold ${isPositive ? 'text-[var(--text-primary)]' : 'text-[var(--text-primary)]'}`}>
                                            {index.ltp?.toLocaleString('en-IN') || '0.00'}
                                        </span>
                                    </div>

                                    <div className={`text-xs font-semibold flex items-center ${isPositive ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                        <span className="mr-1">{isPositive ? '▲' : '▼'}</span>
                                        {Math.abs(change).toFixed(2)} ({Math.abs(changePercent).toFixed(2)}%)
                                    </div>
                                </motion.div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Index Detail Modal */}
            <AnimatePresence>
                {selectedChartIndex && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-[#1A202C] dark:bg-[#1A202C] bg-white w-full max-w-lg rounded-2xl shadow-2xl border border-[var(--border-color)] overflow-hidden"
                        >
                            <div className="p-4 border-b border-[var(--border-color)] flex justify-between items-center">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="font-bold text-[var(--text-primary)]">{selectedChartIndex.symbol}</h3>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onAlertClick && onAlertClick(selectedChartIndex.symbol, selectedChartIndex.token, selectedChartIndex.exch);
                                            }}
                                            className="p-1 hover:bg-[var(--bg-primary)] rounded-full text-[var(--text-muted)] hover:text-[var(--accent-blue)] transition-colors"
                                            title="Create Alert"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                            </svg>
                                        </button>
                                    </div>
                                    <div className="text-xs text-[var(--text-secondary)]">TOKEN: {selectedChartIndex.token}</div>
                                </div>
                                <button
                                    onClick={() => setSelectedChartIndex(null)}
                                    className="p-2 rounded-full hover:bg-[var(--bg-secondary)] text-[var(--text-secondary)] transition-colors"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>

                            <div className="p-4">
                                {/* TradingView Widget */}
                                <div className="w-full h-64 bg-black rounded-xl overflow-hidden border border-[var(--border-color)]">
                                    <iframe
                                        key={selectedChartIndex.token}
                                        src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_76230&symbol=${encodeURIComponent(getTradingViewSymbol(selectedChartIndex.symbol, selectedChartIndex.exch))}&interval=D&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=f1f3f6&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FKolkata&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=in&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=${encodeURIComponent(getTradingViewSymbol(selectedChartIndex.symbol, selectedChartIndex.exch))}`}
                                        width="100%"
                                        height="100%"
                                        frameBorder="0"
                                        allowTransparency="true"
                                        scrolling="no"
                                        allowFullScreen
                                    ></iframe>
                                </div>

                                <div className="grid grid-cols-2 gap-4 mt-6">
                                    <div className="glass-card p-3 rounded-xl text-center">
                                        <div className="text-xs text-[var(--text-muted)] uppercase">LTP</div>
                                        <div className={`text-xl font-bold ${selectedChartIndex.ltp - selectedChartIndex.pdc >= 0 ? 'price-up' : 'price-down'}`}>
                                            ₹{selectedChartIndex.ltp.toLocaleString('en-IN')}
                                        </div>
                                    </div>
                                    <div className="glass-card p-3 rounded-xl text-center">
                                        <div className="text-xs text-[var(--text-muted)] uppercase">Change</div>
                                        <div className={`text-xl font-bold ${selectedChartIndex.ltp - selectedChartIndex.pdc >= 0 ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                            {selectedChartIndex.ltp - selectedChartIndex.pdc >= 0 ? '+' : ''}{(selectedChartIndex.ltp - selectedChartIndex.pdc).toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </>
    );
}

export default MarketOverview;
