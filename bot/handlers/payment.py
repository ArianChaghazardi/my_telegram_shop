# -*- coding: utf-8 -*-
"""Payment handling, discount verification, and fulfillment trigger."""

import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.core.database import db
from bot.services.fulfillment import FulfillmentService
from bot.services.payment_gateway import PaymentGatewayService
from bot.keyboards import invoice_kb, btn, ikb, STYLE_DANGER, STYLE_PRIMARY, STYLE_SUCCESS
from bot.keyboards.reply import MAIN_BUTTONS

log = logging.getLogger(__name__)
router = Router(name="payment")


class DiscountFlow(StatesGroup):
    waiting_for_code = State()


# ---------------------------------------------------------------------------
# 1. Atomic Wallet Payment
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:wallet:"))
async def pay_from_wallet(call: CallbackQuery, bot: Bot) -> None:
    order_code = call.data.split(":")[2]
    user_id = call.from_user.id

    success, message, order = await db.atomic_pay_order_from_wallet(user_id, order_code)

    if not success:
        await call.answer(message, show_alert=True)
        return

    await call.answer("✅ پرداخت با موفقیت انجام شد!", show_alert=True)
    await call.message.edit_text(
        "✅ <b>پرداخت شما با موفقیت ثبت گردید!</b>\n\n"
        f"📦 سفارش: <b>{order['title']}</b>\n"
        f"🔖 کد رهگیری: <code>{order_code}</code>\n"
        f"💵 مبلغ پرداختی: <b>{order['final_price']:,} تومان</b>\n\n"
        "🚀 <i>سفارش شما به صف تحویل خودکار فرستاده شد...</i>"
    )

    await FulfillmentService.deliver_order(bot, order_code)


# ---------------------------------------------------------------------------
# 2. Use Discount Balance (موجودی تخفیف هدیه)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:use_discount:"))
async def pay_use_discount_balance(call: CallbackQuery) -> None:
    order_code = call.data.split(":")[2]
    user_id = call.from_user.id

    success, msg, new_price = await db.apply_discount_balance(user_id, order_code)
    await call.answer(msg, show_alert=True)

    if not success:
        return

    order = await db.get_order(order_code)
    user = await db.get_user(user_id)
    user_balance = user["balance"] if user else 0
    discount_balance = user["discount_balance"] if user else 0

    text = (
        "🧾 <b>پیش فاکتور سفارش (با کسر تخفیف):</b>\n"
        "────────────────────\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"🔖 کد سفارش: <code>{order_code}</code>\n"
        f"💵 مبلغ اولیه: <s>{order['gross_price']:,} تومان</s>\n"
        f"🎁 تخفیف کسر شده: <b>{order['discount_used']:,} تومان</b>\n"
        f"💰 مبلغ نهایی قابل پرداخت: <b>{new_price:,} تومان</b>\n"
        f"👛 موجودی کیف پول: <b>{user_balance:,} تومان</b>\n"
        "────────────────────"
    )

    markup = invoice_kb(
        order_code=order_code,
        user_balance=user_balance,
        final_price=new_price,
        user_discount_balance=discount_balance,
        has_discount_code=bool(order["discount_code"]),
        has_discount_balance_used=True
    )
    await call.message.edit_text(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# 3. Discount Code Application (In-Place Edit)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:discount:"))
async def prompt_discount_code(call: CallbackQuery, state: FSMContext) -> None:
    order_code = call.data.split(":")[2]
    await state.update_data(discount_order_code=order_code, prompt_msg_id=call.message.message_id)
    await state.set_state(DiscountFlow.waiting_for_code)
    await call.answer()
    await call.message.edit_text(
        f"🎟 <b>اعمال کد تخفیف:</b>\n\n"
        f"برای سفارش: <code>{order_code}</code>\n"
        "لطفاً کد تخفیف خود را ارسال کنید:\n"
        "📌 مثال: <code>WelcomeCode</code>",
        reply_markup=ikb([[btn("🔙 بازگشت به پیش فاکتور", callback_data=f"inv:refresh:{order_code}", style=STYLE_DANGER)]])
    )


@router.callback_query(F.data.startswith("inv:refresh:"))
async def refresh_invoice_callback(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    order_code = call.data.split(":")[2]
    order = await db.get_order(order_code)
    if not order:
        await call.answer("سفارش یافت نشد.", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    user_balance = user["balance"] if user else 0
    discount_balance = user["discount_balance"] if user else 0

    text = (
        "🧾 <b>پیش فاکتور سفارش:</b>\n"
        "────────────────────\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"🔖 کد سفارش: <code>{order_code}</code>\n"
        f"💵 مبلغ: <b>{order['final_price']:,} تومان</b>\n"
        f"👛 موجودی کیف پول: <b>{user_balance:,} تومان</b>\n"
        "────────────────────\n"
        "⏳ <i>اعتبار پیش فاکتور: ۱۵ دقیقه</i>"
    )

    markup = invoice_kb(
        order_code=order_code,
        user_balance=user_balance,
        final_price=order["final_price"],
        user_discount_balance=discount_balance,
        has_discount_code=bool(order["discount_code"]),
        has_discount_balance_used=(order["discount_used"] > 0)
    )
    await call.message.edit_text(text, reply_markup=markup)


@router.message(DiscountFlow.waiting_for_code, F.text)
async def process_discount_code(message: Message, state: FSMContext) -> None:
    if message.text.strip() in MAIN_BUTTONS or message.text.strip() in ("❌ انصراف و بازگشت به منو", "/cancel", "انصراف"):
        await state.clear()
        return

    data = await state.get_data()
    order_code = data.get("discount_order_code")
    prompt_id = data.get("prompt_msg_id")
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    if not order_code:
        await message.answer("❌ اطلاعات سفارش یافت نشد.")
        return

    code_str = message.text.strip()
    success, result_msg, new_price = await db.apply_discount_code(
        user_id=message.from_user.id,
        order_code=order_code,
        code_str=code_str
    )

    order = await db.get_order(order_code)
    user = await db.get_user(message.from_user.id)
    user_balance = user["balance"] if user else 0
    discount_balance = user["discount_balance"] if user else 0

    if not success:
        fail_text = (
            f"❌ <b>خطا در اعمال کد تخفیف:</b>\n{result_msg}\n\n"
            f"سفارش: <code>{order_code}</code>"
        )
        fail_markup = ikb([
            [btn("🔄 تلاش مجدد", callback_data=f"pay:discount:{order_code}", style=STYLE_PRIMARY)],
            [btn("🔙 بازگشت به پیش فاکتور", callback_data=f"inv:refresh:{order_code}", style=STYLE_DANGER)],
        ])
        if prompt_id:
            try:
                await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=fail_text, reply_markup=fail_markup)
                return
            except Exception:
                pass
        await message.answer(fail_text, reply_markup=fail_markup)
        return

    text = (
        f"{result_msg}\n\n"
        "🧾 <b>پیش فاکتور با تخفیف به روزرسانی شد:</b>\n"
        "────────────────────\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"🔖 کد سفارش: <code>{order_code}</code>\n"
        f"🏷 کد اعمال شده: <code>{code_str}</code>\n"
        f"💵 مبلغ قابل پرداخت جدید: <b>{new_price:,} تومان</b>\n"
        f"👛 موجودی کیف پول: <b>{user_balance:,} تومان</b>\n"
        "────────────────────"
    )

    markup = invoice_kb(
        order_code=order_code,
        user_balance=user_balance,
        final_price=new_price,
        user_discount_balance=discount_balance,
        has_discount_code=True,
        has_discount_balance_used=(order["discount_used"] > 0)
    )

    if prompt_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=text, reply_markup=markup)
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# 4. Online Rial Payment Gateway
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:online:"))
async def pay_online(call: CallbackQuery) -> None:
    order_code = call.data.split(":")[2]
    order = await db.get_order(order_code)
    if not order:
        await call.answer("سفارش یافت نشد.", show_alert=True)
        return

    success, url_or_msg, _ = await PaymentGatewayService.create_rial_payment(
        user_id=call.from_user.id,
        order_code=order_code,
        amount_toman=order["final_price"]
    )
    await call.answer(url_or_msg, show_alert=True)


# ---------------------------------------------------------------------------
# 5. Order Cancellation
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("order:cancel"))
async def cancel_order(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    parts = call.data.split(":")
    if len(parts) > 2:
        order_code = parts[2]
        conn = await db.get_connection()
        try:
            await conn.execute("UPDATE orders SET status = 'cancelled' WHERE code = ?", (order_code,))
            await conn.commit()
        finally:
            await conn.close()

    await call.message.edit_text("❌ پیش فاکتور با موفقیت لغو شد.")
