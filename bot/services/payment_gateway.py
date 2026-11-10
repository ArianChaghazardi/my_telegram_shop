# -*- coding: utf-8 -*-
"""Payment gateway service abstraction."""

import logging
from typing import Dict, Any, Tuple

log = logging.getLogger(__name__)


class PaymentGatewayService:
    """
    Modular abstraction for online Rial gateways (e.g. Zarinpal, IDPay, NextPay)
    and Crypto merchant processors (e.g. OxaPay, Cryptomus, NOWPayments).
    """

    @classmethod
    async def create_rial_payment(cls, user_id: int, order_code: str, amount_toman: int) -> Tuple[bool, str, str]:
        """
        Request payment token and gateway redirect URL.
        Returns: (success, redirect_url_or_error, authority)
        """
        log.info("Requesting Rial gateway for user %s, order %s (%s Toman)", user_id, order_code, amount_toman)
        # ===================================================================
        # PLUG-IN: Call Zarinpal / NextPay / IDPay REST API here:
        # url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
        # ===================================================================
        return False, "درگاه پرداخت آنلاین در حال حاضر برای نگهداری غیرفعال است. لطفاً از پرداخت با کیف پول استفاده فرمایید.", ""

    @classmethod
    async def create_crypto_invoice(cls, user_id: int, amount_toman: int, currency: str = "TON") -> Dict[str, Any]:
        """Generate deposit address and unique memo for crypto deposits."""
        from bot.core.database import db
        address = await db.get_setting("wallet_address", "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        memo = f"{user_id}"
        return {
            "address": address,
            "memo": memo,
            "currency": currency,
            "amount_toman": amount_toman,
        }
