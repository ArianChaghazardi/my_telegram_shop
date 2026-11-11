# -*- coding: utf-8 -*-
"""Inline keyboards for shops, product catalogs, and invoices."""

from typing import Optional
from aiogram.types import InlineKeyboardMarkup
from config import GIFTS_CATALOG
from bot.keyboards.common import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER


def products_menu_kb() -> InlineKeyboardMarkup:
    """Main inline catalog of all available shop categories."""
    return ikb([
        [
            btn("⭐ خرید استارز تلگرام", callback_data="shop:stars", style=STYLE_SUCCESS),
            btn("💎 خرید تلگرام پرمیوم", callback_data="shop:premium", style=STYLE_SUCCESS),
        ],
        [
            btn("🪙 خرید ارز دیجیتال (TON)", callback_data="shop:crypto", style=STYLE_PRIMARY),
            btn("🎁 خرید گیفت تلگرام", callback_data="shop:gifts", style=STYLE_PRIMARY),
        ],
        [
            btn("❤️ خرید ری اکشن تلگرام", callback_data="shop:reactions", style=STYLE_PRIMARY),
            btn("🚀 خرید بوست کانال", callback_data="shop:boost", style=STYLE_PRIMARY),
        ],
        [
            btn("🔙 بستن منو", callback_data="menu:close", style=STYLE_DANGER),
        ]
    ])


def stars_menu_kb() -> InlineKeyboardMarkup:
    """Stars package selection keyboard."""
    return ikb([
        [
            btn("⭐ ۵۰ استارز", callback_data="stars:pack:50", style=STYLE_SUCCESS),
            btn("⭐ ۱۰۰ استارز", callback_data="stars:pack:100", style=STYLE_SUCCESS),
        ],
        [
            btn("⭐ ۲۰۰ استارز", callback_data="stars:pack:200", style=STYLE_SUCCESS),
            btn("⭐ ۵۰۰ استارز", callback_data="stars:pack:500", style=STYLE_SUCCESS),
        ],
        [
            btn("🔢 وارد کردن تعداد دلخواه (حداقل ۵۰)", callback_data="stars:custom", style=STYLE_PRIMARY),
        ],
        [
            btn("🧮 محاسبه بر اساس موجودی من", callback_data="stars:calc_balance", style=STYLE_PRIMARY),
        ],
        [
            btn("🔙 بازگشت به فروشگاه", callback_data="shop:main", style=STYLE_DANGER),
        ]
    ])


def premium_menu_kb() -> InlineKeyboardMarkup:
    """Telegram premium subscription plans."""
    return ikb([
        [btn("💎 پرمیوم ۳ ماهه", callback_data="prem:3", style=STYLE_SUCCESS)],
        [btn("💎 پرمیوم ۶ ماهه", callback_data="prem:6", style=STYLE_SUCCESS)],
        [btn("💎 پرمیوم ۱۲ ماهه (یک ساله)", callback_data="prem:12", style=STYLE_SUCCESS)],
        [btn("🔙 بازگشت به فروشگاه", callback_data="shop:main", style=STYLE_DANGER)],
    ])


def gifts_grid_kb() -> InlineKeyboardMarkup:
    """11 Telegram Gifts in a neat 2-column grid."""
    rows = []
    current_row = []
    for gift in GIFTS_CATALOG:
        text = f"{gift['name']} ({gift['stars']}⭐)"
        current_row.append(btn(text, callback_data=f"gift:pick:{gift['key']}", style=STYLE_SUCCESS))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    rows.append([btn("🔙 بازگشت به فروشگاه", callback_data="shop:main", style=STYLE_DANGER)])
    return ikb(rows)


def gift_anonymous_kb() -> InlineKeyboardMarkup:
    """Choose if gift should be anonymous or show sender name."""
    return ikb([
        [btn("👁 با نام من نمایش داده شود", callback_data="gift:anon:0", style=STYLE_SUCCESS)],
        [btn("🕶 ارسال به صورت کاملاً ناشناس", callback_data="gift:anon:1", style=STYLE_PRIMARY)],
        [btn("🔙 بازگشت به لیست گیفت ها", callback_data="shop:gifts", style=STYLE_DANGER)],
    ])


def gift_comment_kb() -> InlineKeyboardMarkup:
    """Optional message accompanied with gift."""
    return ikb([
        [btn("⏭ بدون متن (ادامه خرید)", callback_data="gift:comment:skip", style=STYLE_SUCCESS)],
        [btn("🔙 بازگشت به مرحله قبل", callback_data="shop:gifts", style=STYLE_DANGER)],
    ])


def crypto_buy_menu_kb() -> InlineKeyboardMarkup:
    """Crypto purchase options."""
    return ikb([
        [btn("💎 خرید تون کوین (TON)", callback_data="crypto:buy:ton", style=STYLE_SUCCESS)],
        [btn("🔴 خرید ترون (TRX)", callback_data="crypto:buy:trx", style=STYLE_PRIMARY)],
        [btn("🔙 بازگشت به فروشگاه", callback_data="shop:main", style=STYLE_DANGER)],
    ])


def recipient_kb(first_name: str, back_callback: str = "shop:main") -> InlineKeyboardMarkup:
    """Prompt keyboard for selecting recipient with back navigation."""
    return ikb([
        [btn(f"👤 برای خودم ({first_name})", callback_data="recipient:self", style=STYLE_SUCCESS)],
        [btn("🔙 بازگشت به مرحله قبل", callback_data=back_callback, style=STYLE_PRIMARY)],
        [btn("❌ انصراف", callback_data="order:cancel", style=STYLE_DANGER)],
    ])


def invoice_kb(
    order_code: str,
    user_balance: int,
    final_price: int,
    user_discount_balance: int = 0,
    has_discount_code: bool = False,
    has_discount_balance_used: bool = False
) -> InlineKeyboardMarkup:
    """
    Polished pre-invoice action keyboard:
    - Wallet payment if balance is sufficient
    - Topup prompt if insufficient
    - Discount balance usage button
    - Discount code application
    - Cancellation
    """
    rows = []
    if user_balance >= final_price:
        rows.append([btn("👛 پرداخت با کیف پول", callback_data=f"pay:wallet:{order_code}", style=STYLE_SUCCESS)])
    else:
        rows.append([btn(f"❌ کسری موجودی: {final_price - user_balance:,} تومان", callback_data="topup:start", style=STYLE_DANGER)])
        rows.append([btn("💳 شارژ سریع کیف پول", callback_data="topup:start", style=STYLE_SUCCESS)])

    # Discount balance deduction button (if available and not yet applied)
    if user_discount_balance > 0 and not has_discount_balance_used and final_price > 0:
        usable = min(final_price, user_discount_balance)
        rows.append([btn(f"🎁 کسر موجودی تخفیف ({usable:,} تومان)", callback_data=f"pay:use_discount:{order_code}", style=STYLE_SUCCESS)])

    # Discount code row
    if not has_discount_code:
        rows.append([btn("🎟 اعمال کد تخفیف", callback_data=f"pay:discount:{order_code}", style=STYLE_PRIMARY)])

    rows.append([btn("💳 پرداخت آنلاین درگاه (بانکی)", callback_data=f"pay:online:{order_code}", style=STYLE_PRIMARY)])
    rows.append([btn("❌ لغو پیش فاکتور", callback_data=f"order:cancel:{order_code}", style=STYLE_DANGER)])
    return ikb(rows)
