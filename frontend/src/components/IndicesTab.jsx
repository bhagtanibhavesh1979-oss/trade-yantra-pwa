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
        <div className="max-w-4xl mx-auto space-y-4">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div className="text-gray-400 text-sm">
                    Live Market Indices
                </div>
                <button
                    onClick={fetchIndices}
                    disabled={loading}
                    className="px-4 py-2 bg-[#667EEA] hover:bg-[#5568D3] text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                    <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {/* Indices Table */}
            <div className="bg-[#222844] rounded-lg border border-[#2D3748] overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-[#1A1F3A] border-b border-[#2D3748]">
                                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-300">Index</th>
                                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-300">LTP</th>
                                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-300">PDC</th>
                                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-300">Change</th>
                                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-300">Change %</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#2D3748]">
                            {indices.map((index) => {
                                const change = index.ltp - index.pdc;
                                const changePercent = index.pdc > 0
                                    ? ((index.ltp - index.pdc) / index.pdc * 100)
                                    : 0;
                                const isPositive = change >= 0;

                                return (
                                    <tr
                                        key={index.token}
                                        className="hover:bg-[#2D3748] transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <div className="text-white font-bold">{index.symbol}</div>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <div className="text-white font-bold text-lg">
                                                {index.ltp?.toFixed(2) || '0.00'}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-right text-gray-300">
                                            {index.pdc?.toFixed(2) || '0.00'}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <span className={`font-semibold ${isPositive ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                                {isPositive ? '+' : ''}{change.toFixed(2)}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <span className={`font-semibold ${isPositive ? 'text-[#48BB78]' : 'text-[#F56565]'}`}>
                                                {isPositive ? '+' : ''}{changePercent.toFixed(2)}%
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

export default IndicesTab;
