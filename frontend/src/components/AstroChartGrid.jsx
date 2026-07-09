import React, { useState, useEffect, useMemo, useRef } from 'react';
import AstroChart from './AstroChart';

const DEFAULT_TABS = [
  { id: 'chart1', label: 'Chart 1', symbol: 'NIFTY 50', token: '99926000', exchange: 'NSE' },
  { id: 'chart2', label: 'Chart 2', symbol: 'BANKNIFTY', token: '26000', exchange: 'NSE' },
  { id: 'chart3', label: 'Chart 3', symbol: 'RELIANCE', token: '500325', exchange: 'NSE' },
  { id: 'chart4', label: 'Chart 4', symbol: 'HDFCBANK', token: '500180', exchange: 'NSE' },
];

const AstroChartGrid = ({ session, watchlist = [], externalSymbol, theme = 'dark' }) => {
  const [chartCount, setChartCount] = useState(4);
  const [chartSlots, setChartSlots] = useState(DEFAULT_TABS);
  const [activeSlot, setActiveSlot] = useState('chart1');
  const [pickerSymbol, setPickerSymbol] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const gridRef = useRef(null);

  const visibleSlots = chartSlots.slice(0, chartCount);
  const activeSlotData = chartSlots.find((slot) => slot.id === activeSlot) || visibleSlots[0];

  const watchlistOptions = useMemo(() => {
    return watchlist.map((item) => ({
      symbol: item.symbol,
      token: item.token,
      exchange: item.exch_seg || item.exchSeg || 'NSE',
      label: `${item.symbol} (${item.exch_seg || item.exchSeg || 'NSE'})`,
    }));
  }, [watchlist]);

  useEffect(() => {
    if (!externalSymbol) return;
    setChartSlots((prev) => prev.map((slot) => {
      if (slot.id !== activeSlot) return slot;
      return {
        ...slot,
        symbol: externalSymbol.symbol,
        token: externalSymbol.token,
        exchange: externalSymbol.exch_seg || externalSymbol.exchSeg || 'NSE',
      };
    }));
  }, [externalSymbol, activeSlot]);

  const applyPickerToActive = () => {
    const match = watchlistOptions.find((item) => item.symbol === pickerSymbol || item.label === pickerSymbol);
    if (!match) return;
    setChartSlots((prev) => prev.map((slot) => {
      if (slot.id !== activeSlot) return slot;
      return {
        ...slot,
        symbol: match.symbol,
        token: match.token,
        exchange: match.exchange,
      };
    }));
    setPickerSymbol('');
  };

  const resetDefaultCharts = () => {
    setChartSlots(DEFAULT_TABS);
    setChartCount(4);
    setActiveSlot('chart1');
    setPickerSymbol('');
  };

  const toggleFullscreenGrid = async () => {
    if (!gridRef.current) return;
    if (!document.fullscreenElement) {
      try {
        await gridRef.current.requestFullscreen();
        setIsFullscreen(true);
      } catch (_) {
        setIsFullscreen(false);
      }
    } else {
      await document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const changeSlotSymbol = (slotId, symbol, token, exchange) => {
    setChartSlots((prev) => prev.map((slot) => slot.id === slotId ? { ...slot, symbol, token, exchange } : slot));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', height: '100%' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: theme === 'light' ? '#4b5563' : '#c3c3d9' }}>Charts:</span>
          {[1, 2, 4].map((count) => (
            <button key={count} onClick={() => setChartCount(count)} style={{
              padding: '6px 12px', borderRadius: '10px', border: '1px solid',
              borderColor: chartCount === count ? '#7c6af5' : theme === 'light' ? '#d1d5db' : '#2a2a4a',
              color: chartCount === count ? '#fff' : theme === 'light' ? '#374151' : '#d1d5db',
              background: chartCount === count ? '#7c6af5' : theme === 'light' ? '#f8fafc' : '#111827',
              cursor: 'pointer', fontSize: '12px', fontWeight: 700,
            }}>{count}</button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: theme === 'light' ? '#4b5563' : '#c3c3d9' }}>Active panel:</span>
            <select value={activeSlot} onChange={(e) => setActiveSlot(e.target.value)} style={{ padding: '6px 10px', borderRadius: '10px', border: `1px solid ${theme === 'light' ? '#d1d5db' : '#2a2a4a'}`, background: theme === 'light' ? '#fff' : '#111827', color: theme === 'light' ? '#111827' : '#f8fafc' }}>
              {visibleSlots.map((slot) => (
                <option key={slot.id} value={slot.id}>{slot.label}</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select value={pickerSymbol} onChange={(e) => setPickerSymbol(e.target.value)} style={{ padding: '6px 10px', borderRadius: '10px', border: `1px solid ${theme === 'light' ? '#d1d5db' : '#2a2a4a'}`, background: theme === 'light' ? '#fff' : '#111827', color: theme === 'light' ? '#111827' : '#f8fafc', minWidth: '220px' }}>
              <option value="">Select symbol / index</option>
              {watchlistOptions.map((item) => (
                <option key={`${item.symbol}_${item.exchange}`} value={item.symbol}>{item.label}</option>
              ))}
            </select>
            <button onClick={applyPickerToActive} style={{ padding: '6px 12px', borderRadius: '10px', background: '#7c6af5', color: '#fff', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}>Load</button>
          </div>

          <button onClick={toggleFullscreenGrid} style={{ padding: '6px 12px', borderRadius: '10px', background: theme === 'light' ? '#f3f4f6' : '#111827', color: theme === 'light' ? '#374151' : '#d1d5db', border: `1px solid ${theme === 'light' ? '#d1d5db' : '#2a2a4a'}`, cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}>
            {isFullscreen ? 'Exit full screen' : 'Full screen'}
          </button>

          <button onClick={resetDefaultCharts} style={{ padding: '6px 12px', borderRadius: '10px', background: theme === 'light' ? '#f3f4f6' : '#111827', color: theme === 'light' ? '#374151' : '#d1d5db', border: `1px solid ${theme === 'light' ? '#d1d5db' : '#2a2a4a'}`, cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}>Reset default charts</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: chartCount === 1 ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: '10px', flex: 1, minHeight: 0 }} ref={gridRef}>
        {visibleSlots.map((slot) => (
          <div key={slot.id} style={{ background: theme === 'light' ? '#fff' : '#090a14', border: `1px solid ${theme === 'light' ? '#e5e7eb' : '#2a2a4a'}`, borderRadius: '16px', overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ padding: '10px 12px', borderBottom: `1px solid ${theme === 'light' ? '#e5e7eb' : '#2a2a4a'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: theme === 'light' ? '#111827' : '#e5e7eb' }}>{slot.label}</div>
                <div style={{ fontSize: '12px', color: theme === 'light' ? '#6b7280' : '#9ca3af', marginTop: '2px' }}>{slot.symbol} • {slot.exchange}</div>
              </div>
              <button onClick={() => setActiveSlot(slot.id)} style={{ padding: '5px 12px', borderRadius: '999px', border: 'none', background: activeSlot === slot.id ? '#7c6af5' : theme === 'light' ? '#f3f4f6' : '#111827', color: activeSlot === slot.id ? '#fff' : theme === 'light' ? '#374151' : '#d1d5db', cursor: 'pointer', fontSize: '11px', fontWeight: 700 }}>
                {activeSlot === slot.id ? 'Active' : 'Select'}
              </button>
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <AstroChart
                session={session}
                watchlist={watchlist}
                externalSymbol={slot}
                theme={theme}
                compact={chartCount > 1}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AstroChartGrid;
