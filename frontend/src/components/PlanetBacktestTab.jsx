import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { runPlanetNakshatraBacktest } from '../services/api';

const PLANET_OPTIONS = [
  'Sun',
  'Mars',
  'Jupiter',
  'Saturn',
  'Mercury',
  'Rahu',
  'Ketu',
];

const EVENT_TYPES = ['NakshatraChange', 'PadaChange'];

function PlanetBacktestTab({ sessionId, clientId }) {
  const [years, setYears] = useState(5);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState([]);
  const [meta, setMeta] = useState(null);

  const selectedPlanets = useMemo(() => new Set(PLANET_OPTIONS), []);

  const handleRun = async () => {
    setLoading(true);
    setSummary([]);
    setMeta(null);
    try {
      const res = await runPlanetNakshatraBacktest(sessionId, { years });
      setSummary(res?.summary || []);
      setMeta(res?.meta || null);
      toast.success('Planet Nakshatra/Pada Backtest complete');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 space-y-4 pb-24 max-w-5xl mx-auto">
      <div className="glass-card p-6 rounded-2xl border border-[var(--border-color)]">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-black flex items-center gap-2">
              <span className="text-2xl">🪐</span> Planet Nakshatra/Pada Backtest
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              Computes planet transitions (Nakshatra + Pada) and evaluates market performance on next 5/10/20 trading days.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Backtest Years</label>
            <input
              type="number"
              min={1}
              max={30}
              value={years}
              onChange={(e) => setYears(Math.max(1, Math.min(30, parseInt(e.target.value || '5', 10))))}
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl px-4 py-3 outline-none"
            />
          </div>

          <div className="md:col-span-2">
            <div className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Planets</div>
            <div className="flex flex-wrap gap-2">
              {PLANET_OPTIONS.map((p) => (
                <span key={p} className="px-3 py-1.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] text-xs font-black">
                  {p}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5">
          <button
            onClick={handleRun}
            disabled={loading}
            className="w-full py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-2xl font-black text-sm shadow-xl shadow-blue-500/20 hover:scale-[1.01] active:scale-[0.98] transition-all disabled:opacity-50"
          >
            {loading ? 'RUNNING...' : 'RUN BACKTEST'}
          </button>
        </div>
      </div>

      {meta && (
        <div className="glass-card p-4 rounded-2xl border border-[var(--border-color)]">
          <div className="text-xs text-gray-500">{meta.start_date} → {meta.end_date} | years: {meta.years} | events: {meta.event_count} | aligned: {meta.aligned_event_count}</div>
        </div>
      )}

      {summary && summary.length > 0 ? (
        <div className="glass-card p-4 rounded-2xl border border-[var(--border-color)] overflow-x-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-black text-gray-500 uppercase tracking-widest">Summary (Grouped)</h3>
            <span className="text-[10px] text-[var(--accent-blue)] font-bold">Rows: {summary.length}</span>
          </div>

          <table className="min-w-[980px] w-full text-left text-xs">
            <thead className="text-gray-400">
              <tr>
                <th className="px-2 py-2">Planet</th>
                <th className="px-2 py-2">Event</th>
                <th className="px-2 py-2">Entered Nak</th>
                <th className="px-2 py-2">Entered Pada</th>
                <th className="px-2 py-2">Nifty Avg Ret 20d</th>
                <th className="px-2 py-2">Bank Avg Ret 20d</th>
                <th className="px-2 py-2">Win-rate Nifty 20d</th>
                <th className="px-2 py-2">Win-rate Bank 20d</th>
                <th className="px-2 py-2">Event Count</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((r, idx) => (
                <tr key={`${r.planet}-${r.event_type}-${r.entered_nakshatra}-${r.entered_pada}-${idx}`} className="border-t border-[var(--border-color)]/30">
                  <td className="px-2 py-2 font-black">{r.planet}</td>
                  <td className="px-2 py-2">{r.event_type}</td>
                  <td className="px-2 py-2">{r.entered_nakshatra}</td>
                  <td className="px-2 py-2">{r.entered_pada}</td>
                  <td className="px-2 py-2 font-black text-[var(--accent-blue)]">{(r.nifty_avg_ret_20d * 100).toFixed(2)}%</td>
                  <td className="px-2 py-2 font-black text-[var(--accent-blue)]">{(r.bn_avg_ret_20d * 100).toFixed(2)}%</td>
                  <td className="px-2 py-2">{(r.nifty_win_rate_20d || 0).toFixed(1)}%</td>
                  <td className="px-2 py-2">{(r.bn_win_rate_20d || 0).toFixed(1)}%</td>
                  <td className="px-2 py-2">{r.event_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : summary && summary.length === 0 ? (
        <div className="glass-card p-8 rounded-2xl border border-yellow-500/30 bg-yellow-500/5 text-center">
          <div className="text-yellow-400 font-bold">No aligned events for this range.</div>
        </div>
      ) : null}
    </div>
  );
}

export default PlanetBacktestTab;

