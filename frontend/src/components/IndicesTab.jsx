import { useState, useEffect } from 'react';

function IndicesTab({ sessionId }) {
    const [indices, setIndices] = useState([
        { symbol: 'NIFTY 50', token: '99926000', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY BANK', token: '99926009', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY IT', token: '99926013', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY PHARMA', token: '99926023', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY AUTO', token: '99926003', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY FMCG', token: '99926011', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY METAL', token: '99926015', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY REALTY', token: '99926024', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY ENERGY', token: '99926010', ltp: 0, pdc: 0 },
        { symbol: 'NIFTY FIN SERVICE', token: '99926012', ltp: 0, pdc: 0 },
    ]);
    const [loading, setLoading] = useState(false);

    const fetchIndices = async () => {
        setLoading(true);
        try {
            // Fetch from backend API (we'll create this endpoint)
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/api/indices/${sessionId}`);
            if (response.ok) {
                const data = await response.json();
                setIndices(data.indices || indices);
            }
        } catch (err) {
            console.error('Failed to fetch indices:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (sessionId) {
            fetchIndices();
            // Refresh every 30 seconds
            const interval = setInterval(fetchIndices, 30000);
            return () => clearInterval(interval);
        }
    }, [sessionId]);

    return (
        <div className="w-full space-y-4">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div className="text-[var(--text-secondary)] text-sm">
                    Live Market Indices
                </div>
                <button
                    onClick={fetchIndices}
                    disabled={loading}
                    className="px-4 py-2 bg-[var(--accent-blue)] hover:brightness-110 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                    <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {/* Indices Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {indices.map((index) => {
                    const change = index.ltp - index.pdc;
                    const changePercent = index.pdc > 0
                        ? ((index.ltp - index.pdc) / index.pdc * 100)
                        : 0;
                    const isPositive = change >= 0;

                    return (
                        <div
                            key={index.token}
                            className="glass-card p-4 rounded-xl shadow-sm hover:border-[var(--accent-blue)] transition-all group"
                        >
                            <div className="flex justify-between items-start mb-2">
                                <h3 className="text-[var(--text-primary)] font-bold text-lg">{index.symbol}</h3>
                                <div className={`text-xl font-bold ${isPositive ? 'price-up' : 'price-down'}`}>
                                    {index.ltp?.toFixed(2) || '0.00'}
                                </div>
                            </div>

                            <div className="flex justify-between items-end">
                                <div>
                                    <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">P.Close</div>
                                    <div className="text-sm font-medium text-[var(--text-secondary)]">{index.pdc?.toFixed(2) || '0.00'}</div>
                                </div>
                                <div className={`text-sm font-semibold flex items-center gap-1 ${isPositive ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                                    <span>{isPositive ? '▲' : '▼'}</span>
                                    {Math.abs(change).toFixed(2)} ({Math.abs(changePercent).toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default IndicesTab;
