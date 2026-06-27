import { useMemo, useState } from 'react';

function LogsTab({ logs }) {
    const [filter, setFilter] = useState('ALL'); // ALL | ALERTS_ONLY
    const [dateFilter, setDateFilter] = useState(''); // YYYY-MM-DD (local)

    const normalizedLogs = Array.isArray(logs) ? logs : [];

    const filteredLogs = useMemo(() => {
        const inDate = (log) => {
            if (!dateFilter) return true;
            if (!log?.time) return false;

            const d = new Date(log.time);
            if (Number.isNaN(d.getTime())) return false;

            const yyyy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            const localDate = `${yyyy}-${mm}-${dd}`;
            return localDate === dateFilter;
        };

        const is15mNearOrCrossAlert = (log) => {
            const msg = String(log?.msg || '').toLowerCase();

            // Exclude strategy/bulk noise like:
            //   "Generated 225 alerts for 25 stocks"
            const isGeneratedNoise = msg.includes('generated') && msg.includes('alerts');
            if (isGeneratedNoise) return false;

            // Typical candle-close alert messages we generate look like:
            //   "[15M NEAR] SYMBOL close ... is SELL ..."
            const is15mNearOrCross = msg.includes('[15m near]') || msg.includes('[15m cross]');
            if (is15mNearOrCross) return true;

            // Fallback for any alternate formatting: contain "[15m" + near/cross keywords.
            const is15mBlock = msg.includes('[15m');
            const hasNearOrCross = msg.includes(' near ') || msg.includes(' cross ');
            return is15mBlock && hasNearOrCross;
        };

        if (filter === 'ALL') {
            return normalizedLogs.filter((log) => inDate(log));
        }

        return normalizedLogs.filter((log) => inDate(log) && is15mNearOrCrossAlert(log));
    }, [filter, normalizedLogs, dateFilter]);

    const getTodayLocalISO = () => {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    };

    return (
        <div className="w-full">
            <div className="glass-card rounded-xl overflow-hidden shadow-lg border-opacity-50">
                <div className="bg-[var(--bg-secondary)] px-4 py-3 border-b border-[var(--border-color)] flex justify-between items-center gap-3">
                    <h3 className="text-[var(--text-primary)] font-bold flex items-center gap-2">
                        <span className="text-[var(--accent-blue)]">❯_</span> Activity Log
                    </h3>

                    <div className="flex items-center gap-2">
                        <select
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                            className="bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-1 text-xs outline-none"
                        >
                            <option value="ALL">All</option>
                            <option value="ALERTS_ONLY">Alerts only</option>
                        </select>

                        <input
                            type="date"
                            value={dateFilter}
                            onChange={(e) => setDateFilter(e.target.value)}
                            className="bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-1 text-xs outline-none"
                            aria-label="Filter by date"
                        />

                        <button
                            onClick={() => setDateFilter(getTodayLocalISO())}
                            className="px-2 py-1 text-xs font-bold border border-[var(--border-color)] rounded-lg hover:bg-[var(--bg-primary)]"
                            title="Set to today"
                            type="button"
                        >
                            Today
                        </button>

                        <button
                            type="button"
                            onClick={() => {
                                const rows = filteredLogs.map((l) => {
                                    // Logs UI uses `new Date(log.time).toLocaleString('en-IN', ...)`, so export the same IST-local formatted timestamp.
                                    // This avoids Excel showing the underlying UTC time.
                                    let exportTime = l.time ?? '';
                                    if (typeof l.time === 'string' && l.time.includes('T')) {
                                        const d = new Date(l.time);
                                        if (!Number.isNaN(d.getTime())) {
                                            exportTime = d.toLocaleString('en-IN', {
                                                day: '2-digit',
                                                month: 'short',
                                                hour: '2-digit',
                                                minute: '2-digit',
                                                second: '2-digit',
                                                hour12: false,
                                            });
                                        }
                                    }

                                    return {
                                        time: exportTime,
                                        symbol: l.symbol ?? '',
                                        msg: l.msg ?? '',
                                    };
                                });

                                const header = ['time', 'symbol', 'msg'];
                                const escapeCell = (v) => {
                                    const s = String(v ?? '');
                                    // Escape for CSV
                                    if (s.includes('"') || s.includes(',') || s.includes('\n') || s.includes('\r')) {
                                        return `"${s.replace(/"/g, '""')}"`;
                                    }
                                    return s;
                                };

                                const csv = [header.join(','), ...rows.map((r) => header.map((h) => escapeCell(r[h])).join(','))].join('\n');
                                const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                                const url = URL.createObjectURL(blob);

                                const datePart = dateFilter || 'all_dates';
                                const file = `activity_logs_${filter}_${datePart}.csv`;

                                const a = document.createElement('a');
                                a.href = url;
                                a.setAttribute('download', file);
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                URL.revokeObjectURL(url);
                            }}
                            className="px-2 py-1 text-xs font-bold border border-[var(--border-color)] rounded-lg hover:bg-[var(--bg-primary)]"
                            title="Download filtered logs as CSV (open in Excel)"
                        >
                            Download
                        </button>

                        <span className="text-xs text-[var(--text-muted)] font-mono">{filteredLogs.length} entries</span>
                    </div>
                </div>


                <div className="max-h-[600px] overflow-y-auto font-mono text-sm">
                    {filteredLogs.length === 0 ? (
                        <div className="p-12 text-center">
                            <div className="text-4xl mb-2 opacity-50">📝</div>
                            <p className="text-[var(--text-muted)]">No activity recorded yet.</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-[var(--border-color)]">
                            {filteredLogs.map((log, index) => {
                                const msg = String(log?.msg || '');
                                const isAlert = msg.toLowerCase().includes('triggered');

                                return (
                                    <div
                                        key={index}
                                        className="px-4 py-3 hover:bg-[var(--bg-primary)] transition-colors flex gap-4"
                                    >
                                        <div className="text-[var(--text-muted)] text-[10px] whitespace-nowrap pt-0.5 leading-tight">
                                            {log.time && log.time.includes('T')
                                                ? new Date(log.time).toLocaleString('en-IN', {
                                                    day: '2-digit',
                                                    month: 'short',
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                    second: '2-digit',
                                                    hour12: false,
                                                })
                                                : log.time}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="font-bold text-[var(--accent-blue)]">{log.symbol}</span>
                                                {isAlert && (
                                                    <span className="text-[10px] bg-[var(--bg-primary)] px-1.5 rounded text-[var(--text-secondary)] border border-[var(--border-color)]">
                                                        ALERT
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-[var(--text-secondary)] break-words leading-relaxed">
                                                {log.msg || 'No message'}
                                            </p>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default LogsTab;

