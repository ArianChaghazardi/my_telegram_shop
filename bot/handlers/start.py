# -*- coding: utf-8 -*-
"""Start command, forced-join gate, and main menu routing."""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import settings
from bot.core.database import db
from bot.keyboards import (
    main_reply_keyboard,
    products_menu_kb,
    btn,
    ikb,
    STYLE_SUCCESS,
    STYLE_PRIMARY,
)
from bot.keyboards.reply import (
    LBL_BUY_PRODUCT,
    LBL_TOPUP,
    LBL_ACCOUNT,
    LBL_REFERRAL,
    LBL_SUPPORT,
    LBL_TRACKING,
    LBL_TRUST,
)

log = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = (
    "سلام! به فروشگاه خودکار و فوری خدمات تلگرام خوش آمدید ⭐️\n\n"
    "از طریق این ربات می‌توانید تمامی خدمات تلگرام را به صورت آنی دریافت کنید:\n"
    "⭐ <b>استارز تلگرام (Telegram Stars)</b>\n"
    "💎 <b>اشتراک پرمیوم تلگرام (Telegram Premium)</b>\n"
    "🎁 <b>ارسال گیفت‌های تلگرام (Telegram Gifts)</b>\n"
    "🪙 <b>خرید و انتقال ارز دیجیتال (TON & TRX)</b>\n"
    "❤️ <b>ری‌اکشن و بوست کانال</b>\n\n"
    "برای شروع از منوی زیر استفاده کنید 👇"
)


async def check_user_membership(bot: Bot, user_id: int) -> bool:
    """Verify if user is a member of all required channels."""
    channels = settings.channel_list
    if not channels or user_id in settings.admin_id_list:
        return True

    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception as e:
            log.warning("Could not check membership in %s for user %s: %s", channel, user_id, e)
    return True


def gate_keyboard() -> any:
    """Build keyboard for required channel join gate."""
    rows = []
    for ch in settings.channel_list:
        clean_name = ch.lstrip("@")
        rows.append([btn(f"📢 عضویت در {ch}", url=f"https://t.me/{clean_name}", style=STYLE_PRIMARY)])
    rows.append([btn("🔍 بررسی عضویت 🔍", callback_data="gate:check", style=STYLE_SUCCESS)])
    return ikb(rows)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    user_id = message.from_user.id

    # Parse referral code e.g. /start ref_123456
    referrer_id = None
    args = (message.text or "").split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_candidate = args[1].replace("ref_", "")
        if ref_candidate.isdigit():
            referrer_id = int(ref_candidate)

    # Register or get user
    user = await db.get_or_create_user(
        user_id=user_id,
        full_name=message.from_user.full_name or "",
        username=message.from_user.username or "",
        referrer_id=referrer_id,
    )

    # Check forced join
    is_joined = await check_user_membership(bot, user_id)
    if not is_joined:
        await message.answer(
            "⚠️ برای استفاده از امکانات ربات، ابتدا باید در کانال‌های زیر عضو شوید:\n"
            "پس از عضویت، دکمه «بررسی عضویت» را لمس کنید.",
            reply_markup=gate_keyboard()
        )
        return

    await message.answer(WELCOME_TEXT, reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "gate:check")
async def gate_check(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    is_joined = await check_user_membership(bot, call.from_user.id)
    if is_joined:
        await call.answer("✅ عضویت شما تایید شد. خوش آمدید!", show_alert=True)
        await call.message.delete()
        await call.message.answer(WELCOME_TEXT, reply_markup=main_reply_keyboard())
    else:
        await call.answer("❌ هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)


# ---------------------------------------------------------------------------
# Main Reply Menu Actions
# ---------------------------------------------------------------------------

@router.message(F.text == LBL_BUY_PRODUCT)
async def menu_buy_products(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🛍 <b>فهرست محصولات و خدمات تلگرام:</b>\n\n"
        "لطفاً دسته‌بندی مورد نظر خود را انتخاب کنید 👇",
        reply_markup=products_menu_kb()
    )


@router.message(F.text == LBL_SUPPORT)
async def menu_support(message: Message) -> None:
    await message.answer(
        f"🎧 <b>واحد پشتیبانی و پاسخگویی:</b>\n\n"
        "در صورت بروز هرگونه سوال یا مشکل در سفارش‌ها، با آیدی پشتیبانی در ارتباط باشید:\n"
        f"👤 پشتیبانی: {settings.SUPPORT_USERNAME}\n\n"
        "⏰ ساعت پاسخگویی: همه‌روزه از ۹ صبح تا ۱۲ شب"
    )


@router.message(F.text == LBL_TRUST)
async def menu_trust(message: Message) -> None:
    channels_text = "\n".join(f"📢 {ch}" for ch in settings.channel_list) or "کانال گزارش واریزی‌ها"
    await message.answer(
        "🛡 <b>اعتماد و شفافیت:</b>\n\n"
        "کلیه پرداخت‌ها و رضایت مشتریان در کانال رسمی رضایت ثبت می‌شود:\n"
        f"{channels_text}\n\n"
        "✅ تحویل فوری و تضمین بازگشت وجه در صورت بروز مشکل"
    )


@router.callback_query(F.data == "menu:close")
async def menu_close(call: CallbackQuery) -> None:
    await call.message.delete()
