import { useState } from 'react';
import { runBacktest } from '../services/api';
import toast from 'react-hot-toast';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const BacktestTab = ({ clientId, sessionId, watchlist }) => {
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState(null);

    // Initialize state, checking localStorage for blueprint_date
    const [params, setParams] = useState({
        token: '',
        symbol: '',
        blueprint_date: localStorage.getItem('blueprint_date') || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0], // Use saved date or default to yesterday
        start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0],
        interval: 'FIFTEEN_MINUTE',
        mode: 'DISCRETE',
        high: '',
        low: '',
        quantity: 100,
        target: '',
        target_type: 'AMOUNT',
        trade_type: 'INTRADAY',
        stop_loss: '',
        trailing_sl: '',
        buffer: 0.25,
        trigger_mode: 'CANDLE_CLOSE'
    });

    const handleRun = async () => {
        if (!params.token) {
            toast.error('Please select stock');
            return;
        }

        setLoading(true);
        try {
            const data = await runBacktest(sessionId, {
                ...params,
                high: params.high ? parseFloat(params.high) : 0,
                low: params.low ? parseFloat(params.low) : 0,
                target: params.target ? parseFloat(params.target) : null,
                stop_loss: params.stop_loss ? parseFloat(params.stop_loss) : null,
                trailing_sl: params.trailing_sl ? parseFloat(params.trailing_sl) : null
            }, clientId);
            setResults(data);
            toast.success('Simulation Complete!');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Simulation Failed');
        } finally {
            setLoading(false);
        }
    };

    const handleSelectStock = (stock) => {
        setParams(prev => ({
            ...prev,
            symbol: stock.symbol,
            token: stock.token,
            high: stock.pdh || '',
            low: stock.pdl || '',
            // REMOVED: blueprint_date reset. It now persists from state.
        }));
    };

    return (
        <div className="p-4 space-y-6 pb-24 max-w-4xl mx-auto">
            <div className="glass-card p-6 rounded-2xl border border-[var(--border-color)]">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-black flex items-center gap-2">
                        <span className="text-2xl">🧪</span> Strategy Lab 2.0
                    </h2>
                    <div className="flex items-center gap-1 bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)]">
                        {[
                            { label: '5m', value: 'FIVE_MINUTE' },
                            { label: '10m', value: 'TEN_MINUTE' },
                            { label: '15m', value: 'FIFTEEN_MINUTE' },
                            { label: '30m', value: 'THIRTY_MINUTE' }
                        ].map(tf => (
                            <button
                                key={tf.value}
                                onClick={() => setParams(prev => ({ ...prev, interval: tf.value }))}
                                className={`px-2 py-1 text-[10px] font-black rounded-lg transition-all ${params.interval === tf.value ? 'bg-[var(--accent-blue)] text-white shadow-lg' : 'text-gray-500 hover:text-gray-300'}`}
                            >
                                {tf.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    {/* Stock Selection */}
                    <div className="md:col-span-2">
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Choose Instrument</label>
                        <select
                            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl px-4 py-3 outline-none focus:border-[var(--accent-blue)]"
                            onChange={(e) => {
                                const stock = watchlist.find(s => s.token === e.target.value);
                                if (stock) handleSelectStock(stock);
                            }}
                            value={params.token}
                        >
                            <option value="">Select Stock from Watchlist</option>
                            {watchlist.map(s => (
                                <option key={s.token} value={s.token}>{s.symbol}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <details className="group mb-6">
                    <summary className="text-xs font-bold text-[var(--accent-blue)] uppercase cursor-pointer list-none flex items-center justify-between p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] hover:border-[var(--accent-blue)] transition-all select-none shadow-sm">
                        <span>⚙️ Configure Strategy Parameters (Expand to view Blueprint, Targets, etc.)</span>
                        <span className="group-open:rotate-180 transition-transform duration-300">▼</span>
                    </summary>
                    
                    <div className="space-y-6 pt-4 animate-in fade-in duration-300">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Blueprint Date */ }
                    <div className="bg-indigo-500/5 p-4 rounded-xl border border-indigo-500/20">
                        <label className="text-[10px] uppercase font-bold text-indigo-400 mb-2 block flex items-center gap-1">
                            <span>📅 Blueprint Reference Date</span>
                            <span className="text-[8px] bg-indigo-500/20 px-1 rounded text-indigo-300">SYSTEM USES H/L OF THIS DAY</span>
                        </label>
                        <input
                            type="date"
                            className="w-full bg-[var(--bg-secondary)] border border-indigo-500/30 rounded-xl px-4 py-3 outline-none focus:border-indigo-500 text-sm"
                            value={params.blueprint_date}
                            onChange={(e) => {
                                const newDate = e.target.value;
                                localStorage.setItem('blueprint_date', newDate);
                                setParams(prev => ({ ...prev, blueprint_date: newDate }));
                            }}
                        />
                    </div>

                    {/* Simulation Range */}
                    <div className="p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]">
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Simulation Date Range</label>
                        <div className="grid grid-cols-2 gap-2">
                            <input
                                type="date"
                                className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 outline-none focus:border-[var(--accent-blue)] text-xs"
                                value={params.start_date}
                                onChange={(e) => setParams(prev => ({ ...prev, start_date: e.target.value }))}
                            />
                            <input
                                type="date"
                                className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 outline-none focus:border-[var(--accent-blue)] text-xs"
                                value={params.end_date}
                                onChange={(e) => setParams(prev => ({ ...prev, end_date: e.target.value }))}
                            />
                        </div>
                    </div>

                    {/* Target Logic */}
                    <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-[var(--bg-secondary)]/50 rounded-xl border border-dashed border-[var(--border-color)]">
                        <div>
                            <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Quantity</label>
                            <input
                                type="number"
                                className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl px-4 py-3 outline-none"
                                value={params.quantity}
                                onChange={(e) => setParams(prev => ({ ...prev, quantity: e.target.value }))}
                            />
                        </div>
                        <div className="md:col-span-2">
                            <label className="text-[10px] uppercase font-bold text-[var(--success-neon)] mb-2 block flex justify-between">
                                <span>Profit Booking Strategy</span>
                                <span>Current: {params.target_type}</span>
                            </label>
                            <div className="flex gap-2">
                                <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)] flex-1">
                                    <button
                                        onClick={() => setParams(prev => ({ ...prev, target_type: 'AMOUNT' }))}
                                        className={`flex-1 py-2 text-[10px] font-black rounded-lg transition-all ${params.target_type === 'AMOUNT' ? 'bg-[var(--success-neon)] text-black' : 'text-gray-500'}`}
                                    >
                                        BY PROFIT ₹
                                    </button>
                                    <button
                                        onClick={() => setParams(prev => ({ ...prev, target_type: 'POINTS' }))}
                                        className={`flex-1 py-2 text-[10px] font-black rounded-lg transition-all ${params.target_type === 'POINTS' ? 'bg-[var(--accent-blue)] text-white' : 'text-gray-500'}`}
                                    >
                                        BY POINTS
                                    </button>
                                </div>
                                <input
                                    type="number"
                                    placeholder={params.target_type === 'AMOUNT' ? "e.g. 500" : "e.g. 5.0"}
                                    className="w-32 bg-[var(--bg-secondary)] border border-[var(--success-neon)]/30 rounded-xl px-4 py-3 outline-none focus:border-[var(--success-neon)]"
                                    value={params.target}
                                    onChange={(e) => setParams(prev => ({ ...prev, target: e.target.value }))}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Protection */}
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <label className="text-[10px] uppercase font-bold text-red-400 mb-2 block">Stop Loss (₹)</label>
                        <input
                            type="number"
                            placeholder="Optional"
                            className="w-full bg-[var(--bg-secondary)] border border-red-500/30 rounded-xl px-4 py-3 outline-none focus:border-red-500"
                            value={params.stop_loss}
                            onChange={(e) => setParams(prev => ({ ...prev, stop_loss: e.target.value }))}
                        />
                    </div>
                    <div>
                        <label className="text-[10px] uppercase font-bold text-orange-400 mb-2 block">Trailing SL (₹)</label>
                        <input
                            type="number"
                            placeholder="Optional"
                            className="w-full bg-[var(--bg-secondary)] border border-orange-500/30 rounded-xl px-4 py-3 outline-none focus:border-orange-500"
                            value={params.trailing_sl}
                            onChange={(e) => setParams(prev => ({ ...prev, trailing_sl: e.target.value }))}
                        />
                    </div>
                </div>

                {/* Trade Type and Mode Toggle */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Execution Mode</label>
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)]">
                            <button
                                onClick={() => setParams(prev => ({ ...prev, mode: 'DISCRETE' }))}
                                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${params.mode === 'DISCRETE' ? 'bg-[var(--accent-blue)] text-white shadow-lg' : 'text-gray-500'}`}
                            >
                                DISCRETE
                            </button>
                            <button
                                onClick={() => setParams(prev => ({ ...prev, mode: 'ZONE' }))}
                                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${params.mode === 'ZONE' ? 'bg-[var(--success-neon)] text-white shadow-lg' : 'text-gray-500'}`}
                            >
                                ZONE-BASED
                            </button>
                        </div>
                    </div>

                    <div>
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Trade Type (Product)</label>
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)]">
                            <button
                                onClick={() => setParams(prev => ({ ...prev, trade_type: 'INTRADAY' }))}
                                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${params.trade_type === 'INTRADAY' ? 'bg-orange-500 text-white shadow-lg' : 'text-gray-500'}`}
                            >
                                INTRADAY (MIS)
                            </button>
                            <button
                                onClick={() => setParams(prev => ({ ...prev, trade_type: 'POSITIONAL' }))}
                                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${params.trade_type === 'POSITIONAL' ? 'bg-purple-600 text-white shadow-lg' : 'text-gray-500'}`}
                            >
                                HOLDING (CNC)
                            </button>
                        </div>
                    </div>
                </div>

                {/* ADVANCED: Trigger & Sensitivity */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Trigger Logic</label>
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)]">
                            <button
                                onClick={() => setParams(prev => ({ ...prev, trigger_mode: 'CANDLE_CLOSE' }))}
                                className={`flex-1 py-2 text-[10px] font-black rounded-lg transition-all ${params.trigger_mode === 'CANDLE_CLOSE' ? 'bg-white text-black shadow-lg' : 'text-gray-500'}`}
                            >
                                CANDLE CLOSE
                            </button>
                            <button
                                onClick={() => setParams(prev => ({ ...prev, trigger_mode: 'INSTANT_TOUCH' }))}
                                className={`flex-1 py-2 text-[10px] font-black rounded-lg transition-all ${params.trigger_mode === 'INSTANT_TOUCH' ? 'bg-white text-black shadow-lg' : 'text-gray-500'}`}
                            >
                                INSTANT HIT
                            </button>
                        </div>
                    </div>

                    <div>
                        <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Wick Sensitivity (Buffer)</label>
                        <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)] overflow-x-auto scrollbar-hide gap-1 custom-scroll">
                            {[0.18, 0.25, 0.27, 0.30, 0.36, 0.45, 0.54, 0.63, 0.72, 0.81, 0.90, 1.0].map(b => (
                                <button
                                    key={b}
                                    onClick={() => setParams(prev => ({ ...prev, buffer: b }))}
                                    className={`min-w-[48px] px-3 py-2 text-[10px] font-black rounded-lg transition-all whitespace-nowrap ${params.buffer === b ? 'bg-yellow-500 text-black shadow-lg' : 'text-gray-500 hover:bg-[var(--bg-primary)]'}`}
                                >
                                    {b}%
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
                    </div>
                </details>

                <button
                    onClick={handleRun}
                    disabled={loading}
                    className="w-full mt-6 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-2xl font-black text-sm shadow-xl shadow-blue-500/20 hover:scale-[1.01] active:scale-[0.98] transition-all disabled:opacity-50"
                >
                    {loading ? 'SIMULATING TRADES...' : 'RUN BACKTEST SIMULATION'}
                </button>
            </div>

            {results && results.trades.length === 0 && (
                <div className="p-8 text-center glass-card rounded-2xl border border-yellow-500/30 bg-yellow-500/5">
                    <p className="text-yellow-400 font-bold">Simulation Complete: No Trades Triggered 🧊</p>
                    <p className="text-xs text-gray-500 mt-2">The price never hit your Blueprint levels during this period.</p>
                </div>
            )}

            {results && results.trades.length > 0 && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex justify-between items-end px-2">
                        <h3 className="text-xs font-black text-gray-500 uppercase tracking-[0.2em]">Simulation Results</h3>
                        <span className="text-[10px] text-[var(--accent-blue)] font-bold">{results.summary.period}</span>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
                        <div className="glass-card p-3 rounded-2xl border border-[var(--border-color)]">
                            <div className="text-[10px] uppercase text-gray-500 font-bold mb-1">Gross P&L</div>
                            <div className={`text-lg lg:text-xl font-black ${results.summary.total_pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-red-500'}`}>
                                ₹{results.summary.total_pnl}
                            </div>
                        </div>
                        <div className="glass-card p-3 rounded-2xl border border-red-500/20 bg-red-500/5">
                            <div className="text-[10px] uppercase text-red-400 font-bold mb-1">Est. Brokerage</div>
                            <div className="text-lg lg:text-xl font-black text-red-400">
                                -₹{results.summary.total_brokerage}
                            </div>
                        </div>
                        <div className="glass-card p-3 rounded-2xl border-[var(--success-neon)]/30 bg-[var(--success-neon)]/5 col-span-2">
                            <div className="text-[10px] uppercase text-[var(--success-neon)] font-bold mb-1">Net Profit After Taxes</div>
                            <div className={`text-xl lg:text-2xl font-black ${results.summary.net_pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-red-500'}`}>
                                ₹{results.summary.net_pnl}
                            </div>
                        </div>
                        <div className="glass-card p-3 rounded-2xl border border-[var(--border-color)]">
                            <div className="text-[10px] uppercase text-gray-500 font-bold mb-1">Win Rate</div>
                            <div className="text-lg lg:text-xl font-black text-[var(--accent-blue)]">{results.summary.win_rate}%</div>
                        </div>
                        <div className="glass-card p-3 rounded-2xl border border-[var(--border-color)]">
                            <div className="text-[10px] uppercase text-gray-500 font-bold mb-1">Accuracy</div>
                            <div className="text-lg lg:text-xl font-black text-[var(--text-primary)]">{results.summary.wins}W - {results.summary.losses}L</div>
                        </div>
                    </div>

                    {/* Equity Curve */}
                    <div className="glass-card p-6 rounded-2xl border border-[var(--border-color)]">
                        <h3 className="text-xs font-bold text-gray-500 uppercase mb-4 tracking-widest">Simulation Equity Curve</h3>
                        <div className="h-64 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={results.equity_curve}>
                                    <defs>
                                        <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
                                            {(() => {
                                                if (!results.equity_curve || results.equity_curve.length === 0) return null;
                                                const balances = results.equity_curve.map(d => d.balance);
                                                const dataMax = Math.max(...balances);
                                                const dataMin = Math.min(...balances);

                                                if (dataMax <= 0) {
                                                    return <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />;
                                                }
                                                if (dataMin >= 0) {
                                                    return <stop offset="0%" stopColor="#4ade80" stopOpacity={0.4} />;
                                                }

                                                const offset = (dataMax / (dataMax - dataMin));
                                                return (
                                                    <>
                                                        <stop offset={offset} stopColor="#4ade80" stopOpacity={0.4} />
                                                        <stop offset={offset} stopColor="#ef4444" stopOpacity={0.4} />
                                                    </>
                                                );
                                            })()}
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                    <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#718096' }} />
                                    <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#718096' }} />
                                    <Tooltip
                                        contentStyle={{ background: '#1A202C', border: 'none', borderRadius: '12px', fontSize: '12px' }}
                                        labelStyle={{ color: '#A0AEC0' }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="balance"
                                        stroke="#667EEA"
                                        fill="url(#splitColor)"
                                        fillOpacity={1}
                                        strokeWidth={3}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Trade List */}
                    <div className="space-y-3">
                        <div className="flex justify-between items-center px-2">
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest">Simulated Journey</h3>
                            <button
                                onClick={() => {
                                    if (!results?.trades) return;
                                    const headers = ['Entry Time', 'Side', 'Entry Price', 'Exit Time', 'Exit Price', 'Reason', 'PnL'];
                                    const rows = results.trades.map(t => [
                                        t.time.replace('T', ' '),
                                        t.side,
                                        t.entry_price,
                                        t.exit_time.replace('T', ' '),
                                        t.exit_price,
                                        t.reason,
                                        t.pnl
                                    ]);
                                    const csvContent = "data:text/csv;charset=utf-8,"
                                        + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
                                    const encodedUri = encodeURI(csvContent);
                                    const link = document.createElement("a");
                                    link.setAttribute("href", encodedUri);
                                    link.setAttribute("download", `simulation_${params.symbol}_${params.start_date}.csv`);
                                    document.body.appendChild(link);
                                    link.click();
                                    document.body.removeChild(link);
                                }}
                                className="text-[10px] font-black bg-[var(--bg-secondary)] text-[var(--accent-blue)] px-2 py-1 rounded-lg border border-[var(--border-color)] hover:bg-[var(--accent-blue)] hover:text-white transition-all flex items-center gap-1"
                            >
                                <span>📥</span> DOWNLOAD CSV
                            </button>
                        </div>
                        {results.trades.map((t, idx) => {
                            const entryDate = t.time.split('T')[0].slice(5); // MM-DD
                            const entryTime = t.time.split('T')[1].slice(0, 5);
                            const exitDate = t.exit_time.split('T')[0].slice(5);
                            const exitTime = t.exit_time.split('T')[1].slice(0, 5);

                            return (
                                <div key={idx} className="glass-card p-4 rounded-xl border border-[var(--border-color)] flex justify-between items-center text-sm">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className={`text-[9px] font-black px-1.5 py-0.5 rounded ${t.side === 'BUY' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-500'}`}>
                                                {t.side}
                                            </span>
                                            <span className="font-bold text-gray-300 text-xs text-nowrap">
                                                {entryDate} <span className="text-gray-500 font-normal">{entryTime}</span>
                                                <span className="mx-2 text-gray-600">→</span>
                                                {exitDate} <span className="text-gray-500 font-normal">{exitTime}</span>
                                            </span>
                                        </div>
                                        <div className="text-[10px] text-gray-500 mt-1 uppercase font-medium flex gap-2 items-center">
                                            <span>In: ₹{t.entry_price.toLocaleString()}</span>
                                            <span>Out: ₹{t.exit_price.toLocaleString()}</span>
                                            {t.reason && (
                                                <span className={`ml-auto font-bold px-1.5 py-0.5 rounded ${t.reason.includes('TARGET') ? 'bg-indigo-500/10 text-indigo-400' :
                                                    (t.reason === 'STOPLOSS' || t.reason === 'EOD_SQUARE_OFF') ? 'bg-red-500/10 text-red-500' :
                                                        t.reason.includes('trap') ? 'bg-orange-500/10 text-orange-400' :
                                                            'bg-gray-500/10 text-gray-400'
                                                    }`}>
                                                    {t.reason}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className={`font-black text-lg ml-4 ${t.pnl >= 0 ? 'text-[var(--success-neon)]' : 'text-red-500'}`}>
                                        {t.pnl >= 0 ? '+' : ''}{Math.round(t.pnl).toLocaleString()}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default BacktestTab;