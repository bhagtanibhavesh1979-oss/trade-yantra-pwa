import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    toggleLiveTrading,
    getLiveStatus,
    getLivePositions,
    getLiveOrders,
    getLiveFunds,
    placeLiveOrder,
    updateLiveSettings,
    getSession,
    API_BASE_URL
} from '../services/api';
import toast from 'react-hot-toast';

const LiveOrdersTab = ({ watchlist = [] }) => {
    // 1. INDEPENDENT STATE (Fixes the "Frozen" UI)
    const [balance, setBalance] = useState(0);
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);
    const [apiError, setApiError] = useState(null);

    // Control States
    const [liveAutoExec, setLiveAutoExec] = useState(false);
    const [qty, setQty] = useState(1);
    const [cap, setCap] = useState(0);
    const [saveLoading, setSaveLoading] = useState(false);
    const [selectedOrder, setSelectedOrder] = useState(null);

    // 2. LIVE PNL RECALCULATION
    const processedTrades = trades.map(t => {
        const stock = watchlist.find(s => String(s.token) === String(t.token));
        let entryPrice = parseFloat(t.entry_price || t.averageprice || t.price || 0);
        if (!stock) return { ...t, pnl: parseFloat(t.pnl || t.realised || 0), entry_price: entryPrice, current_price: parseFloat(t.ltp || entryPrice) };
        const currentLtp = parseFloat(stock.ltp || 0);
        const quantity = parseInt(t.quantity || 0, 10);
        let livePnl = (t.side === 'BUY') ? (currentLtp - entryPrice) * quantity : (entryPrice - currentLtp) * quantity;
        return { ...t, pnl: livePnl, current_price: currentLtp, entry_price: entryPrice };
    });
    const liveTotalPnl = processedTrades.reduce((sum, t) => sum + (Number(t.pnl) || 0), 0);

    const fetchLiveData = async () => {
        const session = getSession();
        const sid = session?.sessionId || session?.session_id;
        const cid = session?.clientId || session?.client_id;
        
        if (!sid) {
            console.log("📡 [LIVE] No session ID found, skipping fetch");
            setLoading(false);
            return;
        }

        console.log("📡 [LIVE] Fetching Live Data for CID:", cid);
        
        try {
            // Independent fetching for resilience
            getLiveStatus(sid, cid).then(status => {
                setLiveAutoExec(!!status);
                if (status && typeof status === 'object') {
                    if (status.trade_quantity) setQty(status.trade_quantity);
                    if (status.trade_capital) setCap(status.trade_capital);
                }
            }).catch(() => {});

            getLiveFunds(sid, cid).then(funds => {
                const fundValue = funds?.net ?? funds?.availablecash ?? funds?.data?.net ?? 0;
                setBalance(fundValue);
                setApiError(null);
            }).catch(() => setBalance(0));

            getLivePositions(sid, cid).then(posData => {
                const pos = posData?.positions || posData?.data || posData || [];
                setTrades(Array.isArray(pos) ? pos : []);
            }).catch(() => setTrades([]));

        } catch (err) {
            console.error('Fetch error:', err);
            setApiError('Broker Connection Delayed');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLiveData();
        const interval = setInterval(fetchLiveData, 15000);
        return () => clearInterval(interval);
    }, []);

    const handleSave = async () => {
        setSaveLoading(true);
        const session = getSession();
        const sid = session?.sessionId || session?.session_id;
        const cid = session?.clientId || session?.client_id;
        try {
            await updateLiveSettings(sid, {
                trade_quantity: parseInt(qty),
                trade_capital: parseFloat(cap)
            }, cid);
            toast.success('Settings Saved to Broker');
        } catch (err) {
            toast.error('Save Failed');
        } finally {
            setTimeout(() => setSaveLoading(false), 500);
        }
    };

    const handleToggle = async () => {
        const newState = !liveAutoExec;
        setLiveAutoExec(newState); // Instant feedback
        const session = getSession();
        const sid = session?.sessionId || session?.session_id;
        const cid = session?.clientId || session?.client_id;
        try {
            await toggleLiveTrading(sid, newState, cid);
            toast.success(`LIVE ENGINE: ${newState ? 'STARTED' : 'STOPPED'}`);
        } catch (err) {
            setLiveAutoExec(!newState); // Revert
            toast.error('Broker Toggle Failed');
        }
    };

    const handleClosePosition = async (trade) => {
        toast.loading('Closing Position...');
        const session = getSession();
        const sid = session?.sessionId || session?.session_id;
        const cid = session?.clientId || session?.client_id;
        try {
            await placeLiveOrder(sid, {
                symbol: trade.symbol, token: trade.token, exch_seg: trade.exchange,
                side: trade.side === 'BUY' ? 'SELL' : 'BUY',
                quantity: trade.quantity, product_type: trade.product,
                order_type: 'MARKET', price: 0
            }, cid);
            toast.dismiss();
            toast.success('Square-off Complete');
            fetchLiveData();
        } catch (err) {
            toast.dismiss();
            toast.error('Square-off Failed');
        }
    };

    return (
        <div className="w-full space-y-4 pb-24 px-4 border-t-4 border-red-600 bg-red-950/10 min-h-screen pt-4">
            <div className="bg-red-600/20 border border-red-500/50 p-2 text-center rounded-xl mb-4">
                <h2 className="text-red-500 font-black tracking-widest uppercase text-xs animate-pulse">● LIVE TRADING ENGINE ONLINE</h2>
            </div>

            {apiError && (
                <div className="bg-red-600 text-white p-4 rounded-xl border-2 border-white/20 mb-4 text-xs font-black uppercase text-center shadow-lg">
                    ⚠️ {apiError}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-5 rounded-xl border border-red-500/30">
                    <h3 className="text-[10px] text-red-400 uppercase font-bold tracking-widest mb-1">TOTAL FUNDS</h3>
                    <div className="text-white flex items-baseline gap-1">
                        <span className="text-lg">₹</span>
                        <span className="text-3xl font-black">{(balance || 0).toLocaleString('en-IN')}</span>
                    </div>
                </div>

                <div className="glass-card p-5 rounded-xl border border-red-500/30 flex items-center justify-around">
                    <div className="text-center">
                        <div className="text-[10px] text-red-400 uppercase font-bold mb-1">LIVE P&L</div>
                        <div className={`text-3xl font-black ${liveTotalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {liveTotalPnl >= 0 ? '+' : ''}{liveTotalPnl.toFixed(2)}
                        </div>
                    </div>
                </div>
            </div>

            <div className="glass-card p-4 rounded-xl border border-red-500/30 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">CONTRACT QTY</label>
                        <input
                            type="number"
                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-white text-sm font-black focus:border-red-500 transition-all"
                            value={qty}
                            onChange={(e) => setQty(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">MAX CAPITAL (₹)</label>
                        <input
                            type="number"
                            className="w-full bg-black/40 border border-gray-700 rounded p-2 text-white text-sm font-black focus:border-red-500 transition-all"
                            value={cap}
                            onChange={(e) => setCap(e.target.value)}
                        />
                    </div>
                </div>

                <button onClick={handleSave} disabled={saveLoading} className="w-full py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-bold text-gray-400 border border-gray-700 transition-all">
                    {saveLoading ? 'PUSHING SETTINGS...' : 'SAVE CONFIGURATION'}
                </button>

                <button
                    onClick={handleToggle}
                    className={`w-full py-4 rounded-xl font-black text-sm uppercase tracking-widest shadow-2xl transition-all ${liveAutoExec ? 'bg-red-600 text-white shadow-red-600/30' : 'bg-gray-800 text-gray-500 border border-gray-700'}`}
                >
                    {liveAutoExec ? '🔴 STOP ENGINE' : '🟢 START ENGINE'}
                </button>
            </div>

            <div className="space-y-3">
                <h3 className="text-xs font-bold text-red-400 uppercase px-1 tracking-widest">Active Positions</h3>
                {processedTrades.length === 0 ? (
                    <div className="py-12 text-center border-2 border-dashed border-red-500/10 rounded-2xl text-gray-600 text-sm font-bold">
                        NO POSITIONS AT BROKER
                    </div>
                ) : (
                    processedTrades.map(trade => (
                        <div key={trade.id} onClick={() => setSelectedOrder(trade)} className="bg-black/40 p-4 rounded-xl border border-red-500/20 cursor-pointer flex justify-between items-center active:scale-95 transition-all">
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="font-black text-white text-base">{trade.symbol}</span>
                                    <span className={`text-[9px] font-black px-2 py-0.5 rounded ${trade.side === 'BUY' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-500'}`}>{trade.side}</span>
                                </div>
                                <div className="text-[10px] text-gray-400 font-bold">{trade.quantity} QTY @ ₹{Number(trade.entry_price || 0).toFixed(2)}</div>
                            </div>
                            <div className={`text-xl font-black ${Number(trade.pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {Number(trade.pnl || 0) >= 0 ? '+' : ''}{Number(trade.pnl || 0).toFixed(2)}
                            </div>
                        </div>
                    ))
                )}
            </div>

            <AnimatePresence>
                {selectedOrder && (
                    <div className="fixed inset-0 bg-black/95 flex items-center justify-center p-6 z-50 backdrop-blur-md" onClick={() => setSelectedOrder(null)}>
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                            className="bg-gray-900 w-full max-w-sm rounded-3xl p-8 border border-red-500/30 shadow-2xl"
                            onClick={e => e.stopPropagation()}
                        >
                            <h2 className="text-3xl font-black text-white mb-2">{selectedOrder.symbol}</h2>
                            <div className="space-y-4 mb-6">
                                <div className="flex justify-between text-sm"><span className="text-gray-400">Entry</span><span className="font-bold text-white">₹{Number(selectedOrder.entry_price || 0).toFixed(2)}</span></div>
                                <div className="flex justify-between text-sm"><span className="text-gray-400">LTP</span><span className="font-bold text-white">₹{Number(selectedOrder.current_price || 0).toFixed(2)}</span></div>
                                <div className={`flex justify-between text-xl font-black border-t border-white/10 pt-4 ${Number(selectedOrder.pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                    <span>PNL</span><span>{Number(selectedOrder.pnl || 0).toFixed(2)}</span>
                                </div>
                            </div>
                            <button onClick={() => { handleClosePosition(selectedOrder); setSelectedOrder(null); }} className="w-full py-5 bg-red-600 hover:bg-red-700 text-white rounded-2xl font-black uppercase text-sm shadow-xl shadow-red-600/30">
                                SQUARE OFF (EXIT NOW)
                            </button>
                            <button onClick={() => setSelectedOrder(null)} className="w-full py-4 text-gray-500 font-bold uppercase text-[10px] tracking-widest mt-2">CANCEL</button>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default LiveOrdersTab;
