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
        if not
