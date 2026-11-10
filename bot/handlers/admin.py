# -*- coding: utf-8 -*-
"""Admin control panel: statistics, order fulfillment, price controls, and broadcasting."""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.core.database import db
from config import settings
from bot.services.fulfillment import FulfillmentService
from bot.keyboards import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER

log = logging.getLogger(__name__)
router = Router(name="admin")


class AdminFlow(StatesGroup):
    setting_key = State()
    setting_value = State()
    adjust_user_id = State()
    adjust_amount = State()
    broadcast_text = State()
    discount_code = State()
    discount_percent = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list


def admin_dashboard_kb() -> any:
    return ikb([
        [
            btn("📊 آمار و گزارشات", callback_data="adm:stats", style=STYLE_PRIMARY),
            btn("📦 سفارش‌های منتظر تحویل", callback_data="adm:pending", style=STYLE_SUCCESS),
        ],
        [
            btn("⚙️ تنظیم نرخ‌ها و قیمت‌ها", callback_data="adm:prices", style=STYLE_PRIMARY),
            btn("🎟 مدیریت کدهای تخفیف", callback_data="adm:discounts", style=STYLE_PRIMARY),
        ],
        [
            btn("💰 افزایش/کاهش موجودی کاربر", callback_data="adm:adjust", style=STYLE_PRIMARY),
            btn("📣 ارسال پیام همگانی", callback_data="adm:broadcast", style=STYLE_PRIMARY),
        ],
        [
            btn("🔙 خروج از پنل", callback_data="adm:exit", style=STYLE_DANGER),
        ]
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("👑 <b>پنل مدیریت پیشرفته فروشگاه:</b>", reply_markup=admin_dashboard_kb())


@router.callback_query(F.data == "adm:dashboard")
async def adm_dashboard(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("👑 <b>پنل مدیریت پیشرفته فروشگاه:</b>", reply_markup=admin_dashboard_kb())


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        "📊 <b>گزارش آمار کلی ربات:</b>\n\n"
        f"👥 کل کاربران ثبت‌شده: <b>{stats['users_count']:,} نفر</b>\n"
        f"📦 کل سفارش‌های ثبت‌شده: <b>{stats['orders_count']:,} عدد</b>\n"
        f"⏳ سفارش‌های نیازمند تحویل: <b>{stats['pending_delivery']:,} عدد</b>\n"
        f"💰 مجموع فروش موفق: <b>{stats['total_sales']:,} تومان</b>"
    )
    await call.message.edit_text(text, reply_markup=ikb([[btn("🔙 بازگشت", callback_data="adm:dashboard")]]))


# ---------------------------------------------------------------------------
# Pending Orders Review
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "adm:pending")
async def adm_pending_orders(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        return
    conn = await db.get_connection()
    try:
        cursor = await conn.execute("SELECT * FROM orders WHERE status = 'paid' ORDER BY id DESC LIMIT 5")
        rows = await cursor.fetchall()
    finally:
        await conn.close()

    if not rows:
        await call.message.edit_text(
            "✅ در حال حاضر هیچ سفارش پرداخت‌شده‌ای در انتظار تحویل نیست.",
            reply_markup=ikb([[btn("🔙 بازگشت", callback_data="adm:dashboard")]])
        )
        return

    for r in rows:
        r = dict(r)
        markup = ikb([
            [
                btn("✅ تایید و تحویل مجدد", callback_data=f"adm:ok:{r['code']}", style=STYLE_SUCCESS),
                btn("❌ رد سفارش و عودت وجه", callback_data=f"adm:reject:{r['code']}", style=STYLE_DANGER),
            ]
        ])
        await call.message.answer(
            f"🧾 <b>سفارش:</b> <code>{r['code']}</code>\n"
            f"📦 محصول: {r['title']}\n"
            f"👤 کاربر: <code>{r['user_id']}</code> | گیرنده: <code>{r['recipient']}</code>\n"
            f"💵 مبلغ: <b>{r['final_price']:,} تومان</b>",
            reply_markup=markup
        )


@router.callback_query(F.data.startswith("adm:ok:"))
async def adm_approve_order(call: CallbackQuery, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        return
    code = call.data.split(":")[2]
    success, msg = await FulfillmentService.deliver_order(bot, code)
    await call.answer(msg, show_alert=True)
    if success:
        await call.message.edit_text(call.message.text + "\n\n✅ <b>تحویل با موفقیت ثبت شد.</b>")


@router.callback_query(F.data.startswith("adm:reject:"))
async def adm_reject_order(call: CallbackQuery, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        return
    code = call.data.split(":")[2]
    success, msg = await db.admin_refund_order(code)
    await call.answer(msg, show_alert=True)
    if success:
        order = await db.get_order(code)
        if order:
            try:
                await bot.send_message(
                    chat_id=order["user_id"],
                    text=f"❌ سفارش <code>{code}</code> رد شد و مبلغ <b>{order['final_price']:,} تومان</b> به کیف پول شما عودت داده شد."
                )
            except Exception:
                pass
        await call.message.edit_text(call.message.text + "\n\n❌ <b>سفارش رد و مبلغ عودت داده شد.</b>")


# ---------------------------------------------------------------------------
# Balance Adjustment
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "adm:adjust")
async def adm_adjust_start(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminFlow.adjust_user_id)
    await call.message.edit_text("✍️ لطفاً <b>شناسه عددی (User ID)</b> کاربر را ارسال کنید:")


@router.message(AdminFlow.adjust_user_id, F.text)
async def adm_adjust_uid_input(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ شناسه باید عدد باشد. دوباره ارسال کنید:")
        return

    uid = int(text)
    user = await db.get_user(uid)
    if not user:
        await message.answer("❌ کاربر در دیتابیس یافت نشد.")
        return

    await state.update_data(target_uid=uid)
    await state.set_state(AdminFlow.adjust_amount)
    await message.answer(
        f"👤 کاربر: <b>{user['full_name']}</b> (موجودی فعلی: {user['balance']:,} تومان)\n"
        "✍️ مبلغ تغییر را به تومان ارسال کنید (مثبت = افزایش، منفی = کسر):\n"
        "📌 مثال: <code>50000</code> یا <code>-20000</code>"
    )


@router.message(AdminFlow.adjust_amount, F.text)
async def adm_adjust_amount_input(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip().replace(",", "")
    try:
        amount = int(text)
    except ValueError:
        await message.answer("❌ مبلغ نامعتبر است.")
        return

    data = await state.get_data()
    uid = data["target_uid"]
    await state.clear()

    ok = await db.update_user_balance(uid, amount, column="balance")
    if ok:
        await message.answer(f"✅ با موفقیت موجودی کاربر {uid} به میزان {amount:,} تومان تغییر کرد.")
    else:
        await message.answer("❌ خطا در ویرایش موجودی (احتمالاً موجودی منفی می‌شد).")


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminFlow.broadcast_text)
    await call.message.edit_text("✍️ متن پیام همگانی را برای ارسال به تمام کاربران بفرستید:")


@router.message(AdminFlow.broadcast_text)
async def adm_broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    text = message.html_text or message.text

    conn = await db.get_connection()
    try:
        cursor = await conn.execute("SELECT id FROM users")
        users = await cursor.fetchall()
    finally:
        await conn.close()

    sent = 0
    await message.answer(f"🚀 در حال ارسال پیام به {len(users)} کاربر...")
    for u in users:
        try:
            await bot.send_message(chat_id=u[0], text=text)
            sent += 1
        except Exception:
            pass

    await message.answer(f"✅ پیام به {sent} کاربر با موفقیت ارسال شد.")


@router.callback_query(F.data == "adm:exit")
async def adm_exit(call: CallbackQuery) -> None:
    await call.message.delete()
