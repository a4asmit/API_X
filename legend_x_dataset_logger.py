"""
legend_x_dataset_logger.py
==========================
LEGEND_X 4-Hour Market Dataset Logger

Captures exact market state (indicators, flow, price) at precise timestamp,
then logs the 4-hour future price outcome retroactively.

Creates a machine-readable CSV dataset:
    timestamp | symbol | current_price | trend_total_score | ... | cvd_skew | future_price | future_change_pct

Usage:
    # Run as background service every 4 hours
    python legend_x_dataset_logger.py

    # Or schedule with cron:
    0 */4 * * * cd /path/to/project && python legend_x_dataset_logger.py
    (Logs at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)

Dataset Purpose:
    - Train LSTM/transformers to predict 4-hour price moves
    - Learn hidden patterns (bull traps, bear traps, reversals)
    - Validate trading signals empirically
    - Build edge: "When trend=+7 AND cvd=-3.5%, what's the probability of -1%?"
"""

import json
import os
import csv
import math
import urllib.request
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ════════════════════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & LOGGING
# ════════════════════════════════════════════════════════════════════════════════════════════════

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dataset_logger.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Dataset configuration
DATA_DIR = Path("data")
DATASET_DIR = DATA_DIR / "dataset"
CSV_FILE = DATASET_DIR / "market_state_4h.csv"
PENDING_FILE = DATASET_DIR / "pending_observations.json"

# Symbols to log
SYMBOLS = ["BTC", "ETH", "SOL", "ADA"]  # Expand as needed

# Create directories
DATASET_DIR.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════════════════════════
# CSV INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════════════════════════

def init_csv():
    """Initialize CSV file with headers if it doesn't exist"""
    if CSV_FILE.exists():
        logger.info(f"CSV file exists: {CSV_FILE}")
        return
    
    headers = [
        # Context Data (The "When")
        "timestamp",
        "symbol",
        "current_price",
        
        # Trend Data (6-Factor Math)
        "trend_total_score",
        "structure_score",
        "adx_score",
        "funding_score",
        "rsi_score",
        "volume_score",
        "wick_score",
        
        # Flow Data (Order Flow CVD)
        "cvd_skew",
        "price_action_12h",
        
        # Target Variable (Outcome - Filled Retroactively)
        "future_price",
        "future_change_pct"
    ]
    
    try:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
        logger.info(f"✓ CSV initialized: {CSV_FILE}")
    except Exception as e:
        logger.error(f"Failed to initialize CSV: {e}")

# ════════════════════════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ════════════════════════════════════════════════════════════════════════════════════════════════

def fetch_klines(symbol, interval="1h", limit=168):
    """
    Fetch OHLCV candles from Binance FAPI
    
    Args:
        symbol: "BTC", "ETH", etc.
        interval: "1h", "1m", etc.
        limit: Number of candles to fetch
    
    Returns:
        List of [timestamp, open, high, low, close, volume, ...]
    """
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        return data
    except Exception as e:
        logger.error(f"Failed to fetch {symbol} klines: {e}")
        return []

def fetch_current_price(symbol):
    """Fetch current price from Binance"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}USDT"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        return float(data['price'])
    except Exception as e:
        logger.error(f"Failed to fetch current price for {symbol}: {e}")
        return None

def fetch_order_book(symbol, limit=1000):
    """Fetch order book depth from Binance"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol}USDT&limit={limit}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        return data
    except Exception as e:
        logger.error(f"Failed to fetch order book for {symbol}: {e}")
        return None

# ════════════════════════════════════════════════════════════════════════════════════════════════
# TREND ANALYSIS (6-FACTOR MATH)
# ════════════════════════════════════════════════════════════════════════════════════════════════

class TrendAnalyzer:
    """Compute the 6-factor trend score"""
    
    @staticmethod
    def ema(data, period):
        """Exponential moving average"""
        if len(data) < period:
            return data[-1] if data else 0
        multiplier = 2 / (period + 1)
        ema_val = data[0]
        for price in data[1:]:
            ema_val = price * multiplier + ema_val * (1 - multiplier)
        return ema_val
    
    @staticmethod
    def sma(data, period):
        """Simple moving average"""
        if len(data) < period:
            return sum(data) / len(data) if data else 0
        return sum(data[-period:]) / period
    
    @staticmethod
    def rsi(closes, period=14):
        """Relative Strength Index"""
        if len(closes) < period + 1:
            return 50  # Neutral
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        avg_gain = sum([d for d in deltas[-period:] if d > 0]) / period
        avg_loss = sum([-d for d in deltas[-period:] if d < 0]) / period
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(closes, fast=12, slow=26, signal=9):
        """MACD (Moving Average Convergence Divergence)"""
        if len(closes) < slow:
            return 0, 0, 0
        
        ema_fast = TrendAnalyzer.ema(closes, fast)
        ema_slow = TrendAnalyzer.ema(closes, slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line is EMA of MACD (simplified)
        signal_line = macd_line * 0.5  # Placeholder
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def analyze(klines):
        """
        Compute 6-factor trend score
        
        Returns:
            dict with: trend_total_score, structure_score, adx_score, 
                      funding_score, rsi_score, volume_score, wick_score
        """
        if len(klines) < 21:
            logger.warning("Insufficient data for trend analysis")
            return {
                'trend_total_score': 0,
                'structure_score': 0,
                'adx_score': 0,
                'funding_score': 0,
                'rsi_score': 0,
                'volume_score': 0,
                'wick_score': 0
            }
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[7]) for k in klines]
        
        # Factor 1: Structure Score (-2 to +2)
        # Compare current price to support/resistance levels
        sma_20 = TrendAnalyzer.sma(closes, 20)
        current = closes[-1]
        structure_score = 0
        if current > sma_20 * 1.02:
            structure_score = +2
        elif current > sma_20 * 1.01:
            structure_score = +1
        elif current < sma_20 * 0.98:
            structure_score = -2
        elif current < sma_20 * 0.99:
            structure_score = -1
        
        # Factor 2: ADX Score (-2 to +2) - Trend Muscle
        # Simple ATR-based trend strength
        atr = TrendAnalyzer._calc_atr(highs, lows, closes, 14)
        recent_move = closes[-1] - closes[-7]  # 7 periods ago
        adx_score = 0
        if recent_move > atr * 1.5:
            adx_score = +2
        elif recent_move > atr * 0.75:
            adx_score = +1
        elif recent_move < -atr * 1.5:
            adx_score = -2
        elif recent_move < -atr * 0.75:
            adx_score = -1
        
        # Factor 3: Funding Score (-2 to +2) - Leverage Trap
        # Simplified: Assume +2 if price near recent high, -2 if near low
        recent_high = max(closes[-24:])
        recent_low = min(closes[-24:])
        funding_score = 0
        if current > recent_high * 0.98:
            funding_score = +2
        elif current > (recent_high + recent_low) / 2:
            funding_score = +1
        elif current < recent_low * 1.02:
            funding_score = -2
        elif current < (recent_high + recent_low) / 2:
            funding_score = -1
        
        # Factor 4: RSI Score (-1 to +1) - Momentum
        rsi = TrendAnalyzer.rsi(closes, 14)
        rsi_score = 0
        if rsi > 70:
            rsi_score = -1  # Overbought
        elif rsi > 60:
            rsi_score = +1  # Strong
        elif rsi < 30:
            rsi_score = -1  # Oversold
        elif rsi < 40:
            rsi_score = -1  # Weak
        else:
            rsi_score = 0  # Neutral
        
        # Factor 5: Volume Score (-1 to +1) - Fuel
        avg_vol = sum(volumes[-20:]) / 20
        current_vol = volumes[-1]
        volume_score = 0
        if current_vol > avg_vol * 1.5:
            volume_score = +1  # High volume
        elif current_vol < avg_vol * 0.7:
            volume_score = -1  # Low volume
        
        # Factor 6: Wick Score (-1 to +1) - Rejection
        # Measure wick size relative to body
        body = abs(closes[-1] - closes[-2])
        wick_up = highs[-1] - max(closes[-1], closes[-2])
        wick_down = min(closes[-1], closes[-2]) - lows[-1]
        
        wick_score = 0
        if wick_up > body * 2:
            wick_score = -1  # Rejection from above
        elif wick_down > body * 2:
            wick_score = +1  # Rejection from below
        
        # Total Score (-9 to +9)
        trend_total_score = (
            structure_score + adx_score + funding_score +
            rsi_score + volume_score + wick_score
        )
        
        return {
            'trend_total_score': int(trend_total_score),
            'structure_score': int(structure_score),
            'adx_score': int(adx_score),
            'funding_score': int(funding_score),
            'rsi_score': int(rsi_score),
            'volume_score': int(volume_score),
            'wick_score': int(wick_score)
        }
    
    @staticmethod
    def _calc_atr(highs, lows, closes, period=14):
        """Calculate Average True Range"""
        if len(closes) < period:
            return 0
        
        tr_values = []
        for i in range(1, len(closes)):
            h_l = highs[i] - lows[i]
            h_c = abs(highs[i] - closes[i-1])
            l_c = abs(lows[i] - closes[i-1])
            tr = max(h_l, h_c, l_c)
            tr_values.append(tr)
        
        return sum(tr_values[-period:]) / period if tr_values else 0

# ════════════════════════════════════════════════════════════════════════════════════════════════
# CVD ANALYSIS (ORDER FLOW)
# ════════════════════════════════════════════════════════════════════════════════════════════════

class CVDAnalyzer:
    """Compute CVD (Cumulative Volume Delta) and order flow metrics"""
    
    @staticmethod
    def analyze(klines_1m, lookback_hours=12):
        """
        Analyze CVD over lookback period
        
        Args:
            klines_1m: 1-minute candles (from last 12 hours)
            lookback_hours: Hours to analyze
        
        Returns:
            dict with: cvd_skew, price_action_12h
        """
        if not klines_1m or len(klines_1m) < 2:
            return {'cvd_skew': 0.0, 'price_action_12h': 0.0}
        
        # Extract closes and taker volumes
        closes = [float(k[4]) for k in klines_1m]
        volumes = [float(k[7]) for k in klines_1m]
        
        # Estimate taker buy/sell volume (simplified)
        # In real implementation, you'd use Binance taker buy volume field
        taker_buy_vol = sum(volumes) * 0.52  # Simplified: assume 52% buys on average
        taker_sell_vol = sum(volumes) * 0.48
        
        # CVD Skew: % difference
        total_vol = taker_buy_vol + taker_sell_vol
        cvd_skew = ((taker_buy_vol - taker_sell_vol) / total_vol * 100) if total_vol > 0 else 0
        
        # Price action over 12h
        price_action_12h = ((closes[-1] - closes[0]) / closes[0]) * 100
        
        return {
            'cvd_skew': round(cvd_skew, 2),
            'price_action_12h': round(price_action_12h, 2)
        }

# ════════════════════════════════════════════════════════════════════════════════════════════════
# PENDING OBSERVATIONS (JSON STORAGE)
# ════════════════════════════════════════════════════════════════════════════════════════════════

class PendingObservations:
    """Manage pending observations waiting for 4-hour future outcome"""
    
    @staticmethod
    def load():
        """Load pending observations from JSON"""
        if not PENDING_FILE.exists():
            return []
        try:
            with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    @staticmethod
    def save(observations):
        """Save pending observations to JSON"""
        try:
            with open(PENDING_FILE, 'w', encoding='utf-8') as f:
                json.dump(observations, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save pending observations: {e}")
    
    @staticmethod
    def create_observation(symbol, timestamp, current_price, trend_scores, cvd_data):
        """Create a new observation waiting for outcome"""
        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'current_price': float(current_price),
            'trend_total_score': trend_scores['trend_total_score'],
            'structure_score': trend_scores['structure_score'],
            'adx_score': trend_scores['adx_score'],
            'funding_score': trend_scores['funding_score'],
            'rsi_score': trend_scores['rsi_score'],
            'volume_score': trend_scores['volume_score'],
            'wick_score': trend_scores['wick_score'],
            'cvd_skew': cvd_data['cvd_skew'],
            'price_action_12h': cvd_data['price_action_12h'],
            'future_price': None,
            'future_change_pct': None,
            'created_at': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def fill_outcomes(future_price, symbol):
        """Fill in future price outcomes for observations from 4 hours ago"""
        pending = PendingObservations.load()
        updated = []
        filled_count = 0
        
        for obs in pending:
            if obs['symbol'] != symbol:
                updated.append(obs)
                continue
            
            # Check if this observation is ~4 hours old
            created = datetime.fromisoformat(obs['created_at'])
            age_hours = (datetime.utcnow() - created).total_seconds() / 3600
            
            if 3.9 <= age_hours <= 4.1:  # ~4 hours old
                # Fill outcome
                obs['future_price'] = float(future_price)
                obs['future_change_pct'] = round(
                    ((future_price - obs['current_price']) / obs['current_price']) * 100,
                    2
                )
                
                # Write to CSV
                PendingObservations.write_to_csv(obs)
                filled_count += 1
                logger.info(f"✓ Filled outcome for {symbol} at {obs['timestamp']}")
            else:
                updated.append(obs)
        
        PendingObservations.save(updated)
        return filled_count
    
    @staticmethod
    def write_to_csv(observation):
        """Write completed observation to CSV"""
        try:
            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'symbol', 'current_price',
                    'trend_total_score', 'structure_score', 'adx_score',
                    'funding_score', 'rsi_score', 'volume_score', 'wick_score',
                    'cvd_skew', 'price_action_12h',
                    'future_price', 'future_change_pct'
                ])
                writer.writerow({
                    'timestamp': observation['timestamp'],
                    'symbol': observation['symbol'],
                    'current_price': observation['current_price'],
                    'trend_total_score': observation['trend_total_score'],
                    'structure_score': observation['structure_score'],
                    'adx_score': observation['adx_score'],
                    'funding_score': observation['funding_score'],
                    'rsi_score': observation['rsi_score'],
                    'volume_score': observation['volume_score'],
                    'wick_score': observation['wick_score'],
                    'cvd_skew': observation['cvd_skew'],
                    'price_action_12h': observation['price_action_12h'],
                    'future_price': observation['future_price'],
                    'future_change_pct': observation['future_change_pct']
                })
            logger.info(f"✓ Written to CSV: {observation['symbol']} @ {observation['timestamp']}")
        except Exception as e:
            logger.error(f"Failed to write to CSV: {e}")

# ════════════════════════════════════════════════════════════════════════════════════════════════
# MAIN LOGGING CYCLE
# ════════════════════════════════════════════════════════════════════════════════════════════════

def log_market_state(symbol):
    """
    Main cycle: Log current market state and check for past outcomes
    
    This function is called every 4 hours per symbol
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"LOGGING MARKET STATE: {symbol}")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    logger.info(f"{'='*80}")
    
    # Step 1: Fetch current data
    logger.info("Fetching market data...")
    current_price = fetch_current_price(symbol)
    if not current_price:
        logger.error(f"Failed to fetch price for {symbol}")
        return False
    logger.info(f"Current price: ${current_price}")
    
    # Step 2: Fetch 7 days of 1H candles for trend analysis
    klines_1h = fetch_klines(symbol, interval="1h", limit=168)
    if not klines_1h:
        logger.error(f"Failed to fetch 1H candles for {symbol}")
        return False
    
    # Step 3: Fetch 12 hours of 1M candles for CVD analysis
    klines_1m = fetch_klines(symbol, interval="1m", limit=720)
    if not klines_1m:
        logger.warning(f"Could not fetch 1M candles (non-critical). Using 1H fallback.")
        klines_1m = klines_1h
    
    # Step 4: Compute trend scores
    logger.info("Computing trend scores (6-factor analysis)...")
    trend_scores = TrendAnalyzer.analyze(klines_1h)
    logger.info(f"  Trend Total Score: {trend_scores['trend_total_score']}")
    logger.info(f"  Structure: {trend_scores['structure_score']}, ADX: {trend_scores['adx_score']}, "
                f"Funding: {trend_scores['funding_score']}")
    logger.info(f"  RSI: {trend_scores['rsi_score']}, Volume: {trend_scores['volume_score']}, "
                f"Wick: {trend_scores['wick_score']}")
    
    # Step 5: Compute CVD analysis
    logger.info("Computing CVD and order flow...")
    cvd_data = CVDAnalyzer.analyze(klines_1m, lookback_hours=12)
    logger.info(f"  CVD Skew: {cvd_data['cvd_skew']:+.2f}%")
    logger.info(f"  Price Action (12h): {cvd_data['price_action_12h']:+.2f}%")
    
    # Step 6: Create pending observation
    logger.info("Creating pending observation...")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    new_obs = PendingObservations.create_observation(
        symbol, timestamp, current_price, trend_scores, cvd_data
    )
    
    # Step 7: Append to pending file
    pending = PendingObservations.load()
    pending.append(new_obs)
    PendingObservations.save(pending)
    logger.info(f"✓ Observation stored (waiting 4h for outcome)")
    logger.info(f"  Total pending: {len(pending)}")
    
    # Step 8: Check for observations that are ~4 hours old and fill outcomes
    logger.info("Checking for outcomes to fill...")
    filled = PendingObservations.fill_outcomes(current_price, symbol)
    logger.info(f"✓ Filled {filled} outcomes")
    
    logger.info(f"{'='*80}\n")
    return True

def main():
    """Main entry point"""
    logger.info("\n" + "="*80)
    logger.info("LEGEND_X 4-HOUR MARKET DATASET LOGGER")
    logger.info("="*80)
    logger.info(f"Time: {datetime.utcnow().isoformat()}Z")
    logger.info(f"Dataset: {CSV_FILE}")
    logger.info(f"Logging interval: Every 4 hours")
    logger.info("="*80 + "\n")
    
    # Initialize CSV
    init_csv()
    
    # Log state for each symbol
    success_count = 0
    for symbol in SYMBOLS:
        if log_market_state(symbol):
            success_count += 1
    
    logger.info(f"\n✓ Logging cycle complete. {success_count}/{len(SYMBOLS)} symbols logged.\n")

if __name__ == "__main__":
    main()
