function LogsTab({ logs }) {
    return (
        <div className="w-full">
            <div className="glass-card rounded-xl overflow-hidden shadow-lg border-opacity-50">
                <div className="bg-[var(--bg-secondary)] px-4 py-3 border-b border-[var(--border-color)] flex justify-between items-center">
                    <h3 className="text-[var(--text-primary)] font-bold flex items-center gap-2">
                        <span className="text-[var(--accent-blue)]">❯_</span> Activity Log
                    </h3>
                    <span className="text-xs text-[var(--text-muted)] font-mono">{logs.length} entries</span>
                </div>

                <div className="max-h-[600px] overflow-y-auto font-mono text-sm">
                    {logs.length === 0 ? (
                        <div className="p-12 text-center">
                            <div className="text-4xl mb-2 opacity-50">📝</div>
                            <p className="text-[var(--text-muted)]">No activity recorded yet.</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-[var(--border-color)]">
                            {[...logs].reverse().map((log, index) => (
                                <div
                                    key={index}
                                    className="px-4 py-3 hover:bg-[var(--bg-primary)] transition-colors flex gap-4"
                                >
                                    <div className="text-[var(--text-muted)] text-xs whitespace-nowrap pt-0.5">
                                        {log.time && log.time.includes('T')
                                            ? new Date(log.time).toLocaleTimeString()
                                            : log.time}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="font-bold text-[var(--accent-blue)]">{log.symbol}</span>
                                            {log.msg.toLowerCase().includes('triggered') && (
                                                <span className="text-[10px] bg-[var(--bg-primary)] px-1.5 rounded text-[var(--text-secondary)] border border-[var(--border-color)]">ALERT</span>
                                            )}
                                        </div>
                                        <p className="text-[var(--text-secondary)] break-words leading-relaxed">
                                            {log.msg}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default LogsTab;
