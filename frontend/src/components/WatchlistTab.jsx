import { useState, useEffect } from 'react';
import { searchSymbols, addToWatchlist, removeFromWatchlist, refreshWatchlist, getWatchlist, manualTrade } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

function WatchlistTab({ session, watchlist, setWatchlist, referenceDate, isVisible = true, onOpenInChart }) {
    const sessionId = session?.sessionId || session?.session_id;
    const clientId = session?.clientId || session?.client_id;

    // Debug session
    useEffect(() => {
        if (session && !sessionId) {
            console.error('[WatchlistTab] Missing Session ID:', session);
            toast.error('Session Invalid. Please Login Again.');
        }
    }, [session, sessionId]);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [showSearchResults, setShowSearchResults] = useState(false);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [selectedStock, setSelectedStock] = useState(null);
    const [manualQty, setManualQty] = useState(100);

    // Sparkline: accumulate last 20 LTP ticks for selected stock
    const [sparkData, setSparkData] = useState([]);
    const sparkTokenRef = { current: null };

    // Sorting only
    const [sortBy, setSortBy] = useState('none');

    // Search symbols
    useEffect(() => {
        if (searchQuery.length > 2) {
            const timer = setTimeout(async () => {
                try {
                    setLoading(true);
                    const results = await searchSymbols(searchQuery);
                    setSearchResults(results.results || []);
                    setShowSearchResults(true);
                } catch (err) {
                    console.error('Search error:', err);
                } finally {
                    setLoading(false);
                }
            }, 300);

            return () => clearTimeout(timer);
        } else {
            setSearchResults([]);
            setShowSearchResults(false);
        }
    }, [searchQuery]);

    const handleAddStock = async (stock) => {
        console.log('🚀 handleAddStock triggered for:', stock.symbol, stock.token);

        // Close menu immediately for instant feedback
        setSearchQuery('');
        setShowSearchResults(false);

        try {
            console.log('📡 Calling addToWatchlist API...');
            const response = await addToWatchlist(sessionId, stock.symbol, stock.token, stock.exch_seg, clientId);
            console.log('✅ API Success:', response);

            // Add to local state using returned stock from backend if available
            const newStock = response.stock || {
                symbol: stock.symbol,
                token: stock.token,
                exch_seg: stock.exch_seg,
                ltp: 0,
                pdc: 0,
                pdh: 0,
                pdl: 0,
                loading: true
            };

            setWatchlist(prev => {
                // Prevent duplicates
                if (prev.some(s => s.token === newStock.token)) return prev;
                return [...prev, newStock];
            });

            toast.success(`${stock.symbol} added to watchlist`);
        } catch (err) {
            console.error('Add stock error:', err);
            toast.error(err.response?.data?.detail || 'Failed to add stock');
        }
    };

    const handleRemoveStock = async (token) => {
        try {
            await removeFromWatchlist(sessionId, token, clientId);
            setWatchlist(watchlist.filter(s => s.token !== token));
            setSelectedStock(null);
            toast.success('Stock removed');
        } catch (err) {
            console.error('Remove stock error:', err);
            toast.error('Failed to remove stock');
        }
    };

    const handleRefresh = async () => {
        try {
            setRefreshing(true);
            await refreshWatchlist(sessionId, clientId);
            toast.success('Refresh started');
        } catch (err) {
            console.error('Refresh error:', err);
            toast.error('Failed to refresh');
        } finally {
            setRefreshing(false);
        }
    };

    // Corrected polling logic using useEffect
    useEffect(() => {
        if (!sessionId || !isVisible) return;

        const pollInterval = setInterval(async () => {
            try {
                const data = await getWatchlist(sessionId, clientId);
                if (data.watchlist) {
                    setWatchlist(data.watchlist);
                }
            } catch (err) {
                console.error('Watchlist Poll error:', err);
            }
        }, 10000); // Poll every 10s (increased from 5s for mobile efficiency)

        return () => clearInterval(pollInterval);
    }, [sessionId, setWatchlist, isVisible]);


    // Apply sorting only
    let filteredWatchlist = [...watchlist];

    // Sorting
    if (sortBy === 'sym_az') {
        filteredWatchlist.sort((a, b) => a.symbol.localeCompare(b.symbol));
    } else if (sortBy === 'sym_za') {
        filteredWatchlist.sort((a, b) => b.symbol.localeCompare(a.symbol));
    } else if (sortBy === 'price_low') {
        filteredWatchlist.sort((a, b) => a.ltp - b.ltp);
    } else if (sortBy === 'price_high') {
        filteredWatchlist.sort((a, b) => b.ltp - a.ltp);
    }

    // Track LTP changes for sparkline when a stock is selected
    useEffect(() => {
        if (!selectedStock) { setSparkData([]); return; }
        const current = watchlist.find(s => s.token === selectedStock.token);
        if (!current || current.ltp === undefined) return;
        setSparkData(prev => {
            const next = [...prev, current.ltp];
            return next.length > 20 ? next.slice(-20) : next;
        });
    }, [watchlist, selectedStock?.token]);

    // Reset sparkline when modal opens for a new stock
    useEffect(() => {
        setSparkData([]);
    }, [selectedStock?.token]);

    // Mini SVG sparkline component
    const Sparkline = ({ data, width = 320, height = 80 }) => {
        if (!data || data.length < 2) {
            return (
                <div style={{ width, height, display:'flex', alignItems:'center', justifyContent:'center' }}>
                    <span style={{ fontSize:'11px', color:'#555' }}>Waiting for live ticks…</span>
                </div>
            );
        }
        const min   = Math.min(...data);
        const max   = Math.max(...data);
        const range = max - min || 1;
        const pad   = 6;
        const w     = width  - pad * 2;
        const h     = height - pad * 2;
        const pts   = data.map((v, i) => {
            const x = pad + (i / (data.length - 1)) * w;
            const y = pad + (1 - (v - min) / range) * h;
            return `${x},${y}`;
        });
        const polyline = pts.join(' ');
        const isUp     = data[data.length - 1] >= data[0];
        const color    = isUp ? '#26a69a' : '#ef5350';
        const fillColor = isUp ? 'rgba(38,166,154,0.12)' : 'rgba(239,83,80,0.12)';
        // Closed path for fill: go to bottom-right, bottom-left
        const lastPt = pts[pts.length - 1].split(',');
        const firstPt = pts[0].split(',');
        const fillPath = `M ${polyline.replace(/,/g,' L ').replace(/ /g,' ')} L ${lastPt[0]} ${height - pad} L ${firstPt[0]} ${height - pad} Z`;

        return (
            <svg width={width} height={height} style={{ display:'block' }}>
                <defs>
                    <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                        <stop offset="100%" stopColor={color} stopOpacity="0.02" />
                    </linearGradient>
                </defs>
                <path d={fillPath} fill="url(#spark-grad)" />
                <polyline points={polyline} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                {/* Last price dot */}
                <circle cx={pts[pts.length-1].split(',')[0]} cy={pts[pts.length-1].split(',')[1]}
                    r="3" fill={color} />
            </svg>
        );
    };

    return (
        <div className="w-full space-y-2">
            {/* Search */}
            <div className="px-0">
                <div className="bg-[var(--bg-secondary)] p-2 md:rounded-2xl border border-[var(--border-color)] shadow-sm">
                    <div className="relative">
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search companies to invest or trade"
                            className="w-full pl-9 pr-10 py-2 bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] text-xs focus:outline-none focus:border-[var(--accent-blue)] placeholder:text-gray-500"
                        />
                        {loading && (
                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                <svg className="animate-spin h-5 w-5 text-[#667EEA]" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                            </div>
                        )}

                        {/* Search Results Dropdown */}
                        {showSearchResults && searchResults.length > 0 && (
                            <div className="absolute top-full left-0 right-0 mt-2 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-2xl max-h-60 overflow-y-auto z-50 backdrop-blur-xl">
                                {searchResults.map((stock) => (
                                    <div
                                        key={stock.token}
                                        onClick={() => handleAddStock(stock)}
                                        className="w-full flex items-center justify-between px-4 py-3 hover:bg-[var(--accent-blue)]/10 transition-colors border-b border-[var(--border-color)] last:border-0 cursor-pointer group"
                                    >
                                        <div className="flex-1">
                                            <div className="text-[var(--text-primary)] font-medium group-hover:text-[var(--accent-blue)] transition-colors">{stock.symbol}</div>
                                            <div className="text-[10px] text-[var(--text-muted)] font-mono">TOKEN: {stock.token}</div>
                                        </div>
                                        <button
                                            className="px-3 py-1.5 bg-[#667EEA] hover:bg-blue-600 text-white text-[10px] font-bold rounded-md shadow-lg transition-all active:scale-95 flex items-center gap-1"
                                        >
                                            <span>✚</span>
                                            <span>ADD</span>
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Refresh Button and Sort */}
            <div className="flex justify-between items-center px-2">
                <div className="flex items-center gap-2">
                    <div className="text-gray-400 text-[10px] uppercase font-bold tracking-widest">
                        {watchlist.length} Stocks
                    </div>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] text-[10px] font-bold focus:outline-none focus:border-[var(--accent-blue)]"
                    >
                        <option value="none">Sort</option>
                        <option value="sym_az">A-Z</option>
                        <option value="sym_za">Z-A</option>
                        <option value="price_low">Price Low</option>
                        <option value="price_high">Price High</option>
                    </select>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={refreshing}
                    className="px-3 py-1.5 bg-[var(--accent-blue)]/10 hover:bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] text-[10px] font-bold rounded-lg transition-all border border-[var(--accent-blue)]/20 flex items-center gap-1.5"
                >
                    <svg className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh
                </button>
            </div>

            {/* Watchlist */}
            <div className="w-full">
                {filteredWatchlist.length === 0 ? (
                    <div className="p-12 text-center bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] m-2">
                        <div className="text-4xl mb-4 opacity-10">🔍</div>
                        <p className="text-[var(--text-muted)] text-sm">Watchlist is empty</p>
                    </div>
                ) : (
                    <div className="flex flex-col gap-[1px] bg-[var(--border-color)]/20 px-0">
                        <AnimatePresence mode="popLayout">
                            {filteredWatchlist.map((stock) => {
                                const changeValue = stock.ltp - stock.pdc;
                                const changePercent = stock.pdc ? (changeValue / stock.pdc) * 100 : 0;
                                const isPositive = changeValue >= 0;

                                return (
                                    <motion.div
                                        key={stock.token}
                                        layout
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        exit={{ opacity: 0 }}
                                        onClick={() => setSelectedStock(stock)}
                                        className="bg-[var(--bg-secondary)] p-3 hover:bg-[var(--bg-primary)] transition-all cursor-pointer relative overflow-hidden active:bg-[var(--accent-blue)]/5 flex items-center justify-between border-l-4 border-l-transparent hover:border-l-[var(--accent-blue)]"
                                        style={{ borderLeftColor: isPositive ? 'var(--success-neon)' : 'var(--danger-neon)' }}
                                    >
                                        <div className="flex flex-col gap-0.5">
                                            <div className="flex items-center gap-1.5">
                                                <h3 className="text-[var(--text-primary)] font-bold text-sm tracking-tight">{stock.symbol}</h3>
                                                <span className="text-[8px] font-bold text-[var(--text-muted)] uppercase tracking-widest">{stock.exch_seg || 'NSE'}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-[9px] text-[var(--accent-blue)] font-bold">H: {stock.pdh?.toFixed(1)}</span>
                                                <span className="text-[9px] text-orange-400 font-bold">L: {stock.pdl?.toFixed(1)}</span>
                                            </div>
                                        </div>

                                        <div className="text-right flex flex-col items-end">
                                            <div className={`text-base font-bold tabular-nums tracking-tight ${isPositive ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                                {stock.ltp?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
                                            </div>
                                            <div className={`text-[10px] font-bold flex items-center gap-1 ${isPositive ? 'text-[var(--success-neon)]/90' : 'text-[var(--danger-neon)]/90'}`}>
                                                {isPositive ? '+' : ''}{changeValue.toFixed(2)} ({changePercent.toFixed(2)}%)
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>

            {/* Stock Details Modal */}
            {selectedStock && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50" onClick={() => setSelectedStock(null)}>
                    <div className="bg-[var(--bg-card)] w-full max-w-sm rounded-xl border border-[var(--border-color)] shadow-xl p-4 space-y-4" onClick={e => e.stopPropagation()}>
                        <div className="flex justify-between items-start">
                            <div>
                                <h3 className="text-xl font-bold text-[var(--text-primary)]">{selectedStock.symbol}</h3>
                                <p className="text-sm text-[var(--text-muted)]">Token: {selectedStock.token}</p>
                            </div>
                            <button onClick={() => setSelectedStock(null)} className="text-gray-400 hover:text-white p-1 bg-white/5 rounded-full transition-colors">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Live Sparkline */}
                        <div className="w-full bg-[var(--bg-primary)] rounded-xl border border-[var(--border-color)] overflow-hidden">
                            <div className="flex items-center justify-between px-3 pt-2 pb-1">
                                <span className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Live Ticks</span>
                                <span className="text-[9px] font-bold text-[var(--text-muted)]">{sparkData.length}/20</span>
                            </div>
                            <div className="px-1 pb-2">
                                <Sparkline data={sparkData} width={312} height={72} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 py-2">
                            <div className="bg-[var(--bg-secondary)] p-3 rounded-lg border border-[var(--border-color)]">
                                <div className="text-[var(--text-muted)] text-xs text-center">LTP</div>
                                <div className={`text-xl font-bold text-center ${selectedStock.ltp - selectedStock.pdc >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    ₹{selectedStock.ltp?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[var(--bg-secondary)] p-3 rounded-lg border border-[var(--border-color)]">
                                <div className="text-[var(--text-muted)] text-xs text-center">Change</div>
                                <div className={`text-xl font-bold text-center ${(selectedStock.ltp - selectedStock.pdc) >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    {selectedStock.ltp - selectedStock.pdc >= 0 ? '+' : ''}{(selectedStock.ltp - selectedStock.pdc).toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[var(--bg-primary)] p-3 rounded-lg border border-[var(--border-color)]">
                                <div className="text-[var(--text-muted)] text-xs text-center">PDC</div>
                                <div className="text-lg font-semibold text-[var(--text-primary)] text-center">
                                    ₹{selectedStock.pdc?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[var(--bg-primary)] p-3 rounded-lg border border-[var(--border-color)]">
                                <div className="text-[var(--text-muted)] text-xs text-center uppercase tracking-tighter">High ({referenceDate})</div>
                                <div className="text-lg font-semibold text-[var(--text-primary)] text-center">
                                    ₹{selectedStock.pdh?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[var(--bg-primary)] p-3 rounded-lg border border-[var(--border-color)] col-span-2">
                                <div className="text-[var(--text-muted)] text-xs text-center uppercase tracking-tighter">Low ({referenceDate})</div>
                                <div className="text-lg font-semibold text-[var(--text-primary)] text-center">
                                    ₹{selectedStock.pdl?.toFixed(2)}
                                </div>
                            </div>
                        </div>

                        <div className="flex flex-col gap-3">
                            <div className="flex items-center gap-2 bg-[var(--bg-primary)] p-2 rounded-lg border border-[var(--border-color)]/30 self-start">
                                <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Qty</label>
                                <input
                                    type="number"
                                    value={manualQty}
                                    onChange={(e) => setManualQty(e.target.value)}
                                    className="w-16 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded px-2 py-1 text-center text-sm text-[var(--text-primary)] font-bold outline-none focus:border-[var(--accent-blue)]"
                                />
                            </div>

                            <div className="flex gap-2 h-12 w-full">
                                <button
                                    onClick={() => { if (onOpenInChart) onOpenInChart(selectedStock); setSelectedStock(null); }}
                                    className="w-12 bg-[#7c6af5] hover:bg-[#6a58e0] text-white rounded-lg flex items-center justify-center transition-colors"
                                    title="Open in Astro Chart"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                                    </svg>
                                </button>
                                <button
                                    onClick={async () => {
                                        const price = parseFloat(selectedStock.ltp || selectedStock.close || 0);
                                        if (price <= 0) {
                                            toast.error('Invalid Price (0)');
                                            return;
                                        }
                                        try {
                                            await manualTrade(sessionId, selectedStock.symbol, selectedStock.token, price, 'BUY', manualQty);
                                            toast.success(`Bought ${selectedStock.symbol}`);
                                            setSelectedStock(null);
                                        } catch (e) {
                                            console.error(e);
                                            toast.error(e.response?.data?.detail || e.message || 'Buy Failed');
                                        }
                                    }}
                                    className="flex-1 bg-[#48BB78] hover:bg-[#38A169] text-white rounded-lg font-bold transition-colors shadow-lg shadow-green-900/20 text-xl"
                                >
                                    B
                                </button>
                                <button
                                    onClick={async () => {
                                        const price = parseFloat(selectedStock.ltp || selectedStock.close || 0);
                                        if (price <= 0) {
                                            toast.error('Invalid Price (0)');
                                            return;
                                        }
                                        try {
                                            await manualTrade(sessionId, selectedStock.symbol, selectedStock.token, price, 'SELL', manualQty);
                                            toast.success(`Sold ${selectedStock.symbol}`);
                                            setSelectedStock(null);
                                        } catch (e) {
                                            console.error(e);
                                            toast.error(e.response?.data?.detail || e.message || 'Sell Failed');
                                        }
                                    }}
                                    className="flex-1 bg-[#F56565] hover:bg-[#E53E3E] text-white rounded-lg font-bold transition-colors shadow-lg shadow-red-900/20 text-xl"
                                >
                                    S
                                </button>
                                <button
                                    onClick={() => handleRemoveStock(selectedStock.token)}
                                    className="w-12 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white rounded-lg font-semibold transition-all flex items-center justify-center border border-red-500/20"
                                    title="Remove from Watchlist"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default WatchlistTab;