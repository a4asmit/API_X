"""
telegram_bot_render.py
======================
LEGEND_X Telegram Bot - Production Ready for Render Deployment

Key Features:
- Webhook mode (required for Render free tier)
- Proper error handling and logging
- CSV dataset logging every 4 hours
- All 11 market intelligence commands
- No blocking operations
- Clean startup/shutdown

Deployment on Render:
1. Push code to GitHub
2. Create new Web Service on Render
3. Build command: pip install -r requirements.txt
4. Start command: python telegram_bot_render.py
5. Set environment variables:
   - TELEGRAM_BOT_TOKEN=your_token
   - WEBHOOK_URL=https://your-app-name.onrender.com
6. Service will auto-restart every 24h (free tier limitation)

Environment Variables (.env):
    TELEGRAM_BOT_TOKEN=1234567890:ABCDefgh...
    WEBHOOK_URL=https://your-app-name.onrender.com
"""

import csv
import json
import os
import sys
import random
import logging
import urllib.request
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ════════════════════════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES
# ════════════════════════════════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 5000))

# Validate required env vars
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
    sys.exit(1)

if not WEBHOOK_URL:
    logger.error("WEBHOOK_URL not set in environment variables")
    logger.info("Example: https://your-app-name.onrender.com")
    sys.exit(1)

# Import Telegram library
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
    logger.info("✓ python-telegram-bot library loaded")
except ImportError:
    logger.error("python-telegram-bot not installed!")
    logger.error("Run: pip install python-telegram-bot")
    TELEGRAM_AVAILABLE = False
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════════════════════════════════
# LEGEND_X BOT CLASS
# ════════════════════════════════════════════════════════════════════════════════════════════════

class LegendXBot:
    """Core Legend_X Market Intelligence Bot"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.news_dir = self.data_dir / "news"
        self.dataset_dir = self.data_dir / "dataset"
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # ════════════════════════════════════════════════════════════════════════════════════════════
    # NEWS COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def load_news(self):
        """Load latest news from data/news/news_latest.json"""
        news_file = self.news_dir / "news_latest.json"
        if not news_file.exists():
            return None
        try:
            with open(news_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load news: {e}")
            return None
    
    def cmd_start(self):
        """Handle /start command"""
        message = """
╔════════════════════════════════════╗
║       LEGEND_X BOT MENU            ║
╚════════════════════════════════════╝

<b>Available Commands:</b>

/start - Show this menu
/news &lt;count&gt; - Latest crypto news (e.g. /news 5)
/feargreed - Market Fear &amp; Greed Index
/gainers - Top 10 gaining coins (24H)
/losers - Top 10 losing coins (24H)
/fgainers - Filtered gainers (real volume only)
/volume - Top 10 by trading volume (24H)
/trend &lt;symbol&gt; - 6-Factor TA Trend Detector (e.g. /trend BTC)
/liquidation &lt;symbol&gt; - Leverage trap detector
/map &lt;symbol&gt; - Liquidity heatmap
/flow &lt;symbol&gt; - CVD order flow analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Status:</b> [✓ OPERATIONAL]
<b>Mode:</b> Webhook (Render)
<b>Dataset:</b> Logging every 4 hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return message

    def cmd_news(self, count=5):
        """Handle /news command"""
        news_data = self.load_news()
        if not news_data:
            return "[ERROR] No news data found. Make sure <code>data/news/news_latest.json</code> exists."
        
        # Handle different JSON structures
        if isinstance(news_data, list):
            articles = news_data
        elif isinstance(news_data, dict):
            articles = news_data.get('news', news_data.get('articles', 
                      news_data.get('results', news_data.get('data', []))))
        else:
            return "[ERROR] Invalid news data format."

        if not articles:
            return "[ERROR] No articles found."

        count = min(count, len(articles), 20)
        random.shuffle(articles)
        
        message = f"[NEWS] <b>LATEST CRYPTO NEWS</b> <i>({count} of {len(articles)})</i>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for idx, article in enumerate(articles[:count], 1):
            title = article.get('title', article.get('headline', 'No Title'))
            message += f"\n<b>{idx}.</b> {title}\n"
                
        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return message

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # MARKET DATA COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def cmd_feargreed(self):
        """Fetch current Fear & Greed Index"""
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            fng_data = data['data'][0]
            value = int(fng_data['value'])
            classification = fng_data['value_classification'].capitalize()
            
            if value <= 25: 
                indicator = "[EXTREME FEAR]"
            elif value <= 45: 
                indicator = "[FEAR]"
            elif value <= 55: 
                indicator = "[NEUTRAL]"
            elif value <= 75: 
                indicator = "[GREED]"
            else: 
                indicator = "[EXTREME GREED]"
            
            message = f"""
[INDEX] <b>CRYPTO FEAR &amp; GREED INDEX</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{indicator} <b>Score: {value} / 100</b>
Classification: <b>{classification}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Scale:</b>
0-24   → Extreme Fear
25-49  → Fear
50     → Neutral
51-74  → Greed
75-100 → Extreme Greed
"""
            return message
        except Exception as e:
            logger.error(f"Fear & Greed fetch error: {e}")
            return "[ERROR] Failed to fetch Fear & Greed Index."

    def cmd_gainers(self):
        """Top 10 gaining coins"""
        return self._fetch_top_coins("gainers")

    def cmd_losers(self):
        """Top 10 losing coins"""
        return self._fetch_top_coins("losers")

    def _fetch_top_coins(self, coin_type):
        """Fetch top coins by 24H change"""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            # Filter USDT pairs
            usdt_pairs = [t for t in data if t['symbol'].endswith('USDT')]
            
            # Exclude leverage/stablecoin tokens
            exclude = ['UPUSDT', 'DOWNUSDT', 'BULLUSDT', 'BEARUSDT', 
                      'BUSDUSDT', 'USDCUSDT', 'TUSDUSDT', 'DAIUSDT', 'USDPUSDT']
            clean_pairs = [t for t in usdt_pairs if t['symbol'] not in exclude]
            
            # Sort by 24H change
            sorted_pairs = sorted(clean_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
            
            if coin_type == "gainers":
                top_coins = sorted_pairs[:10]
                title = "TOP 10 GAINERS"
                indicator = "[UP]"
            else:
                top_coins = sorted_pairs[-10:][::-1]
                title = "TOP 10 LOSERS"
                indicator = "[DOWN]"
            
            message = f"[MARKET] <b>{title} (24H)</b>\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for idx, coin in enumerate(top_coins, 1):
                symbol = coin['symbol'].replace('USDT', '')
                price = float(coin['lastPrice'])
                change = float(coin['priceChangePercent'])
                volume = float(coin['quoteVolume'])
                
                price_str = self._format_price(price)
                vol_str = self._format_volume(volume)
                change_str = f"{change:+.2f}%"
                
                message += f"\n<b>{idx}.</b> {symbol}\n"
                message += f"   {indicator} {price_str} | {change_str} | Vol: {vol_str}\n"
            
            message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            return message
        except Exception as e:
            logger.error(f"Gainers/losers fetch error: {e}")
            return "[ERROR] Failed to fetch market data."

    def cmd_volume(self):
        """Top 10 coins by volume"""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            usdt_pairs = [t for t in data if t['symbol'].endswith('USDT')]
            exclude = ['UPUSDT', 'DOWNUSDT', 'BULLUSDT', 'BEARUSDT', 
                      'BUSDUSDT', 'USDCUSDT', 'TUSDUSDT', 'DAIUSDT', 'USDPUSDT']
            clean_pairs = [t for t in usdt_pairs if t['symbol'] not in exclude]
            
            sorted_pairs = sorted(clean_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            top_coins = sorted_pairs[:10]
            
            message = f"[MARKET] <b>TOP 10 VOLUME (24H)</b>\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for idx, coin in enumerate(top_coins, 1):
                symbol = coin['symbol'].replace('USDT', '')
                price = float(coin['lastPrice'])
                volume = float(coin['quoteVolume'])
                
                price_str = self._format_price(price)
                vol_str = self._format_volume(volume)
                
                message += f"\n<b>{idx}.</b> {symbol}\n"
                message += f"   {price_str} | Vol: {vol_str}\n"
            
            message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            return message
        except Exception as e:
            logger.error(f"Volume fetch error: {e}")
            return "[ERROR] Failed to fetch volume data."

    def cmd_fgainers(self):
        """Filtered gainers (top 250 MCap, $1M+ vol)"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=false"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            # Filter: $1M MCap + $100K volume
            filtered = []
            for coin in data:
                mcap = coin.get('market_cap', 0) or 0
                vol = coin.get('total_volume', 0) or 0
                if mcap > 1_000_000 and vol > 100_000:
                    filtered.append(coin)
            
            # Sort by 24H gain
            filtered.sort(key=lambda x: x.get('price_change_percentage_24h') or 0, reverse=True)
            top_coins = filtered[:10]
            
            if not top_coins:
                return "[ERROR] No filtered gainers found."

            message = f"[MARKET] <b>TOP 10 FILTERED GAINERS</b>\n"
            message += "<i>Filter: Top 250 MCap | Vol &gt; $100K</i>\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for idx, coin in enumerate(top_coins, 1):
                symbol = coin.get('symbol', 'N/A').upper()
                name = coin.get('name', 'N/A')
                price = coin.get('current_price', 0) or 0
                change = coin.get('price_change_percentage_24h', 0) or 0
                
                price_str = self._format_price(price)
                change_str = f"{change:+.2f}%"
                
                message += f"\n<b>{idx}.</b> {name} ({symbol})\n"
                message += f"   {price_str} | {change_str}\n"
            
            message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            return message
        except Exception as e:
            logger.error(f"Filtered gainers error: {e}")
            return "[ERROR] Failed to fetch filtered gainers."

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # TECHNICAL ANALYSIS COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def cmd_trend(self, symbol):
        """6-Factor TA Trend Detector"""
        symbol = symbol.upper().replace("/", "").replace("USDT", "")
        pair = symbol + "USDT"
        
        try:
            # Fetch 4H candles
            url = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval=4h&limit=100"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                klines = json.loads(response.read().decode())
            
            if not klines or len(klines) < 50:
                raise ValueError("Insufficient data")
            
            # Calculate scores
            current_price = float(klines[-1][4])
            structure_score = self._calc_structure(klines) or 0
            adx_score, _ = self._calc_adx(klines) or (0, 0)
            rsi_score, rsi_val = self._calc_rsi(klines) or (0, 0)
            volume_score = self._calc_volume(klines) or 0
            wick_score = self._calc_wick(klines[-1]) or 0
            
            # Funding rate
            funding_score = 0
            try:
                fund_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={pair}"
                freq = urllib.request.Request(fund_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(freq, timeout=5) as response:
                    fund_data = json.loads(response.read().decode())
                funding_val = float(fund_data.get('lastFundingRate', 0))
                if funding_val > 0.05: 
                    funding_score = -2
                elif funding_val < -0.05: 
                    funding_score = 2
            except:
                funding_val = 0
            
            # Total score
            total_score = (structure_score * 2) + (adx_score * 2) + (funding_score * 2) + volume_score + rsi_score + wick_score
            
            if total_score >= 7: 
                verdict = "[STRONG BULLISH]"
            elif total_score >= 2: 
                verdict = "[BULLISH]"
            elif total_score <= -7: 
                verdict = "[STRONG BEARISH]"
            elif total_score <= -2: 
                verdict = "[BEARISH]"
            else: 
                verdict = "[NEUTRAL]"
            
            price_str = self._format_price(current_price)
            
            message = f"""
[TREND] <b>{symbol} COMPOSITE ANALYSIS</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Price: {price_str}
Verdict: <b>{verdict}</b> (Score: {total_score}/9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Analysis:</b>
1. Structure (x2): {structure_score*2:+d}
2. ADX (x2): {adx_score*2:+d}
3. Funding (x2): {funding_score*2:+d}
4. RSI (x1): {rsi_score:+d} (Value: {rsi_val:.1f})
5. Volume (x1): {volume_score:+d}
6. Wick (x1): {wick_score:+d}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            return message
        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return f"[ERROR] Failed to analyze {symbol}."

    def cmd_liquidation(self, symbol="BTC"):
        """Leverage trap detector"""
        symbol = symbol.upper().replace("/", "").replace("USDT", "")
        pair = symbol + "USDT"
        
        try:
            # Fetch OI
            oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={pair}"
            req = urllib.request.Request(oi_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                oi_data = json.loads(response.read().decode())
            open_interest = float(oi_data['openInterest'])
            
            # Fetch price
            price_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={pair}"
            req = urllib.request.Request(price_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                price_data = json.loads(response.read().decode())
            current_price = float(price_data['price'])
            
            oi_usd = open_interest * current_price
            
            # Fetch L/S ratio
            ls_url = f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={pair}&period=5m&limit=1"
            req = urllib.request.Request(ls_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                ls_data = json.loads(response.read().decode())
            
            long_pct = float(ls_data[0]['longAccount']) * 100
            short_pct = float(ls_data[0]['shortAccount']) * 100
            
            # Funding rate
            try:
                fund_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={pair}"
                req = urllib.request.Request(fund_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    fund_data = json.loads(response.read().decode())
                funding_rate = float(fund_data.get('lastFundingRate', 0))
            except:
                funding_rate = 0.0
            
            oi_str = self._format_volume(oi_usd)
            
            # Determine trap
            if long_pct > 60 and funding_rate > 0.01:
                trap = "[LONG SQUEEZE RISK]"
            elif short_pct > 60 and funding_rate < -0.01:
                trap = "[SHORT SQUEEZE RISK]"
            else:
                trap = "[BALANCED]"
            
            message = f"""
[LIQUIDATION] <b>{symbol} LEVERAGE TRAP</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Open Interest: {oi_str}
Price: ${current_price:,.2f}

Longs: {long_pct:.1f}%
Shorts: {short_pct:.1f}%
Funding: {funding_rate*100:+.3f}%

Verdict: {trap}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            return message
        except Exception as e:
            logger.error(f"Liquidation error: {e}")
            return f"[ERROR] Failed to fetch {symbol} data."

    def cmd_map(self, symbol="BTC"):
        """Liquidity heatmap"""
        symbol = symbol.upper().replace("/", "").replace("USDT", "")
        pair = symbol + "USDT"
        
        try:
            # Fetch order book
            depth_url = f"https://fapi.binance.com/fapi/v1/depth?symbol={pair}&limit=500"
            req = urllib.request.Request(depth_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                depth_data = json.loads(response.read().decode())
            
            bids = depth_data.get('bids', [])
            asks = depth_data.get('asks', [])
            
            if not bids or not asks:
                return "[ERROR] Insufficient order book data."
            
            current_price = float(bids[0][0])
            
            # Calculate range
            min_price = float(bids[-1][0])
            max_price = float(asks[-1][0])
            price_range = max_price - min_price
            
            # Adaptive step
            step = max(1, int(price_range / 15))
            
            # Create buckets
            buckets = {}
            start = int(min_price / step) * step
            end = int(max_price / step) * step + step
            
            for p in range(start, end, step):
                buckets[p] = {'bid': 0, 'ask': 0}
            
            # Populate
            for price, qty in bids:
                p = int(float(price) / step) * step
                if p in buckets:
                    buckets[p]['bid'] += float(price) * float(qty)
            
            for price, qty in asks:
                p = int(float(price) / step) * step
                if p in buckets:
                    buckets[p]['ask'] += float(price) * float(qty)
            
            # Format output
            lines = []
            sorted_keys = sorted(buckets.keys(), reverse=True)
            
            for p in sorted_keys:
                bid_vol = buckets[p]['bid']
                ask_vol = buckets[p]['ask']
                
                if bid_vol > 100000 or ask_vol > 100000:
                    marker = " &lt;&lt;&lt; CURRENT" if abs(p - current_price) < step else ""
                    lines.append(f"${p:,.0f}: Bid: {self._format_volume(bid_vol)} | Ask: {self._format_volume(ask_vol)}{marker}")
            
            message = f"""
[MAP] <b>{symbol} LIQUIDITY LEVELS</b>

{"".join(lines)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            return message
        except Exception as e:
            logger.error(f"Map error: {e}")
            return f"[ERROR] Failed to generate {symbol} map."

    def cmd_flow(self, symbol="BTC"):
        """CVD order flow analysis"""
        symbol = symbol.upper().replace("/", "").replace("USDT", "")
        pair = symbol + "USDT"
        
        try:
            # Fetch 12H of 1M candles
            url = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval=1m&limit=720"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                klines = json.loads(response.read().decode())
            
            if not klines or len(klines) < 100:
                return f"[ERROR] Insufficient data for {symbol}."
            
            # Calculate price action
            open_price = float(klines[0][1])
            close_price = float(klines[-1][4])
            price_change = ((close_price - open_price) / open_price) * 100
            
            # Calculate CVD
            taker_buy = sum(float(k[10]) for k in klines)
            total_vol = sum(float(k[7]) for k in klines)
            taker_sell = total_vol - taker_buy
            cvd_delta = taker_buy - taker_sell
            cvd_skew = (cvd_delta / total_vol * 100) if total_vol > 0 else 0
            
            # Determine verdict
            price_up = close_price > open_price
            cvd_up = cvd_delta > 0
            
            if abs(cvd_skew) < 2:
                verdict = "[NEUTRAL]"
            elif price_up and cvd_up:
                verdict = "[ACCUMULATION]"
            elif not price_up and not cvd_up:
                verdict = "[DISTRIBUTION]"
            elif price_up and not cvd_up:
                verdict = "[BULL TRAP]"
            else:
                verdict = "[BEAR TRAP]"
            
            buy_pct = (taker_buy / total_vol * 100) if total_vol > 0 else 0
            
            message = f"""
[FLOW] <b>{symbol} CVD ANALYSIS (12H)</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Price Change: {price_change:+.2f}%

Taker Buys: {self._format_volume(taker_buy)} ({buy_pct:.1f}%)
Taker Sells: {self._format_volume(taker_sell)} ({100-buy_pct:.1f}%)
CVD Delta: {self._format_volume(abs(cvd_delta))}

Verdict: {verdict}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            return message
        except Exception as e:
            logger.error(f"Flow error: {e}")
            return f"[ERROR] Failed to fetch flow data for {symbol}."

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # TECHNICAL ANALYSIS MATH
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def _calc_structure(self, klines):
        """Market structure: HH/HL or LL/LH"""
        try:
            highs = [float(k[2]) for k in klines[-50:]]
            lows = [float(k[3]) for k in klines[-50:]]
            
            if len(highs) < 3:
                return 0
            
            recent_high_peak = highs[-1] > highs[-2] and highs[-1] > highs[-3]
            recent_low_peak = lows[-1] > lows[-2] and lows[-1] > lows[-3]
            
            if recent_high_peak and recent_low_peak:
                return 1  # Bullish
            
            recent_high_trough = highs[-1] < highs[-2] and highs[-1] < highs[-3]
            recent_low_trough = lows[-1] < lows[-2] and lows[-1] < lows[-3]
            
            if recent_high_trough and recent_low_trough:
                return -1  # Bearish
            
            return 0
        except:
            return 0
    
    def _calc_adx(self, klines, period=14):
        """ADX trend strength"""
        try:
            if len(klines) < period:
                return 0, 0
            
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            closes = [float(k[4]) for k in klines]
            
            # Simplified: if recent move > 1.5*ATR, trend is strong
            atr = sum([highs[i] - lows[i] for i in range(-period, 0)]) / period
            recent_move = abs(closes[-1] - closes[-period])
            
            if recent_move > atr * 1.5:
                return 1 if closes[-1] > closes[-period] else -1, atr
            
            return 0, atr
        except:
            return 0, 0
    
    def _calc_rsi(self, klines, period=14):
        """RSI momentum"""
        try:
            closes = [float(k[4]) for k in klines]
            
            if len(closes) < period:
                return 0, 50
            
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            avg_gain = sum([d for d in deltas[-period:] if d > 0]) / period
            avg_loss = sum([-d for d in deltas[-period:] if d < 0]) / period
            
            if avg_loss == 0:
                rsi = 100 if avg_gain > 0 else 50
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            if rsi > 70:
                return -1, rsi
            elif rsi < 30:
                return -1, rsi
            elif rsi > 60:
                return 1, rsi
            
            return 0, rsi
        except:
            return 0, 50
    
    def _calc_volume(self, klines):
        """Volume vs average"""
        try:
            vols = [float(k[7]) for k in klines[-30:]]
            
            if len(vols) < 20:
                return 0
            
            current_vol = vols[-1]
            avg_vol = sum(vols[-21:-1]) / 20
            
            if current_vol > avg_vol * 1.5:
                return 1
            elif current_vol < avg_vol * 0.5:
                return -1
            
            return 0
        except:
            return 0
    
    def _calc_wick(self, kline):
        """Wick rejection"""
        try:
            o, h, l, c = float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4])
            body = abs(c - o) or 0.0001
            
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l
            
            if upper_wick > body * 2:
                return -1
            elif lower_wick > body * 2:
                return 1
            
            return 0
        except:
            return 0
    
    # ════════════════════════════════════════════════════════════════════════════════════════════
    # DATASET LOGGING
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def collect_snapshot(self, symbol="BTC"):
        """Collect market state for dataset"""
        try:
            symbol = symbol.upper().replace("/", "").replace("USDT", "")
            pair = symbol + "USDT"
            
            # Fetch 4H klines
            url = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval=4h&limit=100"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                klines = json.loads(response.read().decode())
            
            if not klines or len(klines) < 50:
                return None
            
            current_price = float(klines[-1][4])
            
            # Calculate all scores
            trend_scores = {
                'structure': self._calc_structure(klines) or 0,
                'adx': self._calc_adx(klines)[0] or 0,
                'rsi': self._calc_rsi(klines)[0] or 0,
                'volume': self._calc_volume(klines) or 0,
                'wick': self._calc_wick(klines[-1]) or 0,
            }
            
            # Funding
            funding_score = 0
            try:
                fund_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={pair}"
                freq = urllib.request.Request(fund_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(freq, timeout=5) as response:
                    fund_data = json.loads(response.read().decode())
                funding_val = float(fund_data.get('lastFundingRate', 0))
                if funding_val > 0.05:
                    funding_score = -2
                elif funding_val < -0.05:
                    funding_score = 2
            except:
                funding_val = 0
            
            trend_scores['funding'] = funding_score
            
            # CVD
            cvd_skew = 0.0
            price_action_12h = 0.0
            try:
                flow_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval=1m&limit=720"
                req = urllib.request.Request(flow_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    flow_klines = json.loads(response.read().decode())
                
                if flow_klines:
                    taker_buy = sum(float(k[10]) for k in flow_klines)
                    total_vol = sum(float(k[7]) for k in flow_klines)
                    taker_sell = total_vol - taker_buy
                    cvd_delta = taker_buy - taker_sell
                    cvd_skew = (cvd_delta / total_vol * 100) if total_vol > 0 else 0
                    
                    open_price = float(flow_klines[0][1])
                    close_price = float(flow_klines[-1][4])
                    price_action_12h = ((close_price - open_price) / open_price) * 100
            except Exception as e:
                logger.debug(f"CVD calculation error: {e}")
            
            # Total trend score
            trend_total = (
                trend_scores['structure'] * 2 +
                trend_scores['adx'] * 2 +
                trend_scores['funding'] * 2 +
                trend_scores['rsi'] +
                trend_scores['volume'] +
                trend_scores['wick']
            )
            
            return {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                'symbol': symbol,
                'current_price': round(current_price, 8),
                'trend_total_score': int(trend_total),
                'structure_score': int(trend_scores['structure']),
                'adx_score': int(trend_scores['adx']),
                'funding_score': int(trend_scores['funding']),
                'rsi_score': int(trend_scores['rsi']),
                'volume_score': int(trend_scores['volume']),
                'wick_score': int(trend_scores['wick']),
                'cvd_skew': round(cvd_skew, 2),
                'price_action_12h': round(price_action_12h, 2),
                'future_price': None,
                'future_change_pct': None
            }
        except Exception as e:
            logger.error(f"Snapshot error: {e}")
            return None
    
    def log_to_csv(self, data):
        """Log snapshot to CSV"""
        try:
            csv_file = self.dataset_dir / "market_state_4h.csv"
            
            # Initialize CSV if needed
            if not csv_file.exists():
                headers = [
                    'timestamp', 'symbol', 'current_price',
                    'trend_total_score', 'structure_score', 'adx_score',
                    'funding_score', 'rsi_score', 'volume_score', 'wick_score',
                    'cvd_skew', 'price_action_12h',
                    'future_price', 'future_change_pct'
                ]
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
            
            # Append data
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                writer.writerow(data)
            
            logger.info(f"✓ Logged {data['symbol']} snapshot at {data['timestamp']}")
            return True
        except Exception as e:
            logger.error(f"CSV logging error: {e}")
            return False
    
    # ════════════════════════════════════════════════════════════════════════════════════════════
    # UTILITY FUNCTIONS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _format_price(price):
        """Format price with appropriate decimals"""
        if price < 0.01:
            return f"${price:.6f}"
        elif price < 1:
            return f"${price:.4f}"
        else:
            return f"${price:,.2f}"
    
    @staticmethod
    def _format_volume(volume):
        """Format volume with K/M/B suffixes"""
        if volume > 1_000_000_000:
            return f"${volume / 1_000_000_000:.2f}B"
        elif volume > 1_000_000:
            return f"${volume / 1_000_000:.2f}M"
        elif volume > 1_000:
            return f"${volume / 1_000:.0f}K"
        else:
            return f"${volume:,.0f}"

# ════════════════════════════════════════════════════════════════════════════════════════════════
# TELEGRAM COMMAND HANDLERS
# ════════════════════════════════════════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_start()
    await update.message.reply_text(message, parse_mode='HTML')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    count = 5
    if context.args:
        try:
            count = int(context.args[0])
            if count < 1: 
                count = 1
            elif count > 20: 
                count = 20
        except ValueError:
            await update.message.reply_text("[WARNING] Invalid count. Usage: /news 5", parse_mode='HTML')
            return
    message = bot.cmd_news(count=count)
    await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)

async def feargreed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_feargreed()
    await update.message.reply_text(message, parse_mode='HTML')

async def gainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_gainers()
    await update.message.reply_text(message, parse_mode='HTML')

async def losers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_losers()
    await update.message.reply_text(message, parse_mode='HTML')

async def volume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_volume()
    await update.message.reply_text(message, parse_mode='HTML')

async def fgainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = LegendXBot()
    message = bot.cmd_fgainers()
    await update.message.reply_text(message, parse_mode='HTML')

async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("[WARNING] Usage: /trend BTC", parse_mode='HTML')
        return
    bot = LegendXBot()
    message = bot.cmd_trend(context.args[0])
    await update.message.reply_text(message, parse_mode='HTML')

async def liquidation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else "BTC"
    bot = LegendXBot()
    message = bot.cmd_liquidation(symbol=symbol)
    await update.message.reply_text(message, parse_mode='HTML')

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else "BTC"
    bot = LegendXBot()
    message = bot.cmd_map(symbol=symbol)
    await update.message.reply_text(message, parse_mode='HTML')

async def flow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else "BTC"
    bot = LegendXBot()
    message = bot.cmd_flow(symbol=symbol)
    await update.message.reply_text(message, parse_mode='HTML')

# ════════════════════════════════════════════════════════════════════════════════════════════════
# BACKGROUND JOBS
# ════════════════════════════════════════════════════════════════════════════════════════════════

async def log_market_data_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job to log market state every 4 hours"""
    try:
        logger.info("📊 Running market data logging job...")
        bot = LegendXBot()
        
        for symbol in ["BTC", "ETH", "SOL", "ADA"]:
            snapshot = bot.collect_snapshot(symbol=symbol)
            if snapshot:
                bot.log_to_csv(snapshot)
            else:
                logger.warning(f"Failed to collect snapshot for {symbol}")
    except Exception as e:
        logger.error(f"Logging job error: {e}")

# ════════════════════════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════════════════════

def main():
    """Start the bot in webhook mode for Render"""
    
    logger.info("\n" + "="*100)
    logger.info("LEGEND_X TELEGRAM BOT - RENDER DEPLOYMENT")
    logger.info("="*100)
    logger.info(f"Bot Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    logger.info(f"Port: {PORT}")
    logger.info("="*100 + "\n")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("feargreed", feargreed_command))
    application.add_handler(CommandHandler("gainers", gainers_command))
    application.add_handler(CommandHandler("losers", losers_command))
    application.add_handler(CommandHandler("volume", volume_command))
    application.add_handler(CommandHandler("fgainers", fgainers_command))
    application.add_handler(CommandHandler("trend", trend_command))
    application.add_handler(CommandHandler("liquidation", liquidation_command))
    application.add_handler(CommandHandler("map", map_command))
    application.add_handler(CommandHandler("flow", flow_command))
    
    # Add background job (every 4 hours)
    job_queue = application.job_queue
    job_queue.run_repeating(log_market_data_job, interval=14400, first=300)
    logger.info("✓ Market logging job scheduled (every 4 hours)")
    
    # Start webhook
    logger.info("Starting webhook mode...")
    try:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
        )
    except Exception as e:
        logger.error(f"Failed to start webhook: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n✓ Bot shutdown gracefully")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
