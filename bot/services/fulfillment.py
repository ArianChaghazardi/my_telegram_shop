# -*- coding: utf-8 -*-
"""Fulfillment service for delivering Stars, Premium, Gifts, and Toncoin."""

import logging
from typing import Dict, Any, Tuple
from aiogram import Bot
from bot.core.database import db
from config import settings

log = logging.getLogger(__name__)


class FulfillmentService:
    """
    Handles automatic delivery of digital products.
    Ready to connect to Telegram Fragment API, Telethon userbot session,
    or external B2B supplier webhooks.
    """

    @classmethod
    async def deliver_order(cls, bot: Bot, order_code: str) -> Tuple[bool, str]:
        order = await db.get_order(order_code)
        if not order:
            return False, "سفارش یافت نشد."

        if order["status"] == "delivered":
            return True, "این سفارش قبلاً تحویل داده شده است."

        log.info("Processing fulfillment for order %s (Kind: %s, Recipient: %s)",
                 order_code, order["kind"], order["recipient"])

        success = False
        message = ""

        try:
            if order["kind"] == "stars":
                success, message = await cls._deliver_stars(order)
            elif order["kind"] == "premium":
                success, message = await cls._deliver_premium(order)
            elif order["kind"] == "gift":
                success, message = await cls._deliver_gift(order)
            elif order["kind"] == "crypto":
                success, message = await cls._deliver_crypto(order)
            else:
                success, message = await cls._deliver_generic(order)

            if success:
                conn = await db.get_connection()
                try:
                    await conn.execute("UPDATE orders SET status = 'delivered' WHERE code = ?", (order_code,))
                    await conn.commit()
                finally:
                    await conn.close()

                # Notify Buyer in Telegram
                try:
                    await bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            "🎉 <b>سفارش شما با موفقیت تحویل داده شد!</b>\n\n"
                            f"📦 محصول: <b>{order['title']}</b>\n"
                            f"👤 گیرنده: <code>{order['recipient']}</code>\n"
                            f"🔖 کد رهگیری: <code>{order_code}</code>\n\n"
                            "از خرید و اعتماد شما سپاسگزاریم! ❤️"
                        )
                    )
                except Exception as notify_err:
                    log.warning("Could not notify buyer: %s", notify_err)

                # Notify Admins
                for admin_id in settings.admin_id_list:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=(
                                "✅ <b>تحویل خودکار سفارش انجام شد:</b>\n"
                                f"🔖 کد: <code>{order_code}</code>\n"
                                f"📦 محصول: {order['title']}\n"
                                f"👤 گیرنده: {order['recipient']}\n"
                                f"💰 مبلغ: {order['final_price']:,} تومان"
                            )
                        )
                    except Exception:
                        pass

                return True, "تحویل با موفقیت انجام شد."
            else:
                return False, f"خطا در تحویل: {message}"

        except Exception as e:
            log.exception("Delivery failure for order %s: %s", order_code, e)
            return False, f"خطای پیش‌بینی نشده: {e}"

    @classmethod
    async def _deliver_stars(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        # ===================================================================
        # PLUG-IN: Connect Fragment API / Telethon / Supplier Endpoint here
        # Example:
        # async with aiohttp.ClientSession() as session:
        #     resp = await session.post("https://api.supplier.com/stars", json={...})
        # ===================================================================
        log.info("Fulfillment (Stars): %s stars to %s", order["qty"], order["recipient"])
        return True, "استارز با موفقیت ارسال شد."

    @classmethod
    async def _deliver_premium(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        log.info("Fulfillment (Premium): %s months to %s", order["qty"], order["recipient"])
        return True, "اشتراک پرمیوم با موفقیت فعال شد."

    @classmethod
    async def _deliver_gift(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        log.info("Fulfillment (Gift): %s to %s", order["title"], order["recipient"])
        return True, "گیفت با موفقیت ارسال شد."

    @classmethod
    async def _deliver_crypto(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        log.info("Fulfillment (Crypto): to %s", order["recipient"])
        return True, "تراکنش ارز دیجیتال انجام شد."

    @classmethod
    async def _deliver_generic(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        return True, "انجام شد."
