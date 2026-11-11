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
from bot.keyboards.reply import MAIN_BUTTONS

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
    discount_max_uses = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list


def is_menu_navigation(text: str) -> bool:
    return text in MAIN_BUTTONS or text in ("❌ انصراف و بازگشت به منو", "/cancel", "انصراف", "/start")


def admin_dashboard_kb() -> any:
    return ikb([
        [
            btn("📊 آمار و گزارشات", callback_data="adm:stats", style=STYLE_PRIMARY),
            btn("📦 سفارش های منتظر تحویل", callback_data="adm:pending", style=STYLE_SUCCESS),
        ],
        [
            btn("⚙️ تنظیم نرخ ها و قیمت ها", callback_data="adm:prices", style=STYLE_PRIMARY),
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
        f"👥 کل کاربران ثبت شده: <b>{stats['users_count']:,} نفر</b>\n"
        f"📦 کل سفارش های ثبت شده: <b>{stats['orders_count']:,} عدد</b>\n"
        f"⏳ سفارش های نیازمند تحویل: <b>{stats['pending_delivery']:,} عدد</b>\n"
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
            "✅ در حال حاضر هیچ سفارش پرداخت شده ای در انتظار تحویل نیست.",
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
# Prices & Settings Management
# ---------------------------------------------------------------------------

PRICE_KEYS = [
    ("price_per_star", "⭐ نرخ هر استارز (تومان)"),
    ("stars_price_50", "⭐ قیمت پک ۵۰ استارز (تومان)"),
    ("premium_3", "💎 پرمیوم ۳ ماهه (تومان)"),
    ("premium_6", "💎 پرمیوم ۶ ماهه (تومان)"),
    ("premium_12", "💎 پرمیوم ۱۲ ماهه (تومان)"),
    ("ton_personal_price", "🪙 نرخ ۱ واحد تون (تومان)"),
    ("trx_price", "🔴 نرخ ۱ واحد ترون (تومان)"),
    ("wallet_address", "👛 آدرس ولت دریافت شارژ"),
]


@router.callback_query(F.data == "adm:prices")
async def adm_prices_list(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        return

    rows = []
    text_lines = ["⚙️ <b>تنظیمات نرخ ها و قیمت های فروشگاه:</b>\n"]
    for key, label in PRICE_KEYS:
        val = await db.get_setting(key, "تعریف نشده")
        text_lines.append(f"▫️ {label}: <code>{val}</code>")
        rows.append([btn(f"✏️ ویرایش {label}", callback_data=f"adm:setprice:{key}", style=STYLE_PRIMARY)])

    rows.append([btn("🔙 بازگشت به داشبورد", callback_data="adm:dashboard", style=STYLE_DANGER)])
    await call.message.edit_text("\n".join(text_lines), reply_markup=ikb(rows))


@router.callback_query(F.data.startswith("adm:setprice:"))
async def adm_setprice_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    key = call.data.split(":")[2]
    label = dict(PRICE_KEYS).get(key, key)
    current_val = await db.get_setting(key, "")

    await state.update_data(edit_setting_key=key, edit_setting_label=label)
    await state.set_state(AdminFlow.setting_value)
    await call.message.edit_text(
        f"⚙️ <b>ویرایش «{label}»:</b>\n\n"
        f"مقدار فعلی: <code>{current_val}</code>\n\n"
        "✍️ لطفاً مقدار جدید را ارسال فرمایید (یا /cancel برای انصراف):"
    )


@router.message(AdminFlow.setting_value, F.text)
async def adm_setprice_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    new_val = message.text.strip().replace(",", "")
    data = await state.get_data()
    key = data.get("edit_setting_key")
    label = data.get("edit_setting_label", key)
    await state.clear()

    if not key:
        await message.answer("❌ خطا در بازیابی کلید تنظیمات.")
        return

    await db.set_setting(key, new_val)
    await message.answer(
        f"✅ مقدار «{label}» با موفقیت به <code>{new_val}</code> تغییر یافت.",
        reply_markup=ikb([[btn("⚙️ بازگشت به لیست قیمت ها", callback_data="adm:prices", style=STYLE_SUCCESS)]])
    )


# ---------------------------------------------------------------------------
# Discount Codes Management
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "adm:discounts")
async def adm_discounts_list(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        return

    codes = await db.get_discount_codes()
    rows = []
    text = "🎟 <b>مدیریت کدهای تخفیف فعال:</b>\n\n"
    if codes:
        for c in codes:
            limit_str = f"{c['times_used']}/{c['max_uses']}" if c['max_uses'] != -1 else f"{c['times_used']} (نامحدود)"
            text += f"▫️ کد: <code>{c['code']}</code> | <b>{c['percent']}٪</b> تخفیف | استفاده: {limit_str}\n"
            rows.append([btn(f"🗑 حذف کد {c['code']}", callback_data=f"adm:deldisc:{c['code']}", style=STYLE_DANGER)])
    else:
        text += "هیچ کد تخفیف فعالی ثبت نشده است.\n"

    rows.append([btn("➕ افزودن کد تخفیف جدید", callback_data="adm:adddisc", style=STYLE_SUCCESS)])
    rows.append([btn("🔙 بازگشت به داشبورد", callback_data="adm:dashboard", style=STYLE_PRIMARY)])
    await call.message.edit_text(text, reply_markup=ikb(rows))


@router.callback_query(F.data.startswith("adm:deldisc:"))
async def adm_del_discount(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        return
    code = call.data.split(":")[2]
    await db.delete_discount_code(code)
    await call.answer(f"کد تخفیف {code} حذف شد.", show_alert=True)
    await adm_discounts_list(call)


@router.callback_query(F.data == "adm:adddisc")
async def adm_add_discount_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminFlow.discount_code)
    await call.message.edit_text(
        "🎟 <b>ساخت کد تخفیف جدید:</b>\n\n"
        "✍️ لطفاً نام کد تخفیف را به انگلیسی ارسال کنید (مثال: <code>Spring20</code>):"
    )


@router.message(AdminFlow.discount_code, F.text)
async def adm_add_disc_code(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    code = message.text.strip().upper()
    await state.update_data(new_disc_code=code)
    await state.set_state(AdminFlow.discount_percent)
    await message.answer(
        f"کد: <code>{code}</code>\n\n"
        "✍️ لطفاً درصد تخفیف را به عدد ارسال کنید (بین ۱ تا ۱۰۰):"
    )


@router.message(AdminFlow.discount_percent, F.text)
async def adm_add_disc_percent(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 100):
        await message.answer("❌ درصد باید عددی بین ۱ تا ۱۰۰ باشد. دوباره ارسال کنید:")
        return

    percent = int(text)
    await state.update_data(new_disc_percent=percent)
    await state.set_state(AdminFlow.discount_max_uses)
    await message.answer(
        "✍️ سقف تعداد استفاده از این کد را وارد کنید:\n"
        "(برای تعداد نامحدود عدد <code>-1</code> را ارسال کنید)"
    )


@router.message(AdminFlow.discount_max_uses, F.text)
async def adm_add_disc_max_uses(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    text = message.text.strip()
    max_uses = -1
    if text.lstrip("-").isdigit():
        max_uses = int(text)

    data = await state.get_data()
    code = data["new_disc_code"]
    percent = data["new_disc_percent"]
    await state.clear()

    ok = await db.create_discount_code(code=code, percent=percent, max_uses=max_uses)
    if ok:
        await message.answer(
            f"✅ کد تخفیف <code>{code}</code> با <b>{percent}٪</b> تخفیف با موفقیت ساخته شد.",
            reply_markup=ikb([[btn("🎟 بازگشت به لیست تخفیف ها", callback_data="adm:discounts", style=STYLE_SUCCESS)]])
        )
    else:
        await message.answer("❌ خطا در ثبت کد تخفیف.")


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
    if is_menu_navigation(message.text.strip()):
        await state.clear()
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
    if is_menu_navigation(message.text.strip()):
        await state.clear()
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
        await message.answer("❌ خطا در ویرایش موجودی (احتمالاً موجودی منفی می شد).")


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
    if is_menu_navigation(message.text.strip()):
        await state.clear()
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
