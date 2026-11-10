# -*- coding: utf-8 -*-
"""Handlers router registry."""

from aiogram import Router
from bot.handlers.start import router as start_router
from bot.handlers.shops import router as shops_router
from bot.handlers.payment import router as payment_router
from bot.handlers.wallet import router as wallet_router
from bot.handlers.account import router as account_router
from bot.handlers.games import router as games_router
from bot.handlers.admin import router as admin_router

main_router = Router(name="main_router")

# Register all child routers in order
main_router.include_router(admin_router)
main_router.include_router(start_router)
main_router.include_router(shops_router)
main_router.include_router(payment_router)
main_router.include_router(wallet_router)
main_router.include_router(account_router)
main_router.include_router(games_router)

__all__ = ["main_router"]
