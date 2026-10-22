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

from flask import Flask, render_template_string, request, jsonify

# ==================== CONFIGURATION ====================
BOT_TOKEN   = "8670196207:AAG0x5h1IJxK5PhWwPMzSK0i9VzqhOXK3zk"
ADMIN_IDS   = {7488289885}  # Add admin IDs here: {123456789: True}[cite: 11]
DB_PATH     = "123.db"
API_BASE    = "https://cool-sky-e403.twssanjidapi.workers.dev"
SUPPORT_URL = "https://t.me/your_support"
FREE_LIMIT    = 2
PREMIUM_LIMIT = 25  # Increased from 15
CACHE_TTL     = 300
BOT_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"

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
        current_streak INTEGER DEFAULT 0
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
        "is_banned INTEGER DEFAULT 0"
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
            'total_profit','best_streak','current_streak']
    return dict(zip(keys, row))

def db_get(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id=?', (uid,))
    row = c.fetchone()
    conn.close()
    return _row(row)

def db_upsert(uid, username, full_name):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO users (user_id,username,full_name,joined_at) VALUES (?,?,?,?) '
        'ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name',
        (uid, username or '', full_name or '', now)
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
    conn.execute('UPDATE users SET is_premium=0, license_expiry="" WHERE user_id=?', (uid,))
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
    c.execute('SELECT user_id,username,full_name,is_premium,total_sigs,wins,losses FROM users ORDER BY total_sigs DESC')
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
        return PREMIUM_LIMIT
    return FREE_LIMIT

def can_signal(user):
    limit = get_daily_limit(user)
    if limit is None:
        return True
    return user['daily_sigs'] < limit

# ==================== TECHNICAL INDICATORS ====================
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
    return mean + (std * STRATEGY_CONFIG['bb_std']), mean, mean - (std * STRATEGY_CONFIG['bb_std'])

def calculate_atr(highs: List[float], lows: List[float], closes: List[float]) -> float:
    period = STRATEGY_CONFIG['atr_period']
    if len(closes) < period + 1:
        return 0
    tr_values = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(closes))]
    return np.mean(tr_values[-period:]) if tr_values else 0

def calculate_support_resistance(highs: List[float], lows: List[float], lookback: int = 50) -> Tuple[List[float], List[float]]:
    if len(highs) < lookback:
        return [], []
    swing_highs, swing_lows = [], []
    r_highs, r_lows = highs[-lookback:], lows[-lookback:]
    for i in range(2, len(r_highs) - 2):
        if r_highs[i] > r_highs[i-1] and r_highs[i] > r_highs[i-2] and r_highs[i] > r_highs[i+1] and r_highs[i] > r_highs[i+2]:
            swing_highs.append(r_highs[i])
        if r_lows[i] < r_lows[i-1] and r_lows[i] < r_lows[i-2] and r_lows[i] < r_lows[i+1] and r_lows[i] < r_lows[i+2]:
            swing_lows.append(r_lows[i])
    return [s for s in swing_lows][:5], [r for r in swing_highs][:5]

def detect_candlestick_patterns(candle: Dict, prev_candle: Dict) -> List[str]:
    patterns = []
    o, h, l, c = float(candle['open']), float(candle['high']), float(candle['low']), float(candle['close'])
    prev_o, prev_c = float(prev_candle['open']), float(prev_candle['close'])
    body = abs(c - o)
    if body < (h - l) * 0.1: patterns.append("DOJI")
    if c > o and prev_c < prev_o and c > prev_o: patterns.append("BULLISH_ENGULFING")
    elif c < o and prev_c > prev_o and c < prev_o: patterns.append("BEARISH_ENGULFING")
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
    
    score = 0
    signals = []
    if ema_fast > ema_slow > ema_trend: score += 25; signals.append("BULLISH_TREND")
    elif ema_fast < ema_slow < ema_trend: score -= 25; signals.append("BEARISH_TREND")
    if rsi < 30: score += 20; signals.append("RSI_OVERSOLD")
    elif rsi > 70: score -= 20; signals.append("RSI_OVERBOUGHT")
    if macd_line > signal_line: score += 15
    else: score -= 15
    
    direction = "CALL" if score > 0 else "PUT"
    confidence = min(98, max(60, int((abs(score) + 50))))
    return direction, confidence, {'rsi': rsi, 'histogram': histogram, 'score': score, 'signals': signals}

# ==================== CHARTING ====================
def build_enhanced_chart(candles: List[Dict], pair: str, direction: str, analysis: Dict, is_result: bool = False, win: bool = None) -> io.BytesIO:
    disp = list(reversed(candles[:50]))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    fig.patch.set_facecolor('#0a0a0a')
    ax1.set_facecolor('#0f0f0f'); ax2.set_facecolor('#0f0f0f')
    
    all_p = [float(c['high']) for c in disp] + [float(c['low']) for c in disp]
    if all_p:
        pr = max(all_p) - min(all_p)
        ax1.set_ylim(min(all_p) - pr*0.1, max(all_p) + pr*0.1)
    
    for i, c in enumerate(disp):
        o, h, lo, cl = float(c['open']), float(c['high']), float(c['low']), float(c['close'])
        color = '#00e676' if cl >= o else '#ff1744'
        ax1.plot([i, i], [lo, h], color=color, linewidth=0.8)
        ax1.add_patch(plt.Rectangle((i - 0.35, min(o, cl)), 0.7, max(abs(cl - o), 0.0001), facecolor=color, edgecolor=color))
    
    ax1.text(0.01, 0.98, f"DARK SECRET BY RAYHAN\n{pair.upper()}", transform=ax1.transAxes, color='#fff', fontsize=10, fontweight='bold', va='top')
    
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
        async with sem:
            return pair, await get_payout(pair)
    results = await asyncio.gather(*[limited(p) for p in PAIRS], return_exceptions=True)
    return [(p, v) for p, v in results if not isinstance(v, Exception)]

# ==================== TELEGRAM UTILS ====================
def fmt(text: str, bold: bool = False, italic: bool = False, quote: bool = False) -> str:
    res = html.escape(text)
    if bold: res = f"<b>{res}</b>"
    if quote: res = f"<blockquote>{res}</blockquote>"
    return res

def btn(text: str, cb: str = None, url: str = None, style: str = None, icon: str = None) -> Dict:
    b = {"text": text}
    if cb: b["callback_data"] = cb
    if url: b["url"] = url
    return b

def markup(*rows_) -> Dict:
    return {"inline_keyboard": [list(row) for row in rows_]}

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
                form.add_field("photo", photo.read() if hasattr(photo, "read") else photo, filename="chart.png", content_type="image/png")
                async with session.post(url, data=form) as r: return await r.json(content_type=None)
            else:
                async with session.post(url, data=data) as r: return await r.json(content_type=None)
    except Exception:
        return {}

# ==================== KEYBOARDS ====================
def kb_welcome():
    return markup(
        [btn("🤖 AUTO SIGNAL", "auto_signal"), btn("📝 MANUAL SIGNAL", "manual_signal")],
        [btn("💰 PRICING", "pricing"), btn("👤 MY PROFILE", "my_profile")],
        [btn("ℹ️ ABOUT", "about")]
    )
def kb_back_home(): return markup([btn("◀️ BACK", "home")])
def kb_limit(): return markup([btn("💎 GET PREMIUM", url=SUPPORT_URL), btn("🏠 HOME", "home")])
def kb_result_nav(): return markup([btn("🔄 NEW SIGNAL", "res_new_signal"), btn("🏠 HOME", "res_home")])
def kb_auto_result_nav(): return markup([btn("⏹️ STOP AUTO", "res_stop_auto"), btn("🏠 HOME", "res_home")])
def kb_stop_auto(): return markup([btn("⏹️ STOP AUTO", "stop_auto")])
def kb_after_stop(): return markup([btn("🔄 NEW SIGNAL", "new_signal"), btn("🤖 AUTO SIGNAL", "auto_signal"), btn("🏠 HOME", "home")])

# ==================== SIGNAL ENGINE ====================
async def do_signal(bot, chat_id, user_id, pair, from_auto=False, analyzing_msg_id=None):
    try:
        candles = await fetch_candles(pair, count=100)
        if not candles:
            await tg("sendMessage", chat_id=chat_id, text=fmt("❌ Market data unavailable."), parse_mode="HTML", reply_markup=kb_back_home())
            return
        direction, confidence, analysis = enhanced_analyze(candles)
        if not direction:
            await tg("sendMessage", chat_id=chat_id, text=fmt("❌ Unable to analyze market."), parse_mode="HTML", reply_markup=kb_back_home())
            return
        
        entry_time = (datetime.datetime.now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
        payout_val = await get_payout(pair)
        sig_msg = f"✨ SIGNAL ✨\n\n📊 Market: {pair.upper()}\n⏰ Entry: {entry_time.strftime('%H:%M')}\n🎯 Direction: {direction} ({confidence}%)"
        
        chart = build_enhanced_chart(candles, pair, direction, analysis)
        if analyzing_msg_id:
            try: await tg("deleteMessage", chat_id=chat_id, message_id=analyzing_msg_id)
            except: pass
            
        await tg("sendPhoto", chat_id=chat_id, photo=chart, caption=fmt(sig_msg, bold=True, quote=True), parse_mode="HTML")
        db_inc_daily(user_id)
        user_states[user_id] = {'waiting': True, 'pair': pair, 'direction': direction, 'entry_ep': int(entry_time.timestamp()), 'time_str': entry_time.strftime('%H:%M'), 'auto': from_auto, 'payout': payout_val}
        
        await asyncio.sleep((entry_time + timedelta(minutes=1, seconds=10) - datetime.datetime.now()).total_seconds())
        await do_result(bot, chat_id, user_id)
    except Exception:
        user_states.pop(user_id, None)

async def do_result(bot, chat_id, user_id):
    state = user_states.get(user_id)
    if not state: return
    pair, direction, entry_ep, time_str, from_auto, payout = state['pair'], state['direction'], state['entry_ep'], state['time_str'], state['auto'], state.get('payout', 85)
    try:
        candles = await fetch_candles(pair, count=15)
        target = candles[0] if candles else None
        if not target: user_states.pop(user_id, None); return
        win = (float(target['close']) > float(target['open'])) if direction == 'CALL' else (float(target['close']) < float(target['open']))
        profit = (payout / 100) if win else -1
        db_record_result(user_id, win, profit)
        db_partial_add(user_id, pair, direction, time_str, win, is_mtg=False, profit=profit)
        
        rchart = build_enhanced_chart(candles, pair, direction, {}, is_result=True, win=win)
        res_msg = f"RESULT: {'WIN 🏆' if win else 'LOSS 📉'}\nProfit: {profit:+.1f}%"
        await tg("sendPhoto", chat_id=chat_id, photo=rchart, caption=fmt(res_msg, bold=True, quote=True), parse_mode="HTML", reply_markup=kb_auto_result_nav() if from_auto else kb_result_nav())
    finally:
        user_states.pop(user_id, None)

async def auto_loop(bot, chat_id, user_id):
    try:
        while True:
            user = db_get(user_id)
            if not user or not can_signal(user): break
            all_payouts = await fetch_all_payouts()
            eligible = [p for p, v in all_payouts if v >= 80]
            if eligible:
                await do_signal(bot, chat_id, user_id, eligible[0], from_auto=True)
            await asyncio.sleep(10)
    except: pass
    finally:
        auto_tasks.pop(user_id, None)

# ==================== TELEGRAM COMMANDS ====================
def welcome_text(): return "💥 WELCOME TO DARK SECRET BY RAYHAN 🔥\n\nSelect an option below:"

async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db_upsert(u.id, u.username or '', u.full_name or '')
    await tg("sendMessage", chat_id=update.effective_chat.id, text=fmt(welcome_text(), bold=True), parse_mode="HTML", reply_markup=kb_welcome())

async def on_addlicense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if len(context.args) < 3: return
    db_set_license(int(context.args[0]), int(context.args[2]) if context.args[2].isdigit() else 'permanent', context.args[1].lower())
    await update.message.reply_text("✅ License granted successfully.")

async def on_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    all_u = db_all()
    await update.message.reply_text(f"📊 Total Users: {len(all_u)}")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; data = q.data; bot = context.bot
    db_upsert(uid, q.from_user.username or '', q.from_user.full_name or '')
    user = refresh_daily(db_get(uid))
    
    if data == "home" or data == "res_home":
        if uid in auto_tasks: auto_tasks[uid].cancel(); auto_tasks.pop(uid, None)
        await tg("sendMessage", chat_id=q.message.chat_id, text=fmt(welcome_text(), bold=True), parse_mode="HTML", reply_markup=kb_welcome())
    elif data in ("manual_signal", "new_signal", "res_new_signal"):
        pp = await fetch_all_payouts()
        pair_btns = [[btn(f"{p.upper()} ({v}%)", f"pair_{p}")] for p, v in pp[:8]]
        pair_btns.append([btn("◀️ BACK", "home")])
        await tg("sendMessage", chat_id=q.message.chat_id, text=fmt("💎 SELECT MARKET", bold=True), parse_mode="HTML", reply_markup={"inline_keyboard": pair_btns})
    elif data.startswith("pair_"):
        pair = data.replace("pair_", "")
        amsg = await tg("sendMessage", chat_id=q.message.chat_id, text=fmt(f"🙂 Analyzing {pair.upper()}...", bold=True), parse_mode="HTML")
        asyncio.create_task(do_signal(bot, q.message.chat_id, uid, pair, analyzing_msg_id=amsg.get("result", {}).get("message_id")))
    elif data == "auto_signal":
        if not can_signal(user):
            await tg("sendMessage", chat_id=q.message.chat_id, text=fmt("❌ Daily limit reached."), parse_mode="HTML", reply_markup=kb_limit())
            return
        await tg("sendMessage", chat_id=q.message.chat_id, text=fmt("🤖 AUTO MODE ACTIVATED", bold=True), parse_mode="HTML", reply_markup=kb_stop_auto())
        auto_tasks[uid] = asyncio.create_task(auto_loop(bot, q.message.chat_id, uid))
    elif data in ("stop_auto", "res_stop_auto"):
        if uid in auto_tasks: auto_tasks[uid].cancel(); auto_tasks.pop(uid, None)
        await tg("sendMessage", chat_id=q.message.chat_id, text=fmt("⏹️ AUTO MODE STOPPED", bold=True), parse_mode="HTML", reply_markup=kb_after_stop())
    elif data == "my_profile":
        msg = f"👤 PROFILE\nName: {user['full_name']}\nID: {uid}\nSignals Today: {user['daily_sigs']}\nWins: {user['wins']} | Losses: {user['losses']}"
        await tg("sendMessage", chat_id=q.message.chat_id, text=fmt(msg, bold=True), parse_mode="HTML", reply_markup=kb_back_home())

# ==================== FLASK ADMIN PANEL ====================
HTML_ADMIN_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel</title>
    <style>
        body { background: #0b0e14; color: #fff; font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto; }
        .card { background: #151a23; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #232a3b; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #232a3b; }
        .admin-badge { background: #7c3aed; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <h2>⚡ BOT ADMIN CONTROL</h2>
    <div class="card">
        <h3>Statistics</h3>
        <p>Total Users: <span id="totalUsers">0</span></p>
    </div>
    <div class="card">
        <h3>Users List</h3>
        <table>
            <thead><tr><th>ID</th><th>Name / Username</th><th>Role / Status</th></tr></thead>
            <tbody id="userTableBody"></tbody>
        </table>
    </div>
    <script>
        async function fetchAdminData() {
            const res = await fetch('/api/admin/data');
            const data = await res.json();
            document.getElementById('totalUsers').innerText = data.stats.total;
            let tbody = '';
            data.users.forEach(u => {
                let statusBadge = u.is_admin ? '<span class="admin-badge">ADMIN</span>' : (u.is_premium ? 'PREMIUM' : 'FREE');
                tbody += `<tr><td>${u.user_id}</td><td><b>${u.full_name || 'No Name'}</b><br><small>@${u.username || 'none'}</small></td><td>${statusBadge}</td></tr>`;
            });
            document.getElementById('userTableBody').innerText = '';
            document.getElementById('userTableBody').innerHTML = tbody;
        }
        fetchAdminData();
        setInterval(fetchAdminData, 5000);
    </script>
</body>
</html>
"""

web_app = Flask(__name__)

@web_app.route('/')
def admin_panel():
    return render_template_string(HTML_ADMIN_PANEL)

@web_app.route('/api/admin/data')
def get_admin_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM users ORDER BY user_id DESC').fetchall()
    conn.close()
    
    user_list = []
    for r in rows:
        u = dict(r)
        uid = u.get('user_id')
        user_list.append({
            "user_id": uid,
            "username": u.get('username', ''),
            "full_name": u.get('full_name', ''),
            "is_premium": bool(u.get('is_premium', 0)),
            "is_admin": uid in ADMIN_IDS,
            "daily_sigs": u.get('daily_sigs', 0)
        })
    return jsonify({"stats": {"total": len(rows)}, "users": user_list})

def run_flask():
    port = int(os.getenv("PORT", 5000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== MAIN TELEGRAM BOT RUNNER ====================
def main():
    setup_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("addlicense", on_addlicense))
    app.add_handler(CommandHandler("users", on_users))
    app.add_handler(CallbackQueryHandler(on_callback))
    
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ BOT & WEB PANEL STARTED SUCCESSFULLY")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
