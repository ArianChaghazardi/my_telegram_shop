# -*- coding: utf-8 -*-
"""User profile, order tracking, and referral management."""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.core.database import db
from config import settings
from bot.keyboards import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER
from bot.keyboards.reply import LBL_ACCOUNT, LBL_REFERRAL, LBL_TRACKING

log = logging.getLogger(__name__)
router = Router(name="account")


class TrackingFlow(StatesGroup):
    waiting_for_code = State()


# ---------------------------------------------------------------------------
# Profile & Account
# ---------------------------------------------------------------------------

@router.message(F.text == LBL_ACCOUNT)
async def menu_account(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user:
        user = await db.get_or_create_user(message.from_user.id, message.from_user.full_name)

    orders = await db.get_user_orders(message.from_user.id, limit=5)
    orders_text = ""
    if orders:
        orders_text = "\n".join(
            f"🔹 <code>{o['code']}</code> | {o['title']} | <b>{o['status']}</b>" for o in orders
        )
    else:
        orders_text = "هنوز سفارشی ثبت نکرده اید."

    text = (
        "👤 <b>پروفایل و حساب کاربری:</b>\n"
        "────────────────────\n"
        f"🆔 شناسه کاربری: <code>{user['id']}</code>\n"
        f"👤 نام: <b>{user['full_name']}</b>\n"
        f"💵 موجودی اصلی: <b>{user['balance']:,} تومان</b>\n"
        f"🎁 موجودی تخفیف: <b>{user['discount_balance']:,} تومان</b>\n"
        f"⭐️ امتیاز باشگاه: <b>{user['points']:,} امتیاز</b>\n"
        "────────────────────\n"
        "📦 <b>آخرین سفارش های شما:</b>\n"
        f"{orders_text}"
    )

    markup = ikb([
        [btn("🎲 چالش های روزانه و جوایز", callback_data="games:menu", style=STYLE_SUCCESS)],
        [btn("🔎 پیگیری سفارش با کد", callback_data="track:start", style=STYLE_PRIMARY)],
    ])
    await message.answer(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Referral System
# ---------------------------------------------------------------------------

@router.message(F.text == LBL_REFERRAL)
async def menu_referral(message: Message, bot: Bot) -> None:
    user = await db.get_user(message.from_user.id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"

    ref_count = user["ref_count"]
    ref_earnings = user["ref_earnings"]
    total_earned = user["total_ref_earned"]

    text = (
        "👥 <b>سیستم کسب درآمد و زیرمجموعه گیری:</b>\n\n"
        f"با دعوت دوستانتان به ربات، <b>{settings.DEFAULT_REFERRAL_PERCENT}٪</b> از مبلغ هر خرید آن ها به عنوان پاداش به حساب شما واریز می شود!\n\n"
        f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n<code>{ref_link}</code>\n\n"
        f"👤 تعداد دعوت ها: <b>{ref_count} نفر</b>\n"
        f"💰 درآمد قابل برداشت: <b>{ref_earnings:,} تومان</b>\n"
        f"📊 کل سود کسب شده: <b>{total_earned:,} تومان</b>\n\n"
        "حداقل مبلغ درخواست تسویه: ۱۰۰,۰۰۰ تومان"
    )

    markup = ikb([
        [btn("💸 درخواست تسویه حساب درآمد", callback_data="ref:withdraw", style=STYLE_SUCCESS)],
        [btn("🔙 بازگشت", callback_data="menu:close", style=STYLE_DANGER)],
    ])
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "ref:withdraw")
async def ref_withdraw(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    if user["ref_earnings"] < settings.MIN_WITHDRAWAL_TOMAN:
        await call.answer(
            f"❌ حداقل موجودی برای تسویه ۱۰۰,۰۰۰ تومان است.\nموجودی شما: {user['ref_earnings']:,} تومان",
            show_alert=True
        )
        return

    await call.answer("درخواست تسویه به پشتیبانی ارسال شد.", show_alert=True)


# ---------------------------------------------------------------------------
# Order Tracking
# ---------------------------------------------------------------------------

@router.message(F.text == LBL_TRACKING)
@router.callback_query(F.data == "track:start")
async def tracking_start(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TrackingFlow.waiting_for_code)
    text = "🔎 <b>پیگیری وضعیت سفارش:</b>\n\nلطفاً کد رهگیری سفارش خود را ارسال فرمایید (مثال: <code>ORD-ABC123</code>):"
    if isinstance(event, CallbackQuery):
        await event.message.answer(text)
        await event.answer()
    else:
        await event.answer(text)


@router.message(TrackingFlow.waiting_for_code, F.text)
async def tracking_check(message: Message, state: FSMContext) -> None:
    code = message.text.strip().upper()
    await state.clear()

    order = await db.get_order(code)
    if not order:
        await message.answer("❌ سفارشی با این کد رهگیری در سیستم یافت نشد.")
        return

    status_map = {
        "pending": "⏳ در انتظار پرداخت",
        "paid": "🚀 پرداخت شده (در صف تحویل خودکار)",
        "delivered": "✅ تحویل داده شد",
        "cancelled": "❌ لغو شده",
        "refunded": "↩️ بازگشت وجه به کیف پول",
        "expired": "⏰ منقضی شده",
    }
    status_label = status_map.get(order["status"], order["status"])

    await message.answer(
        "🧾 <b>جزئیات سفارش:</b>\n"
        "────────────────────\n"
        f"🔖 کد رهگیری: <code>{order['code']}</code>\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"💵 مبلغ: <b>{order['final_price']:,} تومان</b>\n"
        f"📊 وضعیت فعلی: <b>{status_label}</b>\n"
        "────────────────────"
    )
