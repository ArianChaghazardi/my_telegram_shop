# -*- coding: utf-8 -*-
"""Application configuration and default settings."""

import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BOT_TOKEN: str = Field(default="", description="Telegram Bot API Token")
    ADMIN_IDS: str = Field(default="", description="Comma-separated Telegram user IDs for admins")
    REQUIRED_CHANNELS: str = Field(default="", description="Comma-separated required channels")
    SUPPORT_USERNAME: str = Field(default="@Support", description="Support handle")
    DB_PATH: str = Field(default="data/shop.db", description="Path to SQLite database file")
    
    DEFAULT_REFERRAL_PERCENT: int = 5
    MIN_WITHDRAWAL_TOMAN: int = 100000

    @property
    def admin_id_list(self) -> List[int]:
        if not self.ADMIN_IDS.strip():
            return []
        ids = []
        for item in self.ADMIN_IDS.split(","):
            item = item.strip()
            if item.lstrip("-").isdigit():
                ids.append(int(item))
        return ids

    @property
    def channel_list(self) -> List[str]:
        if not self.REQUIRED_CHANNELS.strip():
            return []
        return [c.strip() for c in self.REQUIRED_CHANNELS.split(",") if c.strip()]


settings = Settings()

# ---------------------------------------------------------------------------
# Default Shop Prices & Catalog
# ---------------------------------------------------------------------------

DEFAULT_PRICES: Dict[str, str] = {
    "price_per_star": "4520",        # Toman per star
    "stars_price_50": "226000",      # 50 Stars pack
    "premium_3": "3650000",          # Premium 3 months (Toman)
    "premium_6": "4870000",          # Premium 6 months (Toman)
    "premium_12": "8820000",         # Premium 12 months (Toman)
    "ton_wallet_activation": "36000",# 0.1 TON wallet activation
    "ton_personal_price": "330000",  # Toman per 1 TON
    "trx_price": "95000",            # Toman per 1 TRX
    "reaction_price_per_10": "4500", # Toman per 10 reactions
    "wallet_address": "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "wallet_memo": "100200",
}

# 11 Telegram Gifts specification with star value and default price in Toman
GIFTS_CATALOG = [
    {"key": "heart",    "name": "قلب 💗",     "stars": 15,  "price": 68000},
    {"key": "bear",     "name": "تدی 🧸",     "stars": 15,  "price": 69000},
    {"key": "giftbox",  "name": "کادو 🎁",    "stars": 25,  "price": 114000},
    {"key": "rose",     "name": "گل رز 🌹",   "stars": 25,  "price": 114000},
    {"key": "cake",     "name": "کیک 🎂",     "stars": 50,  "price": 229000},
    {"key": "bouquet",  "name": "دسته گل 💐", "stars": 50,  "price": 229000},
    {"key": "rocket",   "name": "سفینه 🚀",   "stars": 50,  "price": 229000},
    {"key": "trophy",   "name": "جام 🏆",     "stars": 100, "price": 458000},
    {"key": "ring",     "name": "حلقه 💍",    "stars": 100, "price": 458000},
    {"key": "bottle",   "name": "بطری 🍾",    "stars": 50,  "price": 229000},
    {"key": "diamond",  "name": "الماس 💎",   "stars": 100, "price": 458000},
]

GIFT_BY_KEY = {g["key"]: g for g in GIFTS_CATALOG}

PREMIUM_PLANS = {
    3: "premium_3",
    6: "premium_6",
    12: "premium_12",
}

# Telegram Custom Emoji IDs (Fill in with real IDs if premium emojis are desired)
CUSTOM_EMOJI_IDS: Dict[str, str] = {}
