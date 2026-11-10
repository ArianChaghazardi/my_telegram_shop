# -*- coding: utf-8 -*-
"""Main reply keyboards and persistent menus."""

from aiogram.types import ReplyKeyboardMarkup
from bot.keyboards.common import kbtn, rkb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER

# Kashida / tatweel labels matching the polished user aesthetic
LBL_BUY_PRODUCT = "🛍 خـــریــد مـحـصـول 🛍"
LBL_TOPUP       = "💳 افـزایـش مـوجـودی"
LBL_ACCOUNT     = "👤 حـسـاب کـاربـری"
LBL_REFERRAL    = "👥 زیـرمـجـمـوعه‌گـیـری"
LBL_SUPPORT     = "🎧 پـشـتـیـبـانـی"
LBL_TRACKING    = "🔎 پـیـگـیـری سـفـارش"
LBL_TRUST       = "🛡 اعـتـمـاد بـه مـا"

MAIN_BUTTONS = {
    LBL_BUY_PRODUCT,
    LBL_TOPUP,
    LBL_ACCOUNT,
    LBL_REFERRAL,
    LBL_SUPPORT,
    LBL_TRACKING,
    LBL_TRUST,
}


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Standard main menu reply keyboard."""
    return rkb([
        [kbtn(LBL_BUY_PRODUCT, style=STYLE_SUCCESS)],
        [
            kbtn(LBL_TOPUP, style=STYLE_PRIMARY),
            kbtn(LBL_ACCOUNT, style=STYLE_PRIMARY),
        ],
        [
            kbtn(LBL_REFERRAL, style=STYLE_PRIMARY),
            kbtn(LBL_SUPPORT, style=STYLE_PRIMARY),
        ],
        [
            kbtn(LBL_TRACKING, style=STYLE_DANGER),
            kbtn(LBL_TRUST, style=STYLE_DANGER),
        ],
    ])


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    """Quick cancel keyboard during text inputs."""
    return rkb([[kbtn("❌ انصراف و بازگشت به منو", style=STYLE_DANGER)]])
