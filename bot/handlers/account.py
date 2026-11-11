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
from bot.keyboards.reply import LBL_ACCOUNT, LBL_REFERRAL, LBL_TRACKING, MAIN_BUTTONS

log = logging.getLogger(__name__)
router = Router(name="account")


class TrackingFlow(StatesGroup):
    waiting_for_code = State()


# ---------------------------------------------------------------------------
# Profile & Account (In-Place Edit Support)
# ---------------------------------------------------------------------------

async def display_account_profile(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    user = await db.get_user(user_id)
    if not user:
        user = await db.get_or_create_user(user_id, event.from_user.full_name)

    orders = await db.get_user_orders(user_id, limit=5)
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

    rows = [
        [btn("🎲 چالش های روزانه و جوایز", callback_data="games:menu", style=STYLE_SUCCESS)],
        [btn("🔎 پیگیری سفارش با کد", callback_data="track:start", style=STYLE_PRIMARY)],
    ]

    if user["points"] >= 30:
        rows.append([btn("🎟 تبدیل ۳۰ امتیاز به کد تخفیف ۱۰٪", callback_data="pts:redeem", style=STYLE_SUCCESS)])

    markup = ikb(rows)
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=markup)
        except Exception:
            await event.message.answer(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


@router.message(F.text == LBL_ACCOUNT)
async def menu_account(message: Message) -> None:
    await display_account_profile(message)


@router.callback_query(F.data == "acc:back")
async def acc_back_callback(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await display_account_profile(call)


@router.callback_query(F.data == "pts:redeem")
async def redeem_points_callback(call: CallbackQuery) -> None:
    ok, msg, code = await db.redeem_points_for_discount(call.from_user.id)
    if not ok:
        await call.answer(msg, show_alert=True)
        return

    await call.answer(f"{msg}\nمی توانید در خریدهای بعدی این کد را در پیش فاکتور اعمال نمایید.", show_alert=True)
    await display_account_profile(call)


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
        [btn("🔙 بستن", callback_data="menu:close", style=STYLE_DANGER)],
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
        prompt = await event.message.edit_text(
            text,
            reply_markup=ikb([[btn("🔙 بازگشت به حساب کاربری", callback_data="acc:back", style=STYLE_DANGER)]])
        )
        await state.update_data(prompt_msg_id=prompt.message_id)
        await event.answer()
    else:
        await event.answer(text)


@router.message(TrackingFlow.waiting_for_code, F.text)
async def tracking_check(message: Message, state: FSMContext) -> None:
    if message.text.strip() in MAIN_BUTTONS or message.text.strip() in ("❌ انصراف و بازگشت به منو", "/cancel", "انصراف"):
        await state.clear()
        return

    code = message.text.strip().upper()
    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    order = await db.get_order(code)
    if not order:
        res_text = f"❌ سفارشی با کد رهگیری <code>{code}</code> یافت نشد."
        markup = ikb([[btn("🔙 بازگشت به حساب کاربری", callback_data="acc:back", style=STYLE_DANGER)]])
        if prompt_id:
            try:
                await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=res_text, reply_markup=markup)
                return
            except Exception:
                pass
        await message.answer(res_text, reply_markup=markup)
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

    res_text = (
        "🧾 <b>جزئیات سفارش:</b>\n"
        "────────────────────\n"
        f"🔖 کد رهگیری: <code>{order['code']}</code>\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"💵 مبلغ: <b>{order['final_price']:,} تومان</b>\n"
        f"📊 وضعیت فعلی: <b>{status_label}</b>\n"
        "────────────────────"
    )
    markup = ikb([[btn("🔙 بازگشت به حساب کاربری", callback_data="acc:back", style=STYLE_PRIMARY)]])

    if prompt_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=res_text, reply_markup=markup)
            return
        except Exception:
            pass

    await message.answer(res_text, reply_markup=markup)
