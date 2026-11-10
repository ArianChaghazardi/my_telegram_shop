# -*- coding: utf-8 -*-
"""Main entry point for the Telegram Shop platform."""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import settings
from bot.core.database import db
from bot.handlers import main_router
from bot.middlewares import ThrottlingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("main")


async def main() -> None:
    if not settings.BOT_TOKEN or settings.BOT_TOKEN.startswith("123456789:"):
        log.error("BOT_TOKEN is not configured! Please edit your .env file.")
        print("\n⚠️ خطا: توکن ربات تنظیم نشده است!")
        print("لطفاً فایل .env را باز کنید و BOT_TOKEN خود را درون آن قرار دهید.\n")
        return

    # 1. Initialize Async Database & WAL mode
    log.info("Initializing database at: %s", settings.DB_PATH)
    await db.init()

    # 2. Setup Bot & Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 3. Middlewares
    dp.message.middleware(ThrottlingMiddleware(rate_limit_seconds=0.5))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit_seconds=0.5))

    # 4. Routers
    dp.include_router(main_router)

    # 5. Clear any old active webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # 6. Start Polling
    me = await bot.get_me()
    log.info("Bot started successfully as @%s (ID: %s)", me.username, me.id)
    print(f"\n🚀 ربات با موفقیت روی اکانت @{me.username} روشن شد و آماده دریافت سفارش است!\n")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        log.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Application terminated.")
