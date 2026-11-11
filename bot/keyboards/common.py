# -*- coding: utf-8 -*-
"""Keyboard utilities and Bot API 9.x style helpers."""

import inspect
from typing import List, Optional
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from config import CUSTOM_EMOJI_IDS

STYLE_SUCCESS = "success" # Green
STYLE_PRIMARY = "primary" # Blue / Teal
STYLE_DANGER = "danger" # Red / Warm Brown

_INLINE_SUPPORTS_STYLE = "style" in inspect.signature(InlineKeyboardButton.__init__).parameters
_INLINE_SUPPORTS_CUSTOM_EMOJI = "icon_custom_emoji_id" in inspect.signature(InlineKeyboardButton.__init__).parameters

_REPLY_SUPPORTS_STYLE = "style" in inspect.signature(KeyboardButton.__init__).parameters
_REPLY_SUPPORTS_CUSTOM_EMOJI = "icon_custom_emoji_id" in inspect.signature(KeyboardButton.__init__).parameters


def btn(
    text: str,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    style: Optional[str] = None,
    emoji_key: Optional[str] = None,
) -> InlineKeyboardButton:
    """Create an inline button with optional Bot API 9.x style and custom emoji."""
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style and _INLINE_SUPPORTS_STYLE:
        kwargs["style"] = style
    if emoji_key and _INLINE_SUPPORTS_CUSTOM_EMOJI and emoji_key in CUSTOM_EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = CUSTOM_EMOJI_IDS[emoji_key]
    return InlineKeyboardButton(**kwargs)


def kbtn(
    text: str,
    style: Optional[str] = None,
    emoji_key: Optional[str] = None,
    request_contact: bool = False,
) -> KeyboardButton:
    """Create a reply keyboard button with optional style."""
    kwargs = {"text": text}
    if request_contact:
        kwargs["request_contact"] = True
    if style and _REPLY_SUPPORTS_STYLE:
        kwargs["style"] = style
    if emoji_key and _REPLY_SUPPORTS_CUSTOM_EMOJI and emoji_key in CUSTOM_EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = CUSTOM_EMOJI_IDS[emoji_key]
    return KeyboardButton(**kwargs)


def ikb(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Convenience helper to build InlineKeyboardMarkup."""
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rkb(rows: List[List[KeyboardButton]], resize: bool = True) -> ReplyKeyboardMarkup:
    """Convenience helper to build ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=resize)
