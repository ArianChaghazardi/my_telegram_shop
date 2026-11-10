# -*- coding: utf-8 -*-
"""Keyboards package."""
from bot.keyboards.common import btn, kbtn, ikb, rkb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER
from bot.keyboards.reply import main_reply_keyboard, cancel_reply_keyboard, MAIN_BUTTONS
from bot.keyboards.shops import (
    products_menu_kb,
    stars_menu_kb,
    premium_menu_kb,
    gifts_grid_kb,
    recipient_kb,
    invoice_kb,
)

__all__ = [
    "btn",
    "kbtn",
    "ikb",
    "rkb",
    "STYLE_SUCCESS",
    "STYLE_PRIMARY",
    "STYLE_DANGER",
    "main_reply_keyboard",
    "cancel_reply_keyboard",
    "MAIN_BUTTONS",
    "products_menu_kb",
    "stars_menu_kb",
    "premium_menu_kb",
    "gifts_grid_kb",
    "recipient_kb",
    "invoice_kb",
]
