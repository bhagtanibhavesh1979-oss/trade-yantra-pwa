import { useState, useEffect } from 'react';
import { searchSymbols, addToWatchlist, removeFromWatchlist, refreshWatchlist, getWatchlist } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

function WatchlistTab({ session, watchlist, setWatchlist, referenceDate, isVisible = true }) {
    const sessionId = session?.sessionId;
    const clientId = session?.clientId;
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [showSearchResults, setShowSearchResults] = useState(false);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [selectedStock, setSelectedStock] = useState(null);

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
            await removeFromWatchlist(sessionId, token);
            setWatchlist(watchlist.filter(s => s.token !== token));
            setSelectedStock(null);
        } catch (err) {
            console.error('Remove stock error:', err);
        }
    };

    const handleRefresh = async () => {
        try {
            setRefreshing(true);
            await refreshWatchlist(sessionId);
            // Watchlist will be updated by the useEffect polling
        } catch (err) {
            console.error('Refresh error:', err);
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

    return (
        <div className="w-full space-y-4">
            {/* Search */}
            <div className="bg-[#222844] md:rounded-lg p-2 md:p-3 border-b md:border border-[#2D3748]">
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
                        placeholder="Search symbols (e.g., TATA, RELIANCE)..."
                        className="w-full pl-10 pr-10 py-2 bg-[#0A0E27] border border-[#2D3748] rounded-lg text-white focus:outline-none focus:border-[#667EEA]"
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
                        <div className="absolute top-full left-0 right-0 mt-1 bg-[#222844] border border-[#2D3748] rounded-lg shadow-xl max-h-60 overflow-y-auto z-10">
                            {searchResults.map((stock) => (
                                <div
                                    key={stock.token}
                                    onClick={() => handleAddStock(stock)}
                                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#2D3748] transition-colors border-b border-[#2D3748]/50 last:border-0 cursor-pointer group"
                                >
                                    <div className="flex-1">
                                        <div className="text-white font-medium group-hover:text-[#667EEA] transition-colors">{stock.symbol}</div>
                                        <div className="text-[10px] text-gray-500 font-mono">TOKEN: {stock.token}</div>
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

            {/* Refresh Button and Sort */}
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="text-gray-400 text-xs">
                        {watchlist.length} stocks • Ref: <span className="text-[#667EEA] font-bold">{referenceDate}</span>
                    </div>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="px-3 py-2 bg-[#222844] border border-[#2D3748] rounded-lg text-white text-sm focus:outline-none focus:border-[#667EEA]"
                    >
                        <option value="none">Sort: Default</option>
                        <option value="sym_az">Sort: A-Z</option>
                        <option value="sym_za">Sort: Z-A</option>
                        <option value="price_low">Sort: Price Low</option>
                        <option value="price_high">Sort: Price High</option>
                    </select>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={refreshing}
                    className="px-4 py-2 bg-[#667EEA] hover:bg-[#5568D3] text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                    <svg className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {refreshing ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {/* Watchlist */}
            <div className="w-full">
                {filteredWatchlist.length === 0 ? (
                    <div className="p-8 text-center bg-[#222844] rounded-xl border border-[#2D3748] m-2">
                        <p className="text-gray-400">No stocks in watchlist. Search and add symbols above.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 p-2">
                        <AnimatePresence mode="popLayout">
                            {filteredWatchlist.map((stock) => {
                                const changeValue = stock.ltp - stock.pdc;
                                const changePercent = stock.pdc ? (changeValue / stock.pdc) * 100 : 0;
                                const isPositive = changeValue >= 0;

                                return (
                                    <motion.div
                                        key={stock.token}
                                        layout
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        onClick={() => setSelectedStock(stock)}
                                        className="glass-card p-4 rounded-xl shadow-lg hover:border-[#667EEA]/50 transition-all cursor-pointer group relative overflow-hidden active:scale-[0.98]"
                                    >
                                        {/* Background Glow Effect on Hover */}
                                        <div className="absolute inset-0 bg-gradient-to-br from-[#667EEA]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                        <div className="flex justify-between items-start relative z-10">
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <h3 className="text-[var(--text-primary)] font-bold text-lg leading-tight">{stock.symbol}</h3>
                                                    <a
                                                        href={`https://www.tradingview.com/chart/?symbol=NSE:${stock.symbol.replace('-EQ', '')}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        onClick={(e) => e.stopPropagation()}
                                                        className="text-gray-400 hover:text-[#667EEA] transition-colors p-1"
                                                        title="Open TradingView"
                                                    >
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                                            <path d="M14 3h7v7h-2V6.41l-9 9L8.59 14l9-9H14V3zM5 5h5V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-5h-2v5H5V5z" />
                                                        </svg>
                                                    </a>
                                                </div>
                                                <div className="text-[10px] text-gray-400 font-mono">TOKEN: {stock.token}</div>
                                            </div>

                                            <div className="text-right">
                                                <motion.div
                                                    key={stock.ltp}
                                                    initial={{ color: isPositive ? '#00FF94' : '#FF4D4D' }}
                                                    animate={{
                                                        scale: [1, 1.05, 1],
                                                        transition: { duration: 0.3 }
                                                    }}
                                                    className={`text-xl font-black ${isPositive ? 'price-up' : 'price-down'}`}
                                                >
                                                    ₹{stock.ltp?.toFixed(2) || '0.00'}
                                                </motion.div>
                                                <div className={`text-xs font-semibold ${isPositive ? 'text-[#00FF94]/80' : 'text-[#FF4D4D]/80'}`}>
                                                    {isPositive ? '▲' : '▼'} {Math.abs(changeValue).toFixed(2)} ({Math.abs(changePercent).toFixed(2)}%)
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-[#2D3748]/50 relative z-10">
                                            <div className="text-center">
                                                <div className="text-[9px] text-gray-500 uppercase tracking-wider">P.Close</div>
                                                <div className="text-xs text-[var(--text-secondary)] font-medium">{stock.pdc?.toFixed(2) || '0.00'}</div>
                                            </div>
                                            <div className="text-center">
                                                <div className="text-[9px] text-[#667EEA] uppercase tracking-wider">High</div>
                                                <div className="text-xs text-[var(--text-secondary)] font-medium">{stock.pdh?.toFixed(2) || '0.00'}</div>
                                            </div>
                                            <div className="text-center">
                                                <div className="text-[9px] text-[#667EEA] uppercase tracking-wider">Low</div>
                                                <div className="text-xs text-[var(--text-secondary)] font-medium">{stock.pdl?.toFixed(2) || '0.00'}</div>
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
                    <div className="bg-[#222844] w-full max-w-sm rounded-xl border border-[#2D3748] shadow-2xl p-4 space-y-4" onClick={e => e.stopPropagation()}>
                        <div className="flex justify-between items-start">
                            <div>
                                <h3 className="text-xl font-bold text-white">{selectedStock.symbol}</h3>
                                <p className="text-sm text-gray-400">Token: {selectedStock.token}</p>
                            </div>
                            <button onClick={() => setSelectedStock(null)} className="text-gray-400 hover:text-white p-1 bg-white/5 rounded-full transition-colors">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* TradingView Mini Chart Widget */}
                        <div className="w-full h-48 bg-[#1A1F3A] rounded-xl overflow-hidden border border-[#2D3748] relative">
                            <iframe
                                key={selectedStock.token}
                                src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_76230&symbol=NSE%3A${encodeURIComponent(selectedStock.symbol.replace(/-EQ$/, ''))}&interval=D&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=f1f3f6&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FKolkata&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=in&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=NSE%3A${encodeURIComponent(selectedStock.symbol.replace(/-EQ$/, ''))}`}
                                width="100%"
                                height="100%"
                                frameBorder="0"
                                allowTransparency="true"
                                scrolling="no"
                                allowFullScreen
                            ></iframe>
                        </div>

                        <div className="grid grid-cols-2 gap-4 py-2">
                            <div className="bg-[#1A1F3A] p-3 rounded-lg border border-[#2D3748]">
                                <div className="text-gray-400 text-xs text-center">LTP</div>
                                <div className={`text-xl font-bold text-center ${selectedStock.ltp - selectedStock.pdc >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    ₹{selectedStock.ltp?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg border border-[#2D3748]">
                                <div className="text-gray-400 text-xs text-center">Change</div>
                                <div className={`text-xl font-bold text-center ${(selectedStock.ltp - selectedStock.pdc) >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    {selectedStock.ltp - selectedStock.pdc >= 0 ? '+' : ''}{(selectedStock.ltp - selectedStock.pdc).toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg border border-[#2D3748]">
                                <div className="text-gray-400 text-xs text-center">PDC</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdc?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg border border-[#2D3748]">
                                <div className="text-gray-400 text-xs text-center uppercase tracking-tighter">High ({referenceDate})</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdh?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg border border-[#2D3748] col-span-2">
                                <div className="text-gray-400 text-xs text-center uppercase tracking-tighter">Low ({referenceDate})</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdl?.toFixed(2)}
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <a
                                href={`https://www.tradingview.com/chart/?symbol=NSE:${selectedStock.symbol.replace('-EQ', '')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex-1 py-3 bg-[#667EEA] hover:bg-blue-600 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                                </svg>
                                TradingView
                            </a>
                            <button
                                onClick={() => handleRemoveStock(selectedStock.token)}
                                className="px-4 py-3 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white rounded-lg font-semibold transition-all flex items-center justify-center border border-red-500/20"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default WatchlistTab;
