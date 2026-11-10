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
from bot.keyboards import invoice_kb

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

    # Execute atomic deduction & order update
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

    # Trigger automatic fulfillment immediately
    await FulfillmentService.deliver_order(bot, order_code)


# ---------------------------------------------------------------------------
# 2. Discount Code Application (Anti-Abuse & Single-Use)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:discount:"))
async def prompt_discount_code(call: CallbackQuery, state: FSMContext) -> None:
    order_code = call.data.split(":")[2]
    await state.update_data(discount_order_code=order_code)
    await state.set_state(DiscountFlow.waiting_for_code)
    await call.answer()
    await call.message.answer(
        "🎟 <b>اعمال کد تخفیف:</b>\n\n"
        "لطفاً کد تخفیف خود را ارسال کنید:\n"
        "📌 مثال: <code>WelcomeCode</code>"
    )


@router.message(DiscountFlow.waiting_for_code, F.text)
async def process_discount_code(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_code = data.get("discount_order_code")
    await state.clear()

    if not order_code:
        await message.answer("❌ اطلاعات سفارش یافت نشد.")
        return

    code_str = message.text.strip()
    success, result_msg, new_price = await db.apply_discount_code(
        user_id=message.from_user.id,
        order_code=order_code,
        code_str=code_str
    )

    if not success:
        await message.answer(result_msg)
        return

    order = await db.get_order(order_code)
    user = await db.get_user(message.from_user.id)
    user_balance = user["balance"] if user else 0

    await message.answer(
        f"{result_msg}\n\n"
        "🧾 <b>پیش‌فاکتور با تخفیف به‌روزرسانی شد:</b>\n"
        "────────────────────\n"
        f"📦 محصول: <b>{order['title']}</b>\n"
        f"👤 گیرنده: <code>{order['recipient']}</code>\n"
        f"🔖 کد سفارش: <code>{order_code}</code>\n"
        f"🏷 کد اعمال‌شده: <code>{code_str}</code>\n"
        f"💵 مبلغ قابل پرداخت جدید: <b>{new_price:,} تومان</b>\n"
        f"👛 موجودی کیف پول: <b>{user_balance:,} تومان</b>\n"
        "────────────────────",
        reply_markup=invoice_kb(order_code, user_balance, new_price, has_discount_code=True)
    )


# ---------------------------------------------------------------------------
# 3. Online Rial Payment Gateway
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
# 4. Order Cancellation
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

    await call.message.edit_text("❌ پیش‌فاکتور با موفقیت لغو شد.")
