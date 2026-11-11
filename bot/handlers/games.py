# -*- coding: utf-8 -*-
"""Daily challenges: Dice and Bowling for free discount rewards."""

import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from bot.core.database import db
from bot.keyboards import btn, ikb, STYLE_SUCCESS, STYLE_PRIMARY, STYLE_DANGER

router = Router(name="games")


def games_menu_kb(dice_done: bool = False, bowling_done: bool = False) -> any:
    dice_lbl = "🎲 پرتاب تاس شانس" if not dice_done else "🎲 پرتاب تاس شانس (انجام شد ✅)"
    bowling_lbl = "🎳 چالش بولینگ" if not bowling_done else "🎳 چالش بولینگ (انجام شد ✅)"
    return ikb([
        [btn(dice_lbl, callback_data="game:play:dice", style=STYLE_SUCCESS if not dice_done else STYLE_PRIMARY)],
        [btn(bowling_lbl, callback_data="game:play:bowling", style=STYLE_SUCCESS if not bowling_done else STYLE_PRIMARY)],
        [btn("🔙 بستن", callback_data="menu:close", style=STYLE_DANGER)],
    ])


@router.callback_query(F.data == "games:menu")
async def show_games_menu(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    today = datetime.date.today().isoformat()
    dice_done = (user["dice_last"] == today) if user else False
    bowling_done = (user["bowling_last"] == today) if user else False

    await call.message.edit_text(
        "🎮 <b>چالش های روزانه و دریافت تخفیف رایگان:</b>\n\n"
        "هر روز می توانید شانس خود را امتحان کنید و به ازای امتیاز خود، <b>موجودی تخفیف رایگان</b> هدیه بگیرید که در خریدهایتان کسر می شود!\n\n"
        "یکی از بازی های زیر را انتخاب کنید 👇",
        reply_markup=games_menu_kb(dice_done, bowling_done)
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
        await call.answer("⚠️ شما امروز این چالش را انجام داده اید! فردا دوباره منتظرتان هستیم 🎉", show_alert=True)
        return

    await call.message.delete()
    emoji = "🎲" if game_type == "dice" else "🎳"
    dice_msg = await bot.send_dice(chat_id=user_id, emoji=emoji)
    score = dice_msg.dice.value

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
            "می توانید در خریدهای بعدی از این تخفیف به صورت مستقیم در پیش فاکتور استفاده نمایید."
        )
    )
