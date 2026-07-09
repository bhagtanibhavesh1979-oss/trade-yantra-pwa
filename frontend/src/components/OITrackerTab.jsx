import { useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { getSession } from '../services/api';

import { API_BASE_URL } from '../services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// Simple fetcher without adding lots to api.js yet.
// Uses the same sessionId logic as other tabs.
const fetchOiSnapshot = async (sessionId, clientId = null) => {
  const url = clientId
    ? `${API_BASE_URL}/api/oi/snapshot/${sessionId}?client_id=${encodeURIComponent(clientId)}`
    : `${API_BASE_URL}/api/oi/snapshot/${sessionId}`;

  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`OI snapshot failed: ${res.status} ${txt}`);
  }
  return res.json();
};

const deltaToColor = (d) => {
  if (d === 0) return 'text-gray-400';
  if (d > 0) return 'text-green-400';
  return 'text-red-400';
};

const sign = (n) => (n > 0 ? '+' : '');


const OIBlock = ({ title, rows, sideKeyPrefix }) => {
  // rows: [{ strike, ce_oi, ce_delta_oi, pe_oi, pe_delta_oi }]
  return (
    <div className="glass-card rounded-2xl border border-white/5 overflow-hidden bg-black/20">
      <div className="p-3 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
        <h3 className="text-[11px] text-gray-400 font-black uppercase tracking-widest">{title}</h3>
      </div>
      <div className="p-3">
        <div className="grid grid-cols-[72px_1fr_1fr] gap-2 text-[10px] font-black uppercase tracking-wide text-gray-500">
          <div>Strike</div>
          <div>OI</div>
          <div>ΔOI (Δ%)</div>
        </div>
        <div className="mt-2 space-y-2">
          {rows.map((r) => {
            const oi = sideKeyPrefix === 'CE' ? r.ce_oi : r.pe_oi;
            const d = sideKeyPrefix === 'CE' ? r.ce_delta_oi : r.pe_delta_oi;
            const dir = sideKeyPrefix === 'CE' ? r.ce_dir : r.pe_dir;
            const pct = sideKeyPrefix === 'CE' ? r.ce_delta_pct : r.pe_delta_pct;

            const arrow = dir === 'increased' ? '▲' : dir === 'decreased' ? '▼' : '';

            return (
              <div
                key={r.strike}
                className="grid grid-cols-[72px_1fr_1fr] gap-2 items-center text-[11px]"
              >
                <div className="text-gray-300 font-black tabular-nums">{r.strike}</div>
                <div className="text-gray-100 font-black tabular-nums">{(oi ?? 0).toLocaleString('en-IN')}</div>
                <div className={`font-black tabular-nums ${deltaToColor(d)}`}>
                  {arrow} {sign(d)}{(d ?? 0).toLocaleString('en-IN')}
                  {pct != null && (
                    <span className="text-[10px] font-bold text-gray-400 ml-2">({pct.toFixed(2)}%)</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

const UnderlyingPanel = ({ name, rows }) => {
  const sortedRows = useMemo(() => {
    if (!rows) return [];
    return [...rows].sort((a, b) => a.strike - b.strike);
  }, [rows]);

  const ceTotal = useMemo(() => {
    return (sortedRows || []).reduce((s, r) => s + (r.ce_oi || 0), 0);
  }, [sortedRows]);
  const peTotal = useMemo(() => {
    return (sortedRows || []).reduce((s, r) => s + (r.pe_oi || 0), 0);
  }, [sortedRows]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black tracking-tight">{name}</h2>
          <p className="text-[10px] text-gray-500 font-bold uppercase tracking-[0.15em]">
            ATM ± 5 (step-based)
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <div className="text-[12px] text-gray-400 font-bold">CE Total</div>
          <div className="text-[14px] font-black text-green-400 tabular-nums">{ceTotal.toLocaleString('en-IN')}</div>
          <div className="text-[12px] text-gray-400 font-bold">PE Total</div>
          <div className="text-[14px] font-black text-red-400 tabular-nums">{peTotal.toLocaleString('en-IN')}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <OIBlock title="Call (CE)" rows={sortedRows} sideKeyPrefix="CE" />
        <OIBlock title="Put (PE)" rows={sortedRows} sideKeyPrefix="PE" />
      </div>
    </div>
  );
};

const OITrackerTab = ({ sessionId: propSessionId, clientId: propClientId }) => {
  const sessionFromStorage = useMemo(() => getSession(), []);

  // IMPORTANT:
  // session_id is NOT client_id. This backend route requires session_id (UUID).
  const sessionId = propSessionId || sessionFromStorage?.sessionId || sessionFromStorage?.session_id || sessionFromStorage?.session || null;
  const clientId = propClientId || sessionFromStorage?.clientId || sessionFromStorage?.client_id || null;

  const isProbablyClientId = typeof sessionId === 'string' && sessionId === clientId;
  // Debug helper: show obvious mismatch rather than blank state.
  // (keep for future UI; ignore eslint for now)
  // eslint-disable-next-line no-unused-vars
  const debugMismatch = !sessionId || isProbablyClientId;



  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [oiHistory, setOiHistory] = useState({
    'NIFTY 50': [],
    SENSEX: [],
  });
  // Debug/alerts enabled but currently UI does not render them; keep without eslint failures
  // eslint-disable-next-line no-unused-vars
  const [oiAlerts, setOiAlerts] = useState([]);
  const alertTrackerRef = useRef({});
  const OI_ALERT_THRESHOLD = 100000;
  // eslint-disable-next-line no-unused-vars
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [lastPollMs, setLastPollMs] = useState(null);
  // admin modal state
  const [adminOpen, setAdminOpen] = useState(false);
  const [aggMethod, setAggMethod] = useState('trimmed');
  const [trimAlpha, setTrimAlpha] = useState('0.2');
  const [retentionDays, setRetentionDays] = useState('14');
  const [savingSettings, setSavingSettings] = useState(false);

  const timerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      setError('Missing sessionId');
      return;
    }

    let cancelled = false;

    const poll = async () => {
      const startedAt = Date.now();
      try {
        const res = await fetchOiSnapshot(sessionId, clientId);

        if (cancelled) return;
        console.debug('[OI] poll end', {
          sessionId,
          ms: Date.now(),
          durationMs: Date.now() - startedAt,
          status: res?.status,
          updated_at: res?.updated_at,
        });
        if (res?.status === 'success') {
          setSnapshot(res.data);
          setLastUpdatedAt(res?.updated_at ?? null);
          setLastPollMs(Date.now() - startedAt);
          // update history: sum CE/PE across strikes for each underlying
          try {
            const now = Date.now();
            const next = oiHistory;
            ['NIFTY 50', 'SENSEX'].forEach((u) => {
              const rows = res.data?.[u] || [];
              const ce_total = rows.reduce((s, r) => s + (r.ce_oi || 0), 0);
              const pe_total = rows.reduce((s, r) => s + (r.pe_oi || 0), 0);
              const arr = (next[u] || []).slice(-29).concat([{ ts: now, ce: ce_total, pe: pe_total }]);
              next[u] = arr;

              // alert on large strike-level OI increase
              rows.forEach((r) => {
                const ceDelta = r.ce_delta_oi || 0;
                const peDelta = r.pe_delta_oi || 0;
                const ceKey = `${u}:${r.strike}:CE`;
                const peKey = `${u}:${r.strike}:PE`;
                if (ceDelta >= OI_ALERT_THRESHOLD && !alertTrackerRef.current[ceKey]) {
                  alerts.push({ type: 'CE', underlying: u, strike: r.strike, delta: ceDelta });
                  alertTrackerRef.current[ceKey] = true;
                }
                if (peDelta >= OI_ALERT_THRESHOLD && !alertTrackerRef.current[peKey]) {
                  alerts.push({ type: 'PE', underlying: u, strike: r.strike, delta: peDelta });
                  alertTrackerRef.current[peKey] = true;
                }
              });
            });
            setOiHistory(next);
            if (alerts.length > 0) {
              setOiAlerts((prev) => [...alerts, ...prev].slice(0, 5));
              alerts.forEach((alert) => {
                toast(`OI alert: ${alert.underlying} ${alert.strike} ${alert.type} +${alert.delta.toLocaleString('en-IN')}`, {
                  icon: '⚡',
                  style: {
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: '#0f172a',
                    color: '#f8fafc',
                  },
                });
              });
            }
          } catch (e) {
            // ignore history update errors
          }
          setError(null);
        } else {
          setError(res?.detail || 'OI snapshot failed');
        }
      } catch (e) {
        if (cancelled) return;
        setError(String(e?.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    // immediate
    poll();

    // poll every 4s
    timerRef.current = setInterval(poll, 4000);

    return () => {
      cancelled = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionId, clientId]);

  // On mount, fetch persisted history from backend (last 24h)
  useEffect(() => {
    if (!sessionId) return;

    const fetchHistory = async () => {
      try {
        const now = Math.floor(Date.now() / 1000);
        const from = now - 24 * 3600; // last 24 hours
        const resN = await fetch(`${API_BASE_URL}/api/oi/history/${encodeURIComponent(sessionId)}?underlying=${encodeURIComponent('NIFTY 50')}&from_ts=${from}`);
        const resS = await fetch(`${API_BASE_URL}/api/oi/history/${encodeURIComponent(sessionId)}?underlying=${encodeURIComponent('SENSEX')}&from_ts=${from}`);
        if (resN.ok) {
          const j = await resN.json();
          if (j?.status === 'success') {
            // prefill market minutes for today and merge
            const filled = fillMarketMinutes('NIFTY 50', j.data || []);
            setOiHistory((p) => ({ ...p, 'NIFTY 50': filled }));
          }
        }
        if (resS.ok) {
          const j = await resS.json();
          if (j?.status === 'success') {
            const filled = fillMarketMinutes('SENSEX', j.data || []);
            setOiHistory((p) => ({ ...p, SENSEX: filled }));
          }
        }
      } catch (e) {
        // ignore
      }
    };

    fetchHistory();
  }, [sessionId]);

  // when admin modal opens, fetch current server settings
  useEffect(() => {
    if (!adminOpen) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/oi/admin/settings`);
        if (!res.ok) return;
        const j = await res.json();
        if (j?.status === 'success' && !cancelled) {
          const s = j.settings || {};
          if (s.agg_method) setAggMethod(s.agg_method);
          if (s.trim_alpha != null) setTrimAlpha(String(s.trim_alpha));
          if (s.retention_days != null) setRetentionDays(String(s.retention_days));
        }
      } catch (e) {
        // ignore
      }
    })();
    return () => { cancelled = true; };
  }, [adminOpen]);

  // fill market minutes for today between 09:15 and 15:30 local time and merge history
  const fillMarketMinutes = (underlying, samples) => {
    try {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const open = new Date(today.getTime());
      open.setHours(9, 15, 0, 0);
      const close = new Date(today.getTime());
      close.setHours(15, 30, 0, 0);
      const fromTs = Math.floor(open.getTime() / 1000);
      const toTs = Math.floor(Math.min(close.getTime(), now.getTime()) / 1000);

      // map existing by ts
      const map = {};
      (samples || []).forEach((s) => {
        map[parseInt(s.ts, 10)] = { ts: parseInt(s.ts, 10), ce: s.ce, pe: s.pe };
      });

      const out = [];
      for (let t = fromTs; t <= toTs; t += 60) {
        if (map[t]) out.push(map[t]);
        else out.push({ ts: t, ce: null, pe: null });
      }
      return out;
    } catch (e) {
      return samples || [];
    }
  };

  useEffect(() => {
    if (error && !loading) {
      toast.error('OI tracker error');
    }
  }, [error, loading]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-gray-400 font-medium animate-pulse">Fetching Option OI Snapshot...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 pb-32 px-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">OI Tracker</h1>
          <p className="text-[10px] text-gray-500 font-bold uppercase tracking-[0.2em]">
            5 Calls + 5 Puts around ATM (delta OI)
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-3 py-1.5 rounded-full bg-slate-950/70 border border-white/10 shadow-[0_8px_30px_rgba(15,23,42,0.2)]">
            <span className="text-[10px] font-black text-slate-200 uppercase tracking-wider">
              Poll: ~4s
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="text-[11px] px-4 py-2 rounded-full bg-slate-950/80 border border-slate-700 text-slate-100 font-bold hover:bg-slate-900 transition"
              onClick={() => setAdminOpen(true)}
            >
              Settings
            </button>
            <button
              className="text-[11px] px-4 py-2 rounded-full bg-red-600/10 border border-red-600 text-red-300 font-bold hover:bg-red-600/20 transition"
              onClick={async () => {
                if (!confirm('Trigger prune now?')) return;
                try {
                  const res = await fetch(`${API_BASE_URL}/api/oi/admin/prune`, { method: 'POST' });
                  const j = await res.json();
                  if (res.ok && j?.status === 'success') {
                    toast.success('Prune triggered');
                  } else {
                    toast.error(j?.detail || 'Prune failed');
                  }
                } catch (e) {
                  toast.error('Prune failed');
                }
              }}
            >
              Prune
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-500/50 p-4 rounded-xl flex items-center justify-between gap-4 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-600 rounded-full flex items-center justify-center text-xl shadow-[0_0_20px_rgba(220,38,38,0.4)]">
              ⚠️
            </div>
            <div>
              <h4 className="text-white text-sm font-black uppercase tracking-wider">OI Fetch Failed</h4>
              <p className="text-[10px] text-red-200 font-bold uppercase opacity-80">{error}</p>
            </div>
          </div>
        </div>
      )}

      {snapshot && (
        <div className="space-y-6">
          <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest opacity-80">
            DEBUG rows NIFTY={snapshot?.['NIFTY 50']?.length ?? 0} SENSEX={snapshot?.['SENSEX']?.length ?? 0} | updated_at={lastUpdatedAt ?? '—'} | pollMs={lastPollMs ?? '—'}
          </div>
          {/* NIFTY OI trend chart */}
          <div className="glass-card p-3 rounded-2xl">
            <h4 className="text-sm font-bold text-white mb-2">NIFTY OI Trend (sum CE / sum PE)</h4>
            <div style={{ height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={oiHistory['NIFTY 50'] || []}>
                  <XAxis
                    dataKey="ts"
                    tickFormatter={(t) => new Date(t).toLocaleTimeString()}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                  />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} />
                  <Tooltip
                    labelFormatter={(t) => new Date(t).toLocaleString()}
                    formatter={(value) => value?.toLocaleString('en-IN')}
                  />
                  <Legend />
                    <Line type="monotone" dataKey="ce" stroke="#10b981" dot={false} name="CE Total OI" connectNulls={true} />
                    <Line type="monotone" dataKey="pe" stroke="#ef4444" dot={false} name="PE Total OI" connectNulls={true} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* simple crossover detection */}
            {(() => {
              const arr = oiHistory['NIFTY 50'] || [];
              if (arr.length < 3) return null;
              const p2 = arr[arr.length - 3];
              const p1 = arr[arr.length - 2];
              const p0 = arr[arr.length - 1];
              if (!p2 || !p1 || !p0) return null;
              const prevPrevDiff = (p2.ce || 0) - (p2.pe || 0);
              const prevDiff = (p1.ce || 0) - (p1.pe || 0);
              const curDiff = (p0.ce || 0) - (p0.pe || 0);
              // two-point confirmation: prevPrev and prev must have same sign, and cur opposite
              if (prevPrevDiff < 0 && prevDiff < 0 && curDiff > 0) {
                return <div className="mt-2 text-sm text-green-400 font-bold">Crossover: CE crossed above PE — bullish (2-point confirmed)</div>;
              }
              if (prevPrevDiff > 0 && prevDiff > 0 && curDiff < 0) {
                return <div className="mt-2 text-sm text-red-400 font-bold">Crossover: PE crossed above CE — bearish (2-point confirmed)</div>;
              }
              return null;
            })()}
          </div>

          <UnderlyingPanel name="NIFTY 50" rows={snapshot['NIFTY 50'] || []} />
          {/* SENSEX OI trend chart */}
          <div className="glass-card p-3 rounded-2xl">
            <h4 className="text-sm font-bold text-white mb-2">SENSEX OI Trend (sum CE / sum PE)</h4>
            <div style={{ height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={oiHistory['SENSEX'] || []}>
                  <XAxis
                    dataKey="ts"
                    tickFormatter={(t) => new Date(t).toLocaleTimeString()}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                  />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} />
                  <Tooltip
                    labelFormatter={(t) => new Date(t).toLocaleString()}
                    formatter={(value) => value?.toLocaleString('en-IN')}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="ce" stroke="#10b981" dot={false} name="CE Total OI" />
                  <Line type="monotone" dataKey="pe" stroke="#ef4444" dot={false} name="PE Total OI" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {(() => {
              const arr = oiHistory['SENSEX'] || [];
              if (arr.length < 2) return null;
              const a = arr[arr.length - 2];
              const b = arr[arr.length - 1];
              const prevDiff = a.ce - a.pe;
              const curDiff = b.ce - b.pe;
              if (prevDiff < 0 && curDiff > 0) {
                return <div className="mt-2 text-sm text-green-400 font-bold">Crossover: CE crossed above PE — bullish signal</div>;
              }
              if (prevDiff > 0 && curDiff < 0) {
                return <div className="mt-2 text-sm text-red-400 font-bold">Crossover: PE crossed above CE — bearish signal</div>;
              }
              return null;
            })()}
          </div>

          <UnderlyingPanel name="SENSEX" rows={snapshot['SENSEX'] || []} />
        </div>
      )}

      {/* Admin modal */}
      {adminOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setAdminOpen(false)} />
          <div className="relative w-full max-w-lg p-6 rounded-3xl bg-slate-950 border border-white/10 shadow-2xl shadow-black/40 z-10">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-xl font-black text-white">OI Admin Settings</h3>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500 mt-1">Manage aggregation and retention</p>
              </div>
              <button
                className="text-slate-400 hover:text-white text-sm"
                onClick={() => setAdminOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-2">
                <label className="text-sm text-slate-300 uppercase tracking-[0.2em]">Aggregation Method</label>
                <select
                  value={aggMethod}
                  onChange={(e) => setAggMethod(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white"
                >
                  <option value="trimmed">Trimmed Mean</option>
                  <option value="median">Median</option>
                  <option value="mean">Mean</option>
                </select>
              </div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                <div>
                  <label className="text-sm text-slate-300 uppercase tracking-[0.2em]">Trim Alpha</label>
                  <input
                    value={trimAlpha}
                    onChange={(e) => setTrimAlpha(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white"
                    placeholder="0.2"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-300 uppercase tracking-[0.2em]">Retention Days</label>
                  <input
                    value={retentionDays}
                    onChange={(e) => setRetentionDays(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white"
                    placeholder="14"
                  />
                </div>
              </div>
            </div>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-bold text-slate-200 hover:bg-white/10 transition sm:w-auto"
                onClick={() => setAdminOpen(false)}
              >
                Cancel
              </button>
              <button
                className="w-full rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white hover:bg-emerald-500 transition sm:w-auto"
                onClick={async () => {
                  setSavingSettings(true);
                  try {
                    const payload = { agg_method: aggMethod };
                    if (trimAlpha) payload.trim_alpha = parseFloat(trimAlpha);
                    if (retentionDays) payload.retention_days = parseInt(retentionDays, 10);
                    const res = await fetch(`${API_BASE_URL}/api/oi/admin/settings`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(payload),
                    });
                    const j = await res.json();
                    if (res.ok && j?.status === 'success') {
                      toast.success('Settings saved');
                      setAdminOpen(false);
                    } else {
                      toast.error(j?.detail || 'Failed to save settings');
                    }
                  } catch (e) {
                    toast.error('Failed to save settings');
                  } finally {
                    setSavingSettings(false);
                  }
                }}
                disabled={savingSettings}
              >
                {savingSettings ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      )}

      {!snapshot && !error && (
        <div className="py-10 text-center border border-white/5 rounded-3xl bg-black/20">
          <p className="text-[10px] text-gray-600 font-black uppercase tracking-widest">No snapshot yet</p>
        </div>
      )}
    </div>
  );
};

export default OITrackerTab;

