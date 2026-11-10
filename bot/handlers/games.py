# -*- coding: utf-8 -*-
"""Daily challenges: Dice and Bowling for free discount rewards."""

import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from bot.core.database import db
from bot.keyboards import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER

router = Router(name="games")


def games_menu_kb() -> any:
    return ikb([
        [btn("🎲 پرتاب تاس شانس", callback_data="game:play:dice", style=STYLE_SUCCESS)],
        [btn("🎳 چالش بولینگ", callback_data="game:play:bowling", style=STYLE_PRIMARY)],
        [btn("🔙 بازگشت", callback_data="menu:close", style=STYLE_DANGER)],
    ])


@router.callback_query(F.data == "games:menu")
async def show_games_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🎮 <b>چالش‌های روزانه و دریافت تخفیف رایگان:</b>\n\n"
        "هر روز می‌توانید شانس خود را امتحان کنید و به ازای امتیاز خود، <b>موجودی تخفیف رایگان</b> هدیه بگیرید که در خریدهایتان کسر می‌شود!\n\n"
        "یکی از بازی‌های زیر را انتخاب کنید 👇",
        reply_markup=games_menu_kb()
    )


@router.callback_query(F.data.startswith("game:play:"))
async def play_game(call: CallbackQuery, bot: Bot) -> None:
    game_type = call.data.split(":")[2]
    user_id = call.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    today = datetime.date.today().isoformat()
    last_col = "dice_last" if game_type == "dice" else "bowling_last"

    if user[last_col] == today:
        await call.answer("⚠️ شما امروز این چالش را انجام داده‌اید! فردا دوباره تلاش کنید.", show_alert=True)
        return

    await call.message.delete()
    emoji = "🎲" if game_type == "dice" else "🎳"
    dice_msg = await bot.send_dice(chat_id=user_id, emoji=emoji)
    score = dice_msg.dice.value

    # Reward math: score * 300 Toman discount balance
    reward = score * 300
    conn = await db.get_connection()
    try:
        await conn.execute(
            f"UPDATE users SET discount_balance = discount_balance + ?, {last_col} = ? WHERE id = ?",
            (reward, today, user_id)
        )
        await conn.commit()
    finally:
        await conn.close()

    await bot.send_message(
        chat_id=user_id,
        text=(
            f"🎉 <b>آفرین! امتیاز شما: {score}</b>\n"
            f"🎁 جایزه: <b>{reward:,} تومان موجودی تخفیف</b> به حساب شما افزوده شد.\n"
            "می‌توانید در خریدهای بعدی از این تخفیف استفاده نمایید."
        )
    )
