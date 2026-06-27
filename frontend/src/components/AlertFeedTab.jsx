import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';

function AlertFeedTab({
  feed = [],
  setFeed,
  onSelectSymbol,
}) {
  const [symbolQuery, setSymbolQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Deterministic rendering: never drop websocket items because of inconsistent payload inference.
  // We keep the search box only (symbolQuery). Direction/Event filters are disabled for now.
  const filtered = useMemo(() => {
    const q = symbolQuery.trim().toLowerCase();
    return feed.filter((x) => {
      const alert = x?.alert || {};
      const symbol = alert?.symbol || '';
      return !q || symbol.toLowerCase().includes(q);
    });
  }, [feed, symbolQuery]);

  const clearFeed = () => {
    if (!setFeed) return;
    if (!window.confirm("Clear today's 15m alert feed?")) return;
    setFeed([]);
    toast.success('Alert feed cleared');
  };

  const getColor = (direction) => {
    if (direction === 'BUY') return 'text-[var(--success-neon)] border-l-[var(--success-neon)]';
    return 'text-[var(--danger-neon)] border-l-[var(--danger-neon)]';
  };

  return (
    <div className="w-full space-y-4 pb-24 px-2 md:px-4">
      <div className="glass-card rounded-xl p-4 shadow-xl">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-[var(--text-primary)] font-bold text-lg">15m Feed</h3>
            <p className="text-[var(--text-muted)] text-xs">
              {filtered.length} triggered
            </p>
          </div>

          <button
            onClick={clearFeed}
            className="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg text-xs font-bold"
          >
            Clear
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Symbol</label>
            <input
              value={symbolQuery}
              onChange={(e) => setSymbolQuery(e.target.value)}
              placeholder="Search (NIFTY / RELIANCE)"
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm outline-none"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Direction</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm outline-none"
            >
              <option value="ALL">All</option>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Event</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm outline-none"
            >
              <option value="ALL">All</option>
              <option value="CROSS">CROSS</option>
              <option value="NEAR">NEAR</option>
            </select>
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="glass-card rounded-xl p-8 border-dashed text-center">
          <div className="text-4xl mb-3">🔔</div>
          <div className="text-[var(--text-muted)] text-sm">No 15m feed events match your filters.</div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-widest px-2">
            Newest first
          </div>

          <div className="max-h-[520px] overflow-y-auto pr-1 scrollbar-hide">
            <div className="space-y-2">
              {filtered.map((x) => {
                const alert = x.alert || {};
                const log = x.log || {};

                const direction = alert?.condition === 'ABOVE' ? 'SELL' : 'BUY';
                const colorClass = getColor(direction);

                const eventTypeLabel = (() => {
                  const msg = String(log?.msg || '').toUpperCase();
                  if (msg.includes('[15M NEAR]') || msg.includes(' NEAR ')) return 'NEAR';
                  return 'CROSS';
                })();

                return (
                  <div
                    key={x.id}
                    className={`glass-card rounded-xl p-4 border-l-4 ${colorClass} cursor-pointer transition-colors hover:bg-[var(--bg-secondary)]/30`}
                    onClick={() => {
                      if (onSelectSymbol && alert?.symbol) onSelectSymbol(alert.symbol);
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <div className="font-bold text-base">{alert.symbol}</div>
                          <span className="text-[10px] bg-[var(--bg-secondary)] border border-[var(--border-color)] px-2 py-0.5 rounded font-mono">
                            {eventTypeLabel}
                          </span>
                        </div>
                        <div className="text-[12px] text-[var(--text-secondary)] mt-1">
                          {direction} @ ₹{Number(alert.price || log.price).toFixed(2)}
                          <span className="text-[10px] text-[var(--text-muted)] ml-2">
                            {x.receivedAt ? new Date(x.receivedAt).toLocaleTimeString('en-IN', { hour12: false }) : ''}
                          </span>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className={`font-black text-[18px] ${direction === 'BUY' ? 'text-[var(--success-neon)]' : 'text-[var(--danger-neon)]'}`}>
                          {direction}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] font-mono mt-1">
                          lvl {Number(alert.price).toFixed(2)}
                        </div>
                      </div>
                    </div>

                    {log?.msg && (
                      <div className="text-[11px] text-[var(--text-secondary)] mt-2 break-words">
                        {log.msg}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AlertFeedTab;

