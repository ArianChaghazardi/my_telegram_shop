# -*- coding: utf-8 -*-
"""Shops catalog, product selection, and order draft creation."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.core.database import db
from config import GIFTS_CATALOG, GIFT_BY_KEY, PREMIUM_PLANS
from bot.keyboards import (
    stars_menu_kb,
    premium_menu_kb,
    gifts_grid_kb,
    recipient_kb,
    invoice_kb,
    products_menu_kb,
    main_reply_keyboard,
    MAIN_BUTTONS,
)
from bot.keyboards.shops import (
    gift_anonymous_kb,
    gift_comment_kb,
    crypto_buy_menu_kb,
)

log = logging.getLogger(__name__)
router = Router(name="shops")


class ShopFlow(StatesGroup):
    stars_custom_qty = State()
    stars_recipient = State()
    premium_recipient = State()
    gift_anonymous = State()
    gift_recipient = State()
    gift_comment = State()
    crypto_amount = State()
    crypto_address = State()
    reaction_link = State()
    reaction_qty = State()


def is_menu_navigation(text: str) -> bool:
    """Check if input text is a navigation button or cancellation."""
    return text in MAIN_BUTTONS or text in ("❌ انصراف و بازگشت به منو", "/cancel", "انصراف", "/start")


# ---------------------------------------------------------------------------
# Navigation & Cancellation
# ---------------------------------------------------------------------------

@router.message(F.text.in_({"❌ انصراف و بازگشت به منو", "/cancel", "انصراف"}))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ عملیات لغو شد و به منوی اصلی بازگشتید.", reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "shop:main")
async def shop_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "🛍 <b>فهرست محصولات و خدمات تلگرام:</b>\n\nلطفاً دسته بندی را انتخاب کنید:",
        reply_markup=products_menu_kb()
    )


# ---------------------------------------------------------------------------
# 1. Telegram Stars Shop
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop:stars")
async def shop_stars(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    rate = await db.get_setting("price_per_star", "4520")
    await call.message.edit_text(
        "⭐ <b>خرید استارز تلگرام (Telegram Stars)</b>\n\n"
        f"💵 نرخ هر استارز: <b>{int(float(rate)):,} تومان</b>\n"
        "حداقل سفارش: ۵۰ عدد\n"
        "⚡️ تحویل کاملاً خودکار و فوری بدون نیاز به لاگین\n\n"
        "لطفاً یکی از بسته ها را انتخاب کنید یا تعداد دلخواه را وارد نمایید 👇",
        reply_markup=stars_menu_kb()
    )


@router.callback_query(F.data.startswith("stars:pack:"))
async def stars_pack_pick(call: CallbackQuery, state: FSMContext) -> None:
    qty = int(call.data.split(":")[2])
    rate = int(float(await db.get_setting("price_per_star", "4520")))
    if qty == 50:
        price = int(float(await db.get_setting("stars_price_50", "226000")))
    else:
        price = qty * rate

    await state.update_data(kind="stars", qty=qty, price=price, title=f"خرید {qty} استارز تلگرام")
    await state.set_state(ShopFlow.stars_recipient)
    await call.message.edit_text(
        f"⭐ سفارش: <b>{qty} استارز تلگرام</b>\n"
        f"💵 مبلغ: <b>{price:,} تومان</b>\n\n"
        "👤 <b>استارزها به چه حسابی ارسال شوند؟</b>\n"
        "می توانید دکمه «برای خودم» را بزنید یا <b>آیدی عددی / یوزرنیم</b> گیرنده را ارسال کنید:",
        reply_markup=recipient_kb(call.from_user.first_name, back_callback="shop:stars")
    )


@router.callback_query(F.data == "stars:custom")
async def stars_custom_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ShopFlow.stars_custom_qty)
    await call.message.edit_text(
        "✍️ <b>لطفاً تعداد استارز مورد نیاز خود را به عدد ارسال کنید:</b>\n"
        "📌 حداقل: ۵۰ عدد | حداکثر: ۵,۰۰۰ عدد"
    )


@router.message(ShopFlow.stars_custom_qty, F.text)
async def stars_custom_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    text = message.text.strip().replace(",", "")
    if not text.isdigit() or int(text) < 50:
        await message.answer("❌ تعداد نامعتبر است! حداقل تعداد خرید ۵۰ استارز می باشد. دوباره ارسال کنید:")
        return

    qty = int(text)
    rate = int(float(await db.get_setting("price_per_star", "4520")))
    price = qty * rate
    await state.update_data(kind="stars", qty=qty, price=price, title=f"خرید {qty} استارز تلگرام")
    await state.set_state(ShopFlow.stars_recipient)
    await message.answer(
        f"⭐ سفارش: <b>{qty} استارز تلگرام</b>\n"
        f"💵 مبلغ: <b>{price:,} تومان</b>\n\n"
        "👤 استارزها به چه حسابی ارسال شوند؟\n"
        "یوزرنیم یا آیدی عددی گیرنده را ارسال کنید:",
        reply_markup=recipient_kb(message.from_user.first_name, back_callback="shop:stars")
    )


@router.callback_query(F.data == "stars:calc_balance")
async def stars_calc_balance(call: CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(call.from_user.id)
    balance = user["balance"] if user else 0
    rate = int(float(await db.get_setting("price_per_star", "4520")))
    possible_stars = balance // rate

    if possible_stars < 50:
        need = (50 * rate) - balance
        await call.answer(
            f"❌ موجودی شما ({balance:,} تومان) کمتر از حداقل خرید ۵۰ استارز است.\n"
            f"کسری برای ۵۰ استارز: {need:,} تومان",
            show_alert=True
        )
        return

    price = possible_stars * rate
    await state.update_data(kind="stars", qty=possible_stars, price=price, title=f"خرید {possible_stars} استارز با موجودی")
    await state.set_state(ShopFlow.stars_recipient)
    await call.message.edit_text(
        f"🧮 بر اساس موجودی شما ({balance:,} تومان)، می توانید <b>{possible_stars} استارز</b> خریداری کنید.\n"
        f"💵 مبلغ: <b>{price:,} تومان</b>\n\n"
        "گیرنده استارز چه کسی باشد؟",
        reply_markup=recipient_kb(call.from_user.first_name, back_callback="shop:stars")
    )


# ---------------------------------------------------------------------------
# Recipient Handling & Invoice Creation
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "recipient:self")
async def recipient_self(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    username = call.from_user.username
    recipient = f"@{username}" if username else str(call.from_user.id)
    await state.clear()
    await create_and_display_invoice(call.message, call.from_user.id, data, recipient)


@router.message(ShopFlow.stars_recipient, F.text)
@router.message(ShopFlow.premium_recipient, F.text)
async def recipient_text_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    data = await state.get_data()
    recipient = message.text.strip()
    await state.clear()
    await create_and_display_invoice(message, message.from_user.id, data, recipient)


async def create_and_display_invoice(message_or_target: any, user_id: int, data: dict, recipient: str) -> None:
    """Create draft order and present invoice with full zero-price protection."""
    gross_price = data.get("price", 0)
    title = data.get("title", "")
    kind = data.get("kind", "")
    qty = data.get("qty", 1)
    extra = data.get("extra", "")

    # Zero-price and stale state guard
    if not data or gross_price <= 0 or not title or not kind:
        text_fail = "❌ اطلاعات سفارش منقضی شده است. لطفاً محصول مورد نظر را مجدداً از منو انتخاب فرمایید."
        if isinstance(message_or_target, Message):
            await message_or_target.answer(text_fail, reply_markup=products_menu_kb())
        else:
            await message_or_target.edit_text(text_fail, reply_markup=products_menu_kb())
        return

    order_code = await db.create_order(
        user_id=user_id,
        kind=kind,
        title=title,
        qty=qty,
        recipient=recipient,
        gross_price=gross_price,
        final_price=gross_price,
        extra=extra
    )

    user = await db.get_user(user_id)
    user_balance = user["balance"] if user else 0
    discount_balance = user["discount_balance"] if user else 0

    extra_info = ""
    if "comment" in extra:
        extra_info = "\n💬 متن پیام گیفت: ثبت شد"

    text = (
        "🧾 <b>پیش فاکتور سفارش:</b>\n"
        "────────────────────\n"
        f"📦 محصول: <b>{title}</b>\n"
        f"👤 گیرنده: <code>{recipient}</code>{extra_info}\n"
        f"🔖 کد سفارش: <code>{order_code}</code>\n"
        f"💵 مبلغ کل: <b>{gross_price:,} تومان</b>\n"
        f"👛 موجودی کیف پول شما: <b>{user_balance:,} تومان</b>\n"
    )
    if discount_balance > 0:
        text += f"🎁 موجودی تخفیف شما: <b>{discount_balance:,} تومان</b>\n"

    text += (
        "────────────────────\n"
        "⏳ <i>اعتبار پیش فاکتور: ۱۵ دقیقه</i>\n\n"
        "برای نهایی کردن سفارش، یکی از گزینه های زیر را انتخاب کنید:"
    )

    markup = invoice_kb(
        order_code=order_code,
        user_balance=user_balance,
        final_price=gross_price,
        user_discount_balance=discount_balance,
        has_discount_code=False,
        has_discount_balance_used=False
    )
    if isinstance(message_or_target, Message):
        await message_or_target.answer(text, reply_markup=markup)
    else:
        await message_or_target.edit_text(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# 2. Telegram Premium Shop
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop:premium")
async def shop_premium(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    p3 = int(float(await db.get_setting("premium_3", "3650000")))
    p6 = int(float(await db.get_setting("premium_6", "4870000")))
    p12 = int(float(await db.get_setting("premium_12", "8820000")))

    await call.message.edit_text(
        "💎 <b>خرید اشتراک تلگرام پرمیوم (Telegram Premium)</b>\n\n"
        f"🔹 ۳ ماهه: <b>{p3:,} تومان</b>\n"
        f"🔹 ۶ ماهه: <b>{p6:,} تومان</b>\n"
        f"🔹 ۱۲ ماهه (یک ساله): <b>{p12:,} تومان</b>\n\n"
        "✅ فعال سازی رسمی بدون لاگین روی اکانت (فقط با یوزرنیم)\n"
        "مدت زمان اشتراک مورد نظر را انتخاب کنید:",
        reply_markup=premium_menu_kb()
    )


@router.callback_query(F.data.startswith("prem:"))
async def premium_pick(call: CallbackQuery, state: FSMContext) -> None:
    months = int(call.data.split(":")[1])
    key = PREMIUM_PLANS[months]
    price = int(float(await db.get_setting(key, "3650000")))
    await state.update_data(kind="premium", qty=months, price=price, title=f"تلگرام پرمیوم ({months} ماهه)")
    await state.set_state(ShopFlow.premium_recipient)
    await call.message.edit_text(
        f"💎 سفارش: <b>تلگرام پرمیوم {months} ماهه</b>\n"
        f"💵 مبلغ: <b>{price:,} تومان</b>\n\n"
        "👤 یوزرنیم گیرنده اشتراک را ارسال کنید (مثال: @username):",
        reply_markup=recipient_kb(call.from_user.first_name, back_callback="shop:premium")
    )


# ---------------------------------------------------------------------------
# 3. Telegram Gifts Shop (Complete Flow: Anon toggle + Custom Comment)
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop:gifts")
async def shop_gifts(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "🎁 <b>خرید و ارسال گیفت های تلگرام (Telegram Gifts)</b>\n\n"
        "گیفت مورد نظر خود را از لیست زیر انتخاب کنید 👇",
        reply_markup=gifts_grid_kb()
    )


@router.callback_query(F.data.startswith("gift:pick:"))
async def gift_pick(call: CallbackQuery, state: FSMContext) -> None:
    gift_key = call.data.split(":")[2]
    gift = GIFT_BY_KEY.get(gift_key)
    if not gift:
        await call.answer("گیفت یافت نشد.")
        return

    await state.update_data(
        kind="gift",
        qty=1,
        price=gift["price"],
        title=f"گیفت {gift['name']}",
        gift_key=gift_key,
        extra=f"gift_key={gift_key}"
    )
    await state.set_state(ShopFlow.gift_anonymous)
    await call.message.edit_text(
        f"🎁 سفارش: <b>{gift['name']}</b> ({gift['stars']} استارز)\n"
        f"💵 قیمت: <b>{gift['price']:,} تومان</b>\n\n"
        "آیا مایلید این گیفت با نام شما ارسال شود یا به صورت ناشناس؟",
        reply_markup=gift_anonymous_kb()
    )


@router.callback_query(F.data.startswith("gift:anon:"), ShopFlow.gift_anonymous)
async def gift_anon_pick(call: CallbackQuery, state: FSMContext) -> None:
    is_anon = call.data.split(":")[2] == "1"
    data = await state.get_data()
    data["is_anonymous"] = is_anon
    await state.set_data(data)
    await state.set_state(ShopFlow.gift_recipient)
    await call.message.edit_text(
        "👤 <b>این گیفت برای چه حسابی ارسال شود؟</b>\n\n"
        "می توانید دکمه «برای خودم» را بزنید یا آیدی عددی / یوزرنیم گیرنده را بفرستید:",
        reply_markup=recipient_kb(call.from_user.first_name, back_callback="shop:gifts")
    )


@router.message(ShopFlow.gift_recipient, F.text)
async def gift_recipient_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    recipient = message.text.strip()
    data = await state.get_data()
    data["recipient"] = recipient
    await state.set_data(data)
    await state.set_state(ShopFlow.gift_comment)
    await message.answer(
        "💬 <b>آیا می خواهید متنی همراه گیفت ثبت شود؟</b>\n\n"
        "می توانید متن دلخواه خود را تایپ و ارسال کنید (حداکثر ۱۲۸ کاراکتر) یا دکمه «بدون متن» را بزنید:",
        reply_markup=gift_comment_kb()
    )


@router.callback_query(F.data == "gift:comment:skip", ShopFlow.gift_comment)
async def gift_comment_skip(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    recipient = data.get("recipient", "")
    await state.clear()
    await create_and_display_invoice(call.message, call.from_user.id, data, recipient)


@router.message(ShopFlow.gift_comment, F.text)
async def gift_comment_text(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    comment = message.text.strip()[:128]
    data = await state.get_data()
    data["extra"] = f"{data.get('extra', '')};comment={comment};anon={data.get('is_anonymous', False)}"
    recipient = data.get("recipient", "")
    await state.clear()
    await create_and_display_invoice(message, message.from_user.id, data, recipient)


# ---------------------------------------------------------------------------
# 4. Crypto Shop (TON / TRX Buy Flow)
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop:crypto")
async def shop_crypto_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    ton_price = int(float(await db.get_setting("ton_personal_price", "330000")))
    trx_price = int(float(await db.get_setting("trx_price", "95000")))

    await call.message.edit_text(
        "🪙 <b>خرید آنلاین ارز دیجیتال (انتقال مستقیم به ولت):</b>\n\n"
        f"💎 نرخ هر ۱ واحد تون (TON): <b>{ton_price:,} تومان</b>\n"
        f"🔴 نرخ هر ۱ واحد ترون (TRX): <b>{trx_price:,} تومان</b>\n\n"
        "ارز مورد نظر خود را جهت خرید انتخاب کنید 👇",
        reply_markup=crypto_buy_menu_kb()
    )


@router.callback_query(F.data.startswith("crypto:buy:"))
async def crypto_buy_start(call: CallbackQuery, state: FSMContext) -> None:
    curr = call.data.split(":")[2].upper()
    setting_key = "ton_personal_price" if curr == "TON" else "trx_price"
    rate = int(float(await db.get_setting(setting_key, "330000")))

    await state.update_data(crypto_curr=curr, crypto_rate=rate)
    await state.set_state(ShopFlow.crypto_amount)
    await call.message.edit_text(
        f"🪙 <b>خرید {curr}:</b>\n\n"
        f"💵 نرخ هر واحد: <b>{rate:,} تومان</b>\n"
        f"✍️ لطفاً تعداد واحد {curr} مورد نیاز خود را به عدد ارسال کنید (حداقل ۱):"
    )


@router.message(ShopFlow.crypto_amount, F.text)
async def crypto_amount_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    text = message.text.strip().replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ مقدار نامعتبر است! لطفاً یک عدد معتبر ارسال کنید:")
        return

    data = await state.get_data()
    curr = data.get("crypto_curr", "TON")
    rate = data.get("crypto_rate", 330000)
    price = int(amount * rate)

    await state.update_data(qty=amount, price=price, title=f"خرید {amount} واحد {curr}")
    await state.set_state(ShopFlow.crypto_address)
    await message.answer(
        f"🪙 سفارش: <b>{amount} {curr}</b>\n"
        f"💵 مبلغ: <b>{price:,} تومان</b>\n\n"
        f"👛 لطفاً <b>آدرس کیف پول {curr}</b> مقصد را ارسال فرمایید:"
    )


@router.message(ShopFlow.crypto_address, F.text)
async def crypto_address_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    address = message.text.strip()
    data = await state.get_data()
    data["kind"] = "crypto"
    data["extra"] = f"wallet={address}"
    await state.clear()
    await create_and_display_invoice(message, message.from_user.id, data, recipient=address)


# ---------------------------------------------------------------------------
# 5. Reactions & Boost
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop:reactions")
async def shop_reactions(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ShopFlow.reaction_link)
    await call.message.edit_text(
        "❤️ <b>خرید ری اکشن تلگرام (تلگرام استارز ری اکشن)</b>\n\n"
        "🔗 لطفاً لینک پست عمومی کانال را ارسال کنید:\n"
        "📌 مثال: <code>https://t.me/channel/123</code>"
    )


@router.message(ShopFlow.reaction_link, F.text)
async def reaction_link_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await message.answer("❌ لینک پست نامعتبر است! باید با https://t.me/ شروع شود.")
        return
    await state.update_data(post_link=link)
    await state.set_state(ShopFlow.reaction_qty)
    await message.answer(
        "🔢 لطفاً تعداد ری اکشن مورد نظر را وارد کنید (حداقل ۱۰ عدد):"
    )


@router.message(ShopFlow.reaction_qty, F.text)
async def reaction_qty_input(message: Message, state: FSMContext) -> None:
    if is_menu_navigation(message.text.strip()):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text.isdigit() or int(text) < 10:
        await message.answer("❌ حداقل سفارش ری اکشن ۱۰ عدد می باشد.")
        return
    qty = int(text)
    rate_10 = int(float(await db.get_setting("reaction_price_per_10", "4500")))
    price = int((qty / 10) * rate_10)
    data = await state.get_data()
    link = data.get("post_link", "")
    await state.clear()

    data_payload = {
        "kind": "reaction",
        "qty": qty,
        "price": price,
        "title": f"❤️ ری اکشن تلگرام ({qty} عدد)",
        "extra": f"link={link}"
    }
    await create_and_display_invoice(message, message.from_user.id, data_payload, recipient=link)


@router.callback_query(F.data == "shop:boost")
async def shop_boost(call: CallbackQuery) -> None:
    await call.answer(
        "🚀 بوست کانال به زودی فعال خواهد شد.",
        show_alert=True
    )
