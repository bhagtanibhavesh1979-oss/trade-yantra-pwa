import { useState, useEffect } from 'react';
import { searchSymbols, addToWatchlist, removeFromWatchlist, refreshWatchlist, getWatchlist } from '../services/api';

function WatchlistTab({ sessionId, watchlist, setWatchlist }) {
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
        try {
            await addToWatchlist(sessionId, stock.symbol, stock.token, stock.exch_seg);

            // Add to local state
            setWatchlist([...watchlist, {
                symbol: stock.symbol,
                token: stock.token,
                exch_seg: stock.exch_seg,
                ltp: 0,
                pdc: 0,
                pdh: 0,
                pdl: 0,
            }]);

            setSearchQuery('');
            setShowSearchResults(false);

            // Auto-refresh to fetch prices in background
            setTimeout(() => {
                handleRefresh();
            }, 500);
        } catch (err) {
            console.error('Add stock error:', err);
            alert(err.response?.data?.detail || 'Failed to add stock');
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
            // Poll for updated prices
            pollForUpdates();
        } catch (err) {
            console.error('Refresh error:', err);
        } finally {
            setRefreshing(false);
        }
    };

    const pollForUpdates = () => {
        // Poll every 5 seconds for updates (fallback for WebSocket)
        // Kept alive indefinitely in case WS fails
        const pollInterval = setInterval(async () => {
            try {
                // Only poll if tab is active (optimization could be added here to check visibility)
                const data = await getWatchlist(sessionId);
                if (data.watchlist) {
                    setWatchlist(() => {
                        // Merge strategies: only update if changed? 
                        // For now simple replacement is fine as React handles diffing
                        return data.watchlist;
                    });
                }
            } catch (err) {
                console.error('Poll error:', err);
                // Don't clear interval on error, retry next time
            }
        }, 5000); // Increased to 5s to reduce load

        // Return cleanup function if we were in useEffect, 
        // but here we just let it run. In a real app we should manage this better.
        // For now, let's at least clear it after 1 minute to avoid eternal zombies if component re-renders
        // setTimeout(() => clearInterval(pollInterval), 60000);
    };


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
                                <button
                                    key={stock.token}
                                    onClick={() => handleAddStock(stock)}
                                    className="w-full px-4 py-2 text-left hover:bg-[#2D3748] transition-colors"
                                >
                                    <div className="text-white font-medium">{stock.symbol}</div>
                                    <div className="text-xs text-gray-400">Token: {stock.token}</div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Refresh Button and Sort */}
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="text-gray-400 text-sm">
                        {watchlist.length} stocks
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
            <div className="bg-[#222844] md:rounded-lg border-t border-b md:border border-[#2D3748] overflow-hidden w-full md:max-w-4xl mx-auto">
                {filteredWatchlist.length === 0 ? (
                    <div className="p-8 text-center">
                        <p className="text-gray-400">No stocks in watchlist. Search and add symbols above.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-[#1A1F3A] border-b border-[#2D3748]">
                                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-300 w-[30%] border-r border-[#2D3748]">Symbol</th>
                                    <th className="px-2 py-3 text-center text-xs font-semibold text-gray-300 w-[20%] border-r border-[#2D3748]">LTP</th>
                                    <th className="px-2 py-3 text-center text-xs font-semibold text-gray-300 w-[12%] border-r border-[#2D3748]">PDC</th>
                                    <th className="px-2 py-3 text-center text-xs font-semibold text-gray-300 w-[12%] border-r border-[#2D3748]">High</th>
                                    <th className="px-2 py-3 text-center text-xs font-semibold text-gray-300 w-[12%] border-r border-[#2D3748]">Low</th>
                                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-300 w-[20%]">Chg</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#2D3748]">
                                {filteredWatchlist.map((stock) => {
                                    const changeValue = stock.ltp - stock.pdc;
                                    const isPositive = changeValue >= 0;

                                    return (
                                        <tr
                                            key={stock.token}
                                            onClick={() => setSelectedStock(stock)}
                                            className="hover:bg-[#2D3748] transition-colors cursor-pointer active:bg-[#4A5568]"
                                        >
                                            <td className="px-3 py-3 text-left border-r border-[#2D3748]">
                                                <div className="text-white font-bold text-sm">{stock.symbol}</div>
                                                <div className="text-[10px] text-gray-400">T: {stock.token}</div>
                                            </td>
                                            <td className="px-2 py-3 text-center border-r border-[#2D3748]">
                                                <div className={`font-bold text-sm ${isPositive ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                                    ₹{stock.ltp?.toFixed(2) || '0.00'}
                                                </div>
                                            </td>
                                            <td className="px-2 py-3 text-center text-[11px] text-gray-300 border-r border-[#2D3748]">
                                                {stock.pdc?.toFixed(2) || '0.00'}
                                            </td>
                                            <td className="px-2 py-3 text-center text-[11px] text-gray-300 border-r border-[#2D3748]">
                                                {stock.pdh?.toFixed(2) || '0.00'}
                                            </td>
                                            <td className="px-2 py-3 text-center text-[11px] text-gray-300 border-r border-[#2D3748]">
                                                {stock.pdl?.toFixed(2) || '0.00'}
                                            </td>
                                            <td className="px-3 py-3 text-center text-xs">
                                                <span className={`font-semibold ${isPositive ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                                    {isPositive ? '+' : ''}{changeValue.toFixed(2)}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
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
                            <button onClick={() => setSelectedStock(null)} className="text-gray-400 hover:text-white p-1">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="grid grid-cols-2 gap-4 py-2">
                            <div className="bg-[#1A1F3A] p-3 rounded-lg">
                                <div className="text-gray-400 text-xs text-center">LTP</div>
                                <div className={`text-xl font-bold text-center ${selectedStock.ltp - selectedStock.pdc >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    ₹{selectedStock.ltp?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg">
                                <div className="text-gray-400 text-xs text-center">Change</div>
                                <div className={`text-xl font-bold text-center ${(selectedStock.ltp - selectedStock.pdc) >= 0 ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                    {selectedStock.ltp - selectedStock.pdc >= 0 ? '+' : ''}{(selectedStock.ltp - selectedStock.pdc).toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg">
                                <div className="text-gray-400 text-xs text-center">PDC</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdc?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg">
                                <div className="text-gray-400 text-xs text-center">Prev High</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdh?.toFixed(2)}
                                </div>
                            </div>
                            <div className="bg-[#1A1F3A] p-3 rounded-lg">
                                <div className="text-gray-400 text-xs text-center">Prev Low</div>
                                <div className="text-lg font-semibold text-white text-center">
                                    ₹{selectedStock.pdl?.toFixed(2)}
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={() => handleRemoveStock(selectedStock.token)}
                            className="w-full py-3 bg-[#F56565] hover:bg-red-600 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Remove from Watchlist
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default WatchlistTab;
