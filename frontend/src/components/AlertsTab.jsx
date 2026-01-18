import { useState, useEffect } from 'react';
import { generateAlerts, generateBulkAlerts, deleteAlert, pauseAlerts, clearAllAlerts, deleteMultipleAlerts } from '../services/api';
import toast from 'react-hot-toast';
import { Skeleton } from './Skeleton';

function AlertsTab({ sessionId, clientId, watchlist = [], alerts = [], setAlerts, isPaused, setIsPaused, referenceDate, setReferenceDate, preSelectedSymbol, isLoadingData, onRefreshData }) {
    const [generating, setGenerating] = useState(false);
    const [bulkGenerating, setBulkGenerating] = useState(false);
    const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0 });
    const [visibleCount, setVisibleCount] = useState(50);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('ALL');
    const [selectedIds, setSelectedIds] = useState(new Set());

    // Ensure watchlist is always an array
    const safeWatchlist = Array.isArray(watchlist) ? watchlist : [];

    // Load saved settings from localStorage
    const loadSavedSettings = () => {
        try {
            const saved = localStorage.getItem('trade_yantra_alert_settings');
            if (saved) {
                const settings = JSON.parse(saved);
                return {
                    date: settings.date || new Date().toISOString().split('T')[0],
                    isCustomRange: settings.isCustomRange || false,
                    startTime: settings.startTime || '09:15',
                    endTime: settings.endTime || '15:30',
                    selectedLevels: settings.selectedLevels || ['High', 'Low', 'R1', 'S1']
                };
            }
        } catch (e) {
            console.error('Failed to load saved settings:', e);
        }
        return {
            date: new Date().toISOString().split('T')[0],
            isCustomRange: false,
            startTime: '09:15',
            endTime: '15:30',
            selectedLevels: ['High', 'Low', 'R1', 'S1']
        };
    };

    const savedSettings = loadSavedSettings();

    // Form state with persistence (Note: date is now passed as a prop for global sync)
    const INDICES = [
        { symbol: 'NIFTY 50', token: '99926000', exch: 'NSE' },
        { symbol: 'NIFTY BANK', token: '99926009', exch: 'NSE' },
        { symbol: 'SENSEX', token: '99919000', exch: 'BSE' },
        { symbol: 'NIFTY FIN SERVICE', token: '99926012', exch: 'NSE' }
    ];

    const [selectedSymbol, setSelectedSymbol] = useState(safeWatchlist.length > 0 ? safeWatchlist[0].symbol : '');

    // Handle pre-selection from dashboard
    useEffect(() => {
        if (preSelectedSymbol && preSelectedSymbol.symbol) {
            setSelectedSymbol(preSelectedSymbol.symbol);
        }
    }, [preSelectedSymbol]);

    const [isCustomRange, setIsCustomRange] = useState(savedSettings.isCustomRange);
    const [startTime, setStartTime] = useState(savedSettings.startTime);
    const [endTime, setEndTime] = useState(savedSettings.endTime);
    const [selectedLevels, setSelectedLevels] = useState(savedSettings.selectedLevels);

    // Save other settings to localStorage whenever they change
    useEffect(() => {
        const settings = {
            date: referenceDate,
            isCustomRange,
            startTime,
            endTime,
            selectedLevels
        };
        localStorage.setItem('trade_yantra_alert_settings', JSON.stringify(settings));
    }, [referenceDate, isCustomRange, startTime, endTime, selectedLevels]);

    const handleLevelToggle = (level) => {
        setSelectedLevels(prev =>
            prev.includes(level)
                ? prev.filter(l => l !== level)
                : [...prev, level]
        );
    };

    const handleGenerateAlerts = async () => {
        if (!selectedSymbol) {
            toast.error('Please select a stock or index');
            return;
        }
        if (selectedLevels.length === 0) {
            toast.error('Please select at least one level');
            return;
        }

        try {
            setGenerating(true);

            // Find selected item (stock or index)
            let selectedItem = safeWatchlist.find(s => s.symbol === selectedSymbol);
            if (!selectedItem) {
                selectedItem = INDICES.find(i => i.symbol === selectedSymbol);
            }

            // If pre-selected passed down, it might have details not in our static lists?
            if (!selectedItem && preSelectedSymbol && preSelectedSymbol.symbol === selectedSymbol) {
                selectedItem = preSelectedSymbol;
            }

            const response = await generateAlerts(sessionId, {
                symbol: selectedSymbol,
                date: referenceDate,
                start_time: startTime,
                end_time: endTime,
                is_custom_range: isCustomRange,
                levels: selectedLevels,
                token: selectedItem?.token,     // Pass token explicitly
                exchange: selectedItem?.exch || selectedItem?.exchange || 'NSE', // Pass exchange explicitly
                client_id: clientId
            });

            // The backend now returns the FULL updated list of alerts (session.alerts)
            // for instant sync, which correctly reflects the replacement of old auto-alerts.
            if (response.alerts) {
                setAlerts(response.alerts);
            }
            toast.success(`Generated ${response.count || 0} alerts for ${selectedSymbol}`);
        } catch (err) {
            console.error('Generate alerts error:', err);
            toast.error(err.response?.data?.detail || 'Failed to generate alerts');
        } finally {
            setGenerating(false);
        }
    };

    const handleGenerateBulkAlerts = async () => {
        if (safeWatchlist.length === 0) {
            toast.error('Watchlist is empty');
            return;
        }
        if (selectedLevels.length === 0) {
            toast.error('Please select at least one level');
            return;
        }

        try {
            setBulkGenerating(true);
            setBulkProgress({ current: 0, total: safeWatchlist.length });

            const mainToast = toast.loading(`Starting bulk generation for ${safeWatchlist.length} stocks...`);
            let totalNewAlerts = 0;
            let successCount = 0;
            let failCount = 0;

            // SEQUENTIAL PROCESSING: Loop through each stock to avoid timeouts
            // and keep the connection alive.
            for (let i = 0; i < safeWatchlist.length; i++) {
                const stock = safeWatchlist[i];
                setBulkProgress({ current: i + 1, total: safeWatchlist.length });

                try {
                    // Update main toast with progress
                    toast.loading(`Processing ${stock.symbol} (${i + 1}/${safeWatchlist.length})...`, { id: mainToast });

                    const response = await generateAlerts(sessionId, {
                        symbol: stock.symbol,
                        token: stock.token,
                        exchange: stock.exch_seg || 'NSE',
                        date: referenceDate,
                        start_time: startTime,
                        end_time: endTime,
                        is_custom_range: isCustomRange,
                        levels: selectedLevels,
                        client_id: clientId
                    });

                    if (response.alerts) {
                        // The backend now returns the full list for that stock context
                        setAlerts(response.alerts);
                        totalNewAlerts += (response.count || 0);
                    }
                    successCount++;
                } catch (stockErr) {
                    console.error(`Failed for ${stock.symbol}:`, stockErr);
                    failCount++;
                }
            }

            toast.dismiss(mainToast);

            if (successCount > 0) {
                toast.success(`Success! Generated alerts for ${successCount} stocks.`);
            }

            if (failCount > 0) {
                toast.error(`Failed to process ${failCount} stocks.`, { duration: 5000 });
            }

        } catch (err) {
            console.error('Bulk generate logic error:', err);
            toast.error('Critical failure in bulk generation');
        } finally {
            setBulkGenerating(false);
            setBulkProgress({ current: 0, total: 0 });
        }
    };

    const handleDeleteAlert = async (alertId) => {
        try {
            await deleteAlert(sessionId, alertId, clientId);
            setAlerts(alerts.filter(a => a.id !== alertId));
            toast.success('Alert deleted');
        } catch (err) {
            console.error('Delete alert error:', err);
            toast.error('Failed to delete alert');
        }
    };

    const handleTogglePause = async (newValue) => {
        try {
            await pauseAlerts(sessionId, newValue, clientId);
            setIsPaused(newValue);
            toast.success(newValue ? 'Alerts Paused' : 'Monitoring Resumed');
        } catch (err) {
            console.error('Pause alerts error:', err);
            toast.error('Failed to update pause status');
        }
    };

    const handleClearAllAlerts = async () => {
        if (alerts.length === 0) return;

        console.log('🧹 Manual Clear All triggered...');
        try {
            console.log('🧹 Clearing all alerts...');
            const response = await clearAllAlerts(sessionId, clientId);
            console.log('✅ Server response:', response);
            setAlerts([]);
            setSelectedIds(new Set());
            toast.success(response.message || 'All alerts cleared');
        } catch (err) {
            console.error('Clear all alerts error:', err);
            toast.error('Failed to clear alerts');
        }
    };

    const toggleSelectAll = () => {
        if (selectedIds.size === filteredAlerts.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredAlerts.map(a => a.id)));
        }
    };

    const toggleSelectOne = (id) => {
        const next = new Set(selectedIds);
        if (next.has(id)) {
            next.delete(id);
        } else {
            next.add(id);
        }
        setSelectedIds(next);
    };

    const handleDeleteSelected = async () => {
        const ids = Array.from(selectedIds);
        console.log('Attempting to delete alerts, selected count:', ids.length);

        if (ids.length === 0) {
            toast.error('No alerts selected');
            return;
        }

        console.log('🗑️ Deleting selected alerts:', ids);
        const loadingToast = toast.loading(`Deleting ${ids.length} alerts...`);

        try {
            const response = await deleteMultipleAlerts(sessionId, ids, clientId);
            console.log('✅ Bulk delete response:', response);

            // Use snapshot of ids for filtering to avoid closure issues
            const idsSet = new Set(ids);
            setAlerts(prev => prev.filter(a => !idsSet.has(a.id)));
            setSelectedIds(new Set());

            toast.dismiss(loadingToast);
            toast.success(`Deleted ${response.count || ids.length} alerts`);
        } catch (err) {
            console.error('Delete selected error:', err);
            toast.dismiss(loadingToast);
            toast.error(err.response?.data?.detail || 'Failed to delete selected alerts');
        }
    };

    // Filtered alerts logic
    const filteredAlerts = alerts.filter(alert => {
        const matchesSearch = alert.symbol.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesFilter = filterType === 'ALL' ||
            (filterType === 'ABOVE' && alert.condition === 'ABOVE') ||
            (filterType === 'BELOW' && alert.condition === 'BELOW') ||
            (alert.type && alert.type.includes(filterType));
        return matchesSearch && matchesFilter;
    });

    return (
        <div className="w-full space-y-4 pb-20">
            {/* Strategy Control Panel */}
            <div className="glass-card rounded-xl p-5 shadow-xl">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h3 className="text-[var(--text-primary)] font-bold text-xl">High/Low Alert Strategy</h3>
                        <p className="text-[var(--text-muted)] text-sm">Target historical Highs, Lows and S/R levels</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <span className="text-xs text-gray-500 font-medium">Monitoring</span>
                        <button
                            onClick={() => handleTogglePause(!isPaused)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-300 focus:outline-none ${isPaused ? 'bg-[#F26565]' : 'bg-[#48BB78]'}`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-300 ${isPaused ? 'translate-x-6' : 'translate-x-1'}`} />
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Stock & Date Selection */}
                    <div className="space-y-4">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[var(--text-secondary)] text-xs font-semibold uppercase tracking-wider">Select Stock</label>
                            <select
                                value={selectedSymbol}
                                onChange={(e) => setSelectedSymbol(e.target.value)}
                                className="bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg p-2.5 focus:border-[var(--accent-blue)] focus:ring-1 focus:ring-[var(--accent-blue)] outline-none transition-all"
                            >
                                <option value="">Select a stock...</option>
                                <optgroup label="Indices">
                                    {INDICES.map(i => (
                                        <option key={i.token} value={i.symbol}>{i.symbol}</option>
                                    ))}
                                </optgroup>
                                <optgroup label="Watchlist">
                                    {safeWatchlist.map(s => (
                                        <option key={s.token} value={s.symbol}>{s.symbol}</option>
                                    ))}
                                </optgroup>
                            </select>
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[var(--text-secondary)] text-xs font-semibold uppercase tracking-wider">Calculation Date</label>
                            <input
                                type="date"
                                value={referenceDate}
                                onChange={(e) => setReferenceDate(e.target.value)}
                                className="bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg p-2.5 focus:border-[var(--accent-blue)] outline-none transition-all [color-scheme:dark]"
                            />
                        </div>
                    </div>

                    {/* Levels & Time Options */}
                    <div className="space-y-4">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[var(--text-secondary)] text-xs font-semibold uppercase tracking-wider">Alert Levels</label>
                            <div className="flex flex-wrap gap-2">
                                {['High', 'Low', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6'].map(level => (
                                    <button
                                        key={level}
                                        onClick={() => handleLevelToggle(level)}
                                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${selectedLevels.includes(level)
                                            ? 'bg-[var(--accent-blue)] border-[var(--accent-blue)] text-white shadow-lg shadow-indigo-500/20'
                                            : 'bg-transparent border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-muted)]'
                                            }`}
                                    >
                                        {level}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="pt-2">
                            <label className="flex items-center gap-2 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={isCustomRange}
                                    onChange={(e) => setIsCustomRange(e.target.checked)}
                                    className="w-4 h-4 rounded border-gray-300 text-[var(--accent-blue)] focus:ring-[var(--accent-blue)] bg-[var(--bg-secondary)]"
                                />
                                <span className="text-[var(--text-primary)] text-sm group-hover:text-[var(--text-primary)] transition-colors">Custom Time Range</span>
                            </label>

                            {isCustomRange && (
                                <div className="flex gap-2 mt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                                    <input
                                        type="time"
                                        value={startTime}
                                        onChange={(e) => setStartTime(e.target.value)}
                                        className="flex-1 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg p-1.5 text-sm outline-none [color-scheme:dark]"
                                    />
                                    <input
                                        type="time"
                                        value={endTime}
                                        onChange={(e) => setEndTime(e.target.value)}
                                        className="flex-1 bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-lg p-1.5 text-sm outline-none [color-scheme:dark]"
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                    <button
                        onClick={handleGenerateAlerts}
                        disabled={generating || bulkGenerating || !selectedSymbol}
                        className="py-3 bg-[var(--accent-blue)] hover:brightness-110 text-white font-bold rounded-lg shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {generating ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Calculating...
                            </>
                        ) : (
                            '⚡ Generate for Selected Stock'
                        )}
                    </button>

                    <button
                        onClick={handleGenerateBulkAlerts}
                        disabled={generating || bulkGenerating || safeWatchlist.length === 0}
                        className="py-3 bg-[var(--success-neon)] hover:brightness-110 text-white font-bold rounded-lg shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {bulkGenerating ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Processing {bulkProgress.current}/{bulkProgress.total}...
                            </>
                        ) : (
                            `🚀 Generate for All Watchlist (${safeWatchlist.length})`
                        )}
                    </button>
                </div>
            </div>

            {/* Active Alerts List */}
            <div className="space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <h3 className="text-[var(--text-primary)] font-bold text-lg">Active Alerts ({filteredAlerts.length})</h3>
                    <div className="flex flex-wrap items-center gap-2">
                        {onRefreshData && (
                            <button
                                onClick={() => onRefreshData(true)}
                                className="px-3 py-1.5 bg-[var(--bg-secondary)] hover:bg-[var(--border-color)] text-[var(--text-secondary)] hover:text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2 border border-[var(--border-color)]"
                                title="Fetch alerts and logs from backend"
                            >
                                🔄 History
                            </button>
                        )}

                        {selectedIds.size > 0 && (
                            <button
                                onClick={() => {
                                    console.log('Delete Clicked');
                                    handleDeleteSelected();
                                }}
                                style={{ backgroundColor: 'red', color: 'white', padding: '10px', borderRadius: '8px', zIndex: 1000, position: 'relative' }}
                            >
                                DELETE SELECTED ({selectedIds.size})
                            </button>
                        )}

                        {alerts.length > 0 && selectedIds.size === 0 && (
                            <button
                                onClick={() => {
                                    console.log('Clear All Clicked');
                                    handleClearAllAlerts();
                                }}
                                style={{ backgroundColor: 'rgba(255,0,0,0.1)', color: 'red', border: '1px solid red', padding: '10px', borderRadius: '8px' }}
                            >
                                CLEAR ALL
                            </button>
                        )}
                    </div>
                </div>

                {alerts.length > 0 && (
                    <div className="flex items-center gap-3 px-1 py-1">
                        <label className="flex items-center gap-2 cursor-pointer group">
                            <input
                                type="checkbox"
                                checked={selectedIds.size === filteredAlerts.length && filteredAlerts.length > 0}
                                onChange={toggleSelectAll}
                                className="w-4 h-4 rounded border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)] cursor-pointer"
                            />
                            <span className="text-xs text-[var(--text-secondary)] group-hover:text-white transition-colors">
                                Select All {filteredAlerts.length < alerts.length && '(Filtered)'}
                            </span>
                        </label>
                    </div>
                )}

                {/* Search and Filters */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pb-2">
                    <div className="relative">
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input
                            type="text"
                            placeholder="Search alerts by symbol (e.g. NIFTY)..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full pl-9 pr-4 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none transition-all"
                        />
                        {searchTerm && (
                            <button
                                onClick={() => setSearchTerm('')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        )}
                    </div>
                    <select
                        value={filterType}
                        onChange={(e) => setFilterType(e.target.value)}
                        className="w-full px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none transition-all"
                    >
                        <option value="ALL">All Types & Conditions</option>
                        <optgroup label="Conditions">
                            <option value="ABOVE">Condition: ABOVE</option>
                            <option value="BELOW">Condition: BELOW</option>
                        </optgroup>
                        <optgroup label="Auto Strategy Levels">
                            <option value="HIGH">Level: HIGH</option>
                            <option value="LOW">Level: LOW</option>
                            <option value="R1">Level: R1</option>
                            <option value="S1">Level: S1</option>
                            <option value="R2">Level: R2</option>
                            <option value="S2">Level: S2</option>
                        </optgroup>
                        <option value="MANUAL">Manual Alerts</option>
                    </select>
                </div>

                {isLoadingData && alerts.length === 0 ? (
                    <div className="space-y-3">
                        {/* Skeleton Items */}
                        {Array(3).fill(0).map((_, i) => (
                            <div key={i} className="glass-card rounded-xl p-4 border-l-4 border-[var(--border-color)]">
                                <div className="flex items-center gap-4">
                                    <Skeleton className="h-10 w-10 rounded-lg" />
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2">
                                            <Skeleton className="h-4 w-24" />
                                            <Skeleton className="h-4 w-12" />
                                        </div>
                                        <Skeleton className="h-6 w-32" />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : filteredAlerts.length === 0 ? (
                    <div className="glass-card rounded-xl p-10 border-dashed text-center">
                        <div className="text-4xl mb-3">🔍</div>
                        <p className="text-[var(--text-muted)]">No alerts match your search or filter.</p>
                        <button
                            onClick={() => { setSearchTerm(''); setFilterType('ALL'); }}
                            className="text-[var(--accent-blue)] text-sm mt-2 hover:underline"
                        >
                            Reset filters
                        </button>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-1 gap-3">
                            {filteredAlerts.slice(0, visibleCount).map((alert) => {
                                const isAbove = alert.condition === 'ABOVE';
                                const colorClass = isAbove ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]';
                                const borderColorClass = isAbove ? 'border-l-[var(--success-neon)]' : 'border-l-[var(--danger-neon)]';
                                const icon = isAbove ? '📈' : '📉';
                                const typeLabel = alert.type?.replace('AUTO_', '') || 'MANUAL';

                                return (
                                    <div
                                        key={alert.id}
                                        onClick={() => toggleSelectOne(alert.id)}
                                        className={`glass-card rounded-xl p-4 border-l-4 ${borderColorClass} ${selectedIds.has(alert.id) ? 'bg-[var(--accent-blue)]/10 border-r-2 border-r-[var(--accent-blue)]' : 'hover:border-[var(--accent-blue)]'} transition-all duration-300 group shadow-sm cursor-pointer relative`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedIds.has(alert.id)}
                                                    onChange={(e) => {
                                                        e.stopPropagation();
                                                        toggleSelectOne(alert.id);
                                                    }}
                                                    className="w-4 h-4 rounded border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)] cursor-pointer"
                                                />
                                                <div className="flex items-center gap-3">
                                                    <span className="text-xl bg-[var(--bg-secondary)] p-2 rounded-lg">{icon}</span>
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <h4 className="text-[var(--text-primary)] font-bold text-base">{alert.symbol}</h4>
                                                            <span className="text-[10px] bg-[var(--bg-secondary)] text-[var(--text-muted)] px-1.5 py-0.5 rounded font-mono uppercase">
                                                                {typeLabel}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-2 mt-0.5">
                                                            <span className={`font-mono font-bold text-lg ${colorClass}`}>
                                                                ₹{alert.price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                            </span>
                                                            <span className="text-[var(--text-secondary)] text-xs font-medium uppercase tracking-tighter">
                                                                {alert.condition}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteAlert(alert.id);
                                                }}
                                                className="p-2 text-red-400 hover:text-white hover:bg-red-500 rounded-lg transition-all duration-200"
                                                title="Delete Alert"
                                            >
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        {alerts.length > visibleCount && (
                            <button
                                onClick={() => setVisibleCount(prev => prev + 50)}
                                className="w-full py-3 mt-4 text-[var(--text-secondary)] hover:text-white font-medium border border-dashed border-[var(--border-color)] rounded-xl transition-all"
                            >
                                Load More (+50)
                            </button>
                        )}
                    </>
                )}
            </div>
            {/* Emergency Floating Button */}
            <button
                onClick={() => {
                    if (window.confirm("Clear ALL alerts locally and force sync?")) {
                        setAlerts([]);
                        setSelectedIds(new Set());
                        toast.success("Emergency local clear complete");
                    }
                }}
                className="fixed bottom-24 right-4 z-[9999] bg-orange-600 text-white p-3 rounded-full shadow-2xl font-bold text-xs"
            >
                ⚠️ CLEAR
            </button>
        </div>
    );
}

export default AlertsTab;
