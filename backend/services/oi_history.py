"""Simple SQLite-backed persistence for OI snapshots.

Stores minute-level (or poll-level) totals per session+underlying so frontend
can request day history without keeping state in memory.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import List, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT, 'data')
DB_PATH = os.path.join(DATA_DIR, 'oi_history.sqlite')

# retention in days (configurable)
RETENTION_DAYS = int(os.getenv('OI_HISTORY_DAYS', '14'))

# aggregation config (runtime-changeable)
AGG_METHOD = os.getenv('OI_AGG_METHOD', 'trimmed')
try:
    TRIM_ALPHA = float(os.getenv('OI_TRIM_ALPHA', '0.2'))
except Exception:
    TRIM_ALPHA = 0.2


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _get_conn():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS oi_samples (
            session_id TEXT,
            underlying TEXT,
            ts INTEGER,
            ce REAL,
            pe REAL,
            sum_ce REAL,
            sum_pe REAL,
            cnt INTEGER
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_oi_samples_sid ON oi_samples(session_id, underlying, ts)")
    # table to store raw per-poll samples (for intra-minute aggregation)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS oi_sample_values (
            session_id TEXT,
            underlying TEXT,
            minute_ts INTEGER,
            sample_ts INTEGER,
            ce REAL,
            pe REAL
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_oi_values_minute ON oi_sample_values(session_id, underlying, minute_ts)")
    conn.commit()
    conn.close()


def _ensure_migration():
    # add missing columns if db pre-dates this schema
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(oi_samples)")
    cols = [r[1] for r in cur.fetchall()]
    if 'sum_ce' not in cols:
        try:
            cur.execute("ALTER TABLE oi_samples ADD COLUMN sum_ce REAL")
        except Exception:
            pass
    if 'sum_pe' not in cols:
        try:
            cur.execute("ALTER TABLE oi_samples ADD COLUMN sum_pe REAL")
        except Exception:
            pass
    if 'cnt' not in cols:
        try:
            cur.execute("ALTER TABLE oi_samples ADD COLUMN cnt INTEGER")
        except Exception:
            pass
    conn.commit()
    conn.close()

    # ensure oi_sample_values exists
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='oi_sample_values'")
    if not cur.fetchone():
        cur.execute(
            """
            CREATE TABLE oi_sample_values (
                session_id TEXT,
                underlying TEXT,
                minute_ts INTEGER,
                sample_ts INTEGER,
                ce REAL,
                pe REAL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oi_values_minute ON oi_sample_values(session_id, underlying, minute_ts)")
    conn.commit()
    conn.close()


# ensure migrations run on import
_ensure_migration()


def save_sample(session_id: str, underlying: str, ts: float, ce: float, pe: float) -> None:
    """Store raw sample and recompute minute-aggregate using configured method.

    Aggregation method controlled by env `OI_AGG_METHOD` (median|trimmed|mean).
    Default is `trimmed` with alpha=0.2.
    """
    minute_ts = int(int(ts) // 60 * 60)
    conn = _get_conn()
    cur = conn.cursor()
    # insert raw sample
    cur.execute(
        "INSERT INTO oi_sample_values(session_id, underlying, minute_ts, sample_ts, ce, pe) VALUES(?,?,?,?,?,?)",
        (session_id, underlying, minute_ts, int(ts), float(ce), float(pe)),
    )

    # fetch all samples for this minute
    cur.execute(
        "SELECT ce, pe FROM oi_sample_values WHERE session_id=? AND underlying=? AND minute_ts=?",
        (session_id, underlying, minute_ts),
    )
    rows = cur.fetchall()
    ces = [float(r[0]) for r in rows if r[0] is not None]
    pes = [float(r[1]) for r in rows if r[1] is not None]

    def median(arr):
        a = sorted(arr)
        n = len(a)
        if n == 0:
            return None
        mid = n // 2
        if n % 2 == 1:
            return a[mid]
        return (a[mid - 1] + a[mid]) / 2.0

    def trimmed_mean(arr, alpha=0.2):
        a = sorted(arr)
        n = len(a)
        if n == 0:
            return None
        k = int(n * alpha)
        if n - 2 * k <= 0:
            # fallback to median if trimming removes all
            return median(a)
        trimmed = a[k : n - k]
        return sum(trimmed) / len(trimmed)

    method = AGG_METHOD
    if method == 'median':
        agg_ce = median(ces)
        agg_pe = median(pes)
    elif method == 'mean':
        agg_ce = (sum(ces) / len(ces)) if ces else None
        agg_pe = (sum(pes) / len(pes)) if pes else None
    else:
        # trimmed mean default
        try:
            alpha = float(TRIM_ALPHA)
        except Exception:
            alpha = 0.2
        agg_ce = trimmed_mean(ces, alpha) if ces else None
        agg_pe = trimmed_mean(pes, alpha) if pes else None

    # upsert aggregated minute row
    if agg_ce is None:
        agg_ce = 0.0
    if agg_pe is None:
        agg_pe = 0.0

    cur.execute(
        "SELECT 1 FROM oi_samples WHERE session_id=? AND underlying=? AND ts=?",
        (session_id, underlying, minute_ts),
    )
    exists = cur.fetchone()
    if exists:
        cur.execute(
            "UPDATE oi_samples SET ce=?, pe=?, sum_ce=?, sum_pe=?, cnt=? WHERE session_id=? AND underlying=? AND ts=?",
            (agg_ce, agg_pe, sum(ces) if ces else agg_ce, sum(pes) if pes else agg_pe, len(ces) if ces else 1, session_id, underlying, minute_ts),
        )
    else:
        cur.execute(
            "INSERT INTO oi_samples(session_id, underlying, ts, ce, pe, sum_ce, sum_pe, cnt) VALUES(?,?,?,?,?,?,?,?)",
            (session_id, underlying, minute_ts, float(agg_ce), float(agg_pe), float(sum(ces) if ces else agg_ce), float(sum(pes) if pes else agg_pe), len(ces) if ces else 1),
        )

    conn.commit()
    conn.close()


def prune_history(days: int = 7) -> None:
    """Delete samples older than `days` days."""
    cutoff = int((__import__('time').time() - int(days) * 86400) // 60 * 60)
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM oi_samples WHERE ts < ?", (cutoff,))
    # also delete raw values older than cutoff
    try:
        cur.execute("DELETE FROM oi_sample_values WHERE minute_ts < ?", (cutoff,))
    except Exception:
        pass
    conn.commit()
    conn.close()


def _prune_worker():
    """Background thread to prune old history periodically."""
    while True:
        try:
            prune_history(days=RETENTION_DAYS)
        except Exception:
            pass
        # sleep one hour
        time.sleep(3600)


# Start background prune thread (daemon)
try:
    t = threading.Thread(target=_prune_worker, daemon=True)
    t.start()
except Exception:
    pass


def set_agg_method(method: str) -> None:
    """Set aggregation method at runtime. method in {median, mean, trimmed}."""
    global AGG_METHOD
    if method not in ('median', 'mean', 'trimmed'):
        raise ValueError('invalid agg method')
    AGG_METHOD = method


def set_trim_alpha(alpha: float) -> None:
    global TRIM_ALPHA
    TRIM_ALPHA = float(alpha)


def set_retention_days(days: int) -> None:
    global RETENTION_DAYS
    RETENTION_DAYS = int(days)


def trigger_prune() -> None:
    prune_history(days=RETENTION_DAYS)


def get_history(session_id: str, underlying: str, from_ts: Optional[int] = None, to_ts: Optional[int] = None) -> List[Dict]:
    conn = _get_conn()
    cur = conn.cursor()
    q = "SELECT ts, ce, pe FROM oi_samples WHERE session_id=? AND underlying=?"
    params = [session_id, underlying]
    if from_ts is not None:
        q += " AND ts >= ?"
        params.append(int(from_ts))
    if to_ts is not None:
        q += " AND ts <= ?"
        params.append(int(to_ts))
    q += " ORDER BY ts ASC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({"ts": int(r["ts"]), "ce": float(r["ce"]), "pe": float(r["pe"])})
    return out


# initialize on import
init_db()
