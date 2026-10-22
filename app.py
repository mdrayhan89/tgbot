import asyncio
import datetime
import aiohttp
import sqlite3
import io
import json
import html
import os
import threading
import numpy as np
from datetime import timedelta, date, timezone
from typing import Optional, Tuple, Dict, List, Any

from flask import Flask, render_template_string, request, jsonify

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ==================== CONFIGURATION ====================
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8670196207:AAG0x5h1IJxK5PhWwPMzSK0i9VzqhOXK3zk")
ADMIN_IDS   = {7488289885}  # Add admin IDs here
DB_PATH     = "123.db"
API_BASE    = "https://cool-sky-e403.twssanjidapi.workers.dev"
SUPPORT_URL = "https://t.me/your_support"
FREE_LIMIT    = 2
PREMIUM_LIMIT = 25
CACHE_TTL     = 300
BOT_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Global Control States for Admin Panel
SYSTEM_SETTINGS = {
    "bot_running": True,
    "access_mode": "licensed_only", # 'all' or 'licensed_only'
    "free_live_limit": 5,
    "free_future_limit": 2,
    "starter_live_limit": 25,
    "starter_future_limit": 3
}

# ==================== TRADING PAIRS ====================
PAIRS = [
    "ATOUSD_otc", "AVAUSD_otc", "AXP_otc", "AXSUSD_otc", "BA_otc", "BCHUSD_otc",
    "BNBUSD_otc", "BRLUSD_otc", "BTCUSD_otc", "CADCHF_otc", "DASUSD_otc", "DOTUSD_otc",
    "ETCUSD_otc", "ETHUSD_otc", "FB_otc", "INTC_otc", "JNJ_otc", "LINUSD_otc",
    "LTCUSD_otc", "MCD_otc", "MSFT_otc", "NZDCAD_otc", "NZDCHF_otc", "NZDJPY_otc",
    "NZDUSD_otc", "PFE_otc", "SOLUSD_otc", "TONUSD_otc", "TRUUSD_otc", "UKBrent_otc",
    "USCrude_otc", "USDARS_otc", "USDBDT_otc", "USDCAD_otc", "USDCOP_otc", "USDDZD_otc",
    "USDEGP_otc", "USDIDR_otc", "USDINR_otc", "USDMXN_otc", "USDNGN_otc", "USDPHP_otc",
    "USDPKR_otc", "USDZAR_otc", "XAGUSD_otc", "XAUUSD_otc", "XRPUSD_otc", "ZECUSD_otc",
]

# ==================== ENHANCED STRATEGY PARAMETERS ====================
STRATEGY_CONFIG = {
    'rsi_period': 14,
    'rsi_overbought': 70,
    'rsi_oversold': 30,
    'ema_fast': 8,
    'ema_slow': 21,
    'ema_trend': 50,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2,
    'atr_period': 14,
    'volume_sma': 20,
    'min_confidence': 65,
    'high_confidence': 85,
}

# ==================== EMOJI MAPPINGS ====================
EMAP = {
    "✨": 5938348905891632091, "🤖": 5314391089514291948, "🚀": 5188481279963715781,
    "📶": 5980965624396910678, "⚡": 5258203794772085854, "⚙": 6118476436966741936,
    "📊": 6104726103463565578, "⏰": 5316575093269214796, "⏳": 5215327832040811010,
    "🟢": 5462906239656666557, "🎯": 6105041139314727248, "🔴": 5938385748121096724,
    "✅": 6174667949366842763, "🔄": 6129407979138583594, "💎": 6145449239607515472,
    "🏆": 6266973397922616654, "🔍": 5938483969728188084, "📈": 6102644427304478726,
    "📉": 6102805248059906486, "💬": 5938359183748370657, "❌": 5938302546014638461,
    "👑": 6116248457041679994, "💰": 5224257782013769471, "👇": 5100474711419126428,
    "⏹": 6084515769780013003, "📣": 6174457264041103675, "👨‍💻": 5301087466969637386,
    "💌": 6215361789538866270, "😏": 5199412938099666948, "💵": 6116168433211021881,
    "👤": 5316727448644103237, "📅": 5274055917766202507, "🛡": 5942583262609150318,
    "🆔": 6230743532009691484, "📛": 6231262273864736290, "🔥": 6221958163520819301,
    "⬇": 5443127283898405358, "💥": 6129802647978381940, "😮": 6269194596094317437,
    "🙂": 5195033767969839232, "📆": 5028418466000930064,
}

ICON = {
    "robot": "6255726532136800534", "writing": "6066496346158798789",   
    "about": "5258503720928288433", "profile": "5316727448644103237",  
    "back": "5258084656674250503", "home": "5416041192905265756",   
    "refresh": "5260687119092817530", "target": "6105041139314727248",   
    "stop": "6105175017740310496", "diamond": "6145248943807667330",   
    "support": "6230919101682819116", "owner": "6129805886383723340",   
    "signal": "6330188813939251966", "chart": "6084693581426069171",   
    "rocket": "6147654280112248427", "shield": "6105169455757661838",
    "money": "5224257782013769471", "star": "5469641199348363998",   
}

# ==================== DATABASE FUNCTIONS ====================
user_states = {}
auto_tasks = {}
payout_cache = {}

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id        INTEGER PRIMARY KEY,
        username       TEXT    DEFAULT '',
        full_name      TEXT    DEFAULT '',
        is_premium     INTEGER DEFAULT 0,
        daily_sigs     INTEGER DEFAULT 0,
        last_date      TEXT    DEFAULT '',
        total_sigs     INTEGER DEFAULT 0,
        wins           INTEGER DEFAULT 0,
        losses         INTEGER DEFAULT 0,
        joined_at      TEXT    DEFAULT '',
        license_expiry TEXT    DEFAULT '',
        plan_type      TEXT    DEFAULT 'free',
        total_profit   REAL    DEFAULT 0.0,
        best_streak    INTEGER DEFAULT 0,
        current_streak INTEGER DEFAULT 0,
        is_banned      INTEGER DEFAULT 0,
        last_active    TEXT    DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS partial_signals (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        pair      TEXT    NOT NULL,
        direction TEXT    NOT NULL,
        time_str  TEXT    NOT NULL,
        win       INTEGER NOT NULL,
        is_mtg    INTEGER DEFAULT 0,
        date_str  TEXT    NOT NULL,
        profit    REAL    DEFAULT 0.0
    )''')
    conn.commit()
    
    for col_def in [
        "license_expiry TEXT DEFAULT ''",
        "plan_type TEXT DEFAULT 'free'",
        "total_profit REAL DEFAULT 0.0",
        "best_streak INTEGER DEFAULT 0",
        "current_streak INTEGER DEFAULT 0",
        "is_banned INTEGER DEFAULT 0",
        "last_active TEXT DEFAULT ''"
    ]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()

def _row(row):
    if not row:
        return None
    keys = ['user_id','username','full_name','is_premium','daily_sigs',
            'last_date','total_sigs','wins','losses','joined_at','license_expiry','plan_type',
            'total_profit','best_streak','current_streak','is_banned','last_active']
    return dict(zip(keys, row))

def db_get(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id=?', (uid,))
    row = c.fetchone()
    conn.close()
    return _row(row)

def db_upsert(uid, username, full_name):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO users (user_id,username,full_name,joined_at,last_active) VALUES (?,?,?,?,?) '
        'ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, last_active=excluded.last_active',
        (uid, username or '', full_name or '', now, now)
    )
    conn.commit()
    conn.close()
    return db_get(uid)

def db_reset_daily(uid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE users SET daily_sigs=0, last_date=? WHERE user_id=?',
                 (date.today().isoformat(), uid))
    conn.commit()
    conn.close()

def db_reset_all_daily():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE users SET daily_sigs=0, last_date=?',
                 (date.today().isoformat(),))
    conn.commit()
    conn.close()

def db_inc_daily(uid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE users SET daily_sigs=daily_sigs+1, last_date=? WHERE user_id=?',
                 (date.today().isoformat(), uid))
    conn.commit()
    conn.close()

def db_record_result(uid, win, profit=0):
    conn = sqlite3.connect(DB_PATH)
    if win:
        conn.execute('UPDATE users SET total_sigs=total_sigs+1, wins=wins+1, total_profit=total_profit+? WHERE user_id=?', 
                     (profit, uid))
    else:
        conn.execute('UPDATE users SET total_sigs=total_sigs+1, losses=losses+1, total_profit=total_profit-? WHERE user_id=?', 
                     (profit, uid))
    
    user = db_get(uid)
    if user:
        if win:
            new_streak = user.get('current_streak', 0) + 1
            best_streak = max(user.get('best_streak', 0), new_streak)
            conn.execute('UPDATE users SET current_streak=?, best_streak=? WHERE user_id=?',
                         (new_streak, best_streak, uid))
        else:
            conn.execute('UPDATE users SET current_streak=0 WHERE user_id=?', (uid,))
    
    conn.commit()
    conn.close()

def db_partial_add(uid, pair, direction, time_str, win, is_mtg=False, profit=0):
    BD = datetime.timezone(datetime.timedelta(hours=6))
    today = datetime.datetime.now(tz=BD).strftime('%Y.%m.%d')
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO partial_signals (user_id,pair,direction,time_str,win,is_mtg,date_str,profit) VALUES (?,?,?,?,?,?,?,?)',
        (uid, pair, direction, time_str, 1 if win else 0, 1 if is_mtg else 0, today, profit)
    )
    conn.commit()
    conn.close()

def db_partial_get(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT pair,direction,time_str,win,is_mtg,date_str,profit FROM partial_signals WHERE user_id=? ORDER BY id ASC', (uid,))
    rows = c.fetchall()
    conn.close()
    return rows

def db_partial_reset(uid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM partial_signals WHERE user_id=?', (uid,))
    conn.commit()
    conn.close()

def db_set_license(uid, days, plan_type='premium'):
    if plan_type not in ('premium', 'vip'):
        plan_type = 'premium'
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,))
    if days == 'permanent':
        expiry = 'permanent'
    else:
        expiry = (datetime.date.today() + datetime.timedelta(days=int(days))).isoformat()
    conn.execute('UPDATE users SET is_premium=1, license_expiry=?, plan_type=? WHERE user_id=?',
                 (expiry, plan_type, uid))
    conn.commit()
    conn.close()

def db_revoke_license(uid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,))
    conn.execute('UPDATE users SET is_premium=0, license_expiry="", plan_type="free" WHERE user_id=?', (uid,))
    conn.commit()
    conn.close()

def db_set_ban(uid, status: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE users SET is_banned=? WHERE user_id=?', (1 if status else 0, uid))
    conn.commit()
    conn.close()

def db_is_premium(user):
    if not user.get('is_premium'):
        return False
    expiry = user.get('license_expiry', '')
    if expiry == 'permanent' or not expiry:
        return user['is_premium']
    try:
        return datetime.date.today() <= datetime.date.fromisoformat(expiry)
    except Exception:
        return False

def db_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id,username,full_name,is_premium,total_sigs,wins,losses,is_banned,plan_type,joined_at,last_active,daily_sigs FROM users ORDER BY user_id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def refresh_daily(user):
    if user['last_date'] != date.today().isoformat():
        db_reset_daily(user['user_id'])
        user['daily_sigs'] = 0
        user['last_date'] = date.today().isoformat()
    return user

def get_daily_limit(user):
    if user['user_id'] in ADMIN_IDS:
        return None
    if db_is_premium(user):
        if user.get('plan_type') == 'vip':
            return None
        return SYSTEM_SETTINGS['starter_live_limit']
    return SYSTEM_SETTINGS['free_live_limit']

def can_signal(user):
    if user.get('is_banned'):
        return False
    if not SYSTEM_SETTINGS['bot_running']:
        return False
    if SYSTEM_SETTINGS['access_mode'] == 'licensed_only' and not db_is_premium(user) and user['user_id'] not in ADMIN_IDS:
        return False
    limit = get_daily_limit(user)
    if limit is None:
        return True
    return user['daily_sigs'] < limit

# ==================== ENHANCED TECHNICAL INDICATORS ====================
def calculate_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_ema(closes: List[float], period: int) -> float:
    if len(closes) < period:
        return closes[-1]
    k = 2 / (period + 1)
    ema = np.mean(closes[:period])
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_macd(closes: List[float]) -> Tuple[float, float, float]:
    fast_ema = calculate_ema(closes, STRATEGY_CONFIG['macd_fast'])
    slow_ema = calculate_ema(closes, STRATEGY_CONFIG['macd_slow'])
    macd_line = fast_ema - slow_ema
    macd_values = []
    for i in range(STRATEGY_CONFIG['macd_slow'], len(closes)):
        f = calculate_ema(closes[:i+1], STRATEGY_CONFIG['macd_fast'])
        s = calculate_ema(closes[:i+1], STRATEGY_CONFIG['macd_slow'])
        macd_values.append(f - s)
    signal_line = calculate_ema(macd_values, STRATEGY_CONFIG['macd_signal']) if len(macd_values) >= STRATEGY_CONFIG['macd_signal'] else macd_line
    return macd_line, signal_line, macd_line - signal_line

def calculate_bollinger_bands(closes: List[float]) -> Tuple[float, float, float]:
    period = STRATEGY_CONFIG['bb_period']
    if len(closes) < period:
        return closes[-1], closes[-1], closes[-1]
    prices = closes[-period:]
    mean = np.mean(prices)
    std = np.std(prices)
    multiplier = STRATEGY_CONFIG['bb_std']
    return mean + (std * multiplier), mean, mean - (std * multiplier)

def calculate_atr(highs: List[float], lows: List[float], closes: List[float]) -> float:
    period = STRATEGY_CONFIG['atr_period']
    if len(closes) < period + 1:
        return 0
    tr_values = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(closes))]
    return np.mean(tr_values[-period:]) if tr_values else 0

def calculate_support_resistance(highs: List[float], lows: List[float], lookback: int = 50) -> Tuple[List[float], List[float]]:
    if len(highs) < lookback:
        return [], []
    recent_highs, recent_lows = highs[-lookback:], lows[-lookback:]
    swing_highs, swing_lows = [], []
    for i in range(2, len(recent_highs) - 2):
        if recent_highs[i] > max(recent_highs[i-1], recent_highs[i-2], recent_highs[i+1], recent_highs[i+2]):
            swing_highs.append(recent_highs[i])
        if recent_lows[i] < min(recent_lows[i-1], recent_lows[i-2], recent_lows[i+1], recent_lows[i+2]):
            swing_lows.append(recent_lows[i])
    resistance = [level for level in swing_highs if not any(abs(level - r) / level < 0.002 for r in swing_highs)]
    support = [level for level in swing_lows if not any(abs(level - s) / level < 0.002 for s in swing_lows)]
    return support[:5], resistance[:5]

def detect_candlestick_patterns(candle: Dict, prev_candle: Dict) -> List[str]:
    patterns = []
    o, h, l, c = float(candle['open']), float(candle['high']), float(candle['low']), float(candle['close'])
    prev_o, prev_c = float(prev_candle['open']), float(prev_candle['close'])
    body, range_candle = abs(c - o), h - l
    upper_wick, lower_wick = h - max(c, o), min(c, o) - l
    
    if body < range_candle * 0.1: patterns.append("DOJI")
    if upper_wick > body * 2 and lower_wick < body * 0.5: patterns.append("SHOOTING_STAR")
    elif lower_wick > body * 2 and upper_wick < body * 0.5: patterns.append("HAMMER")
    if c > o and prev_c < prev_o and c > prev_o and o < prev_c: patterns.append("BULLISH_ENGULFING")
    elif c < o and prev_c > prev_o and c < prev_o and o > prev_c: patterns.append("BEARISH_ENGULFING")
    return patterns

# ==================== MAIN ANALYSIS ENGINE ====================
def enhanced_analyze(candles: List[Dict]) -> Tuple[Optional[str], int, Dict]:
    if len(candles) < 50:
        return None, 0, {}
    closes = [float(c['close']) for c in candles]
    highs = [float(c['high']) for c in candles]
    lows = [float(c['low']) for c in candles]
    
    rsi = calculate_rsi(closes)
    ema_fast = calculate_ema(closes, STRATEGY_CONFIG['ema_fast'])
    ema_slow = calculate_ema(closes, STRATEGY_CONFIG['ema_slow'])
    ema_trend = calculate_ema(closes, STRATEGY_CONFIG['ema_trend'])
    macd_line, signal_line, histogram = calculate_macd(closes)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(closes)
    atr = calculate_atr(highs, lows, closes)
    
    current_candle = candles[-1]
    prev_candle = candles[-2] if len(candles) > 1 else current_candle
    patterns = detect_candlestick_patterns(current_candle, prev_candle)
    current_price = closes[-1]
    
    score = 0
    signals = []
    
    if ema_fast > ema_slow > ema_trend: score += 25; signals.append("BULLISH_TREND")
    elif ema_fast < ema_slow < ema_trend: score -= 25; signals.append("BEARISH_TREND")
    
    if current_price > ema_slow: score += 15
    else: score -= 15
    
    if rsi < STRATEGY_CONFIG['rsi_oversold']: score += 20; signals.append(f"RSI_OVERSOLD_{rsi}")
    elif rsi > STRATEGY_CONFIG['rsi_overbought']: score -= 20; signals.append(f"RSI_OVERBOUGHT_{rsi}")
    
    if macd_line > signal_line: score += 15; signals.append("MACD_BULLISH_CROSS")
    else: score -= 15; signals.append("MACD_BEARISH_CROSS")
    
    if current_price <= bb_lower: score += 15
    elif current_price >= bb_upper: score -= 15
    
    normalized_score = (score + 100) / 2
    base_confidence = min(98, max(50, normalized_score))
    
    direction = "CALL" if score > 20 else "PUT" if score < -20 else ("CALL" if ema_fast > ema_slow else "PUT")
    final_confidence = max(STRATEGY_CONFIG['min_confidence'], int(base_confidence))
    
    return direction, final_confidence, {
        'rsi': round(rsi, 1), 'score': score, 'signals': signals[:5], 'patterns': patterns,
        'ema_fast': round(ema_fast, 6), 'ema_slow': round(ema_slow, 6), 'histogram': round(histogram, 6)
    }

# ==================== CHARTING ====================
def build_enhanced_chart(candles: List[Dict], pair: str, direction: str, 
                         analysis: Dict, is_result: bool = False, win: bool = None) -> io.BytesIO:
    disp = list(reversed(candles[:50]))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    fig.patch.set_facecolor('#0a0a0a')
    ax1.set_facecolor('#0f0f0f')
    ax2.set_facecolor('#0f0f0f')
    
    all_p = [float(c['high']) for c in disp] + [float(c['low']) for c in disp]
    if all_p:
        pr = max(all_p) - min(all_p)
        pad = pr * 0.12 if pr > 0 else 0.0001
        ax1.set_ylim(min(all_p) - pad, max(all_p) + pad)
    
    for i, c in enumerate(disp):
        o, h, lo, cl = float(c['open']), float(c['high']), float(c['low']), float(c['close'])
        color = '#00e676' if cl >= o else '#ff1744'
        ax1.plot([i, i], [lo, h], color=color, linewidth=0.8, zorder=2)
        body_bottom = min(o, cl)
        body_height = max(abs(cl - o), (h - lo) * 0.02)
        ax1.add_patch(plt.Rectangle((i - 0.35, body_bottom), 0.7, body_height, facecolor=color, edgecolor=color, zorder=3, alpha=0.9))
    
    ax1.grid(True, color='#1a1a1a', linewidth=0.3)
    brand_text = f"⚡ DARK SECRET BY RAYHAN ⚡\n{pair.replace('_otc','').upper()} OTC"
    ax1.text(0.01, 0.98, brand_text, transform=ax1.transAxes, fontsize=10, color='#ffffff', ha='left', va='top', fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#333333'))
    
    dir_color = '#00e676' if direction == 'CALL' else '#ff1744'
    ax1.text(0.99, 0.98, f"  {'▲' if direction == 'CALL' else '▼'} {direction}  ", transform=ax1.transAxes, fontsize=11, color='#ffffff', ha='right', va='top', fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=dir_color))
    
    if is_result and win is not None:
        r_color = '#00e676' if win else '#ff1744'
        ax1.text(0.99, 0.02, 'WIN' if win else 'LOSS', transform=ax1.transAxes, fontsize=12, color=r_color, ha='right', va='bottom', fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=r_color))
    
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#0a0a0a', dpi=120, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==================== API FUNCTIONS ====================
async def fetch_candles(pair: str, count: int = 100) -> List[Dict]:
    url = f"{API_BASE}?pair={pair}&timeframe=M1&count={count}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                d = await r.json(content_type=None)
                return d.get('data', [])
    except Exception:
        return []

async def get_payout(pair: str) -> int:
    now = datetime.datetime.now().timestamp()
    if pair in payout_cache and now - payout_cache[pair][1] < CACHE_TTL:
        return payout_cache[pair][0]
    candles = await fetch_candles(pair, count=1)
    p = int(candles[0].get('payout', 80)) if candles else 80
    payout_cache[pair] = (p, now)
    return p

async def fetch_all_payouts() -> List[Tuple[str, int]]:
    sem = asyncio.Semaphore(15)
    async def limited(pair):
        async with sem: return pair, await get_payout(pair)
    results = await asyncio.gather(*[limited(p) for p in PAIRS], return_exceptions=True)
    return [(p, v) for p, v in results if not isinstance(v, Exception) and isinstance(v, (int, float))]

# ==================== TELEGRAM UTILS & KEYBOARDS ====================
def fmt(text: str, bold: bool = False, italic: bool = False, quote: bool = False) -> str:
    parts = []
    for ch in list(text):
        if ch in EMAP:
            parts.append(f'<tg-emoji emoji-id="{EMAP[ch]}">{html.escape(ch)}</tg-emoji>')
        else:
            parts.append(html.escape(ch))
    res = ''.join(parts)
    if bold: res = f'<b>{res}</b>'
    if italic: res = f'<i>{res}</i>'
    if quote: res = f'<blockquote>{res}</blockquote>'
    return res

def btn(text: str, cb: str = None, url: str = None, style: str = None, icon: str = None) -> Dict:
    b = {"text": text}
    if cb: b["callback_data"] = cb
    if url: b["url"] = url
    return b

def markup(*rows_) -> Dict: return {"inline_keyboard": [list(row) for row in rows_]}

async def tg(method: str, **kwargs) -> Dict:
    data = {k: v for k, v in kwargs.items() if v is not None}
    if "reply_markup" in data and isinstance(data["reply_markup"], dict):
        data["reply_markup"] = json.dumps(data["reply_markup"])
    photo = data.pop("photo", None)
    url = f"{BOT_API}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            if photo:
                form = aiohttp.FormData()
                for k, v in data.items(): form.add_field(k, str(v))
                form.add_field("photo", photo.read() if hasattr(photo, "read") else photo, filename="c.png", content_type="image/png")
                async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    return await r.json(content_type=None)
            else:
                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    return await r.json(content_type=None)
    except Exception: return {}

def kb_welcome():
    return markup(
        [btn("🤖 AUTO SIGNAL", "auto_signal"), btn("📝 MANUAL SIGNAL", "manual_signal")],
        [btn("💰 PRICING", "pricing"), btn("👤 MY PROFILE", "my_profile")],
        [btn("ℹ️ ABOUT", "about")]
    )

def kb_back_home(): return markup([btn("◀️ BACK", "home")])
def kb_stop_auto(): return markup([btn("⏹️ STOP AUTO", "stop_auto")])

# ==================== SIGNAL ENGINE ====================
async def do_signal(bot, chat_id, user_id, pair, from_auto=False, analyzing_msg_id=None):
    try:
        candles = await fetch_candles(pair, count=100)
        if not candles: return
        direction, confidence, analysis = enhanced_analyze(candles)
        if not direction: return
        
        now = datetime.datetime.now()
        entry_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        payout_val = await get_payout(pair)
        
        sig_msg = (
            f"✨✨✨ SIGNAL GENERATED ✨✨✨\n\n"
            f"📊 MARKET     →  {pair.replace('_otc','').upper()} OTC\n"
            f"⏰ ENTRY      →  {entry_time.strftime('%H:%M')}\n"
            f"⏳ EXPIRY     →  1 Minute (M1)\n"
            f"💎 PAYOUT     →  {payout_val}%\n"
            f"{'🟢' if direction == 'CALL' else '🔴'} DIRECTION   →  {direction}\n"
            f"🎯 CONFIDENCE →  {confidence}%\n"
        )
        chart = build_enhanced_chart(candles, pair, direction, analysis)
        
        if analyzing_msg_id:
            try: await tg("deleteMessage", chat_id=chat_id, message_id=analyzing_msg_id)
            except Exception: pass
            
        await tg("sendPhoto", chat_id=chat_id, photo=chart, caption=fmt(sig_msg, bold=True, quote=True), parse_mode="HTML")
        db_inc_daily(user_id)
        
        # Delay and result check
        delay = max(0, ((entry_time + timedelta(minutes=1, seconds=10)) - datetime.datetime.now()).total_seconds())
        await asyncio.sleep(delay)
        
        profit = (payout_val / 100)
        db_record_result(user_id, True, profit)
        res_msg = f"🏆 WIN 🏆\n\nMARKET: {pair.replace('_otc','').upper()} OTC\nENTRY: {entry_time.strftime('%H:%M')}"
        await tg("sendMessage", chat_id=chat_id, text=fmt(res_msg, bold=True), parse_mode="HTML")
    except Exception as e:
        print(f"Signal Error: {e}")

# ==================== TELEGRAM COMMANDS ====================
async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_upsert(uid, update.effective_user.username, update.effective_user.full_name)
    user = db_get(uid)
    
    if user.get('is_banned'):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
        
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt("💥 WELCOME TO DARK SECRET BOT 🔥\n\nSelect an option below:", bold=True),
             parse_mode="HTML", reply_markup=kb_welcome())

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    db_upsert(uid, query.from_user.username, query.from_user.full_name)
    user = db_get(uid)
    
    if user.get('is_banned'):
        await query.answer("You are banned!", show_alert=True)
        return
        
    if not can_signal(user) and data in ("auto_signal", "manual_signal"):
        await query.answer("Access Denied or Limit Reached!", show_alert=True)
        return

    await query.answer()

# ==================== FLASK ADMIN PANEL ====================
web_app = Flask(__name__)

HTML_ADMIN_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DARK SECRET BOT Admin</title>
    <style>
        :root {
            --bg-color: #0b0e14;
            --card-bg: #151a23;
            --accent: #7c3aed;
            --text-main: #f3f4f6;
            --text-sub: #9ca3af;
            --danger: #ef4444;
            --success: #10b981;
            --border: #232a3b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg-color); color: var(--text-main); padding: 15px; max-width: 500px; margin: 0 auto; }
        
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .brand { display: flex; align-items: center; gap: 10px; }
        .logo { width: 36px; height: 36px; background: linear-gradient(135deg, #a855f7, #6366f1); borderRadius: 8px; display: flex; align-items: center; justify-content: center; font-weight: bold; }
        .title-group h2 { font-size: 16px; font-weight: 700; }
        .title-group p { font-size: 11px; color: var(--text-sub); }
        .status-badge { background: #13271d; color: var(--success); padding: 4px 10px; border-radius: 20px; font-size: 12px; border: 1px solid #1b4d3e; }
        .status-badge.stopped { background: #2d1517; color: var(--danger); border-color: #5c1d24; }

        .section-title { font-size: 11px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 1px; margin: 15px 0 10px 0; }
        
        .grid-2x2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .stat-card { background: var(--card-bg); padding: 15px; border-radius: 12px; border: 1px solid var(--border); position: relative; }
        .stat-card h1 { font-size: 26px; font-weight: 700; margin-bottom: 2px; }
        .stat-card p { font-size: 11px; color: var(--text-sub); font-weight: 600; }
        .stat-card .icon { position: absolute; right: 12px; top: 15px; color: #374151; }

        .nav-tabs { display: flex; background: #0f131a; border-radius: 10px; padding: 3px; border: 1px solid var(--border); margin-bottom: 15px; }
        .tab-btn { flex: 1; padding: 8px 0; text-align: center; font-size: 13px; font-weight: 600; color: var(--text-sub); border: none; background: transparent; cursor: pointer; border-radius: 8px; }
        .tab-btn.active { background: #211c38; color: #c084fc; border: 1px solid #3b2a59; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .card { background: var(--card-bg); border-radius: 12px; padding: 15px; border: 1px solid var(--border); margin-bottom: 15px; }
        
        .flex-between { display: flex; justify-content: space-between; align-items: center; }
        .btn { padding: 8px 16px; border-radius: 8px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; }
        .btn-purple { background: linear-gradient(135deg, #9333ea, #c084fc); color: #fff; width: 100%; margin-top: 10px; padding: 10px; }
        .btn-danger { background: #ef4444; color: #fff; }

        select, input, textarea { width: 100%; background: #0b0e14; border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; margin-top: 6px; font-size: 13px; outline: none; }
        
        .user-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
        .user-item:last-child { border-bottom: none; }
        .avatar { width: 36px; height: 36px; background: #e879f9; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #000; font-size: 13px; }
        .user-info { flex: 1; margin-left: 12px; }
        .user-info h4 { font-size: 13px; }
        .user-info p { font-size: 11px; color: var(--text-sub); }

        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); align-items: flex-end; justify-content: center; z-index: 100; }
        .modal-content { background: var(--card-bg); width: 100%; max-width: 500px; border-radius: 20px 20px 0 0; padding: 20px; border-top: 1px solid var(--border); }
        .modal-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
    </style>
</head>
<body>

    <div class="header">
        <div class="brand">
            <div class="logo">⚡</div>
            <div class="title-group">
                <h2>DARK SECRECT BOT <span style="color:#a855f7">Admin</span></h2>
                <p>PRIVATE CONSOLE</p>
            </div>
        </div>
        <div id="botStatusBadge" class="status-badge">● Running</div>
    </div>

    <div class="section-title">OVERVIEW</div>
    <div class="grid-2x2">
        <div class="stat-card">
            <h1 id="statTotalUsers">0</h1>
            <p>TOTAL USERS</p>
        </div>
        <div class="stat-card">
            <h1 id="statLicensed">0</h1>
            <p>LICENSED</p>
        </div>
        <div class="stat-card">
            <h1 id="statBanned">0</h1>
            <p>BANNED</p>
        </div>
        <div class="stat-card">
            <h1 id="statToday">0</h1>
            <p>TODAY</p>
        </div>
    </div>

    <div class="section-title">MANAGEMENT</div>
    <div class="nav-tabs">
        <button class="tab-btn active" onclick="switchTab('control')">Control</button>
        <button class="tab-btn" onclick="switchTab('users')">Users</button>
        <button class="tab-btn" onclick="switchTab('limits')">Limits</button>
    </div>

    <!-- TAB 1: CONTROL -->
    <div id="tab-control" class="tab-content active">
        <div class="card">
            <h3>Bot Control</h3>
            <br>
            <div class="flex-between">
                <span>Bot Status</span>
                <button id="toggleBotBtn" class="btn btn-danger" onclick="toggleBot()">Stop</button>
            </div>
            <br>
            <label style="font-size: 12px; color: var(--text-sub);">Access Mode</label>
            <select id="accessModeSelect">
                <option value="licensed_only">Licensed Only</option>
                <option value="all">Public Access</option>
            </select>
            <button class="btn btn-purple" onclick="saveAccessMode()">Save Access Mode</button>
        </div>

        <div class="card">
            <h3>Send Announcement</h3>
            <p style="font-size: 11px; color: var(--text-sub); margin-top: 2px;">Sent only to non-banned users of this bot.</p>
            <textarea id="broadcastMsg" rows="3" placeholder="Write your announcement..."></textarea>
            <button class="btn btn-purple" onclick="sendBroadcast()">Send Broadcast</button>
        </div>
    </div>

    <!-- TAB 2: USERS -->
    <div id="tab-users" class="tab-content">
        <input type="text" id="userSearch" placeholder="Search by name, username or ID..." onkeyup="filterUsers()">
        <div id="userList" style="margin-top: 10px;"></div>
    </div>

    <!-- TAB 3: LIMITS -->
    <div id="tab-limits" class="tab-content">
        <div class="card">
            <h3>FREE Plan</h3>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <div>
                    <label style="font-size:10px;">LIVE SIGNALS / DAY</label>
                    <input type="number" id="freeLive" value="5">
                </div>
                <div>
                    <label style="font-size:10px;">FUTURE LISTS / DAY</label>
                    <input type="number" id="freeFuture" value="2">
                </div>
            </div>
            <button class="btn btn-purple" onclick="saveLimits()">Save Free Limits</button>
        </div>

        <div class="card">
            <h3>STARTER Plan</h3>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <div>
                    <label style="font-size:10px;">LIVE SIGNALS / DAY</label>
                    <input type="number" id="starterLive" value="25">
                </div>
                <div>
                    <label style="font-size:10px;">FUTURE LISTS / DAY</label>
                    <input type="number" id="starterFuture" value="3">
                </div>
            </div>
            <button class="btn btn-purple" onclick="saveLimits()">Save Starter Limits</button>
        </div>
    </div>

    <!-- USER MODAL -->
    <div id="userModal" class="modal">
        <div class="modal-content">
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 15px;">
                <div class="avatar" id="modalAvatar">MD</div>
                <div>
                    <h3 id="modalName">User Name</h3>
                    <p style="font-size:11px; color:var(--text-sub);" id="modalUsername">@username</p>
                </div>
            </div>
            
            <div class="modal-item"><span>User ID</span><span id="modalUid">00000</span></div>
            <div class="modal-item"><span>Plan</span><span id="modalPlan">FREE</span></div>
            <div class="modal-item"><span>First Seen</span><span id="modalJoined">2026-10-18</span></div>
            <div class="modal-item"><span>Last Active</span><span id="modalLast">2026-10-19</span></div>
            <div class="modal-item"><span>Status</span><span id="modalStatus" style="color:var(--success)">Active</span></div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px;">
                <button class="btn btn-danger" id="modalBanBtn" onclick="toggleBan()">Ban User</button>
                <button class="btn btn-purple" style="margin-top:0" onclick="grantLicense()">Grant License</button>
                <button class="btn" style="background:#374151; color:#fff;" onclick="resetUsage()">Reset Usage</button>
                <button class="btn" style="background:#1f2937; color:#fff;" onclick="closeModal()">Close</button>
            </div>
        </div>
    </div>

    <script>
        let allUsersData = [];
        let selectedUserId = null;

        function switchTab(name) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }

        async function loadData() {
            const res = await fetch('/api/admin/data');
            const data = await res.json();
            
            document.getElementById('statTotalUsers').innerText = data.stats.total;
            document.getElementById('statLicensed').innerText = data.stats.licensed;
            document.getElementById('statBanned').innerText = data.stats.banned;
            document.getElementById('statToday').innerText = data.stats.today;

            const badge = document.getElementById('botStatusBadge');
            const toggleBtn = document.getElementById('toggleBotBtn');
            if (data.settings.bot_running) {
                badge.innerText = '● Running';
                badge.className = 'status-badge';
                toggleBtn.innerText = 'Stop';
                toggleBtn.className = 'btn btn-danger';
            } else {
                badge.innerText = '● Stopped';
                badge.className = 'status-badge stopped';
                toggleBtn.innerText = 'Start';
                toggleBtn.className = 'btn';
                toggleBtn.style.background = '#10b981';
            }

            allUsersData = data.users;
            renderUsers(allUsersData);
        }

        function renderUsers(list) {
            const container = document.getElementById('userList');
            container.innerHTML = '';
            list.forEach(u => {
                const initials = u.full_name ? u.full_name.substring(0,2).toUpperCase() : 'US';
                container.innerHTML += `
                    <div class="user-item" onclick="openModal(${u.user_id})">
                        <div class="avatar">${initials}</div>
                        <div class="user-info">
                            <h4>${u.full_name || 'No Name'}</h4>
                            <p>@${u.username || 'none'} ID:${u.user_id}</p>
                        </div>
                        <span style="font-size:11px; background:#1f2937; padding:3px 8px; border-radius:10px;">
                            ${u.is_premium ? u.plan_type : 'Free'}
                        </span>
                    </div>
                `;
            });
        }

        function filterUsers() {
            const q = document.getElementById('userSearch').value.toLowerCase();
            const filtered = allUsersData.filter(u => 
                (u.full_name && u.full_name.toLowerCase().includes(q)) ||
                (u.username && u.username.toLowerCase().includes(q)) ||
                u.user_id.toString().includes(q)
            );
            renderUsers(filtered);
        }

        function openModal(uid) {
            const u = allUsersData.find(x => x.user_id === uid);
            if(!u) return;
            selectedUserId = uid;

            document.getElementById('modalAvatar').innerText = u.full_name ? u.full_name.substring(0,2).toUpperCase() : 'US';
            document.getElementById('modalName').innerText = u.full_name || 'No Name';
            document.getElementById('modalUsername').innerText = '@' + (u.username || 'none');
            document.getElementById('modalUid').innerText = u.user_id;
            document.getElementById('modalPlan').innerText = u.is_premium ? u.plan_type.toUpperCase() : 'FREE';
            document.getElementById('modalJoined').innerText = u.joined_at || 'N/A';
            document.getElementById('modalLast').innerText = u.last_active || 'N/A';
            
            const banBtn = document.getElementById('modalBanBtn');
            if(u.is_banned) {
                document.getElementById('modalStatus').innerText = 'Banned';
                document.getElementById('modalStatus').style.color = 'var(--danger)';
                banBtn.innerText = 'Unban User';
            } else {
                document.getElementById('modalStatus').innerText = 'Active';
                document.getElementById('modalStatus').style.color = 'var(--success)';
                banBtn.innerText = 'Ban User';
            }

            document.getElementById('userModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('userModal').style.display = 'none';
        }

        async function toggleBot() {
            await fetch('/api/admin/toggle_bot', {method:'POST'});
            loadData();
        }

        async function toggleBan() {
            await fetch('/api/admin/toggle_ban', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id: selectedUserId})
            });
            closeModal();
            loadData();
        }

        async function grantLicense() {
            const days = prompt("Enter duration in days (or 'permanent'):", "30");
            if(days) {
                await fetch('/api/admin/grant_license', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({user_id: selectedUserId, days: days})
                });
                closeModal();
                loadData();
            }
        }

        async function resetUsage() {
            await fetch('/api/admin/reset_usage', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id: selectedUserId})
            });
            alert("Usage reset successful!");
            closeModal();
            loadData();
        }

        async function sendBroadcast() {
            const msg = document.getElementById('broadcastMsg').value;
            if(!msg) return alert("Write a message first!");
            await fetch('/api/admin/broadcast', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({message: msg})
            });
            alert("Broadcast sent!");
            document.getElementById('broadcastMsg').value = '';
        }

        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
"""

@web_app.route('/')
def admin_panel():
    return render_template_string(HTML_ADMIN_PANEL)

@web_app.route('/api/admin/data')
def get_admin_data():
    users = db_all()
    user_list = []
    licensed_count = 0
    banned_count = 0
    
    for u in users:
        is_prem = bool(u[3])
        if is_prem: licensed_count += 1
        if u[7]: banned_count += 1
        
        user_list.append({
            "user_id": u[0], "username": u[1], "full_name": u[2],
            "is_premium": is_prem, "total_sigs": u[4], "wins": u[5],
            "losses": u[6], "is_banned": bool(u[7]), "plan_type": u[8],
            "joined_at": u[9], "last_active": u[10], "daily_sigs": u[11]
        })
        
    return jsonify({
        "stats": {
            "total": len(users),
            "licensed": licensed_count,
            "banned": banned_count,
            "today": sum(u[11] for u in users)
        },
        "settings": SYSTEM_SETTINGS,
        "users": user_list
    })

@web_app.route('/api/admin/toggle_bot', methods=['POST'])
def api_toggle_bot():
    SYSTEM_SETTINGS['bot_running'] = not SYSTEM_SETTINGS['bot_running']
    return jsonify({"success": True, "status": SYSTEM_SETTINGS['bot_running']})

@web_app.route('/api/admin/toggle_ban', methods=['POST'])
def api_toggle_ban():
    data = request.get_json()
    uid = data.get('user_id')
    user = db_get(uid)
    if user:
        new_status = not bool(user.get('is_banned'))
        db_set_ban(uid, new_status)
    return jsonify({"success": True})

@web_app.route('/api/admin/grant_license', methods=['POST'])
def api_grant_license():
    data = request.get_json()
    db_set_license(data.get('user_id'), data.get('days', 30), 'premium')
    return jsonify({"success": True})

@web_app.route('/api/admin/reset_usage', methods=['POST'])
def api_reset_usage():
    data = request.get_json()
    db_reset_daily(data.get('user_id'))
    return jsonify({"success": True})

@web_app.route('/api/admin/broadcast', methods=['POST'])
def api_broadcast():
    data = request.get_json()
    msg = data.get('message')
    if msg:
        for u in db_all():
            if not u[7]: # if not banned
                try:
                    asyncio.run(tg("sendMessage", chat_id=u[0], text=fmt(msg, bold=True), parse_mode="HTML"))
                except Exception: pass
    return jsonify({"success": True})

# ==================== STARTUP LOGIC ====================
def run_flask():
    port = int(os.getenv("PORT", 5000))
    web_app.run(host="0.0.0.0", port=port)

def main():
    setup_db()
    
    # Run Flask in background thread for Render
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CallbackQueryHandler(on_callback))

    print("✅ DARK SECRET BOT + ADMIN PANEL STARTED SUCCESSFULLY!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
