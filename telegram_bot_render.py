"""
telegram_bot_render.py
======================
LEGEND_X Telegram Bot - Production Ready for Render Deployment

Key Features:
- Polling mode (stable, reliable for Render)
- Anti-cloud-block API fetching (Browser headers + fapi1)
- CSV dataset logging every 4 hours
- All 11 market intelligence commands

Deployment on Render:
1. Push code to GitHub
2. Create new Web Service on Render
3. Build command: pip install -r requirements.txt
4. Start command: python telegram_bot_render.py
5. Set environment variables:
   - TELEGRAM_BOT_TOKEN=your_token
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

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
    sys.exit(1)

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
    logger.info("✓ python-telegram-bot library loaded")
except ImportError:
    logger.error("python-telegram-bot not installed!")
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
    # API HELPER (Anti-Block)
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def _fetch_api(self, url):
        """Helper to fetch API data with browser-like headers to bypass cloud blocks"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'application/json,application/text',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode('utf-8')
            if not data:
                raise ValueError("API returned empty response")
            return json.loads(data)

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # NEWS COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def load_news(self):
        news_file = self.news_dir / "news_latest.json"
        if not news_file.exists(): return None
        try:
            with open(news_file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return None
    
    def cmd_start(self):
        return """
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
"""

    def cmd_news(self, count=5):
        news_data = self.load_news()
        if not news_data: return "[ERROR] No news data found."
        if isinstance(news_data, list): articles = news_data
        elif isinstance(news_data, dict): articles = news_data.get('news', news_data.get('articles', []))
        else: return "[ERROR] Invalid news data format."
        if not articles: return "[ERROR] No articles found."

        count = min(count, len(articles), 20)
        random.shuffle(articles)
        message = f"[NEWS] <b>LATEST CRYPTO NEWS</b> <i>({count} of {len(articles)})</i>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for idx, article in enumerate(articles[:count], 1):
            title = article.get('title', article.get('headline', 'No Title'))
            message += f"\n<b>{idx}.</b> {title}\n"
        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return message

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # MARKET DATA COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def cmd_feargreed(self):
        try:
            data = self._fetch_api("https://api.alternative.me/fng/?limit=1")
            fng_data = data['data'][0]
            value = int(fng_data['value'])
            classification = fng_data['value_classification'].capitalize()
            if value <= 25: indicator = "[EXTREME FEAR]"
            elif value <= 45: indicator = "[FEAR]"
            elif value <= 55: indicator = "[NEUTRAL]"
            elif value <= 75: indicator = "[GREED]"
            else: indicator = "[EXTREME GREED]"
            return f"[INDEX] <b>CRYPTO FEAR &amp; GREED INDEX</b>\n\n{indicator} <b>Score: {value} / 100</b>\nClassification: <b>{classification}</b>"
        except Exception as e:
            return "[ERROR] Failed to fetch Fear & Greed Index."

    def cmd_gainers(self): return self._fetch_top_coins("gainers")
    def cmd_losers(self): return self._fetch_top_coins("losers")

    def _fetch_top_coins(self, coin_type):
        try:
            data = self._fetch_api("https://fapi1.binance.com/fapi/v1/ticker/24hr")
            usdt_pairs = [t for t in data if t['symbol'].endswith('USDT')]
            exclude = ['UPUSDT', 'DOWNUSDT', 'BULLUSDT', 'BEARUSDT', 'BUSDUSDT', 'USDCUSDT', 'TUSDUSDT', 'DAIUSDT', 'USDPUSDT']
            clean_pairs = [t for t in usdt_pairs if t['symbol'] not in exclude]
            sorted_pairs = sorted(clean_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
            if coin_type == "gainers":
                top_coins = sorted_pairs[:10]; title = "TOP 10 GAINERS"; indicator = "[UP]"
            else:
                top_coins = sorted_pairs[-10:][::-1]; title = "TOP 10 LOSERS"; indicator = "[DOWN]"
            message = f"[MARKET] <b>{title} (24H)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for idx, coin in enumerate(top_coins, 1):
                symbol = coin['symbol'].replace('USDT', '')
                price_str = self._format_price(float(coin['lastPrice']))
                vol_str = self._format_volume(float(coin['quoteVolume']))
                change_str = f"{float(coin['priceChangePercent']):+.2f}%"
                message += f"\n<b>{idx}.</b> {symbol}\n   {indicator} {price_str} | {change_str} | Vol: {vol_str}\n"
            return message + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        except Exception as e:
            return "[ERROR] Failed to fetch market data."

    def cmd_volume(self):
        try:
            data = self._fetch_api("https://fapi1.binance.com/fapi/v1/ticker/24hr")
            usdt_pairs = [t for t in data if t['symbol'].endswith('USDT')]
            exclude = ['UPUSDT', 'DOWNUSDT', 'BULLUSDT', 'BEARUSDT', 'BUSDUSDT', 'USDCUSDT', 'TUSDUSDT', 'DAIUSDT', 'USDPUSDT']
            clean_pairs = [t for t in usdt_pairs if t['symbol'] not in exclude]
            sorted_pairs = sorted(clean_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)[:10]
            message = f"[MARKET] <b>TOP 10 VOLUME (24H)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for idx, coin in enumerate(sorted_pairs, 1):
                symbol = coin['symbol'].replace('USDT', '')
                message += f"\n<b>{idx}.</b> {symbol}\n   {self._format_price(float(coin['lastPrice']))} | Vol: {self._format_volume(float(coin['quoteVolume']))}\n"
            return message + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        except Exception as e:
            return "[ERROR] Failed to fetch volume data."

    def cmd_fgainers(self):
        try:
            data = self._fetch_api("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=false")
            filtered = [c for c in data if (c.get('market_cap', 0) or 0) > 1_000_000 and (c.get('total_volume', 0) or 0) > 100_000]
            filtered.sort(key=lambda x: x.get('price_change_percentage_24h') or 0, reverse=True)
            top_coins = filtered[:10]
            if not top_coins: return "[ERROR] No filtered gainers found."
            message = f"[MARKET] <b>TOP 10 FILTERED GAINERS</b>\n<i>Filter: Top 250 MCap | Vol &gt; $100K</i>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for idx, coin in enumerate(top_coins, 1):
                symbol = coin.get('symbol', 'N/A').upper(); name = coin.get('name', 'N/A')
                price = coin.get('current_price', 0) or 0; change = coin.get('price_change_percentage_24h', 0) or 0
                message += f"\n<b>{idx}.</b> {name} ({symbol})\n   {self._format_price(price)} | {change:+.2f}%\n"
            return message + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        except Exception as e:
            return "[ERROR] Failed to fetch filtered gainers."

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # TECHNICAL ANALYSIS COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def cmd_trend(self, symbol):
        symbol = symbol.upper().replace("/", "").replace("USDT", "")
        pair = symbol + "USDT"
        try:
            klines = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/klines?symbol={pair}&interval=4h&limit=100")
            if not klines or len(klines) < 50: raise ValueError("Insufficient data")
            current_price = float(klines[-1][4])
            structure_score = self._calc_structure(klines) or 0
            adx_score, _ = self._calc_adx(klines) or (0, 0)
            rsi_score, rsi_val = self._calc_rsi(klines) or (0, 0)
            volume_score = self._calc_volume(klines) or 0
            wick_score = self._calc_wick(klines[-1]) or 0
            funding_score = 0; funding_val = 0
            try:
                fund_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/premiumIndex?symbol={pair}")
                funding_val = float(fund_data.get('lastFundingRate', 0))
                if funding_val > 0.05: funding_score = -2
                elif funding_val < -0.05: funding_score = 2
            except: pass
            total_score = (structure_score * 2) + (adx_score * 2) + (funding_score * 2) + volume_score + rsi_score + wick_score
            if total_score >= 7: verdict = "[STRONG BULLISH]"
            elif total_score >= 2: verdict = "[BULLISH]"
            elif total_score <= -7: verdict = "[STRONG BEARISH]"
            elif total_score <= -2: verdict = "[BEARISH]"
            else: verdict = "[NEUTRAL]"
            return f"[TREND] <b>{symbol} COMPOSITE ANALYSIS</b>\n\nPrice: {self._format_price(current_price)}\nVerdict: <b>{verdict}</b> (Score: {total_score}/9)\n\n1. Structure (x2): {structure_score*2:+d}\n2. ADX (x2): {adx_score*2:+d}\n3. Funding (x2): {funding_score*2:+d}\n4. RSI (x1): {rsi_score:+d}\n5. Volume (x1): {volume_score:+d}\n6. Wick (x1): {wick_score:+d}"
        except Exception as e:
            return f"[ERROR] Failed to analyze {symbol}. Binance may be blocking this server."

    def cmd_liquidation(self, symbol="BTC"):
        symbol = symbol.upper().replace("/", "").replace("USDT", ""); pair = symbol + "USDT"
        try:
            oi_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/openInterest?symbol={pair}")
            price_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/ticker/price?symbol={pair}")
            ls_data = self._fetch_api(f"https://fapi1.binance.com/futures/data/topLongShortAccountRatio?symbol={pair}&period=5m&limit=1")
            open_interest = float(oi_data['openInterest']); current_price = float(price_data['price'])
            oi_usd = open_interest * current_price; long_pct = float(ls_data[0]['longAccount']) * 100; short_pct = float(ls_data[0]['shortAccount']) * 100
            funding_rate = 0.0
            try:
                fund_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/premiumIndex?symbol={pair}")
                funding_rate = float(fund_data.get('lastFundingRate', 0))
            except: pass
            if long_pct > 60 and funding_rate > 0.01: trap = "[LONG SQUEEZE RISK]"
            elif short_pct > 60 and funding_rate < -0.01: trap = "[SHORT SQUEEZE RISK]"
            else: trap = "[BALANCED]"
            return f"[LIQUIDATION] <b>{symbol} LEVERAGE TRAP</b>\n\nOpen Interest: {self._format_volume(oi_usd)}\nPrice: ${current_price:,.2f}\n\nLongs: {long_pct:.1f}%\nShorts: {short_pct:.1f}%\nFunding: {funding_rate*100:+.3f}%\n\nVerdict: {trap}"
        except Exception as e:
            return f"[ERROR] Failed to fetch {symbol} data. API block detected."

    def cmd_map(self, symbol="BTC"):
        symbol = symbol.upper().replace("/", "").replace("USDT", ""); pair = symbol + "USDT"
        try:
            depth_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/depth?symbol={pair}&limit=500")
            bids = depth_data.get('bids', []); asks = depth_data.get('asks', [])
            if not bids or not asks: return "[ERROR] Insufficient order book data."
            current_price = float(bids[0][0]); min_price = float(bids[-1][0]); max_price = float(asks[-1][0])
            price_range = max_price - min_price; step = max(1, int(price_range / 15))
            buckets = {}; start = int(min_price / step) * step; end = int(max_price / step) * step + step
            for p in range(start, end, step): buckets[p] = {'bid': 0, 'ask': 0}
            for price, qty in bids:
                p = int(float(price) / step) * step
                if p in buckets: buckets[p]['bid'] += float(price) * float(qty)
            for price, qty in asks:
                p = int(float(price) / step) * step
                if p in buckets: buckets[p]['ask'] += float(price) * float(qty)
            lines = []
            for p in sorted(buckets.keys(), reverse=True):
                bid_vol = buckets[p]['bid']; ask_vol = buckets[p]['ask']
                if bid_vol > 100000 or ask_vol > 100000:
                    marker = " &lt;&lt;&lt; CURRENT" if abs(p - current_price) < step else ""
                    lines.append(f"${p:,.0f}: Bid: {self._format_volume(bid_vol)} | Ask: {self._format_volume(ask_vol)}{marker}")
            return f"[MAP] <b>{symbol} LIQUIDITY LEVELS</b>\n\n{''.join(lines)}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        except Exception as e:
            return f"[ERROR] Failed to generate {symbol} map. API block detected."

    def cmd_flow(self, symbol="BTC"):
        symbol = symbol.upper().replace("/", "").replace("USDT", ""); pair = symbol + "USDT"
        try:
            klines = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/klines?symbol={pair}&interval=1m&limit=720")
            if not klines or len(klines) < 100: return f"[ERROR] Insufficient data for {symbol}."
            open_price = float(klines[0][1]); close_price = float(klines[-1][4])
            price_change = ((close_price - open_price) / open_price) * 100
            taker_buy = sum(float(k[10]) for k in klines); total_vol = sum(float(k[7]) for k in klines)
            taker_sell = total_vol - taker_buy; cvd_delta = taker_buy - taker_sell
            cvd_skew = (cvd_delta / total_vol * 100) if total_vol > 0 else 0
            price_up = close_price > open_price; cvd_up = cvd_delta > 0
            if abs(cvd_skew) < 2: verdict = "[NEUTRAL]"
            elif price_up and cvd_up: verdict = "[ACCUMULATION]"
            elif not price_up and not cvd_up: verdict = "[DISTRIBUTION]"
            elif price_up and not cvd_up: verdict = "[BULL TRAP]"
            else: verdict = "[BEAR TRAP]"
            buy_pct = (taker_buy / total_vol * 100) if total_vol > 0 else 0
            return f"[FLOW] <b>{symbol} CVD ANALYSIS (12H)</b>\n\nPrice Change: {price_change:+.2f}%\n\nTaker Buys: {self._format_volume(taker_buy)} ({buy_pct:.1f}%)\nTaker Sells: {self._format_volume(taker_sell)} ({100-buy_pct:.1f}%)\nCVD Delta: {self._format_volume(abs(cvd_delta))}\n\nVerdict: {verdict}"
        except Exception as e:
            return f"[ERROR] Failed to fetch flow data for {symbol}. API block detected."

    # ════════════════════════════════════════════════════════════════════════════════════════════
    # TECHNICAL ANALYSIS MATH
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def _calc_structure(self, klines):
        try:
            highs = [float(k[2]) for k in klines[-50:]]; lows = [float(k[3]) for k in klines[-50:]]
            if len(highs) < 3: return 0
            recent_high_peak = highs[-1] > highs[-2] and highs[-1] > highs[-3]
            recent_low_peak = lows[-1] > lows[-2] and lows[-1] > lows[-3]
            if recent_high_peak and recent_low_peak: return 1
            recent_high_trough = highs[-1] < highs[-2] and highs[-1] < highs[-3]
            recent_low_trough = lows[-1] < lows[-2] and lows[-1] < lows[-3]
            if recent_high_trough and recent_low_trough: return -1
            return 0
        except: return 0
    
    def _calc_adx(self, klines, period=14):
        try:
            if len(klines) < period: return 0, 0
            highs = [float(k[2]) for k in klines]; lows = [float(k[3]) for k in klines]; closes = [float(k[4]) for k in klines]
            atr = sum([highs[i] - lows[i] for i in range(-period, 0)]) / period
            recent_move = abs(closes[-1] - closes[-period])
            if recent_move > atr * 1.5: return 1 if closes[-1] > closes[-period] else -1, atr
            return 0, atr
        except: return 0, 0
    
    def _calc_rsi(self, klines, period=14):
        try:
            closes = [float(k[4]) for k in klines]
            if len(closes) < period: return 0, 50
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            avg_gain = sum([d for d in deltas[-period:] if d > 0]) / period
            avg_loss = sum([-d for d in deltas[-period:] if d < 0]) / period
            if avg_loss == 0: rsi = 100 if avg_gain > 0 else 50
            else: rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
            if rsi > 70 or rsi < 30: return -1, rsi
            elif rsi > 60: return 1, rsi
            return 0, rsi
        except: return 0, 50
    
    def _calc_volume(self, klines):
        try:
            vols = [float(k[7]) for k in klines[-30:]]
            if len(vols) < 20: return 0
            if vols[-1] > (sum(vols[-21:-1]) / 20) * 1.5: return 1
            elif vols[-1] < (sum(vols[-21:-1]) / 20) * 0.5: return -1
            return 0
        except: return 0
    
    def _calc_wick(self, kline):
        try:
            o, h, l, c = float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4])
            body = abs(c - o) or 0.0001
            if (h - max(o, c)) > body * 2: return -1
            elif (min(o, c) - l) > body * 2: return 1
            return 0
        except: return 0
    
    # ════════════════════════════════════════════════════════════════════════════════════════════
    # DATASET LOGGING
    # ════════════════════════════════════════════════════════════════════════════════════════════
    
    def collect_snapshot(self, symbol="BTC"):
        try:
            symbol = symbol.upper().replace("/", "").replace("USDT", ""); pair = symbol + "USDT"
            klines = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/klines?symbol={pair}&interval=4h&limit=100")
            if not klines or len(klines) < 50: return None
            current_price = float(klines[-1][4])
            scores = {'structure': self._calc_structure(klines) or 0, 'adx': self._calc_adx(klines)[0] or 0, 'rsi': self._calc_rsi(klines)[0] or 0, 'volume': self._calc_volume(klines) or 0, 'wick': self._calc_wick(klines[-1]) or 0}
            funding_score = 0; funding_val = 0
            try:
                fund_data = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/premiumIndex?symbol={pair}")
                funding_val = float(fund_data.get('lastFundingRate', 0))
                if funding_val > 0.05: funding_score = -2
                elif funding_val < -0.05: funding_score = 2
            except: pass
            scores['funding'] = funding_score
            cvd_skew = 0.0; price_action_12h = 0.0
            try:
                flow_klines = self._fetch_api(f"https://fapi1.binance.com/fapi/v1/klines?symbol={pair}&interval=1m&limit=720")
                if flow_klines:
                    taker_buy = sum(float(k[10]) for k in flow_klines); total_vol = sum(float(k[7]) for k in flow_klines)
                    cvd_delta = taker_buy - (total_vol - taker_buy)
                    cvd_skew = (cvd_delta / total_vol * 100) if total_vol > 0 else 0
                    price_action_12h = ((float(flow_klines[-1][4]) - float(flow_klines[0][1])) / float(flow_klines[0][1])) * 100
            except: pass
            trend_total = (scores['structure']*2 + scores['adx']*2 + scores['funding']*2 + scores['rsi'] + scores['volume'] + scores['wick'])
            return {'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M'), 'symbol': symbol, 'current_price': round(current_price, 8), 'trend_total_score': int(trend_total), 'structure_score': int(scores['structure']), 'adx_score': int(scores['adx']), 'funding_score': int(scores['funding']), 'rsi_score': int(scores['rsi']), 'volume_score': int(scores['volume']), 'wick_score': int(scores['wick']), 'cvd_skew': round(cvd_skew, 2), 'price_action_12h': round(price_action_12h, 2), 'future_price': None, 'future_change_pct': None}
        except Exception as e:
            logger.error(f"Snapshot error: {e}")
            return None
    
    def log_to_csv(self, data):
        try:
            csv_file = self.dataset_dir / "market_state_4h.csv"
            if not csv_file.exists():
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    csv.DictWriter(f, fieldnames=data.keys()).writeheader()
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                csv.DictWriter(f, fieldnames=data.keys()).writerow(data)
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
        if price < 0.01: return f"${price:.6f}"
        elif price < 1: return f"${price:.4f}"
        else: return f"${price:,.2f}"
    
    @staticmethod
    def _format_volume(volume):
        if volume > 1_000_000_000: return f"${volume / 1_000_000_000:.2f}B"
        elif volume > 1_000_000: return f"${volume / 1_000_000:.2f}M"
        elif volume > 1_000: return f"${volume / 1_000:.0f}K"
        else: return f"${volume:,.0f}"

# ════════════════════════════════════════════════════════════════════════════════════════════════
# TELEGRAM COMMAND HANDLERS
# ════════════════════════════════════════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_start(), parse_mode='HTML')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = 5
    if context.args:
        try: count = max(1, min(20, int(context.args[0])))
        except ValueError: await update.message.reply_text("[WARNING] Usage: /news 5", parse_mode='HTML'); return
    await update.message.reply_text(LegendXBot().cmd_news(count), parse_mode='HTML', disable_web_page_preview=True)

async def feargreed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_feargreed(), parse_mode='HTML')

async def gainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_gainers(), parse_mode='HTML')

async def losers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_losers(), parse_mode='HTML')

async def volume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_volume(), parse_mode='HTML')

async def fgainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_fgainers(), parse_mode='HTML')

async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("[WARNING] Usage: /trend BTC", parse_mode='HTML'); return
    await update.message.reply_text(LegendXBot().cmd_trend(context.args[0]), parse_mode='HTML')

async def liquidation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_liquidation(context.args[0] if context.args else "BTC"), parse_mode='HTML')

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_map(context.args[0] if context.args else "BTC"), parse_mode='HTML')

async def flow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LegendXBot().cmd_flow(context.args[0] if context.args else "BTC"), parse_mode='HTML')

# ════════════════════════════════════════════════════════════════════════════════════════════════
# BACKGROUND JOBS
# ════════════════════════════════════════════════════════════════════════════════════════════════

async def log_market_data_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("📊 Running market data logging job...")
        bot = LegendXBot()
        for symbol in ["BTC", "ETH", "SOL", "ADA"]:
            snapshot = bot.collect_snapshot(symbol=symbol)
            if snapshot: bot.log_to_csv(snapshot)
            else: logger.warning(f"Failed to collect snapshot for {symbol}")
    except Exception as e:
        logger.error(f"Logging job error: {e}")

# ════════════════════════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════════════════════

async def main():
    """Start the bot using async polling (Python 3.14 compatible)"""
    
    logger.info("\n" + "="*100)
    logger.info("LEGEND_X TELEGRAM BOT - RENDER DEPLOYMENT")
    logger.info("="*100)
    
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
    try:
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_repeating(log_market_data_job, interval=14400, first=300)
            logger.info("✓ Market logging job scheduled (every 4 hours)")
        else:
            logger.warning("⚠️ Job queue not available")
    except Exception as e:
        logger.warning(f"⚠️ Could not set up job queue: {e}")
    
    # Initialize and start application (Python 3.14 compatible)
    await application.initialize()
    await application.start()
    
    if application.updater:
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("✓ Bot started! Listening for commands...")
    
    # Keep running until interrupted
    try:
        import asyncio as _asyncio
        await _asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown requested")
    finally:
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("✓ Bot shutdown complete")


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n✓ Bot shutdown gracefully")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import sys
        sys.exit(1)
