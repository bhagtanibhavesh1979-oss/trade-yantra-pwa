import { useState, useMemo } from 'react';
import toast from 'react-hot-toast';
import { runPlanetNakshatraBacktest } from '../services/api';

const PLANET_OPTIONS = ['Sun', 'Mars', 'Jupiter', 'Saturn', 'Mercury', 'Rahu', 'Ketu'];
const HORIZONS = [5, 10, 20];

// Color helpers
const retColor = (v) => {
  if (v === null || v === undefined || isNaN(v)) return 'text-gray-400';
  if (v > 0.005) return 'text-emerald-400 font-bold';
  if (v < -0.005) return 'text-red-400 font-bold';
  return 'text-gray-300';
};
const retBg = (v) => {
  if (v > 0.01) return 'bg-emerald-500/10 rounded-lg';
  if (v < -0.01) return 'bg-red-500/10 rounded-lg';
  return '';
};
const winColor = (v) => {
  if (v >= 60) return 'text-emerald-400 font-black';
  if (v >= 50) return 'text-yellow-400 font-bold';
  return 'text-red-400';
};
const fPct = (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '—' : `${(v * 100).toFixed(d)}%`;
const fWin = (v) => (v === null || v === undefined || isNaN(v)) ? '—' : `${Number(v).toFixed(1)}%`;

function HorizonCell({ row, market, horizon }) {
  const ret = row[`${market}_avg_ret_${horizon}d`];
  const win = row[`${market}_win_rate_${horizon}d`];
  const dd = row[`${market}_avg_dd_${horizon}d`];
  return (
    <div className={`flex flex-col items-center min-w-[52px] px-1.5 py-1 ${retBg(ret)}`}>
      <span className="text-[8px] text-gray-500 font-bold">{horizon}D</span>
      <span className={`text-[11px] ${retColor(ret)}`}>{fPct(ret)}</span>
      <span className={`text-[9px] ${winColor(win)}`}>{fWin(win)}</span>
      <span className="text-[8px] text-gray-600">↓{fPct(dd)}</span>
    </div>
  );
}

function DetailedHorizonCell({ row, market, horizon }) {
  const ret = row[`${market}_ret_${horizon}d`];
  const dd = row[`${market}_dd_${horizon}d`];
  return (
    <div className={`flex flex-col items-center min-w-[52px] px-1.5 py-1 ${retBg(ret)}`}>
      <span className="text-[8px] text-gray-500 font-bold">{horizon}D</span>
      <span className={`text-[11px] ${retColor(ret)}`}>{fPct(ret)}</span>
      <span className="text-[8px] text-gray-600">↓{fPct(dd)}</span>
    </div>
  );
}

function PlanetBacktestTab({ sessionId, clientId }) {
  const [years, setYears] = useState(5);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState([]);
  const [events, setEvents] = useState([]);
  const [meta, setMeta] = useState(null);
  const [selectedPlanets, setSelectedPlanets] = useState(() => new Set(PLANET_OPTIONS));
  const [filterPlanet, setFilterPlanet] = useState('All');
  const [filterEvent, setFilterEvent] = useState('All');
  const [viewMode, setViewMode] = useState('summary'); // 'summary' or 'detailed'
  const [ayanamsha, setAyanamsha] = useState('lahiri'); // lahiri | chitra | true_citra


  // Summary Sort
  const [sortKey, setSortKey] = useState('nifty_avg_ret_20d');
  const [sortDir, setSortDir] = useState('desc');

  // Detailed Sort
  const [detSortKey, setDetSortKey] = useState('date');
  const [detSortDir, setDetSortDir] = useState('desc');

  const togglePlanet = (planet) => {
    setSelectedPlanets((prev) => {
      const next = new Set(prev);
      if (next.has(planet)) next.delete(planet);
      else next.add(planet);
      if (next.size === 0) next.add(planet);
      return next;
    });
  };

  const handleRun = async () => {

    setLoading(true);
    setSummary([]);
    setEvents([]);
    setMeta(null);
    try {
      const res = await runPlanetNakshatraBacktest(sessionId, { years, planets: Array.from(selectedPlanets), sidereal_mode: ayanamsha });

      setSummary(res?.summary || []);
      setEvents(res?.events || []);
      setMeta(res?.meta || null);
      toast.success(`Backtest complete — ${res?.summary?.length || 0} groups, ${res?.events?.length || 0} transitions`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = (key) => {
    if (viewMode === 'summary') {
      if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      else { setSortKey(key); setSortDir('desc'); }
    } else {
      if (detSortKey === key) setDetSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      else { setDetSortKey(key); setDetSortDir('desc'); }
    }
  };

  const uniquePlanets = useMemo(() => {
    const list = viewMode === 'summary' ? summary : events;
    return ['All', ...Array.from(new Set(list.map((r) => r.planet)))];
  }, [summary, events, viewMode]);

  const uniqueEvents = useMemo(() => {
    const list = viewMode === 'summary' ? summary : events;
    return ['All', ...Array.from(new Set(list.map((r) => r.event_type)))];
  }, [summary, events, viewMode]);

  const displayedSummary = useMemo(() => {
    let rows = summary;
    if (filterPlanet !== 'All') rows = rows.filter((r) => r.planet === filterPlanet);
    if (filterEvent !== 'All') rows = rows.filter((r) => r.event_type === filterEvent);
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      if (typeof av === 'string') return sortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv);
      return sortDir === 'desc' ? bv - av : av - bv;
    });
  }, [summary, filterPlanet, filterEvent, sortKey, sortDir]);

  const displayedEvents = useMemo(() => {
    let rows = events;
    if (filterPlanet !== 'All') rows = rows.filter((r) => r.planet === filterPlanet);
    if (filterEvent !== 'All') rows = rows.filter((r) => r.event_type === filterEvent);
    return [...rows].sort((a, b) => {
      const av = a[detSortKey] ?? 0;
      const bv = b[detSortKey] ?? 0;
      if (typeof av === 'string') return detSortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv);
      return detSortDir === 'desc' ? bv - av : av - bv;
    });
  }, [events, filterPlanet, filterEvent, detSortKey, detSortDir]);

  // CSV Exporter
  const handleExport = () => {
    if (viewMode === 'summary') {
      if (!displayedSummary.length) return toast.error("No summary data to export");
      const headers = [
        'planet', 'event_type', 'entered_nakshatra', 'entered_pada',
        'nifty_avg_ret_5d', 'nifty_win_rate_5d', 'nifty_avg_dd_5d',
        'nifty_avg_ret_10d', 'nifty_win_rate_10d', 'nifty_avg_dd_10d',
        'nifty_avg_ret_20d', 'nifty_win_rate_20d', 'nifty_avg_dd_20d',
        'bn_avg_ret_5d', 'bn_win_rate_5d', 'bn_avg_dd_5d',
        'bn_avg_ret_10d', 'bn_win_rate_10d', 'bn_avg_dd_10d',
        'bn_avg_ret_20d', 'bn_win_rate_20d', 'bn_avg_dd_20d',
        'event_count'
      ];
      const headerNames = [
        'Planet', 'Event Type', 'Entered Nakshatra', 'Entered Pada',
        'Nifty Avg Ret 5D', 'Nifty WinRate 5D', 'Nifty Avg MaxDD 5D',
        'Nifty Avg Ret 10D', 'Nifty WinRate 10D', 'Nifty Avg MaxDD 10D',
        'Nifty Avg Ret 20D', 'Nifty WinRate 20D', 'Nifty Avg MaxDD 20D',
        'BankNifty Avg Ret 5D', 'BankNifty WinRate 5D', 'BankNifty Avg MaxDD 5D',
        'BankNifty Avg Ret 10D', 'BankNifty WinRate 10D', 'BankNifty Avg MaxDD 10D',
        'BankNifty Avg Ret 20D', 'BankNifty WinRate 20D', 'BankNifty Avg MaxDD 20D',
        'Event Count'
      ];
      downloadCSV(displayedSummary, headers, headerNames, `planet_backtest_summary_${years}y.csv`);
    } else {
      if (!displayedEvents.length) return toast.error("No detailed transitions data to export");
      const headers = [
        'date', 'planet', 'event_type', 'entered_nakshatra', 'entered_pada', 'prev_nakshatra', 'prev_pada',
        'nifty_ret_5d', 'nifty_dd_5d', 'nifty_ret_10d', 'nifty_dd_10d', 'nifty_ret_20d', 'nifty_dd_20d',
        'bn_ret_5d', 'bn_dd_5d', 'bn_ret_10d', 'bn_dd_10d', 'bn_ret_20d', 'bn_dd_20d'
      ];
      const headerNames = [
        'Date', 'Planet', 'Event Type', 'Entered Nakshatra', 'Entered Pada', 'Prev Nakshatra', 'Prev Pada',
        'Nifty Ret 5D', 'Nifty MaxDD 5D', 'Nifty Ret 10D', 'Nifty MaxDD 10D', 'Nifty Ret 20D', 'Nifty MaxDD 20D',
        'BankNifty Ret 5D', 'BankNifty MaxDD 5D', 'BankNifty Ret 10D', 'BankNifty MaxDD 10D', 'BankNifty Ret 20D', 'BankNifty MaxDD 20D'
      ];
      downloadCSV(displayedEvents, headers, headerNames, `planet_transitions_detailed_${years}y.csv`);
    }
  };

  const downloadCSV = (data, headers, headerNames, filename) => {
    const lines = [headerNames.join(",")];
    data.forEach((row) => {
      const line = headers.map((h) => {
        let val = row[h];
        if (val === null || val === undefined) return '';
        if (typeof val === 'string') {
          val = val.replace(/"/g, '""');
          if (val.includes(',') || val.includes('"') || val.includes('\n')) {
            val = `"${val}"`;
          }
        } else if (typeof val === 'number' && h.includes('ret') || h.includes('dd')) {
          // Format numeric returns/drawdowns as % in excel
          val = `${(val * 100).toFixed(4)}`;
        }
        return val;
      }).join(",");
      lines.push(line);
    });

    const blob = new Blob([lines.join("\n")], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("CSV Downloaded successfully");
  };

  const SortTh = ({ label, k, center }) => {
    const currentSortKey = viewMode === 'summary' ? sortKey : detSortKey;
    const currentSortDir = viewMode === 'summary' ? sortDir : detSortDir;
    return (
      <th
        className={`px-2 py-2 cursor-pointer select-none hover:text-white transition-colors whitespace-nowrap ${center ? 'text-center' : ''}`}
        onClick={() => toggleSort(k)}
      >
        {label}{currentSortKey === k ? (currentSortDir === 'desc' ? ' ▼' : ' ▲') : ''}
      </th>
    );
  };

  return (
    <div className="p-4 space-y-4 pb-28 max-w-6xl mx-auto">
      {/* Config card */}
      <div className="glass-card p-6 rounded-2xl border border-[var(--border-color)]">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h2 className="text-lg font-black flex items-center gap-2">
              <span className="text-2xl">🪐</span> Planet Nakshatra / Pada Backtest
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              Evaluate NIFTY &amp; BANKNIFTY returns after planetary Nakshatra/Pada transitions — 5d, 10d, 20d horizons.
            </p>
          </div>
          {meta && (
            <div className="text-right shrink-0 text-[10px] text-gray-500 space-y-0.5 bg-[var(--bg-secondary)]/50 px-3 py-1.5 rounded-xl border border-[var(--border-color)]">
              <div>📅 Range: <span className="font-bold text-gray-300">{meta.start_date}</span> to <span className="font-bold text-gray-300">{meta.end_date}</span></div>
              <div>⚡ Aligned Events: <span className="font-bold text-[var(--accent-blue)]">{meta.aligned_event_count ?? 0}</span> / {meta.event_count ?? 0}</div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="text-[10px] uppercase font-bold text-gray-500 mb-2 block">Backtest Years</label>
            <input
              type="number" min={1} max={30} value={years}
              onChange={(e) => setYears(Math.max(1, Math.min(30, parseInt(e.target.value || '5', 10))))}
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl px-4 py-3 outline-none focus:border-[var(--accent-blue)] transition-colors"
            />
          </div>
          <div className="md:col-span-2">
            <div className="text-[10px] uppercase font-bold text-gray-500 mb-2">Planets</div>
            <div className="flex flex-wrap gap-2">
              {PLANET_OPTIONS.map((p) => {
                const isOn = selectedPlanets.has(p);
                return (
                  <button key={p} onClick={() => togglePlanet(p)} type="button"
                    className={`px-3 py-1.5 rounded-xl border text-xs font-black transition-all ${isOn
                      ? 'bg-[var(--accent-blue)]/20 border-[var(--accent-blue)] text-[var(--accent-blue)]'
                      : 'bg-[var(--bg-secondary)] border-[var(--border-color)] text-[var(--text-primary)] hover:border-[var(--accent-blue)]'}`}>
                    {p}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="mt-5">
          <button onClick={handleRun} disabled={loading}
            className="w-full py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-2xl font-black text-sm shadow-xl shadow-blue-500/20 hover:scale-[1.01] active:scale-[0.98] transition-all disabled:opacity-50">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="62" strokeLinecap="round"/>
                </svg>
                COMPUTING PLANETARY TRANSITIONS…
              </span>
            ) : '▶  RUN BACKTEST'}
          </button>
        </div>
      </div>

      {/* Legend & View Toggles */}
      {(summary.length > 0 || events.length > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="glass-card px-4 py-2.5 rounded-2xl border border-[var(--border-color)] flex flex-wrap gap-4 text-[10px] text-gray-400 items-center">
            <span className="font-bold text-gray-300">Legend:</span>
            {viewMode === 'summary' ? (
              <>
                <span className="text-gray-300">Avg Ret / Win% / MaxDD</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"/> &gt;0.5% avg</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block"/> &lt;-0.5% avg</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block"/> Win ≥50%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"/> Win ≥60%</span>
              </>
            ) : (
              <>
                <span className="text-gray-300">Actual Ret / MaxDD</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"/> Pos Return</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block"/> Neg Return</span>
              </>
            )}
          </div>

          <div className="flex bg-[var(--bg-secondary)] p-1 rounded-xl border border-[var(--border-color)] items-center shadow-lg shrink-0">
            <button onClick={() => setViewMode('summary')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${viewMode === 'summary' ? 'bg-[var(--accent-blue)] text-white' : 'text-gray-400 hover:text-gray-200'}`}>
              📊 Summary View
            </button>
            <button onClick={() => setViewMode('detailed')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${viewMode === 'detailed' ? 'bg-[var(--accent-blue)] text-white' : 'text-gray-400 hover:text-gray-200'}`}>
              📅 Detailed Logs ({events.length})
            </button>
          </div>
        </div>
      )}

      {/* Results Box */}
      {viewMode === 'summary' && displayedSummary.length > 0 ? (
        <div className="glass-card rounded-2xl border border-[var(--border-color)] overflow-hidden">
          {/* Filters & Export */}
          <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 border-b border-[var(--border-color)]/40 bg-[var(--bg-secondary)]/30">
            <span className="text-[10px] text-gray-500 font-bold uppercase">Filter:</span>
            <select value={filterPlanet} onChange={(e) => setFilterPlanet(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-2 py-1 text-xs outline-none">
              {uniquePlanets.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={filterEvent} onChange={(e) => setFilterEvent(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-2 py-1 text-xs outline-none">
              {uniqueEvents.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>

            <button onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600/20 hover:bg-emerald-600 border border-emerald-500/20 text-emerald-400 hover:text-white rounded-lg text-xs font-bold transition-all ml-auto">
              📥 Export Summary to Excel
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[860px]">
              <thead className="text-gray-400 bg-[var(--bg-secondary)]/40">
                <tr>
                  <SortTh label="Planet" k="planet" />
                  <SortTh label="Event" k="event_type" />
                  <th className="px-2 py-2">Nakshatra</th>
                  <th className="px-2 py-2">Pada</th>
                  <th className="px-2 py-2 text-center text-blue-400 font-black">
                    NIFTY <span className="text-[8px] text-gray-500 font-normal">(5d / 10d / 20d)</span>
                  </th>
                  <th className="px-2 py-2 text-center text-purple-400 font-black">
                    BANKNIFTY <span className="text-[8px] text-gray-500 font-normal">(5d / 10d / 20d)</span>
                  </th>
                  <SortTh label="Count" k="event_count" center />
                </tr>
              </thead>
              <tbody>
                {displayedSummary.map((r, idx) => (
                  <tr key={`${r.planet}-${r.event_type}-${r.entered_nakshatra}-${r.entered_pada}-${idx}`}
                    className="border-t border-[var(--border-color)]/20 hover:bg-white/[0.02] transition-colors">
                    <td className="px-2 py-2 font-black text-[var(--accent-blue)]">{r.planet}</td>
                    <td className="px-2 py-2 text-gray-400 text-[10px]">{r.event_type}</td>
                    <td className="px-2 py-2 font-bold">{r.entered_nakshatra || '—'}</td>
                    <td className="px-2 py-2 text-gray-400">{r.entered_pada ?? '—'}</td>
                    {/* NIFTY horizons */}
                    <td className="px-2 py-1.5">
                      <div className="flex gap-1 justify-center">
                        {HORIZONS.map((h) => <HorizonCell key={h} row={r} market="nifty" horizon={h} />)}
                      </div>
                    </td>
                    {/* BANKNIFTY horizons */}
                    <td className="px-2 py-1.5">
                      <div className="flex gap-1 justify-center">
                        {HORIZONS.map((h) => <HorizonCell key={h} row={r} market="bn" horizon={h} />)}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-center text-gray-400">{r.event_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Detailed Transitions Log View */}
      {viewMode === 'detailed' && displayedEvents.length > 0 ? (
        <div className="glass-card rounded-2xl border border-[var(--border-color)] overflow-hidden">
          {/* Filters & Export */}
          <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 border-b border-[var(--border-color)]/40 bg-[var(--bg-secondary)]/30">
            <span className="text-[10px] text-gray-500 font-bold uppercase">Filter:</span>
            <select value={filterPlanet} onChange={(e) => setFilterPlanet(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-2 py-1 text-xs outline-none">
              {uniquePlanets.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={filterEvent} onChange={(e) => setFilterEvent(e.target.value)}
              className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-2 py-1 text-xs outline-none">
              {uniqueEvents.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>

            <button onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600/20 hover:bg-emerald-600 border border-emerald-500/20 text-emerald-400 hover:text-white rounded-lg text-xs font-bold transition-all ml-auto">
              📥 Export Detailed Logs to Excel
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[900px]">
              <thead className="text-gray-400 bg-[var(--bg-secondary)]/40">
                <tr>
                  <SortTh label="Event Date" k="date" />
                  <SortTh label="Planet" k="planet" />
                  <SortTh label="Transition Type" k="event_type" />
                  <th className="px-2 py-2">Entered Nak / Pada</th>
                  <th className="px-2 py-2">Previous Nak / Pada</th>
                  <th className="px-2 py-2 text-center text-blue-400 font-black">
                    NIFTY <span className="text-[8px] text-gray-500 font-normal">(5d / 10d / 20d Ret &amp; MaxDD)</span>
                  </th>
                  <th className="px-2 py-2 text-center text-purple-400 font-black">
                    BANKNIFTY <span className="text-[8px] text-gray-500 font-normal">(5d / 10d / 20d Ret &amp; MaxDD)</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {displayedEvents.map((r, idx) => (
                  <tr key={`${r.date}-${r.planet}-${r.event_type}-${idx}`}
                    className="border-t border-[var(--border-color)]/20 hover:bg-white/[0.02] transition-colors">
                    <td className="px-2 py-2 font-bold text-gray-200 whitespace-nowrap">{r.date}</td>
                    <td className="px-2 py-2 font-black text-[var(--accent-blue)]">{r.planet}</td>
                    <td className="px-2 py-2 text-gray-400 text-[10px]">{r.event_type}</td>
                    <td className="px-2 py-2 font-bold text-gray-300">
                      {r.entered_nakshatra} <span className="text-xs text-gray-500 font-normal">P{r.entered_pada}</span>
                    </td>
                    <td className="px-2 py-2 text-gray-400">
                      {r.prev_nakshatra ? `${r.prev_nakshatra} P${r.prev_pada}` : '—'}
                    </td>
                    {/* NIFTY Detailed */}
                    <td className="px-2 py-1.5">
                      <div className="flex gap-1 justify-center">
                        {HORIZONS.map((h) => <DetailedHorizonCell key={h} row={r} market="nifty" horizon={h} />)}
                      </div>
                    </td>
                    {/* BANKNIFTY Detailed */}
                    <td className="px-2 py-1.5">
                      <div className="flex gap-1 justify-center">
                        {HORIZONS.map((h) => <DetailedHorizonCell key={h} row={r} market="bn" horizon={h} />)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {(summary.length === 0 && events.length === 0) && meta ? (
        <div className="glass-card p-8 rounded-2xl border border-yellow-500/30 bg-yellow-500/5 text-center">
          <div className="text-yellow-400 font-bold">No aligned events for this range.</div>
          <div className="text-gray-500 text-xs mt-1">Try increasing years or selecting more planets.</div>
        </div>
      ) : null}
    </div>
  );
}

export default PlanetBacktestTab;
