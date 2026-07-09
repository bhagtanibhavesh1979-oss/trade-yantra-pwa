import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';
import wsClient from '../services/websocket';
import api from '../services/api';

// ── localStorage helpers ──────────────────────────────────────────────────────
const storageKey   = (sym) => `astro_levels_${sym.replace(/\s+/g, '_')}`;
const DATE_RANGE_KEY = 'astro_date_range';

const saveToStorage = (sym, levels) => {
  try { localStorage.setItem(storageKey(sym), JSON.stringify({ levels })); } catch (_) {}
};
const loadFromStorage = (sym) => {
  try { const r = localStorage.getItem(storageKey(sym)); return r ? JSON.parse(r) : null; } catch (_) { return null; }
};
const saveDateRange = (start, end) => {
  try { localStorage.setItem(DATE_RANGE_KEY, JSON.stringify({ start, end })); } catch (_) {}
};
const loadDateRange = () => {
  try { const r = localStorage.getItem(DATE_RANGE_KEY); return r ? JSON.parse(r) : { start: '', end: '' }; } catch (_) { return { start: '', end: '' }; }
};

const AstroChart = ({ session, watchlist, externalSymbol, theme = 'dark', compact = false }) => {
  const chartRef         = useRef(null);
  const containerRef     = useRef(null);
  const chartInstanceRef = useRef(null);
  const candleSeriesRef  = useRef(null);
  const lastCandleRef    = useRef(null);
  const rawCandlesRef    = useRef([]);
  const priceLineRefs    = useRef([]);
  const hLineRefs        = useRef([]);   // [{pl, price, id}]
  const vLineRefs        = useRef([]);   // [{id, time, element}]

  const [symbol,        setSymbol]        = useState('NIFTY 50');
  const [token,         setToken]         = useState('99926000');
  const [exchange,      setExchange]      = useState('NSE');
  const [timeframe,     setTimeframe]     = useState('15m');
  const [searchQuery,   setSearchQuery]   = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching,   setIsSearching]   = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [error,         setError]         = useState(null);
  const [startDate,     setStartDate]     = useState(() => loadDateRange().start);
  const [endDate,       setEndDate]       = useState(() => loadDateRange().end);
  const [levelsDrawn,   setLevelsDrawn]   = useState(false);
  const [ohlc,          setOhlc]          = useState(null);
  const [nakshatra,     setNakshatra]     = useState(null);  // current Moon nakshatra
  const [drawMode,      setDrawMode]      = useState(false);
  const [lineType,      setLineType]      = useState('horizontal'); // 'horizontal' or 'vertical'
  const [lineValue,     setLineValue]     = useState('');
  const [lineLabel,     setLineLabel]     = useState('');
  const drawModeRef     = useRef(false);
  const lineTypeRef     = useRef('horizontal');
  const lineLabelRef    = useRef('');
  const overlayRef      = useRef(null);

  const symbolRef    = useRef(symbol);
  const tokenRef     = useRef(token);
  const exchangeRef  = useRef(exchange);
  const timeframeRef = useRef(timeframe);

  const timeframes = [
    { label: '1m',  value: '1m'  }, { label: '3m',  value: '3m'  },
    { label: '5m',  value: '5m'  }, { label: '15m', value: '15m' },
    { label: '30m', value: '30m' }, { label: '1H',  value: '1H'  },
    { label: '4H',  value: '4H'  }, { label: '1D',  value: '1D'  },
    { label: '1W',  value: '1W'  }, { label: '1M',  value: '1M'  },
  ];

  // ── Keep refs in sync ────────────────────────────────────────────────────────
  useEffect(() => {
    symbolRef.current    = symbol;
    tokenRef.current     = token;
    exchangeRef.current  = exchange;
    timeframeRef.current = timeframe;
    drawModeRef.current  = drawMode;    lineTypeRef.current  = lineType;
    lineLabelRef.current = lineLabel;  });

  // ── Persist date range whenever it changes ───────────────────────────────────
  useEffect(() => {
    saveDateRange(startDate, endDate);
  }, [startDate, endDate]);

  // ── Initialize chart ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;

    lineTypeRef.current = lineType;
    lineLabelRef.current = lineLabel;

    const isLight = (theme === 'light') || document.documentElement.classList.contains('light-theme');
    const chartOpts = isLight ? {
      autoSize: true,
      layout: { background: { color: '#ffffff' }, textColor: '#1f2937' },
      grid: { vertLines: { color: '#e6e6e6' }, horzLines: { color: '#e6e6e6' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#e6e6e6' },
      timeScale: { borderColor: '#e6e6e6', visible: true, secondsVisible: false, timeVisible: true },
    } : {
      autoSize: true,
      layout: { background: { color: '#0d0d1a' }, textColor: '#c3c3d9' },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#1a1a2e' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#2a2a4a' },
      timeScale: { borderColor: '#2a2a4a', visible: true, secondsVisible: false, timeVisible: true },
    };

    let chartInstance;
    try {
      chartInstance = createChart(chartRef.current, chartOpts);
      const candleSeries = chartInstance.addSeries(CandlestickSeries, isLight ? {
        upColor: '#16a34a', downColor: '#ef4444', borderVisible: false, wickUpColor: '#16a34a', wickDownColor: '#ef4444',
      } : {
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350',
      });

      chartInstanceRef.current = chartInstance;
      candleSeriesRef.current  = candleSeries;

      chartInstance.subscribeCrosshairMove((param) => {
        if (!param.time || !param.seriesData) { setOhlc(null); return; }
        const bar = param.seriesData.get(candleSeries);
        if (bar) setOhlc({ open: bar.open, high: bar.high, low: bar.low, close: bar.close });
        else setOhlc(null);
      });

      // H-Line: use LWC subscribeClick — gives pixel coords that we convert to price
      chartInstance.subscribeClick((param) => {
        if (!drawModeRef.current || !param.point) return;
        const currentLineType = lineTypeRef.current;
        const currentLabel = lineLabelRef.current;
        if (currentLineType === 'horizontal') {
          const price = chartInstance.priceScale('right')?.coordinateToPrice(param.point.y);
          if (price == null || isNaN(price)) return;
          const id = Date.now();
          const pl = candleSeries.createPriceLine({
            price,
            color: '#f0b429',
            lineWidth: 1,
            lineStyle: 0,
            axisLabelVisible: true,
            title: currentLabel || '─',
            draggable: true,
          });
          hLineRefs.current.push({ pl, price, id, label: currentLabel });
          try {
            const key = `astro_hlines_${symbolRef.current.replace(/\s+/g,'_')}`;
            localStorage.setItem(key, JSON.stringify(hLineRefs.current.map(h => ({ price: h.price, id: h.id, label: h.label }))));
          } catch(_) {}
        } else {
          const time = param.time;
          if (time == null) return;
          const id = Date.now();
          const entry = { id, time, label: currentLabel || '│', element: null };
          vLineRefs.current.push(entry);
          saveVLines(symbolRef.current);
          renderVLines();
        }
        setDrawMode(false);
        setLineValue('');
        setLineLabel('');
      });

      if (typeof chartInstance.timeScale().subscribeVisibleTimeRangeChange === 'function') {
        chartInstance.timeScale().subscribeVisibleTimeRangeChange(renderVLines);
      }
    } catch (err) {
      console.error('[AstroChart] chart init failed:', err);
      setError('Chart initialization failed. See console for details.');
      return undefined;
    }

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
        candleSeriesRef.current  = null;
      }
    };
  }, [theme]);

  // ── Restore H-Lines from localStorage for a symbol ────────────────────────────
  const restoreHLines = useCallback((sym) => {
    if (!candleSeriesRef.current) return;
    hLineRefs.current.forEach(h => { try { candleSeriesRef.current.removePriceLine(h.pl); } catch(_) {} });
    hLineRefs.current = [];
    try {
      const key = `astro_hlines_${sym.replace(/\s+/g,'_')}`;
      const raw = localStorage.getItem(key);
      if (!raw) return;
      JSON.parse(raw).forEach(({ price, id, label }) => {
        const pl = candleSeriesRef.current.createPriceLine({
          price, color: '#f0b429', lineWidth: 1, lineStyle: 0,
          axisLabelVisible: true, title: label || '─', draggable: true,
        });
        hLineRefs.current.push({ pl, price, id, label });
      });
    } catch(_) {}
  }, []);

  const renderVLines = useCallback(() => {
    if (!chartInstanceRef.current || !overlayRef.current) return;
    const overlay = overlayRef.current;
    const timeScale = chartInstanceRef.current.timeScale();
    vLineRefs.current.forEach((item) => {
      const x = timeScale.timeToCoordinate(item.time);
      if (x == null || isNaN(x)) {
        if (item.element) item.element.style.display = 'none';
        return;
      }
      if (!item.element) {
        const line = document.createElement('div');
        line.style.position = 'absolute';
        line.style.width = '2px';
        line.style.background = '#f0b429';
        line.style.top = '0';
        line.style.bottom = '0';
        line.style.pointerEvents = 'none';
        line.style.zIndex = '10';
        const label = document.createElement('div');
        label.style.position = 'absolute';
        label.style.top = '8px';
        label.style.left = '4px';
        label.style.padding = '2px 5px';
        label.style.background = 'rgba(240,180,41,0.9)';
        label.style.color = '#000';
        label.style.fontSize = '10px';
        label.style.fontWeight = '700';
        label.style.whiteSpace = 'nowrap';
        label.style.pointerEvents = 'none';
        label.textContent = item.label || '│';
        line.appendChild(label);
        overlay.appendChild(line);
        item.element = line;
      }
      item.element.style.display = 'block';
      item.element.style.left = `${Math.round(x)}px`;
    });
  }, []);

  const saveVLines = useCallback((sym) => {
    try {
      const key = `astro_vlines_${sym.replace(/\s+/g,'_')}`;
      localStorage.setItem(key, JSON.stringify(vLineRefs.current.map(({ time, label }) => ({ time, label }))));
    } catch(_) {}
  }, []);

  const restoreVLines = useCallback((sym) => {
    if (!overlayRef.current) return;
    vLineRefs.current.forEach(item => { if (item.element) item.element.remove(); });
    vLineRefs.current = [];
    try {
      const key = `astro_vlines_${sym.replace(/\s+/g,'_')}`;
      const raw = localStorage.getItem(key);
      if (!raw) return;
      JSON.parse(raw).forEach(({ time, label }) => {
        vLineRefs.current.push({ id: Date.now() + Math.random(), time, label, element: null });
      });
      setTimeout(() => renderVLines(), 100);
    } catch(_) {}
  }, [renderVLines]);

  const clearAllVLines = useCallback(() => {
    vLineRefs.current.forEach(item => { if (item.element) item.element.remove(); });
    vLineRefs.current = [];
    try {
      const key = `astro_vlines_${symbolRef.current.replace(/\s+/g,'_')}`;
      localStorage.removeItem(key);
    } catch(_) {}
  }, []);

  const addHorizontalLine = useCallback((price, label = '') => {
    if (!candleSeriesRef.current || price == null || isNaN(price)) return;
    const id = Date.now();
    const pl = candleSeriesRef.current.createPriceLine({
      price,
      color: '#f0b429',
      lineWidth: 1,
      lineStyle: 0,
      axisLabelVisible: true,
      title: label || '─',
      draggable: true,
    });
    hLineRefs.current.push({ pl, price, id, label });
    try {
      const key = `astro_hlines_${symbolRef.current.replace(/\s+/g,'_')}`;
      localStorage.setItem(key, JSON.stringify(hLineRefs.current.map(h => ({ price: h.price, id: h.id, label: h.label }))));
    } catch(_) {}
  }, []);

  const addVerticalLine = useCallback((time, label = '') => {
    if (!overlayRef.current || time == null) return;
    const entry = { id: Date.now(), time, label: label || '│', element: null };
    vLineRefs.current.push(entry);
    saveVLines(symbolRef.current);
    renderVLines();
  }, [renderVLines, saveVLines]);

  const parseLineTime = useCallback((value) => {
    if (!value) return null;
    const text = value.trim();
    if (/^\d+$/.test(text)) return Number(text);
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    const dt = new Date(text);
    if (!isNaN(dt)) return Math.floor(dt.getTime() / 1000);
    return null;
  }, []);

  const handleAddLine = useCallback(() => {
    if (!lineValue) return;
    if (lineType === 'horizontal') {
      const price = parseFloat(lineValue);
      if (!isNaN(price)) addHorizontalLine(price, lineLabel);
    } else {
      const time = parseLineTime(lineValue);
      if (time != null) addVerticalLine(time, lineLabel);
    }
    setLineValue('');
    setLineLabel('');
  }, [lineType, lineValue, lineLabel, addHorizontalLine, addVerticalLine, parseLineTime]);

  // ── Clear all H-Lines ───────────────────────────────────────────────────────────
  const clearAllHLines = useCallback(() => {
    hLineRefs.current.forEach(h => { try { candleSeriesRef.current.removePriceLine(h.pl); } catch(_) {} });
    hLineRefs.current = [];
    try {
      const key = `astro_hlines_${symbolRef.current.replace(/\s+/g,'_')}`;
      localStorage.removeItem(key);
    } catch(_) {}
  }, []);

  const clearAllLines = useCallback(() => {
    clearAllHLines();
    clearAllVLines();
  }, [clearAllHLines, clearAllVLines]);

  // ── Draw Pine Script levels ──────────────────────────────────────────────────
  const drawLevels = useCallback((start, end) => {
    if (!candleSeriesRef.current || !start || !end) return;

    priceLineRefs.current.forEach(pl => { try { candleSeriesRef.current.removePriceLine(pl); } catch (_) {} });
    priceLineRefs.current = [];
    setLevelsDrawn(false);

    const isDailyOrAbove = ['1D', '1W', '1M'].includes(timeframeRef.current);
    let startTs, endTs;
    if (isDailyOrAbove) {
      startTs = start; endTs = end;
    } else {
      startTs = Math.floor(new Date(`${start}T09:15:00+05:30`).getTime() / 1000) + 19800;
      endTs   = Math.floor(new Date(`${end}T15:30:00+05:30`).getTime()   / 1000) + 19800;
    }

    let rangeHigh = null, rangeLow = null;
    for (const [ts, , h, l] of rawCandlesRef.current) {
      if (ts >= startTs && ts <= endTs) {
        rangeHigh = rangeHigh === null ? h : Math.max(rangeHigh, h);
        rangeLow  = rangeLow  === null ? l : Math.min(rangeLow,  l);
      }
    }

    if (rangeHigh === null || rangeLow === null) { setError('No candles in selected range.'); return; }

    const diff = rangeHigh - rangeLow;
    const mid  = (rangeHigh + rangeLow) / 2;

    const defs = [
      { price: rangeHigh,              color: '#1CB11C', title: 'Resistance'    },
      { price: rangeLow,               color: '#FF0000', title: 'Support'       },
      { price: mid,                    color: '#800080', title: 'Midpoint'      },
      { price: rangeHigh + diff,       color: '#f97316', title: 'Target High 1' },
      { price: rangeHigh + 2 * diff,   color: '#fb8c00', title: 'Target High 2' },
      { price: rangeHigh + 3 * diff,   color: '#ea580c', title: 'Target High 3' },
      { price: rangeLow  - diff,       color: '#1CB11C', title: 'Target Low 1'  },
      { price: rangeLow  - 2 * diff,   color: '#1CB11C', title: 'Target Low 2'  },
      { price: rangeLow  - 3 * diff,   color: '#1CB11C', title: 'Target Low 3'  },
      { price: rangeHigh + 0.5 * diff, color: '#D620B5', title: 'Mid High 1'   },
      { price: rangeHigh + 1.5 * diff, color: '#D620B5', title: 'Mid High 2'   },
      { price: rangeHigh + 2.5 * diff, color: '#D620B5', title: 'Mid High 3'   },
      { price: rangeLow  - 0.5 * diff, color: '#D620B5', title: 'Mid Low 1'    },
      { price: rangeLow  - 1.5 * diff, color: '#D620B5', title: 'Mid Low 2'    },
      { price: rangeLow  - 2.5 * diff, color: '#D620B5', title: 'Mid Low 3'    },
    ];

    defs.forEach(({ price, color, title }) => {
      const pl = candleSeriesRef.current.createPriceLine({
        price, color, title, lineWidth: 1, lineStyle: 0, axisLabelVisible: true,
      });
      priceLineRefs.current.push(pl);
    });

    setLevelsDrawn(true);
    saveToStorage(symbolRef.current, { start, end });
  }, []);

  // ── Clear levels ─────────────────────────────────────────────────────────────
  const clearLevels = useCallback(() => {
    priceLineRefs.current.forEach(pl => { try { candleSeriesRef.current.removePriceLine(pl); } catch (_) {} });
    priceLineRefs.current = [];
    setLevelsDrawn(false);
    saveToStorage(symbolRef.current, null);
  }, []);

  // ── Fetch Nakshatra transitions and set chart markers ────────────────────────
  const fetchNakshatras = useCallback(async (candles) => {
    if (!candles.length || !candleSeriesRef.current) return;

    const sessionId = session?.sessionId || session?.session_id;
    const clientId  = session?.clientId  || session?.client_id;
    if (!sessionId) return;

    const isDailyOrAbove = ['1D', '1W', '1M'].includes(timeframeRef.current);

    // Get unix timestamps from candle data
    let fromTs, toTs;
    if (isDailyOrAbove) {
      // Daily candles: time is 'YYYY-MM-DD', convert to unix
      const toDate = (dateStr) => {
        const [y, m, d] = dateStr.split('-').map(Number);
        return Math.floor(new Date(y, m - 1, d, 9, 15, 0).getTime() / 1000) + 19800;
      };
      fromTs = toDate(candles[0][0]);
      toTs   = toDate(candles[candles.length - 1][0]);
    } else {
      fromTs = candles[0][0];
      toTs   = candles[candles.length - 1][0];
    }

    try {
      const res = await api.get('/api/astro/nakshatras', {
        params: { from_ts: fromTs, to_ts: toTs, session_id: sessionId, client_id: clientId },
      });

      const { transitions, current } = res.data;
      setNakshatra(current);

      if (!transitions?.length || !candleSeriesRef.current) return;

      // Map each transition to the nearest candle timestamp
      const markers = transitions.map((t) => {
        // Find candle closest to transition timestamp
        let closest = candles[0];
        let minDiff = Infinity;
        for (const c of candles) {
          const cTs = isDailyOrAbove
            ? Math.floor(new Date(c[0]).getTime() / 1000)
            : c[0];
          const diff = Math.abs(cTs - t.timestamp);
          if (diff < minDiff) { minDiff = diff; closest = c; }
        }

        // Alternate above/below for readability
        const pos   = t.index % 2 === 0 ? 'aboveBar' : 'belowBar';
        const shape = pos === 'aboveBar' ? 'arrowDown' : 'arrowUp';

        // Color by nakshatra group (every 3 nakshatras in a cycle)
        const colors = ['#7c6af5', '#26a69a', '#f0b429', '#ef5350', '#D620B5',
                        '#4fc3f7', '#81c784', '#ffb74d', '#e57373'];
        const color = colors[Math.floor(t.index / 3) % colors.length];

        return {
          time:     closest[0],
          position: pos,
          color,
          shape,
          text:     `${t.nakshatra}${t.pada ? ' P' + t.pada : ''}`,
          size:     1,
          id:       `nak_${t.timestamp}`,
        };
      });

      // Sort markers by time (required by lightweight-charts)
      markers.sort((a, b) => {
        if (typeof a.time === 'string') return a.time.localeCompare(b.time);
        return a.time - b.time;
      });

      candleSeriesRef.current.setMarkers(markers);
      console.log(`[AstroChart] ${markers.length} nakshatra markers set`);
    } catch (err) {
      console.warn('[AstroChart] Nakshatra fetch failed:', err.message);
    }
  }, [session]);

  // ── Load historical data ─────────────────────────────────────────────────────
  const zoomToRecentRange = useCallback(() => {
    if (!chartInstanceRef.current || !rawCandlesRef.current || rawCandlesRef.current.length === 0) return;
    const candles = rawCandlesRef.current;
    const last = candles[candles.length - 1];
    let endTime = last.time;
    let startTime = null;

    if (typeof endTime === 'string') {
      const endDate = new Date(`${endTime}T00:00:00Z`);
      const threshold = new Date(endDate.getTime() - 2 * 86400 * 1000);
      for (let i = candles.length - 1; i >= 0; i -= 1) {
        const current = new Date(`${candles[i][0]}T00:00:00Z`);
        if (current >= threshold) startTime = candles[i][0];
        else break;
      }
      if (!startTime) startTime = candles[Math.max(0, candles.length - 2)][0];
    } else {
      endTime = Number(endTime);
      const threshold = endTime - 2 * 86400;
      for (let i = candles.length - 1; i >= 0; i -= 1) {
        const current = Number(candles[i][0]);
        if (current >= threshold) startTime = current;
        else break;
      }
      if (!startTime) startTime = candles[Math.max(0, candles.length - 2)][0];
    }

    const timeScale = chartInstanceRef.current.timeScale();
    if (typeof timeScale.setVisibleRange === 'function') {
      timeScale.setVisibleRange({ from: startTime, to: endTime });
    }
  }, []);

  const loadHistoricalData = useCallback(async (sym, tok, exch, tf) => {
    const sessionId = session?.sessionId || session?.session_id;
    const clientId  = session?.clientId  || session?.client_id;
    if (!sessionId) { setError('No active session.'); return; }
    if (!chartInstanceRef.current || !candleSeriesRef.current) return;

    setIsLoadingData(true);
    setError(null);

    // Clear stale levels
    priceLineRefs.current.forEach(pl => { try { candleSeriesRef.current.removePriceLine(pl); } catch (_) {} });
    priceLineRefs.current = [];
    setLevelsDrawn(false);

    try {
      const isDailyOrAbove = ['1D', '1W', '1M'].includes(tf);
      const DAYS_BACK = { '1m':7,'3m':30,'5m':60,'15m':60,'30m':90,'1H':90,'4H':90,'1D':90,'1W':90,'1M':90 };
      const daysBack  = DAYS_BACK[tf] ?? 90;
      const toDate    = new Date();
      const fromDate  = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);

      const response = await api.get('/api/chart/history', {
        params: {
          symbol: sym, token: tok, exchange: exch, interval: tf,
          to_date:    toDate.toISOString().split('T')[0],
          from_date:  fromDate.toISOString().split('T')[0],
          session_id: sessionId, client_id: clientId,
        },
      });

      const rawCandles = response.data?.data;
      if (!Array.isArray(rawCandles) || rawCandles.length === 0) {
        setError(`No data for ${sym} (${tf}).`);
        candleSeriesRef.current.setData([]);
        lastCandleRef.current = null;
        rawCandlesRef.current = [];
        return;
      }

      const formattedData = rawCandles.map(d => {
        let timeVal = d[0];
        if (isDailyOrAbove) {
          const dt = new Date(timeVal * 1000);
          timeVal  = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`;
        } else {
          timeVal = timeVal + 19800;
        }
        return { time: timeVal, open: d[1], high: d[2], low: d[3], close: d[4] };
      });

      rawCandlesRef.current = formattedData.map(c => [c.time, c.open, c.high, c.low, c.close]);
      candleSeriesRef.current.setData(formattedData);
      lastCandleRef.current = formattedData[formattedData.length - 1];
      chartInstanceRef.current.timeScale().fitContent();
      setTimeout(() => zoomToRecentRange(), 100);

      // Restore H-Lines for this symbol
      restoreHLines(sym);
      restoreVLines(sym);

      // Fetch and render nakshatra markers
      fetchNakshatras(rawCandlesRef.current);

      // Restore saved levels for this symbol
      const saved = loadFromStorage(sym);
      if (saved?.levels?.start && saved?.levels?.end) {
        setStartDate(saved.levels.start);
        setEndDate(saved.levels.end);
        setTimeout(() => drawLevels(saved.levels.start, saved.levels.end), 50);
      }

      restoreVLines(sym);
      setTimeout(() => renderVLines(), 100);
      console.log(`[AstroChart] ${formattedData.length} candles for ${sym} @ ${tf}`);
    } catch (err) {
      setError(`Failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsLoadingData(false);
    }
  }, [session, drawLevels, restoreHLines, fetchNakshatras]);


  // ── Data load trigger ────────────────────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => {
      if (chartInstanceRef.current && candleSeriesRef.current)
        loadHistoricalData(symbol, token, exchange, timeframe);
    }, 50);
    return () => clearTimeout(t);
  }, [symbol, token, exchange, timeframe, loadHistoricalData, theme]);

  // ── External symbol from watchlist ───────────────────────────────────────────
  useEffect(() => {
    if (!externalSymbol) return;
    setSymbol(externalSymbol.symbol);
    setToken(externalSymbol.token);
    setExchange(externalSymbol.exch_seg || 'NSE');
    setSearchQuery(externalSymbol.symbol);
  }, [externalSymbol]);

  // ── WebSocket real-time (all timeframes) ────────────────────────────────────
  const TF_SECONDS = {
    '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
    '1H': 3600, '4H': 14400, '1D': 86400, '1W': 604800, '1M': 2592000,
  };

  const handlePriceUpdate = useCallback((data) => {
    const ltp = data.ltp;
    // Debug: confirm WS tick delivery + ltp existence
    // (safe to keep; remove if too noisy)
    if (ltp === undefined || !candleSeriesRef.current) return;
    // eslint-disable-next-line no-console
    console.log('[AstroChart] tick', { symbol: data.symbol, token: data.token, ltp, tf: timeframeRef.current });


    const tf       = timeframeRef.current;
    const last     = lastCandleRef.current;
    if (!last) return; // wait for historical data first

    const isDailyOrAbove = ['1D', '1W', '1M'].includes(tf);

    if (isDailyOrAbove) {
      // Daily+: just update close/high/low on current candle, no new candle logic
      const c = { ...last, high: Math.max(last.high, ltp), low: Math.min(last.low, ltp), close: ltp };
      candleSeriesRef.current.update(c);
      lastCandleRef.current = c;
      return;
    }

    // Intraday: check if a new candle interval has started
    const interval        = TF_SECONDS[tf] || 60;
    const nowTs           = Math.floor(Date.now() / 1000) + 19800; // IST unix seconds
    const currentCandleTs = Math.floor(nowTs / interval) * interval;

    if (last.time < currentCandleTs) {
      // New candle — open it
      const c = { time: currentCandleTs, open: ltp, high: ltp, low: ltp, close: ltp };
      candleSeriesRef.current.update(c);
      lastCandleRef.current = c;
    } else {
      // Same candle — update high/low/close
      const c = { ...last, high: Math.max(last.high, ltp), low: Math.min(last.low, ltp), close: ltp };
      candleSeriesRef.current.update(c);
      lastCandleRef.current = c;
    }
  }, []);

  useEffect(() => {
    if (!token) return;

    // Keep token subscription alive even when this chart unmounts.
    // This avoids starving other widgets (e.g., indices cards) due to WS
    // subscription churn triggered by tab navigation.
    wsClient.subscribeToToken(token, handlePriceUpdate);
    return () => {
      // Intentionally NOT unsubscribing here.
    };
  }, [token, handlePriceUpdate]);


  // ── Symbol search ────────────────────────────────────────────────────────────
  const handleSearchInput = async (e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return; }
    setIsSearching(true);
    try {
      const res = await api.get(`/api/watchlist/search/${q}`);
      setSearchResults(res.data?.results || res.data || []);
    } catch { setSearchResults([]); }
    finally  { setIsSearching(false); }
  };

  const handleSelectSymbol = (r) => {
    setSymbol(r.symbol);
    setToken(r.token);
    setExchange(r.exchSeg || r.exch_seg || 'NSE');
    setSearchQuery(r.symbol);
    setSearchResults([]);
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) containerRef.current.requestFullscreen().catch(() => {});
    else document.exitFullscreen();
  };

  const isLight = (theme === 'light') || document.documentElement.classList.contains('light-theme');
  const panelBackground = isLight ? '#ffffff' : '#0d0d1a';
  const toolbarBackground = isLight ? '#f8fafc' : '#0d0d1a';
  const borderColor = isLight ? '#e6e6e6' : '#2a2a4a';
  const cardBackground = isLight ? '#f8fafc' : '#1a1a2e';
  const textPrimary = isLight ? '#1f2937' : '#c3c3d9';
  const textSecondary = isLight ? '#4b5563' : '#888';
  const inputStyle = {
    padding: '5px 8px',
    background: isLight ? '#ffffff' : '#1a1a2e',
    border: `1px solid ${borderColor}`,
    borderRadius: '6px', color: textPrimary, fontSize: '12px', outline: 'none', cursor: 'pointer',
  };
  const chartHeight = compact ? '100%' : (document.fullscreenElement ? '100vh' : 'calc(100vh - 240px)');

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div ref={containerRef} style={{
      height: chartHeight,
      minHeight: compact ? '0' : chartHeight,
      display: 'flex', flexDirection: 'column', background: panelBackground, color: textPrimary,
    }}>

      {/* ── Toolbar ── */}
      {!compact && (
      <div style={{ padding: '8px 12px', display: 'flex', gap: '8px', flexWrap: 'wrap',
        alignItems: 'center', borderBottom: `1px solid ${borderColor}`, background: toolbarBackground, flexShrink: 0 }}>

        {/* Symbol search */}
        <div style={{ position: 'relative' }}>
          <input type="text" placeholder="Search symbol…" value={searchQuery}
            onChange={handleSearchInput}
            style={{ padding: '6px 10px', width: '160px', background: isLight ? '#ffffff' : '#1a1a2e',
              border: `1px solid ${borderColor}`, borderRadius: '6px', color: textPrimary,
              fontSize: '13px', outline: 'none' }} />
          {isSearching && <span style={{ position:'absolute', right:'8px', top:'7px', fontSize:'11px', color:'#888' }}>…</span>}
          {searchResults.length > 0 && (
            <div style={{ position:'absolute', top:'100%', left:0, zIndex:99, background: cardBackground,
              border:`1px solid ${borderColor}`, borderRadius:'6px', marginTop:'4px', minWidth:'220px',
              maxHeight:'220px', overflowY:'auto', boxShadow:'0 8px 24px rgba(0,0,0,0.15)' }}>
              {searchResults.map((r, i) => (
                <div key={i} onClick={() => handleSelectSymbol(r)}
                  style={{ padding:'8px 12px', cursor:'pointer', fontSize:'13px', borderBottom:`1px solid ${borderColor}` }}
                  onMouseEnter={e => e.currentTarget.style.background = isLight ? '#f1f5f9' : '#2a2a4a'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <strong>{r.symbol}</strong>
                  <span style={{ marginLeft:'8px', color: textSecondary, fontSize:'11px' }}>{r.exchSeg || r.exch_seg}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Symbol badge */}
        <span style={{ padding:'4px 10px', background: cardBackground, border:`1px solid ${borderColor}`,
          borderRadius:'6px', fontSize:'13px', fontWeight:700, color:'#7c6af5', letterSpacing:'0.5px' }}>
          {symbol}
        </span>

        {/* Timeframe pills */}
        <div style={{ display:'flex', gap:'4px', flexWrap:'wrap' }}>
          {timeframes.map(tf => (
            <button key={tf.value} onClick={() => setTimeframe(tf.value)} style={{
              padding:'4px 8px', fontSize:'11px', fontWeight:700, border:'1px solid',
              borderRadius:'5px', cursor:'pointer', transition:'all 0.15s',
              borderColor: timeframe === tf.value ? '#7c6af5' : borderColor,
              background:  timeframe === tf.value ? '#7c6af5' : 'transparent',
              color:       timeframe === tf.value ? '#fff'    : textSecondary,
            }}>{tf.label}</button>
          ))}
        </div>

        <div style={{ width:'1px', height:'24px', background: borderColor, flexShrink:0 }} />

        {/* ── Draw tools ── */}
        <span style={{ fontSize:'11px', color: textSecondary, fontWeight:600, letterSpacing:'0.5px', whiteSpace:'nowrap' }}>DRAW</span>

        <button
          onClick={() => setDrawMode(d => !d)}
          title={drawMode ? 'Click chart to add a line' : 'Enable click-to-draw mode'}
          style={{
            padding:'5px 10px', fontSize:'12px', fontWeight:600, borderRadius:'6px',
            cursor:'pointer', transition:'all 0.15s', whiteSpace:'nowrap',
            border: `1px solid ${drawMode ? '#f0b429' : borderColor}`,
            background: drawMode ? '#f0b42922' : 'transparent',
            color: drawMode ? '#f0b429' : textSecondary,
            boxShadow: drawMode ? '0 0 8px #f0b42966' : 'none',
          }}>
          {drawMode ? '✎ Click chart…' : 'Draw'}
        </button>

        <div style={{ display:'flex', alignItems:'center', gap:'4px' }}>
          <select value={lineType} onChange={e => setLineType(e.target.value)} style={inputStyle}>
            <option value="horizontal">Horizontal</option>
            <option value="vertical">Vertical</option>
          </select>
          <input
            type="text"
            placeholder={lineType === 'horizontal' ? 'Price (e.g. 18750)' : 'Time (YYYY-MM-DD or unix)'}
            value={lineValue}
            onChange={e => setLineValue(e.target.value)}
            style={{ ...inputStyle, width:'140px' }}
          />
          <input
            type="text"
            placeholder="Label"
            value={lineLabel}
            onChange={e => setLineLabel(e.target.value)}
            style={{ ...inputStyle, width:'100px' }}
          />
          <button onClick={handleAddLine}
            title="Add manual line"
            style={{ padding:'5px 10px', fontSize:'12px', fontWeight:600,
              border:`1px solid ${borderColor}`, borderRadius:'6px', cursor:'pointer',
              background:'transparent', color:textSecondary, whiteSpace:'nowrap' }}>
            + Add
          </button>
        </div>

        <button onClick={clearAllLines}
          title="Clear all lines"
          style={{ padding:'5px 10px', fontSize:'12px', fontWeight:600,
            border:`1px solid ${borderColor}`, borderRadius:'6px',
            cursor:'pointer', background:'transparent', color:textSecondary, whiteSpace:'nowrap' }}>
          ✕ Clear
        </button>

        <div style={{ width:'1px', height:'24px', background: borderColor, flexShrink:0 }} />

        {/* ── Level plotter ── */}
        <span style={{ fontSize:'11px', color:textSecondary, fontWeight:600, letterSpacing:'0.5px', whiteSpace:'nowrap' }}>LEVELS</span>

        <div style={{ display:'flex', flexDirection:'column', gap:'1px' }}>
          <label style={{ fontSize:'9px', color:'#555', letterSpacing:'0.4px' }}>FROM</label>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={inputStyle} />
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:'1px' }}>
          <label style={{ fontSize:'9px', color:'#555', letterSpacing:'0.4px' }}>TO</label>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={inputStyle} />
        </div>

        <button onClick={() => drawLevels(startDate, endDate)} disabled={!startDate || !endDate}
          style={{
            padding:'5px 12px', fontSize:'12px', fontWeight:600, borderRadius:'6px',
            transition:'all 0.15s', whiteSpace:'nowrap',
            background:  (!startDate || !endDate) ? cardBackground : '#7c6af5',
            border:      `1px solid ${(!startDate || !endDate) ? borderColor : '#7c6af5'}`,
            color:       (!startDate || !endDate) ? textSecondary : '#fff',
            cursor:      (!startDate || !endDate) ? 'not-allowed' : 'pointer',
          }}>⊕ Plot</button>

        {levelsDrawn && (
          <button onClick={clearLevels} style={{
            padding:'5px 10px', fontSize:'12px', fontWeight:600,
            border:'1px solid #ef5350', borderRadius:'6px',
            cursor:'pointer', background:'transparent', color:'#ef5350', whiteSpace:'nowrap',
          }}>✕ Clear</button>
        )}

        <div style={{ width:'1px', height:'24px', background: borderColor, flexShrink:0 }} />

        {/* Reload */}
        <button onClick={() => loadHistoricalData(symbol, token, exchange, timeframe)}
          disabled={isLoadingData} title="Reload"
          style={{ padding:'5px 10px', background:'transparent', border:`1px solid ${borderColor}`,
            borderRadius:'6px', color:textSecondary, cursor: isLoadingData ? 'not-allowed':'pointer', fontSize:'14px' }}>
          {isLoadingData ? '⏳' : '↺'}
        </button>

        {/* Zoom recent two days */}
        <button onClick={zoomToRecentRange} title="Zoom to last 2 days" style={{
          padding:'5px 10px', background:'transparent', border:`1px solid ${borderColor}`,
          borderRadius:'6px', color:textSecondary, cursor:'pointer', fontSize:'12px' }}>2D</button>

        {/* Fullscreen */}
        <button onClick={toggleFullscreen} style={{
          padding:'5px 10px', background:'transparent', border:`1px solid ${borderColor}`,
          borderRadius:'6px', color:textSecondary, cursor:'pointer', fontSize:'14px' }}>⛶</button>
      </div>
      )}

      {/* ── OHLC bar ── */}
      {!compact && (
      <div style={{ padding:'4px 14px', fontSize:'12px', background: toolbarBackground,
        borderBottom:`1px solid ${borderColor}`, flexShrink:0, display:'flex',
        alignItems:'center', gap:'14px', minHeight:'26px', fontFamily:'monospace' }}>
        {ohlc ? (
          <>
            <span style={{ color:textSecondary, fontSize:'11px' }}>O</span>
            <span style={{ color: ohlc.close >= ohlc.open ? '#26a69a':'#ef5350', fontWeight:600 }}>{ohlc.open.toFixed(2)}</span>
            <span style={{ color:textSecondary, fontSize:'11px' }}>H</span>
            <span style={{ color:'#26a69a', fontWeight:600 }}>{ohlc.high.toFixed(2)}</span>
            <span style={{ color:textSecondary, fontSize:'11px' }}>L</span>
            <span style={{ color:'#ef5350', fontWeight:600 }}>{ohlc.low.toFixed(2)}</span>
            <span style={{ color:textSecondary, fontSize:'11px' }}>C</span>
            <span style={{ color: ohlc.close >= ohlc.open ? '#26a69a':'#ef5350', fontWeight:600 }}>{ohlc.close.toFixed(2)}</span>
            <span style={{ fontSize:'11px', color: ohlc.close >= ohlc.open ? '#26a69a':'#ef5350' }}>
              {ohlc.close >= ohlc.open ? '▲' : '▼'} {Math.abs(ohlc.close - ohlc.open).toFixed(2)} ({((ohlc.close - ohlc.open) / ohlc.open * 100).toFixed(2)}%)
            </span>
            {nakshatra && (
              <span style={{ marginLeft:'auto', fontSize:'11px', color:'#7c6af5', fontWeight:600, display:'flex', alignItems:'center', gap:'6px' }}>
                <span style={{ width:'6px', height:'6px', borderRadius:'50%', background:'#7c6af5', display:'inline-block' }} />
                🌙 {nakshatra.nakshatra} P{nakshatra.pada}
                <span style={{ color:'#555', fontWeight:400 }}>{nakshatra.degree?.toFixed(2)}°</span>
              </span>
            )}
          </>
        ) : (
          <span style={{ color:'#333', fontSize:'11px' }}>
            Hover over a candle to see OHLC
            {nakshatra && (
              <span style={{ marginLeft:'16px', color:'#7c6af5', fontWeight:600 }}>
                🌙 {nakshatra.nakshatra} P{nakshatra.pada}
              </span>
            )}
          </span>
        )}
      </div> )}

      {/* ── Status bar ── */}
      {!compact && (isLoadingData || error) && (
        <div style={{ padding:'6px 14px', fontSize:'12px', flexShrink:0,
          background: error ? (isLight ? '#fef2f2' : '#2d0f0f') : (isLight ? '#eff6ff' : '#0d1a2d'),
          color: error ? '#ef5350' : '#26a69a', borderBottom:`1px solid ${borderColor}` }}>
          {isLoadingData ? `Loading ${symbol} (${timeframe})…` : error}
        </div>
      )}

      {/* ── Chart canvas ── */}
      <div style={{ position:'relative', flex:1, width:'100%', minHeight:'400px', cursor: drawMode ? 'crosshair' : 'default' }}>
        <div ref={chartRef} style={{ width:'100%', height:'100%' }} />
        <div ref={overlayRef} style={{ position:'absolute', inset:0, pointerEvents:'none' }} />
      </div>
    </div>
  );
};

export default AstroChart;