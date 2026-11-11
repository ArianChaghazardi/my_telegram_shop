# -*- coding: utf-8 -*-
"""Wallet management, balance overview, and top-up flows."""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.core.database import db
from config import settings
from bot.keyboards import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER
from bot.keyboards.reply import LBL_TOPUP

log = logging.getLogger(__name__)
router = Router(name="wallet")


class WalletFlow(StatesGroup):
    topup_amount = State()
    crypto_hash = State()


def wallet_menu_kb() -> any:
    return ikb([
        [btn("💳 شارژ با درگاه آنلاین بانکی", callback_data="topup:rial", style=STYLE_SUCCESS)],
        [btn("🪙 شارژ با ارز دیجیتال (TON / TRX)", callback_data="topup:crypto", style=STYLE_PRIMARY)],
        [btn("🔙 بستن", callback_data="menu:close", style=STYLE_DANGER)],
    ])


@router.message(F.text == LBL_TOPUP)
@router.callback_query(F.data == "topup:start")
async def show_wallet_overview(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    user = await db.get_user(user_id)
    if not user:
        user = await db.get_or_create_user(user_id, event.from_user.full_name)

    balance = user["balance"]
    discount_bal = user["discount_balance"]
    points = user["points"]

    text = (
        "💼 <b>کیف پول و موجودی حساب شما:</b>\n\n"
        f"💵 موجودی اصلی: <b>{balance:,} تومان</b>\n"
        f"🎁 موجودی تخفیف هدیه: <b>{discount_bal:,} تومان</b>\n"
        f"⭐️ امتیاز باشگاه مشتریان: <b>{points:,} امتیاز</b>\n\n"
        "جهت افزایش موجودی کیف پول، یکی از روش های زیر را انتخاب نمایید 👇"
    )

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=wallet_menu_kb())
        except Exception:
            await event.message.answer(text, reply_markup=wallet_menu_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=wallet_menu_kb())


@router.callback_query(F.data == "topup:rial")
async def topup_rial(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        "💳 <b>افزایش موجودی ریالی (درگاه آنلاین):</b>\n\n"
        "درگاه پرداخت آنلاین شتابی در حال حاضر در حال به روزرسانی سیستم شاپرک می باشد.\n"
        "می توانید موجودی خود را از طریق ارز دیجیتال شارژ فرمایید یا به پشتیبانی پیام دهید.",
        reply_markup=ikb([[btn("🔙 بازگشت", callback_data="topup:start", style=STYLE_DANGER)]])
    )


@router.callback_query(F.data == "topup:crypto")
async def topup_crypto(call: CallbackQuery, state: FSMContext) -> None:
    wallet_address = await db.get_setting("wallet_address", "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    user_memo = f"{call.from_user.id}"

    text = (
        "🪙 <b>شارژ خودکار با ارز دیجیتال تونکوین (TON):</b>\n\n"
        "برای شارژ حساب، معادل مبلغ مورد نظر را به آدرس زیر واریز کنید:\n\n"
        f"👛 <b>آدرس کیف پول:</b>\n<code>{wallet_address}</code>\n\n"
        f"🏷 <b>ممو (Memo / Comment) الزامی:</b>\n<code>{user_memo}</code>\n\n"
        "⚠️ <b>بسیار مهم:</b> حتماً شناسه ممو را در هنگام انتقال وارد کنید تا واریزی به حساب شما اعمال شود.\n\n"
        "پس از انجام تراکنش، دکمه «ثبت هش تراکنش» را بزنید:"
    )

    markup = ikb([
        [btn("📝 ثبت هش تراکنش (TX Hash)", callback_data="topup:send_hash", style=STYLE_SUCCESS)],
        [btn("🔙 بازگشت", callback_data="topup:start", style=STYLE_DANGER)],
    ])
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "topup:send_hash")
async def topup_send_hash_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WalletFlow.crypto_hash)
    await state.update_data(prompt_msg_id=call.message.message_id)
    await call.message.edit_text(
        "✍️ لطفاً <b>هش تراکنش (TX Hash)</b> یا شناسه انتقال را ارسال کنید:",
        reply_markup=ikb([[btn("🔙 بازگشت به کیف پول", callback_data="topup:start", style=STYLE_DANGER)]])
    )


@router.message(WalletFlow.crypto_hash, F.text)
async def topup_crypto_hash_received(message: Message, state: FSMContext, bot: Bot) -> None:
    from bot.keyboards.reply import MAIN_BUTTONS
    if message.text.strip() in MAIN_BUTTONS or message.text.strip() in ("❌ انصراف و بازگشت به منو", "/cancel", "انصراف"):
        await state.clear()
        return

    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    tx_hash = message.text.strip()
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    success_text = (
        "✅ هش تراکنش با موفقیت ثبت شد و در صف تایید قرار گرفت.\n"
        "پس از تایید روی شبکه بلاکچین، موجودی به کیف پول شما افزوده خواهد شد."
    )
    markup = ikb([[btn("🔙 بازگشت به کیف پول", callback_data="topup:start", style=STYLE_PRIMARY)]])

    if prompt_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_id,
                text=success_text,
                reply_markup=markup
            )
        except Exception:
            await message.answer(success_text, reply_markup=markup)
    else:
        await message.answer(success_text, reply_markup=markup)

    # Notify Admins
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    "🔔 <b>اعلام واریز کریپتو:</b>\n"
                    f"👤 کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                    f"🔗 هش: <code>{tx_hash}</code>\n"
                    "از پنل مدیریت می توانید موجودی را شارژ کنید."
                )
            )
        except Exception:
            pass
