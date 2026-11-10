# -*- coding: utf-8 -*-
"""Anti-flood / Rate limiting middleware."""

import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class ThrottlingMiddleware(BaseMiddleware):
    """Simple in-memory rate limiting to prevent spam and race-condition bursts."""

    def __init__(self, rate_limit_seconds: float = 0.5):
        self.rate_limit_seconds = rate_limit_seconds
        self.last_action: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            last_time = self.last_action.get(user_id, 0.0)
            if now - last_time < self.rate_limit_seconds:
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ لطفاً کمی صبر کنید...", show_alert=False)
                return None
            self.last_action[user_id] = now

        return await handler(event, data)
