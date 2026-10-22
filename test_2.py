import asyncio
import datetime
import aiohttp
import sqlite3
import io
import json
import html
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

# ==================== CONFIGURATION ====================
BOT_TOKEN   = "8670196207:AAG0x5h1IJxK5PhWwPMzSK0i9VzqhOXK3zk"
ADMIN_IDS   = {7488289885}  # Add admin IDs here: {123456789: True}
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
        "current_streak INTEGER DEFAULT 0"
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
    
    # Update streak
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

def db_premium_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id,username,full_name,plan_type FROM users WHERE is_premium=1')
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

# ==================== ENHANCED TECHNICAL INDICATORS ====================

def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Calculate RSI indicator"""
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
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_ema(closes: List[float], period: int) -> float:
    """Calculate EMA indicator"""
    if len(closes) < period:
        return closes[-1]
    
    k = 2 / (period + 1)
    ema = np.mean(closes[:period])
    
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    
    return ema

def calculate_macd(closes: List[float]) -> Tuple[float, float, float]:
    """Calculate MACD indicator"""
    fast_ema = calculate_ema(closes, STRATEGY_CONFIG['macd_fast'])
    slow_ema = calculate_ema(closes, STRATEGY_CONFIG['macd_slow'])
    macd_line = fast_ema - slow_ema
    
    # Calculate signal line (EMA of MACD)
    macd_values = []
    for i in range(STRATEGY_CONFIG['macd_slow'], len(closes)):
        f = calculate_ema(closes[:i+1], STRATEGY_CONFIG['macd_fast'])
        s = calculate_ema(closes[:i+1], STRATEGY_CONFIG['macd_slow'])
        macd_values.append(f - s)
    
    if len(macd_values) >= STRATEGY_CONFIG['macd_signal']:
        signal_line = calculate_ema(macd_values, STRATEGY_CONFIG['macd_signal'])
    else:
        signal_line = macd_line
    
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(closes: List[float]) -> Tuple[float, float, float]:
    """Calculate Bollinger Bands"""
    period = STRATEGY_CONFIG['bb_period']
    if len(closes) < period:
        return closes[-1], closes[-1], closes[-1]
    
    prices = closes[-period:]
    mean = np.mean(prices)
    std = np.std(prices)
    multiplier = STRATEGY_CONFIG['bb_std']
    
    upper = mean + (std * multiplier)
    lower = mean - (std * multiplier)
    
    return upper, mean, lower

def calculate_atr(highs: List[float], lows: List[float], closes: List[float]) -> float:
    """Calculate Average True Range"""
    period = STRATEGY_CONFIG['atr_period']
    if len(closes) < period + 1:
        return 0
    
    tr_values = []
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr = max(hl, hc, lc)
        tr_values.append(tr)
    
    if not tr_values:
        return 0
    
    return np.mean(tr_values[-period:])

def calculate_support_resistance(highs: List[float], lows: List[float], lookback: int = 50) -> Tuple[List[float], List[float]]:
    """Identify support and resistance levels"""
    if len(highs) < lookback:
        return [], []
    
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    
    # Find swing highs and lows
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(recent_highs) - 2):
        if (recent_highs[i] > recent_highs[i-1] and 
            recent_highs[i] > recent_highs[i-2] and
            recent_highs[i] > recent_highs[i+1] and 
            recent_highs[i] > recent_highs[i+2]):
            swing_highs.append(recent_highs[i])
        
        if (recent_lows[i] < recent_lows[i-1] and 
            recent_lows[i] < recent_lows[i-2] and
            recent_lows[i] < recent_lows[i+1] and 
            recent_lows[i] < recent_lows[i+2]):
            swing_lows.append(recent_lows[i])
    
    # Cluster nearby levels
    resistance = []
    for level in swing_highs:
        if not any(abs(level - r) / level < 0.002 for r in resistance):
            resistance.append(level)
    
    support = []
    for level in swing_lows:
        if not any(abs(level - s) / level < 0.002 for s in support):
            support.append(level)
    
    return support[:5], resistance[:5]

def detect_candlestick_patterns(candle: Dict, prev_candle: Dict) -> List[str]:
    """Detect candlestick patterns"""
    patterns = []
    
    o = float(candle['open'])
    h = float(candle['high'])
    l = float(candle['low'])
    c = float(candle['close'])
    prev_o = float(prev_candle['open'])
    prev_c = float(prev_candle['close'])
    
    body = abs(c - o)
    range_candle = h - l
    upper_wick = h - max(c, o)
    lower_wick = min(c, o) - l
    
    # Doji
    if body < range_candle * 0.1:
        patterns.append("DOJI")
    
    # Hammer / Shooting Star
    if upper_wick > body * 2 and lower_wick < body * 0.5:
        patterns.append("SHOOTING_STAR")
    elif lower_wick > body * 2 and upper_wick < body * 0.5:
        patterns.append("HAMMER")
    
    # Engulfing
    if c > o and prev_c < prev_o and c > prev_o and o < prev_c:
        patterns.append("BULLISH_ENGULFING")
    elif c < o and prev_c > prev_o and c < prev_o and o > prev_c:
        patterns.append("BEARISH_ENGULFING")
    
    # Marubozu
    if upper_wick < body * 0.1 and lower_wick < body * 0.1:
        if c > o:
            patterns.append("BULLISH_MARUBOZU")
        else:
            patterns.append("BEARISH_MARUBOZU")
    
    return patterns

# ==================== MAIN ANALYSIS ENGINE ====================

def enhanced_analyze(candles: List[Dict]) -> Tuple[Optional[str], int, Dict]:
    """
    Enhanced trading strategy with multiple confirmations
    Returns: (direction, confidence, details)
    """
    if len(candles) < 50:
        return None, 0, {}
    
    # Prepare price data
    closes = [float(c['close']) for c in candles]
    opens = [float(c['open']) for c in candles]
    highs = [float(c['high']) for c in candles]
    lows = [float(c['low']) for c in candles]
    volumes = [float(c.get('volume', 0)) for c in candles]
    
    # Calculate indicators
    rsi = calculate_rsi(closes)
    ema_fast = calculate_ema(closes, STRATEGY_CONFIG['ema_fast'])
    ema_slow = calculate_ema(closes, STRATEGY_CONFIG['ema_slow'])
    ema_trend = calculate_ema(closes, STRATEGY_CONFIG['ema_trend'])
    macd_line, signal_line, histogram = calculate_macd(closes)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(closes)
    atr = calculate_atr(highs, lows, closes)
    support, resistance = calculate_support_resistance(highs, lows)
    
    # Current candle
    current_candle = candles[-1]
    prev_candle = candles[-2] if len(candles) > 1 else current_candle
    
    # Detect patterns
    patterns = detect_candlestick_patterns(current_candle, prev_candle)
    
    # Price position
    current_price = closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else current_price
    
    # Initialize scoring
    score = 0
    signals = []
    confidence_factors = []
    
    # ========== TREND ANALYSIS ==========
    # EMA alignment
    if ema_fast > ema_slow > ema_trend:
        score += 25
        signals.append("BULLISH_TREND")
        confidence_factors.append(25)
    elif ema_fast < ema_slow < ema_trend:
        score -= 25
        signals.append("BEARISH_TREND")
        confidence_factors.append(25)
    
    # Price vs EMA
    if current_price > ema_slow:
        score += 15
        signals.append("PRICE_ABOVE_EMA")
        confidence_factors.append(15)
    elif current_price < ema_slow:
        score -= 15
        signals.append("PRICE_BELOW_EMA")
        confidence_factors.append(15)
    
    # ========== MOMENTUM ANALYSIS ==========
    # RSI
    if rsi < STRATEGY_CONFIG['rsi_oversold']:
        score += 20
        signals.append(f"RSI_OVERSOLD_{rsi}")
        confidence_factors.append(20)
    elif rsi > STRATEGY_CONFIG['rsi_overbought']:
        score -= 20
        signals.append(f"RSI_OVERBOUGHT_{rsi}")
        confidence_factors.append(20)
    
    # RSI divergence
    if len(closes) >= 20:
        recent_rsi_lows = []
        recent_price_lows = []
        for i in range(-20, 0):
            if i >= -len(closes):
                recent_rsi_lows.append(calculate_rsi(closes[:i+20] if i+20 > 0 else closes[:i+20]))
                recent_price_lows.append(closes[i])
        
        if len(recent_rsi_lows) > 5:
            if min(recent_rsi_lows[-5:]) > min(recent_rsi_lows[:-5]) and min(recent_price_lows[-5:]) < min(recent_price_lows[:-5]):
                score += 30
                signals.append("BULLISH_RSI_DIVERGENCE")
                confidence_factors.append(30)
            elif max(recent_rsi_lows[-5:]) < max(recent_rsi_lows[:-5]) and max(recent_price_lows[-5:]) > max(recent_price_lows[:-5]):
                score -= 30
                signals.append("BEARISH_RSI_DIVERGENCE")
                confidence_factors.append(30)
    
    # ========== MACD ANALYSIS ==========
    if macd_line > signal_line:
        score += 15
        signals.append("MACD_BULLISH_CROSS")
        confidence_factors.append(15)
        
        if histogram > 0:
            score += 5
            signals.append("MACD_HISTOGRAM_POSITIVE")
    else:
        score -= 15
        signals.append("MACD_BEARISH_CROSS")
        confidence_factors.append(15)
        
        if histogram < 0:
            score -= 5
            signals.append("MACD_HISTOGRAM_NEGATIVE")
    
    # ========== BOLLINGER BANDS ==========
    if current_price <= bb_lower:
        score += 15
        signals.append("PRICE_AT_LOWER_BB")
        confidence_factors.append(15)
    elif current_price >= bb_upper:
        score -= 15
        signals.append("PRICE_AT_UPPER_BB")
        confidence_factors.append(15)
    
    # BB squeeze (volatility contraction)
    bb_width = (bb_upper - bb_lower) / bb_middle
    prev_bb_upper, prev_bb_middle, prev_bb_lower = calculate_bollinger_bands(closes[:-1])
    prev_width = (prev_bb_upper - prev_bb_lower) / prev_bb_middle
    
    if bb_width < prev_width and bb_width < 0.05:
        if score > 0:
            score += 10
            signals.append("BB_SQUEEZE_BULLISH")
        else:
            score -= 10
            signals.append("BB_SQUEEZE_BEARISH")
    
    # ========== CANDLESTICK PATTERNS ==========
    pattern_scores = {
        "BULLISH_ENGULFING": 20,
        "BEARISH_ENGULFING": -20,
        "HAMMER": 15,
        "SHOOTING_STAR": -15,
        "BULLISH_MARUBOZU": 10,
        "BEARISH_MARUBOZU": -10,
        "DOJI": 0
    }
    
    for pattern in patterns:
        if pattern in pattern_scores:
            score += pattern_scores[pattern]
            signals.append(pattern)
            confidence_factors.append(abs(pattern_scores[pattern]))
    
    # ========== SUPPORT/RESISTANCE ==========
    # Check distance to levels
    for sup in support:
        if abs(current_price - sup) / current_price < 0.005:  # Within 0.5%
            score += 20
            signals.append("NEAR_SUPPORT")
            confidence_factors.append(20)
            break
    
    for res in resistance:
        if abs(current_price - res) / current_price < 0.005:
            score -= 20
            signals.append("NEAR_RESISTANCE")
            confidence_factors.append(20)
            break
    
    # ========== VOLUME ANALYSIS ==========
    if len(volumes) > STRATEGY_CONFIG['volume_sma']:
        avg_volume = np.mean(volumes[-STRATEGY_CONFIG['volume_sma']:-1])
        current_volume = volumes[-1]
        
        if current_volume > avg_volume * 1.5:
            if score > 0:
                score += 10
                signals.append("HIGH_VOLUME_BULLISH")
            else:
                score -= 10
                signals.append("HIGH_VOLUME_BEARISH")
    
    # ========== FINAL DECISION ==========
    # Normalize score to 0-100 range (original range approx -100 to 100)
    normalized_score = (score + 100) / 2
    base_confidence = min(98, max(50, normalized_score))
    
    # Adjust confidence based on signal consistency
    if len(set(signals)) >= 3:
        base_confidence = min(98, base_confidence + 10)
    
    # Determine direction
    if score > 20:
        direction = "CALL"
        final_confidence = min(98, base_confidence + 5)
    elif score < -20:
        direction = "PUT"
        final_confidence = min(98, base_confidence + 5)
    else:
        # Neutral - use EMA trend
        if ema_fast > ema_slow:
            direction = "CALL"
            final_confidence = 65
        else:
            direction = "PUT"
            final_confidence = 65
    
    # Ensure minimum confidence
    final_confidence = max(STRATEGY_CONFIG['min_confidence'], final_confidence)
    
    # Prepare detailed analysis
    analysis_details = {
        'rsi': round(rsi, 1),
        'ema_fast': round(ema_fast, 6),
        'ema_slow': round(ema_slow, 6),
        'macd': round(macd_line, 6),
        'signal': round(signal_line, 6),
        'histogram': round(histogram, 6),
        'bb_upper': round(bb_upper, 6),
        'bb_middle': round(bb_middle, 6),
        'bb_lower': round(bb_lower, 6),
        'atr': round(atr, 6),
        'score': score,
        'signals': signals[:5],  # Top 5 signals
        'patterns': patterns
    }
    
    return direction, final_confidence, analysis_details

# ==================== CHARTING ====================

def build_enhanced_chart(candles: List[Dict], pair: str, direction: str, 
                         analysis: Dict, is_result: bool = False, win: bool = None) -> io.BytesIO:
    """Create enhanced professional chart with indicators"""
    disp = list(reversed(candles[:50]))
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), 
                                    gridspec_kw={'height_ratios': [3, 1]},
                                    sharex=True)
    
    fig.patch.set_facecolor('#0a0a0a')
    ax1.set_facecolor('#0f0f0f')
    ax2.set_facecolor('#0f0f0f')
    
    # ===== CANDLE CHART =====
    all_p = []
    for c in disp:
        all_p += [float(c['high']), float(c['low'])]
    
    if all_p:
        pr = max(all_p) - min(all_p)
        pad = pr * 0.12 if pr > 0 else 0.0001
        ax1.set_ylim(min(all_p) - pad, max(all_p) + pad)
    
    # Plot candles
    for i, c in enumerate(disp):
        o = float(c['open'])
        h = float(c['high'])
        lo = float(c['low'])
        cl = float(c['close'])
        bull = cl >= o
        color = '#00e676' if bull else '#ff1744'
        
        # Wick
        ax1.plot([i, i], [lo, h], color=color, linewidth=0.8, zorder=2, solid_capstyle='round')
        
        # Body
        body_bottom = min(o, cl)
        body_height = abs(cl - o)
        body_height = max(body_height, (h - lo) * 0.02)  # Minimum height for visibility
        
        ax1.add_patch(plt.Rectangle((i - 0.35, body_bottom), 0.7, body_height,
                                    facecolor=color, edgecolor=color, zorder=3, alpha=0.9))
    
    # Calculate and plot EMAs
    closes = [float(c['close']) for c in disp]
    if len(closes) >= STRATEGY_CONFIG['ema_fast']:
        ema8_values = []
        ema21_values = []
        for i in range(STRATEGY_CONFIG['ema_slow'], len(closes) + 1):
            ema8 = calculate_ema(closes[:i], STRATEGY_CONFIG['ema_fast'])
            ema21 = calculate_ema(closes[:i], STRATEGY_CONFIG['ema_slow'])
            ema8_values.append(ema8)
            ema21_values.append(ema21)
        
        x_vals = list(range(len(disp) - len(ema8_values), len(disp)))
        ax1.plot(x_vals, ema8_values, color='#ffd54f', linewidth=1.5, label=f'EMA{STRATEGY_CONFIG["ema_fast"]}', alpha=0.8)
        ax1.plot(x_vals, ema21_values, color='#64b5f6', linewidth=1.5, label=f'EMA{STRATEGY_CONFIG["ema_slow"]}', alpha=0.8)
    
    # Bollinger Bands
    if len(closes) >= STRATEGY_CONFIG['bb_period']:
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(closes)
        x_range = range(len(disp))
        ax1.axhline(y=bb_upper, color='#9c27b0', linestyle='--', linewidth=1, alpha=0.6, label='BB Upper')
        ax1.axhline(y=bb_middle, color='#9c27b0', linestyle='-', linewidth=1, alpha=0.6, label='BB Middle')
        ax1.axhline(y=bb_lower, color='#9c27b0', linestyle='--', linewidth=1, alpha=0.6, label='BB Lower')
    
    # Grid and styling
    ax1.grid(True, color='#1a1a1a', linewidth=0.3, linestyle='-', alpha=0.5)
    ax1.set_axisbelow(True)
    
    # Title and info
    brand_text = f"⚡ DARK SECRET BY RAYHAN⚡\n{pair.replace('_otc','').upper()} OTC"
    ax1.text(0.01, 0.98, brand_text, transform=ax1.transAxes, fontsize=10,
             color='#ffffff', ha='left', va='top', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#333333', alpha=0.9))
    
    # Direction indicator
    dir_color = '#00e676' if direction == 'CALL' else '#ff1744'
    dir_symbol = '▲' if direction == 'CALL' else '▼'
    dir_text = f"  {dir_symbol} {direction}  "
    ax1.text(0.99, 0.98, dir_text, transform=ax1.transAxes, fontsize=11,
             color='#ffffff', ha='right', va='top', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=dir_color, alpha=0.9))
    
    # Analysis info
    if analysis:
        info_text = f"RSI: {analysis.get('rsi', '--')} | Score: {analysis.get('score', 0):.0f}"
        ax1.text(0.01, 0.02, info_text, transform=ax1.transAxes, fontsize=8,
                 color='#aaaaaa', ha='left', va='bottom', fontfamily='monospace')
    
    # Result indicator
    if is_result and win is not None:
        result_text = 'WIN' if win else 'LOSS'
        result_color = '#00e676' if win else '#ff1744'
        ax1.text(0.99, 0.02, result_text, transform=ax1.transAxes, fontsize=12,
                 color=result_color, ha='right', va='bottom', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=result_color, alpha=0.9))
    
    # ===== RSI SUBPLOT =====
    if len(closes) >= STRATEGY_CONFIG['rsi_period']:
        rsi_values = []
        for i in range(STRATEGY_CONFIG['rsi_period'], len(closes) + 1):
            rsi = calculate_rsi(closes[:i])
            rsi_values.append(rsi)
        
        x_rsi = list(range(len(disp) - len(rsi_values), len(disp)))
        ax2.plot(x_rsi, rsi_values, color='#ffd54f', linewidth=1.5, label='RSI')
        ax2.axhline(y=STRATEGY_CONFIG['rsi_overbought'], color='#ff1744', linestyle='--', linewidth=1, alpha=0.7)
        ax2.axhline(y=STRATEGY_CONFIG['rsi_oversold'], color='#00e676', linestyle='--', linewidth=1, alpha=0.7)
        ax2.axhline(y=50, color='#ffffff', linestyle=':', linewidth=0.8, alpha=0.5)
        ax2.fill_between(x_rsi, rsi_values, 50, where=(np.array(rsi_values) > 50), 
                          color='#00e676', alpha=0.1, interpolate=True)
        ax2.fill_between(x_rsi, rsi_values, 50, where=(np.array(rsi_values) < 50), 
                          color='#ff1744', alpha=0.1, interpolate=True)
    
    ax2.set_ylim(0, 100)
    ax2.grid(True, color='#1a1a1a', linewidth=0.3, linestyle='-', alpha=0.5)
    ax2.set_ylabel('RSI', color='#aaaaaa', fontsize=9)
    ax2.tick_params(axis='y', colors='#aaaaaa', labelsize=7)
    
    # X-axis formatting
    n = len(disp)
    step = max(1, n // 8)
    xt = list(range(0, n, step))
    BD = timezone(timedelta(hours=6))
    
    def ep_to_bd(c):
        ep = c.get('epoch') or c.get('time')
        try:
            return datetime.datetime.fromtimestamp(int(ep), tz=BD).strftime('%H:%M')
        except Exception:
            raw = str(c.get('time', ''))
            return raw[-5:] if len(raw) >= 5 else raw
    
    xl = [ep_to_bd(disp[i]) for i in xt if i < n]
    ax2.set_xticks(xt[:len(xl)])
    ax2.set_xticklabels(xl, color='#aaaaaa', fontsize=8)
    ax2.set_xlim(-0.8, max(n - 0.2, 1))
    
    ax1.tick_params(axis='y', colors='#aaaaaa', labelsize=8)
    ax1.tick_params(axis='x', colors='#aaaaaa', labelsize=8)
    
    for sp in ax1.spines.values():
        sp.set_color('#333333')
        sp.set_linewidth(0.5)
    for sp in ax2.spines.values():
        sp.set_color('#333333')
        sp.set_linewidth(0.5)
    
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#0a0a0a', dpi=120, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==================== API FUNCTIONS ====================

async def fetch_candles(pair: str, count: int = 100) -> List[Dict]:
    """Fetch candle data from API"""
    url = f"{API_BASE}?pair={pair}&timeframe=M1&count={count}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                d = await r.json(content_type=None)
                return d.get('data', [])
    except Exception as e:
        print(f"Error fetching {pair}: {e}")
        return []

async def get_payout(pair: str) -> int:
    """Get payout percentage for a pair"""
    now = datetime.datetime.now().timestamp()
    if pair in payout_cache:
        p, t = payout_cache[pair]
        if now - t < CACHE_TTL:
            return p
    candles = await fetch_candles(pair, count=1)
    p = int(candles[0].get('payout', 80)) if candles else 80
    payout_cache[pair] = (p, now)
    return p

async def fetch_all_payouts() -> List[Tuple[str, int]]:
    """Fetch payouts for all pairs concurrently"""
    sem = asyncio.Semaphore(15)
    
    async def limited(pair):
        async with sem:
            return pair, await get_payout(pair)
    
    results = await asyncio.gather(*[limited(p) for p in PAIRS], return_exceptions=True)
    return [(p, v) for p, v in results if not isinstance(v, Exception) and isinstance(v, (int, float))]

# ==================== TELEGRAM FUNCTIONS ====================

def fmt(text: str, bold: bool = False, italic: bool = False, quote: bool = False) -> str:
    """Format text with emojis and HTML"""
    parts = []
    i = 0
    chars = list(text)
    while i < len(chars):
        ch = chars[i]
        next_ch = chars[i + 1] if i + 1 < len(chars) else ''
        if ch in EMAP:
            safe = html.escape(ch)
            parts.append(f'<tg-emoji emoji-id="{EMAP[ch]}">{safe}</tg-emoji>')
            if next_ch == '\ufe0f':
                i += 2
            else:
                i += 1
        elif ch == '\ufe0f':
            i += 1
        else:
            parts.append(html.escape(ch))
            i += 1
    result = ''.join(parts)
    if bold and italic:
        result = f'<b><i>{result}</i></b>'
    elif bold:
        result = f'<b>{result}</b>'
    elif italic:
        result = f'<i>{result}</i>'
    if quote:
        result = f'<blockquote>{result}</blockquote>'
    return result

def btn(text: str, cb: str = None, url: str = None, style: str = None, icon: str = None) -> Dict:
    """Create inline keyboard button"""
    b = {"text": text}
    if cb:
        b["callback_data"] = cb
    if url:
        b["url"] = url
    if style:
        b["style"] = style
    if icon:
        b["icon_custom_emoji_id"] = ICON.get(icon, str(icon))
    return b

def markup(*rows_) -> Dict:
    """Create inline keyboard markup"""
    return {"inline_keyboard": [list(row) for row in rows_]}

async def tg(method: str, **kwargs) -> Dict:
    """Telegram API wrapper"""
    data = {k: v for k, v in kwargs.items() if v is not None}
    
    if "reply_markup" in data and isinstance(data["reply_markup"], dict):
        data["reply_markup"] = json.dumps(data["reply_markup"])
    
    photo = data.pop("photo", None)
    url = f"{BOT_API}/{method}"
    
    try:
        async with aiohttp.ClientSession() as session:
            if photo:
                form = aiohttp.FormData()
                for k, v in data.items():
                    form.add_field(k, str(v))
                photo_bytes = photo.read() if hasattr(photo, "read") else photo
                form.add_field("photo", photo_bytes, filename="chart.png", content_type="image/png")
                async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    return await r.json(content_type=None)
            else:
                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    return await r.json(content_type=None)
    except Exception as e:
        print(f"[TG API] {method} error: {e}")
        return {}

# ==================== KEYBOARDS ====================

def kb_welcome():
    return markup(
        [btn("🤖 AUTO SIGNAL", "auto_signal", style="success", icon="robot"),
         btn("📝 MANUAL SIGNAL", "manual_signal", style="primary", icon="writing")],
        [btn("💰 PRICING", "pricing", style="primary", icon="money"),
         btn("👤 MY PROFILE", "my_profile", style="primary", icon="profile")],
        [btn("ℹ️ ABOUT", "about", style="primary", icon="about")],
    )

def kb_back_home():
    return markup([btn("◀️ BACK", "home", style="primary", icon="back")])

def kb_home_only():
    return markup([btn("🏠 HOME", "home", style="primary", icon="home")])

def kb_new_home():
    return markup(
        [btn("🔄 NEW SIGNAL", "new_signal", style="success", icon="refresh"),
         btn("🎯 CHECK POINTS", "check_points", style="primary", icon="target")],
        [btn("🏠 HOME", "home", style="primary", icon="home")],
    )

def kb_stop_auto():
    return markup([btn("⏹️ STOP AUTO", "stop_auto", style="danger", icon="stop")])

def kb_after_stop():
    return markup(
        [btn("🔄 NEW SIGNAL", "new_signal", style="success", icon="refresh"),
         btn("🤖 AUTO SIGNAL", "auto_signal", style="success", icon="robot")],
        [btn("🏠 HOME", "home", style="primary", icon="home")],
    )

def kb_limit():
    return markup(
        [btn("💎 GET PREMIUM", url=SUPPORT_URL, style="success", icon="owner")],
        [btn("🏠 HOME", "home", style="primary", icon="home")],
    )

def kb_result_nav():
    return markup(
        [btn("🔄 NEW SIGNAL", "res_new_signal", style="success", icon="refresh"),
         btn("📊 SEND PARTIAL", "res_send_partial", style="primary", icon="target")],
        [btn("🏠 HOME", "res_home", style="primary", icon="home")],
    )

def kb_auto_result_nav():
    return markup(
        [btn("📊 SEND PARTIAL", "res_send_partial", style="primary", icon="target")],
        [btn("⏹️ STOP AUTO", "res_stop_auto", style="danger", icon="stop")],
        [btn("🏠 HOME", "res_home", style="primary", icon="home")],
    )

# ==================== SIGNAL GENERATION ====================

async def do_signal(bot, chat_id, user_id, pair, from_auto=False, analyzing_msg_id=None):
    """Generate and send a trading signal"""
    try:
        candles = await fetch_candles(pair, count=100)
        
        if not candles:
            fail_msg = "❌ Market data unavailable. Please try again."
            await tg("sendMessage", chat_id=chat_id, text=fmt(fail_msg, bold=True),
                     parse_mode="HTML", reply_markup=kb_back_home())
            return
        
        direction, confidence, analysis = enhanced_analyze(candles)
        
        if not direction:
            fail_msg = "❌ Unable to analyze market. Please try another pair."
            await tg("sendMessage", chat_id=chat_id, text=fmt(fail_msg, bold=True),
                     parse_mode="HTML", reply_markup=kb_back_home())
            return
        
        now = datetime.datetime.now()
        entry_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        payout_val = await get_payout(pair)
        
        # Signal message
        di = "🟢" if direction == "CALL" else "🔴"
        
        # Add confidence stars
        confidence_stars = "⭐" * (confidence // 20) if confidence >= 60 else "📊"
        
        sig_msg = (
            f"✨✨✨ SIGNAL GENERATED ✨✨✨\n\n"
            f"📊 MARKET     →  {pair.replace('_otc','').upper()} OTC\n"
            f"⏰ ENTRY      →  {entry_time.strftime('%H:%M')}\n"
            f"⏳ EXPIRY     →  1 Minute (M1)\n"
            f"💎 PAYOUT     →  {payout_val}%\n"
            f"{di} DIRECTION   →  {direction}\n"
            f"🎯 CONFIDENCE →  {confidence}% {confidence_stars}\n\n"
            f"📈 RSI: {analysis.get('rsi', '--')} | "
            f"MACD: {analysis.get('histogram', 0):.2f}\n"
            f"🔍 Signals: {', '.join(analysis.get('signals', [])[:3])}\n\n"
            f"⏳ Checking result automatically..."
        )
        
        chart = build_enhanced_chart(candles, pair, direction, analysis)
        chart.name = 'signal.png'
        
        # Delete analyzing message
        if analyzing_msg_id:
            try:
                await tg("deleteMessage", chat_id=chat_id, message_id=analyzing_msg_id)
            except Exception:
                pass
        
        await tg("sendPhoto", chat_id=chat_id, photo=chart,
                 caption=fmt(sig_msg, bold=True, quote=True), parse_mode="HTML")
        
        db_inc_daily(user_id)
        user_states[user_id] = {
            'waiting': True,
            'pair': pair,
            'direction': direction,
            'entry_ep': int(entry_time.timestamp()),
            'time_str': entry_time.strftime('%H:%M'),
            'auto': from_auto,
            'payout': payout_val
        }
        
        # Schedule result check
        check_at = entry_time + timedelta(minutes=1, seconds=10)
        delay = max(0, (check_at - datetime.datetime.now()).total_seconds())
        await asyncio.sleep(delay)
        await do_result(bot, chat_id, user_id)
        
    except asyncio.CancelledError:
        user_states.pop(user_id, None)
        raise
    except Exception as e:
        print(f"Error in do_signal: {e}")
        user_states.pop(user_id, None)

async def do_result(bot, chat_id, user_id):
    """Check and send signal result"""
    state = user_states.get(user_id)
    if not state:
        return
    
    pair = state['pair']
    direction = state['direction']
    entry_ep = state['entry_ep']
    time_str = state['time_str']
    from_auto = state['auto']
    payout = state.get('payout', 85)
    
    try:
        candles = await fetch_candles(pair, count=15)
        
        # Find target candle
        target = None
        for c in candles:
            if abs(int(c.get('epoch', 0)) - entry_ep) <= 30:
                target = c
                break
        if not target and len(candles) > 1:
            target = candles[1]
        if not target and candles:
            target = candles[0]
        
        if not target:
            user_states.pop(user_id, None)
            return
        
        c_o = float(target['open'])
        c_c = float(target['close'])
        win = (c_c > c_o) if direction == 'CALL' else (c_c < c_o)
        
        profit = (payout / 100) if win else -1
        
        db_record_result(user_id, win, profit)
        db_partial_add(user_id, pair, direction, time_str, win, is_mtg=False, profit=profit)
        
        # Create result chart
        analysis = enhanced_analyze(candles)[2] if len(candles) >= 50 else {}
        rchart = build_enhanced_chart(candles, pair, direction, analysis, is_result=True, win=win)
        rchart.name = 'result.png'
        
        di = "🟢" if direction == "CALL" else "🔴"
        result_icon = "✅✅✅" if win else "❌❌❌"
        result_text = "🏆 WIN 🏆" if win else "📉 LOSS"
        
        result_msg = (
            f"{result_icon} RESULT {result_icon}\n\n"
            f"📊 MARKET    →  {pair.replace('_otc','').upper()} OTC\n"
            f"⏰ ENTRY     →  {time_str}\n"
            f"{di} DIRECTION →  {direction}\n"
            f"📈 PROFIT    →  {profit:+.1f}%\n\n"
            f"{'✅' if win else '❌'} RESULT    →  {result_text}\n"
        )
        
        result_kb = kb_auto_result_nav() if from_auto else kb_result_nav()
        
        await tg("sendPhoto", chat_id=chat_id, photo=rchart,
                 caption=fmt(result_msg, bold=True, quote=True),
                 parse_mode="HTML", reply_markup=result_kb)
        
        # Check for MTG (second minute)
        if not win:
            entry_time_obj = datetime.datetime.fromtimestamp(entry_ep)
            mtg_entry_time = entry_time_obj + timedelta(minutes=1)
            
            user_states[user_id] = {
                'waiting': True,
                'pair': pair,
                'direction': direction,
                'entry_ep': int(mtg_entry_time.timestamp()),
                'time_str': mtg_entry_time.strftime('%H:%M'),
                'orig_time': time_str,
                'auto': from_auto,
                'mtg': True,
                'payout': payout
            }
            
            mtg_delay = max(0, (mtg_entry_time + timedelta(minutes=1, seconds=10) - datetime.datetime.now()).total_seconds())
            await asyncio.sleep(mtg_delay)
            await do_mtg_result(bot, chat_id, user_id)
        else:
            user_states.pop(user_id, None)
            
    except asyncio.CancelledError:
        user_states.pop(user_id, None)
        raise
    except Exception as e:
        print(f"Error in do_result: {e}")
        user_states.pop(user_id, None)

async def do_mtg_result(bot, chat_id, user_id):
    """Check MTG (second minute) result"""
    state = user_states.get(user_id)
    if not state:
        return
    
    pair = state['pair']
    direction = state['direction']
    mtg_ep = state['entry_ep']
    orig_time = state.get('orig_time', state['time_str'])
    from_auto = state['auto']
    payout = state.get('payout', 85)
    
    try:
        candles = await fetch_candles(pair, count=15)
        
        target = None
        for c in candles:
            if abs(int(c.get('epoch', 0)) - mtg_ep) <= 30:
                target = c
                break
        if not target and len(candles) > 1:
            target = candles[1]
        if not target and candles:
            target = candles[0]
        
        if not target:
            user_states.pop(user_id, None)
            return
        
        c_o = float(target['open'])
        c_c = float(target['close'])
        win = (c_c > c_o) if direction == 'CALL' else (c_c < c_o)
        
        profit = (payout / 100) if win else -1
        
        db_record_result(user_id, win, profit)
        db_partial_add(user_id, pair, direction, orig_time, win, is_mtg=True, profit=profit)
        
        analysis = enhanced_analyze(candles)[2] if len(candles) >= 50 else {}
        rchart = build_enhanced_chart(candles, pair, direction, analysis, is_result=True, win=win)
        rchart.name = 'mtg_result.png'
        
        result_icon = "✅✅✅" if win else "❌❌❌"
        result_text = "🏆 WIN (MTG) 🏆" if win else "📉 LOSS"
        di = "🟢" if direction == "CALL" else "🔴"
        
        result_msg = (
            f"{result_icon} RESULT {result_icon}\n\n"
            f"📊 MARKET    →  {pair.replace('_otc','').upper()} OTC\n"
            f"⏰ ENTRY     →  {orig_time}\n"
            f"{di} DIRECTION →  {direction}\n"
            f"📈 PROFIT    →  {profit:+.1f}%\n\n"
            f"{'✅' if win else '❌'} RESULT    →  {result_text}\n"
        )
        
        result_kb = kb_auto_result_nav() if from_auto else kb_result_nav()
        
        await tg("sendPhoto", chat_id=chat_id, photo=rchart,
                 caption=fmt(result_msg, bold=True, quote=True),
                 parse_mode="HTML", reply_markup=result_kb)
        
    except Exception as e:
        print(f"Error in do_mtg_result: {e}")
    finally:
        user_states.pop(user_id, None)

# ==================== AUTO MODE ====================

AUTO_MIN_CONFIDENCE = 70
AUTO_PAIR_BLOCK_MINS = 5
AUTO_CYCLE_SLEEP = 10

async def auto_loop(bot, chat_id, user_id):
    """Automatic signal generation loop"""
    blocked_pairs = {}
    
    try:
        while True:
            user = db_get(user_id)
            if not user:
                break
            user = refresh_daily(user)
            
            if not can_signal(user):
                limit_msg = (
                    f"❌ DAILY LIMIT REACHED\n\n"
                    f"You have used your limit.\n"
                    "Upgrade to continue trading."
                )
                await tg("sendMessage", chat_id=chat_id,
                         text=fmt(limit_msg, bold=True),
                         parse_mode="HTML", reply_markup=kb_limit())
                break
            
            all_payouts = await fetch_all_payouts()
            eligible = [(p, v) for p, v in all_payouts if v >= 80]
            
            if not eligible:
                await asyncio.sleep(AUTO_CYCLE_SLEEP)
                continue
            
            now_dt = datetime.datetime.now()
            blocked_pairs = {p: t for p, t in blocked_pairs.items() if t > now_dt}
            eligible = [(p, v) for p, v in eligible if p not in blocked_pairs]
            
            if not eligible:
                await asyncio.sleep(AUTO_CYCLE_SLEEP)
                continue
            
            # Analyze pairs
            best_pair = None
            best_confidence = 0
            best_analysis = None
            
            for pair, payout in eligible[:10]:  # Limit to 10 pairs per cycle
                candles = await fetch_candles(pair, count=100)
                if candles:
                    direction, confidence, analysis = enhanced_analyze(candles)
                    if direction and confidence > best_confidence:
                        best_confidence = confidence
                        best_pair = pair
                        best_analysis = analysis
            
            if best_pair and best_confidence >= AUTO_MIN_CONFIDENCE:
                blocked_pairs[best_pair] = now_dt + timedelta(minutes=AUTO_PAIR_BLOCK_MINS)
                await do_signal(bot, chat_id, user_id, best_pair, from_auto=True)
                
                if user_id not in auto_tasks:
                    break
                
                await asyncio.sleep(AUTO_CYCLE_SLEEP)
            else:
                await asyncio.sleep(AUTO_CYCLE_SLEEP)
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Auto loop error: {e}")
    finally:
        auto_tasks.pop(user_id, None)
        user_states.pop(user_id, None)

# ==================== WELCOME TEXT ====================

def welcome_text() -> str:
    return (
"💥 WELCOME TO DARK SECRET BY RAYHAN🔥\n\n"
"━━━━━━━━━━━━━━━━━━━━\n\n"
"⚡ Next-generation binary signal engine\n"
"⚡ AI-powered technical analysis\n"
"⚡ Real-time market scanning\n\n"
"━━━━━━━━━━━━━━━━━━━━\n\n"
"✨ FEATURES:\n"
"🤖 Auto trading mode\n"
"📊 Advanced technical indicators\n"
"🎯 80%+ accuracy target\n"
"📈 Real-time charts with indicators\n"
"💎 Premium signals with high payout\n\n"
"━━━━━━━━━━━━━━━━━━━━\n\n"
"🚀 Select an option below to begin\n"
    )

# ==================== COMMAND HANDLERS ====================

async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or ''
    fname = update.effective_user.full_name or ''
    db_upsert(uid, uname, fname)
    
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt(welcome_text(), bold=True, italic=True),
             parse_mode="HTML", reply_markup=kb_welcome())

async def on_addlicense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usage: /addlicense <user_id> <plan> <duration>\n\n"
            "Plans: premium (25/day), vip (unlimited)\n"
            "Durations: weekly, monthly, permanent, or days number",
            parse_mode="HTML"
        )
        return
    
    DURATION_MAP = {'weekly': 7, 'monthly': 30, 'permanent': 'permanent'}
    
    try:
        uid = int(context.args[0])
        plan_arg = context.args[1].lower()
        dur_arg = context.args[2].lower()
        
        if plan_arg not in ('premium', 'vip'):
            await update.message.reply_text("❌ Invalid plan. Use: premium or vip")
            return
        
        days = DURATION_MAP.get(dur_arg, int(dur_arg) if dur_arg.isdigit() else None)
        if days is None:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid input. Check usage.")
        return
    
    db_set_license(uid, days, plan_type=plan_arg)
    
    plan_label = "PREMIUM (25/day)" if plan_arg == 'premium' else "VIP (Unlimited)"
    duration_label = "Permanent ♾️" if days == 'permanent' else f"{days} days"
    
    msg = f"✅ LICENSE GRANTED\n\n🆔 User: {uid}\n💎 Plan: {plan_label}\n⏳ Duration: {duration_label}"
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt(msg, bold=True), parse_mode="HTML")

async def on_removelicense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /removelicense <user_id>")
        return
    uid = int(context.args[0])
    db_revoke_license(uid)
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt(f"❌ License revoked for user {uid}", bold=True),
             parse_mode="HTML")

async def on_checklicense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /checklicense <user_id>")
        return
    uid = int(context.args[0])
    user = db_get(uid)
    if not user:
        await update.message.reply_text(f"❌ User {uid} not found.")
        return
    
    active = db_is_premium(user)
    plan = "VIP" if user.get('plan_type') == 'vip' else "PREMIUM" if active else "FREE"
    
    msg = (
        f"👤 USER INFO\n\n"
        f"Name: {user['full_name']}\n"
        f"ID: {uid}\n"
        f"Plan: {plan}\n"
        f"Signals: {user['total_sigs']}\n"
        f"Wins: {user['wins']} | Losses: {user['losses']}\n"
        f"Win Rate: {user['wins']/(user['wins']+user['losses'])*100:.1f}%"
    )
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt(msg, bold=True), parse_mode="HTML")

async def on_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    all_users = db_all()
    premium = sum(1 for u in all_users if u[3])
    msg = f"📊 USERS\n\nTotal: {len(all_users)}\nPremium: {premium}\nFree: {len(all_users) - premium}"
    await tg("sendMessage", chat_id=update.effective_chat.id,
             text=fmt(msg, bold=True), parse_mode="HTML")

async def on_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
    msg = ' '.join(context.args)
    sent = failed = 0
    for u in db_all():
        try:
            await tg("sendMessage", chat_id=u[0], text=fmt(msg, bold=True), parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Broadcast: {sent} sent, {failed} failed")

# ==================== CALLBACK HANDLER ====================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    uname = query.from_user.username or ''
    fname = query.from_user.full_name or ''
    bot = context.bot
    
    db_upsert(uid, uname, fname)
    user = db_get(uid)
    user = refresh_daily(user)
    
    # Navigation handlers
    if data in ("res_home", "res_new_signal", "res_send_partial", "res_stop_auto"):
        await query.answer()
        try:
            await tg("editMessageReplyMarkup", chat_id=query.message.chat_id,
                     message_id=query.message.message_id, reply_markup={"inline_keyboard": []})
        except Exception:
            pass
        
        if data == "res_home":
            if uid in auto_tasks:
                auto_tasks[uid].cancel()
                auto_tasks.pop(uid, None)
            user_states.pop(uid, None)
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt(welcome_text(), bold=True, italic=True),
                     parse_mode="HTML", reply_markup=kb_welcome())
        
        elif data == "res_send_partial":
            rows = db_partial_get(uid)
            if not rows:
                await tg("sendMessage", chat_id=query.message.chat_id,
                         text=fmt("📭 No records yet.", bold=True), parse_mode="HTML")
            else:
                wins = sum(1 for r in rows if r[3])
                total = len(rows)
                wr = round(wins / total * 100, 1) if total else 0
                
                lines = []
                for r in rows[:20]:  # Limit to 20 most recent
                    pair, direction, t_str, win, is_mtg, date_str, profit = r
                    dir_label = 'BUY' if direction == 'CALL' else 'PUT'
                    result_sym = '✅' if win else '❌'
                    profit_str = f"+{profit:.0f}%" if profit > 0 else f"{profit:.0f}%"
                    lines.append(f"{result_sym} {pair.replace('_otc','').upper()} {dir_label} @{t_str} {profit_str}")
                
                msg = (
                    f"📊 PARTIAL SIGNALS REPORT\n\n"
                    f"Period: {rows[0][5]} - {rows[-1][5]}\n"
                    f"Total: {total} | Wins: {wins} | WR: {wr}%\n\n"
                    + "\n".join(lines)
                )
                
                kb_partial = markup(
                    [btn("🔄 NEW SIGNAL", "res_new_signal", style="success", icon="refresh"),
                     btn("🗑️ RESET", "partial_reset", style="danger", icon="stop")]
                )
                await tg("sendMessage", chat_id=query.message.chat_id,
                         text=fmt(msg, bold=True, quote=True), parse_mode="HTML",
                         reply_markup=kb_partial)
        
        elif data == "res_stop_auto":
            if uid in auto_tasks:
                auto_tasks[uid].cancel()
                auto_tasks.pop(uid, None)
            user_states.pop(uid, None)
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt("⏹️ AUTO MODE STOPPED", bold=True),
                     parse_mode="HTML", reply_markup=kb_after_stop())
        
        elif data == "res_new_signal":
            if uid in user_states and user_states[uid].get('waiting'):
                await query.answer("⏳ Please wait for current signal result.", show_alert=True)
                return
            if uid in auto_tasks:
                await query.answer("⏹️ Stop Auto Mode first.", show_alert=True)
                return
            
            await query.answer()
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt("📊 Fetching markets...", bold=True), parse_mode="HTML")
            
            pp = await fetch_all_payouts()
            pp.sort(key=lambda x: x[1], reverse=True)
            
            pair_btns = []
            row = []
            for i, (pair, pv) in enumerate(pp):
                label = f"{pair.replace('_otc','').upper()} ({pv}%)"
                style = "success" if pv >= 80 else "primary" if pv >= 70 else "danger"
                row.append(btn(label, f"pair_{pair}", style=style))
                if len(row) == 2 or i == len(pp) - 1:
                    pair_btns.append(row)
                    row = []
            
            pair_btns.append([btn("◀️ BACK", "home", style="primary", icon="back")])
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt("💎 SELECT MARKET\n\nHigher payout = better return", bold=True),
                     parse_mode="HTML", reply_markup={"inline_keyboard": pair_btns})
        return
    
    if data == "partial_reset":
        await query.answer()
        db_partial_reset(uid)
        try:
            await tg("editMessageReplyMarkup", chat_id=query.message.chat_id,
                     message_id=query.message.message_id, reply_markup={"inline_keyboard": []})
        except Exception:
            pass
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt("🔄 PARTIAL RECORDS RESET", bold=True), parse_mode="HTML")
        return
    
    if data == "home":
        await query.answer()
        if uid in auto_tasks:
            auto_tasks[uid].cancel()
            auto_tasks.pop(uid, None)
        user_states.pop(uid, None)
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(welcome_text(), bold=True, italic=True),
                 parse_mode="HTML", reply_markup=kb_welcome())
        return
    
    if data == "pricing":
        await query.answer()
        msg = (
"💎 PREMIUM PLANS\n\n"
"━━━━━━━━━━━━━━━━━━━━\n\n"
"📊 FREE PLAN\n"
"• 2 signals/day\n"
"• Basic analysis\n\n"
"💎 PREMIUM ($10/week, $35/month)\n"
"• 25 signals/day\n"
"• Advanced analysis\n"
"• Priority support\n\n"
"👑 VIP ($15/week, $50/month)\n"
"• Unlimited signals\n"
"• Full indicators\n"
"• 24/7 priority support\n\n"
"━━━━━━━━━━━━━━━━━━━━\n\n"
"Contact @Dark_secrect to upgrade"
        )
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(msg, bold=True), parse_mode="HTML",
                 reply_markup=markup([btn("◀️ BACK", "home", style="primary", icon="back")]))
        return
    
    if data == "about":
        await query.answer()
        msg = (
"🤖 DARK SECRET BY RAYHAN\n\n"
"👑 Owner: @Dark_secrect\n"
"⚡ Version: 2.0\n\n"
"📊 Features:\n"
"• AI-powered analysis\n"
"• Multiple indicators\n"
"• Auto trading mode\n"
"• Real-time charts\n"
"• Win/loss tracking\n\n"
"💬 Support: @Dark_secrect"
        )
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(msg, bold=True), parse_mode="HTML",
                 reply_markup=markup(
                     [btn("👑 OWNER", url="https://t.me/Dark_secrect", style="primary", icon="owner")],
                     [btn("◀️ BACK", "home", style="primary", icon="back")]
                 ))
        return
    
    if data == "my_profile":
        await query.answer()
        total = user['wins'] + user['losses']
        wr = round(user['wins'] / total * 100, 1) if total else 0
        
        plan_type = user.get('plan_type', 'free')
        is_prem = db_is_premium(user)
        
        if uid in ADMIN_IDS:
            plan_icon, plan_label, daily_limit = "👑", "ADMIN", "Unlimited"
        elif is_prem and plan_type == 'vip':
            plan_icon, plan_label, daily_limit = "👑", "VIP", "Unlimited"
        elif is_prem:
            plan_icon, plan_label, daily_limit = "💎", "PREMIUM", f"{PREMIUM_LIMIT}/day"
        else:
            plan_icon, plan_label, daily_limit = "🆓", "FREE", f"{FREE_LIMIT}/day"
        
        used = user['daily_sigs']
        remaining = "∞" if daily_limit == "Unlimited" else max(0, int(daily_limit.split('/')[0]) - used)
        
        msg = (
            f"👤 MY PROFILE\n\n"
            f"📛 Name: {user['full_name']}\n"
            f"🆔 ID: {uid}\n"
            f"💬 @{user['username'] or 'None'}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{plan_icon} Plan: {plan_label}\n"
            f"📊 Daily: {used} used / {remaining} remaining\n"
            f"🏆 Total: {user['total_sigs']} signals\n"
            f"✅ Wins: {user['wins']} | ❌ Losses: {user['losses']}\n"
            f"📈 Win Rate: {wr}%\n"
            f"🔥 Streak: {user.get('current_streak', 0)}\n"
            f"💰 Total P/L: {user.get('total_profit', 0):.1f}%"
        )
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(msg, bold=True), parse_mode="HTML",
                 reply_markup=markup([btn("◀️ BACK", "home", style="primary", icon="back")]))
        return
    
    if data == "check_points":
        await query.answer()
        total = user['wins'] + user['losses']
        wr = round(user['wins'] / total * 100, 1) if total else 0
        
        msg = (
            f"🎯 PERFORMANCE\n\n"
            f"🏆 Wins: {user['wins']}\n"
            f"❌ Losses: {user['losses']}\n"
            f"📊 Total: {user['total_sigs']}\n"
            f"📈 Win Rate: {wr}%\n"
            f"🔥 Best Streak: {user.get('best_streak', 0)}\n"
            f"💰 Net Profit: {user.get('total_profit', 0):.1f}%"
        )
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(msg, bold=True), parse_mode="HTML",
                 reply_markup=markup(
                     [btn("🔄 NEW SIGNAL", "new_signal", style="success", icon="refresh"),
                      btn("🏠 HOME", "home", style="primary", icon="home")]
                 ))
        return
    
    if data == "auto_signal":
        await query.answer()
        if uid in auto_tasks:
            auto_tasks[uid].cancel()
            await asyncio.sleep(0.1)
            auto_tasks.pop(uid, None)
        user_states.pop(uid, None)
        
        if not can_signal(user):
            msg = f"❌ Daily limit reached ({FREE_LIMIT} free signals). Upgrade to continue."
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt(msg, bold=True), parse_mode="HTML", reply_markup=kb_limit())
            return
        
        msg = "🤖 AUTO MODE ACTIVATED\n\nScanning markets for high-probability setups..."
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt(msg, bold=True), parse_mode="HTML", reply_markup=kb_stop_auto())
        
        task = asyncio.create_task(auto_loop(bot, query.message.chat_id, uid))
        auto_tasks[uid] = task
        return
    
    if data == "stop_auto":
        await query.answer()
        if uid in auto_tasks:
            auto_tasks[uid].cancel()
            auto_tasks.pop(uid, None)
        user_states.pop(uid, None)
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt("⏹️ AUTO MODE STOPPED", bold=True),
                 parse_mode="HTML", reply_markup=kb_after_stop())
        return
    
    if data in ("manual_signal", "new_signal"):
        if uid in user_states and user_states[uid].get('waiting'):
            await query.answer("⏳ Please wait for current signal result.", show_alert=True)
            return
        if uid in auto_tasks:
            await query.answer("⏹️ Stop Auto Mode first.", show_alert=True)
            return
        
        await query.answer()
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt("📊 Fetching markets...", bold=True), parse_mode="HTML")
        
        pp = await fetch_all_payouts()
        pp.sort(key=lambda x: x[1], reverse=True)
        
        pair_btns = []
        row = []
        for i, (pair, pv) in enumerate(pp):
            label = f"{pair.replace('_otc','').upper()} ({pv}%)"
            style = "success" if pv >= 80 else "primary" if pv >= 70 else "danger"
            row.append(btn(label, f"pair_{pair}", style=style))
            if len(row) == 2 or i == len(pp) - 1:
                pair_btns.append(row)
                row = []
        
        pair_btns.append([btn("◀️ BACK", "home", style="primary", icon="back")])
        await tg("sendMessage", chat_id=query.message.chat_id,
                 text=fmt("💎 SELECT MARKET\n\nHigher payout = better return", bold=True),
                 parse_mode="HTML", reply_markup={"inline_keyboard": pair_btns})
        return
    
    if data.startswith("pair_"):
        if uid in user_states and user_states[uid].get('waiting'):
            await query.answer("⏳ Please wait for current signal result.", show_alert=True)
            return
        if uid in auto_tasks:
            await query.answer("⏹️ Stop Auto Mode first.", show_alert=True)
            return
        
        await query.answer()
        
        user = db_get(uid)
        user = refresh_daily(user)
        if not can_signal(user):
            msg = f"❌ Daily limit reached. You have {FREE_LIMIT} free signals/day.\nUpgrade to continue."
            await tg("sendMessage", chat_id=query.message.chat_id,
                     text=fmt(msg, bold=True), parse_mode="HTML", reply_markup=kb_limit())
            return
        
        pair = data.replace("pair_", "")
        try:
            await tg("deleteMessage", chat_id=query.message.chat_id,
                     message_id=query.message.message_id)
        except Exception:
            pass
        
        pair_display = pair.replace('_otc', '').upper()
        analyzing_text = f"🙂 Analyzing {pair_display} OTC..."
        amsg = await tg("sendMessage", chat_id=query.message.chat_id,
                        text=fmt(analyzing_text, bold=True), parse_mode="HTML")
        amsg_id = amsg.get("result", {}).get("message_id")
        
        asyncio.create_task(do_signal(bot, query.message.chat_id, uid, pair,
                                      from_auto=False, analyzing_msg_id=amsg_id))
        return

# ==================== MAIN ====================

def main():
    setup_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("addlicense", on_addlicense))
    app.add_handler(CommandHandler("removelicense", on_removelicense))
    app.add_handler(CommandHandler("checklicense", on_checklicense))
    app.add_handler(CommandHandler("users", on_users))
    app.add_handler(CommandHandler("broadcast", on_broadcast))
    app.add_handler(CallbackQueryHandler(on_callback))
    
    async def midnight_reset_loop():
        while True:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6)))
            tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait_sec = (tomorrow - now).total_seconds()
            await asyncio.sleep(wait_sec)
            db_reset_all_daily()
    
    async def on_startup(application):
        asyncio.create_task(midnight_reset_loop())
    
    async def on_shutdown(application):
        for task in list(auto_tasks.values()):
            task.cancel()
        auto_tasks.clear()
        user_states.clear()
    
    app.post_init = on_startup
    app.post_shutdown = on_shutdown
    
    print("✅ DARK SECRET BY RAYHAN - STARTED (Enhanced Strategy)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
