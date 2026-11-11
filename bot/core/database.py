# -*- coding: utf-8 -*-
"""Asynchronous Database Module with Atomic Operations and Concurrency Protection."""

import os
import time
import random
import string
import logging
from typing import Optional, Dict, Any, List
import aiosqlite
from config import settings, DEFAULT_PRICES

log = logging.getLogger(__name__)


def generate_order_code() -> str:
    """Generate a clean unique tracking/order code e.g. ORD-AB12CD."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"ORD-{suffix}"


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_connection(self) -> aiosqlite.Connection:
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def init(self) -> None:
        """Create tables and seed default settings."""
        conn = await self.get_connection()
        try:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT DEFAULT '',
                    username TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    balance INTEGER DEFAULT 0 CHECK(balance >= 0),
                    discount_balance INTEGER DEFAULT 0 CHECK(discount_balance >= 0),
                    points INTEGER DEFAULT 0 CHECK(points >= 0),
                    referrer_id INTEGER,
                    ref_count INTEGER DEFAULT 0,
                    ref_earnings INTEGER DEFAULT 0 CHECK(ref_earnings >= 0),
                    total_ref_earned INTEGER DEFAULT 0,
                    verified INTEGER DEFAULT 0,
                    dice_last TEXT DEFAULT '',
                    bowling_last TEXT DEFAULT '',
                    joined_at INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    qty REAL DEFAULT 1,
                    recipient TEXT DEFAULT '',
                    gross_price INTEGER NOT NULL,
                    final_price INTEGER NOT NULL,
                    discount_used INTEGER DEFAULT 0,
                    discount_code TEXT DEFAULT '',
                    paid_from TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    extra TEXT DEFAULT '',
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS discount_codes (
                    code TEXT PRIMARY KEY,
                    percent INTEGER NOT NULL,
                    active INTEGER DEFAULT 1,
                    max_uses INTEGER DEFAULT -1,
                    times_used INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_discount_redemptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    order_code TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT DEFAULT ''
                );
                """
            )

            # Seed default settings
            for key, val in DEFAULT_PRICES.items():
                await conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, str(val))
                )

            # Seed Welcome discount code
            await conn.execute(
                "INSERT OR IGNORE INTO discount_codes(code, percent, active, max_uses) "
                "VALUES('WelcomeCode', 5, 1, -1)"
            )
            await conn.commit()
            log.info("Database initialized successfully with WAL mode.")
        finally:
            await conn.close()

    # -----------------------------------------------------------------------
    # User Management
    # -----------------------------------------------------------------------

    async def get_or_create_user(self, user_id: int, full_name: str = "", username: str = "", referrer_id: Optional[int] = None) -> Dict[str, Any]:
        conn = await self.get_connection()
        try:
            cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                # Update username/name if changed
                await conn.execute(
                    "UPDATE users SET full_name = ?, username = ? WHERE id = ?",
                    (full_name, username or "", user_id)
                )
                await conn.commit()
                return dict(row)

            # New user registration
            actual_ref = None
            if referrer_id and referrer_id != user_id:
                # Check if referrer exists
                ref_cur = await conn.execute("SELECT id FROM users WHERE id = ?", (referrer_id,))
                if await ref_cur.fetchone():
                    actual_ref = referrer_id

            now = int(time.time())
            await conn.execute(
                """
                INSERT INTO users (id, full_name, username, balance, discount_balance, points, referrer_id, joined_at)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?)
                """,
                (user_id, full_name, username or "", actual_ref, now)
            )
            if actual_ref:
                await conn.execute(
                    "UPDATE users SET ref_count = ref_count + 1 WHERE id = ?",
                    (actual_ref,)
                )
            await conn.commit()

            cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return dict(await cursor.fetchone())
        finally:
            await conn.close()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = await self.get_connection()
        try:
            cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    async def update_user_balance(self, user_id: int, amount: int, column: str = "balance") -> bool:
        if column not in ("balance", "discount_balance", "points", "ref_earnings", "total_ref_earned"):
            raise ValueError(f"Invalid column: {column}")
        conn = await self.get_connection()
        try:
            # Atomic update with check to prevent negative balance
            cursor = await conn.execute(
                f"UPDATE users SET {column} = {column} + ? WHERE id = ? AND ({column} + ?) >= 0",
                (amount, user_id, amount)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # -----------------------------------------------------------------------
    # Orders & Safe Payment
    # -----------------------------------------------------------------------

    async def create_order(
        self,
        user_id: int,
        kind: str,
        title: str,
        qty: float,
        recipient: str,
        gross_price: int,
        final_price: int,
        discount_used: int = 0,
        discount_code: str = "",
        extra: str = ""
    ) -> str:
        conn = await self.get_connection()
        try:
            code = generate_order_code()
            now = int(time.time())
            await conn.execute(
                """
                INSERT INTO orders (code, user_id, kind, title, qty, recipient, gross_price,
                                    final_price, discount_used, discount_code, status, extra, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (code, user_id, kind, title, qty, recipient, gross_price, final_price, discount_used, discount_code, extra, now)
            )
            await conn.commit()
            return code
        finally:
            await conn.close()

    async def get_order(self, code: str) -> Optional[Dict[str, Any]]:
        conn = await self.get_connection()
        try:
            cursor = await conn.execute("SELECT * FROM orders WHERE code = ?", (code.strip().upper(),))
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    async def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def atomic_pay_order_from_wallet(self, user_id: int, order_code: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        ATOMIC WALLET PAYMENT:
        Executes in an immediate transaction to completely prevent:
        - Race conditions
        - Double spending
        - Duplicate referral rewards
        - Expired invoice payment
        """
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN IMMEDIATE")

            # 1. Fetch and lock order
            cursor = await conn.execute("SELECT * FROM orders WHERE code = ?", (order_code,))
            order = await cursor.fetchone()
            if not order:
                await conn.rollback()
                return False, "❌ سفارش یافت نشد.", None

            order = dict(order)
            if order["user_id"] != user_id:
                await conn.rollback()
                return False, "❌ این سفارش متعلق به شما نیست.", None

            if order["status"] != "pending":
                await conn.rollback()
                return False, "⚠️ این سفارش قبلاً پرداخت یا تعیین تکلیف شده است.", None

            # 2. Check 15-minute expiration
            if time.time() - order["created_at"] > 900: # 15 minutes
                await conn.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (order["id"],))
                await conn.commit()
                return False, "⏰ مهلت پرداخت این پیش فاکتور (۱۵ دقیقه) منقضی شده است. لطفاً سفارش جدید ثبت کنید.", None

            # 3. Fetch user balance
            u_cur = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = dict(await u_cur.fetchone())

            payable = order["final_price"]
            if user["balance"] < payable:
                await conn.rollback()
                deficit = payable - user["balance"]
                return False, f"❌ موجودی کیف پول کافی نیست! کسری: {deficit:,} تومان", None

            # 4. Atomic balance deduction
            deduct_cur = await conn.execute(
                "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
                (payable, user_id, payable)
            )
            if deduct_cur.rowcount == 0:
                await conn.rollback()
                return False, "❌ موجودی کافی نیست یا تراکنش همزمان رخ داده است.", None

            # 5. Mark order as paid
            await conn.execute(
                "UPDATE orders SET status = 'paid', paid_from = 'wallet' WHERE id = ?",
                (order["id"],)
            )

            # 6. Referral Commission
            if user.get("referrer_id"):
                ref_id = user["referrer_id"]
                commission = int(order["final_price"] * settings.DEFAULT_REFERRAL_PERCENT / 100)
                if commission > 0:
                    await conn.execute(
                        "UPDATE users SET ref_earnings = ref_earnings + ?, total_ref_earned = total_ref_earned + ? WHERE id = ?",
                        (commission, commission, ref_id)
                    )

            # 7. Loyalty Points
            points_earned = max(1, order["final_price"] // 100000)
            await conn.execute(
                "UPDATE users SET points = points + ? WHERE id = ?",
                (points_earned, user_id)
            )

            await conn.commit()
            order["status"] = "paid"
            return True, "✅ پرداخت با موفقیت از کیف پول انجام شد.", order
        except Exception as e:
            await conn.rollback()
            log.exception("Error in atomic_pay_order_from_wallet: %s", e)
            return False, f"خطای سیستمی: {e}", None
        finally:
            await conn.close()

    # -----------------------------------------------------------------------
    # Discount Codes & Anti-Abuse
    # -----------------------------------------------------------------------

    async def apply_discount_code(self, user_id: int, order_code: str, code_str: str) -> tuple[bool, str, int]:
        """
        Validates discount code and applies it ONCE to an order without compounding.
        """
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN IMMEDIATE")
            code_str = code_str.strip()

            # 1. Fetch order
            o_cur = await conn.execute("SELECT * FROM orders WHERE code = ?", (order_code,))
            order = await o_cur.fetchone()
            if not order:
                await conn.rollback()
                return False, "❌ سفارش یافت نشد.", 0
            order = dict(order)

            if order["status"] != "pending":
                await conn.rollback()
                return False, "❌ این سفارش دیگر معتبر نیست.", 0

            if order["discount_code"]:
                await conn.rollback()
                return False, "⚠️ روی این سفارش قبلاً کد تخفیف اعمال شده است.", order["final_price"]

            # 2. Check code validity
            c_cur = await conn.execute(
                "SELECT * FROM discount_codes WHERE code = ? AND active = 1",
                (code_str,)
            )
            discount = await c_cur.fetchone()
            if not discount:
                await conn.rollback()
                return False, "❌ کد تخفیف معتبر نیست یا منقضی شده است.", 0
            discount = dict(discount)

            # Check max uses
            if discount["max_uses"] != -1 and discount["times_used"] >= discount["max_uses"]:
                await conn.rollback()
                return False, "❌ ظرفیت استفاده از این کد تخفیف تمام شده است.", 0

            # 3. Check if user already redeemed this code
            r_cur = await conn.execute(
                "SELECT id FROM user_discount_redemptions WHERE user_id = ? AND code = ?",
                (user_id, code_str)
            )
            if await r_cur.fetchone():
                await conn.rollback()
                return False, "⚠️ شما قبلاً از این کد تخفیف استفاده کرده اید.", 0

            # 4. Calculate discount from GROSS price (prevents price compounding)
            percent = discount["percent"]
            discount_amount = int(order["gross_price"] * percent / 100)
            new_final_price = max(0, order["gross_price"] - discount_amount - order["discount_used"])

            await conn.execute(
                """
                UPDATE orders SET final_price = ?, discount_code = ? WHERE id = ?
                """,
                (new_final_price, code_str, order["id"])
            )
            await conn.execute(
                "UPDATE discount_codes SET times_used = times_used + 1 WHERE code = ?",
                (code_str,)
            )
            await conn.execute(
                """
                INSERT INTO user_discount_redemptions (user_id, code, order_code, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, code_str, order_code, int(time.time()))
            )
            await conn.commit()
            return True, f"✅ کد تخفیف {percent}٪ با موفقیت اعمال شد.", new_final_price
        except Exception as e:
            await conn.rollback()
            log.exception("Error applying discount: %s", e)
            return False, "خطا در اعمال تخفیف.", 0
        finally:
            await conn.close()

    # -----------------------------------------------------------------------
    # Settings Management
    # -----------------------------------------------------------------------

    async def get_setting(self, key: str, default: str = "") -> str:
        conn = await self.get_connection()
        try:
            cursor = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row["value"] if row else default
        finally:
            await conn.close()

    async def set_setting(self, key: str, value: str) -> None:
        conn = await self.get_connection()
        try:
            await conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value))
            )
            await conn.commit()
        finally:
            await conn.close()

    # -----------------------------------------------------------------------
    # Admin Stats & Operations
    # -----------------------------------------------------------------------

    async def get_stats(self) -> Dict[str, Any]:
        conn = await self.get_connection()
        try:
            u_count = (await (await conn.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            o_count = (await (await conn.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
            sales = (await (await conn.execute("SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE status IN ('paid', 'delivered')")).fetchone())[0]
            pending_orders = (await (await conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid'")).fetchone())[0]
            return {
                "users_count": u_count,
                "orders_count": o_count,
                "total_sales": sales,
                "pending_delivery": pending_orders,
            }
        finally:
            await conn.close()

    async def admin_refund_order(self, order_code: str) -> tuple[bool, str]:
        """Admin rejection and safe refund to wallet."""
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN IMMEDIATE")
            cursor = await conn.execute("SELECT * FROM orders WHERE code = ?", (order_code,))
            order = await cursor.fetchone()
            if not order:
                await conn.rollback()
                return False, "سفارش یافت نشد."
            order = dict(order)
            if order["status"] not in ("paid", "pending"):
                await conn.rollback()
                return False, "سفارش قبلاً بسته یا عودت داده شده است."

            # Safe refund to wallet
            await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE id = ?",
                (order["final_price"], order["user_id"])
            )
            await conn.execute(
                "UPDATE orders SET status = 'refunded' WHERE id = ?",
                (order["id"],)
            )
            await conn.commit()
            return True, f"سفارش رد و مبلغ {order['final_price']:,} تومان به کیف پول کاربر بازگردانده شد."
        except Exception as e:
            await conn.rollback()
            return False, f"خطا در رد سفارش: {e}"
        finally:
            await conn.close()


db = Database(settings.DB_PATH)
