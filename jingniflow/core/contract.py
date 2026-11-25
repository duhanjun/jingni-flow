# -*- coding: utf-8 -*-
"""跨平台统一契约：证券代码、频率、字段。

设计原则：
- 内部规范代码统一为 ``600000.SH`` / ``000001.SZ`` / ``430047.BJ``；
- 平台适配器只在边界做格式转换，策略层不感知平台差异；
- 转换必须幂等，非法输入抛 ``ValidationError``，不静默返回原值。
"""

import re

from .errors import ValidationError

string_types = (str,)


_MARKET_NAMES = {
    "SH": "SH",
    "SS": "SH",
    "XSHG": "SH",
    "SHSE": "SH",
    "SZ": "SZ",
    "XSHE": "SZ",
    "SZSE": "SZ",
    "BJ": "BJ",
    "BJSE": "BJ",
}

_CODE_RE = re.compile(
    r"^(?:(?P<prefix>SHSE|SZSE|BJSE)\.)?"
    r"(?P<digits>\d{6})"
    r"(?:\.(?P<suffix>SH|SS|SZ|XSHG|XSHE|BJ))?$",
    re.IGNORECASE,
)

_PREFIX_CODE_RE = re.compile(
    r"^(?P<prefix>SH|SZ|BJ)(?P<digits>\d{6})$", re.IGNORECASE
)


_FREQUENCY_ALIASES = {
    "tick": "tick",
    "1m": "1m",
    "1min": "1m",
    "min": "1m",
    "minute": "1m",
    "5m": "5m",
    "5min": "5m",
    "15m": "15m",
    "15min": "15m",
    "30m": "30m",
    "30min": "30m",
    "60m": "60m",
    "60min": "60m",
    "1h": "60m",
    "hour": "60m",
    "1d": "1d",
    "d": "1d",
    "day": "1d",
    "daily": "1d",
    "1w": "1w",
    "w": "1w",
    "week": "1w",
    "weekly": "1w",
}

_VALID_FREQUENCIES = ("tick", "1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M")


_TICK_FIELD_MAP = {
    "goldminer": {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "price",
        "volume": "volume",
        "amount": "amount",
    },
    "qmt": {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "lastPrice",
        "volume": "volume",
        "amount": "amount",
    },
    "ptrade": {
        "open": "open_px",
        "high": "high_px",
        "low": "low_px",
        "close": "last_px",
        "volume": "volume",
        "amount": "business_amount",
    },
}


def _market_from_token(token):
    if token is None or token == "":
        return None
    token = str(token).upper()
    if token not in _MARKET_NAMES:
        raise ValidationError("unsupported market token: {0}".format(token))
    return _MARKET_NAMES[token]


def infer_market(digits):
    """根据 6 位代码推断交易所；仅用于无显式市场后缀的输入。"""
    digits = str(digits)
    if len(digits) != 6 or not digits.isdigit():
        raise ValidationError("security code must be 6 digits: {0}".format(digits))
    if digits.startswith("920"):
        return "BJ"
    first = digits[0]
    if first in ("6", "5", "9"):
        return "SH"
    if first in ("0", "1", "2", "3"):
        return "SZ"
    if first in ("4", "8"):
        return "BJ"
    raise ValidationError("cannot infer market from code: {0}".format(digits))


def split_code(code):
    """返回 ``(digits, market)``；market 为 SH/SZ/BJ。"""
    if code is None:
        raise ValidationError("security code is required")
    if isinstance(code, int):
        code = str(code).zfill(6)
    if not isinstance(code, string_types):
        raise ValidationError("security code must be a string or int")
    text = code.strip().upper().replace(" ", "")
    if not text:
        raise ValidationError("security code is empty")

    match = _CODE_RE.match(text)
    if match is None:
        match = _PREFIX_CODE_RE.match(text)
        if match is None:
            raise ValidationError("invalid security code: {0}".format(code))
        prefix_market = _market_from_token(match.group("prefix"))
        digits = match.group("digits")
        return digits, prefix_market

    digits = match.group("digits")
    prefix_market = _market_from_token(match.group("prefix"))
    suffix_market = _market_from_token(match.group("suffix"))
    if prefix_market is not None and suffix_market is not None:
        if prefix_market != suffix_market:
            raise ValidationError(
                "conflicting market in security code: {0}".format(code)
            )
        market = prefix_market
    elif prefix_market is not None:
        market = prefix_market
    elif suffix_market is not None:
        market = suffix_market
    else:
        market = infer_market(digits)
    return digits, market


def normalize_code(code, target=None):
    """把任意受支持的证券代码转换为目标平台格式。

    target: ``None``/``canonical`` 返回 ``600000.SH``；``goldminer``/``gm``
    返回 ``SHSE.600000``；``qmt`` 返回 ``600000.SH``；``ptrade`` 返回
    ``600000.SS``。
    """
    digits, market = split_code(code)
    target_name = "canonical" if target is None else str(target).strip().lower()
    if target_name in ("goldminer", "gm"):
        prefix = {"SH": "SHSE.", "SZ": "SZSE.", "BJ": "BJSE."}[market]
        return prefix + digits
    if target_name == "qmt":
        return digits + "." + market
    if target_name == "ptrade":
        suffix = "SS" if market == "SH" else market
        return digits + "." + suffix
    if target_name in ("canonical", "internal", "jingni"):
        return digits + "." + market
    raise ValidationError("unsupported code target: {0}".format(target))


def normalize_platform(mode):
    """把 gm/goldminer/qmt/ptrade 统一为内部平台名。"""
    if mode is None:
        return None
    text = str(mode).strip().lower()
    if text in ("gm", "goldminer", "掘金"):
        return "goldminer"
    if text in ("qmt", "迅投"):
        return "qmt"
    if text in ("ptrade", "ptrader"):
        return "ptrade"
    return text


def normalize_frequency(frequency):
    """把常见频率别名统一为 tick/1m/5m/15m/30m/60m/1d/1w/1M。"""
    if frequency is None:
        raise ValidationError("frequency is required")
    raw = str(frequency).strip()
    if raw in ("1M", "M", "month", "monthly", "mo"):
        return "1M"
    low = raw.lower()
    if low in _FREQUENCY_ALIASES:
        return _FREQUENCY_ALIASES[low]
    if low in _VALID_FREQUENCIES:
        return low
    raise ValidationError("unsupported frequency: {0}".format(frequency))


def map_history_fields(fields, platform):
    """统一字段名转换为平台字段名列表。"""
    platform = normalize_platform(platform)
    if fields is None or fields == "" or fields == []:
        fields = ["open", "high", "low", "close", "volume", "amount"]
    elif isinstance(fields, string_types):
        fields = [item.strip() for item in fields.split(",") if item.strip()]
    elif not isinstance(fields, (list, tuple)):
        raise ValidationError("fields must be a string or list")

    result = []
    for field in fields:
        name = str(field).strip()
        if platform == "ptrade" and name == "pre_close":
            name = "preclose"
        elif platform == "ptrade" and name == "amount":
            # PTrade get_history/get_price 的成交额字段叫 money。
            name = "money"
        elif platform == "qmt" and name == "pre_close":
            name = "preClose"
        result.append(name)
    if not result:
        raise ValidationError("fields is empty")
    return result


def map_tick_field(field, platform):
    """统一 tick 字段名转换为平台字段名。"""
    platform = normalize_platform(platform)
    if field is None:
        return None
    name = str(field).strip()
    table = _TICK_FIELD_MAP.get(platform, {})
    return table.get(name, name)


def canonical_tick_field(field, platform):
    """平台 tick 字段名转回统一字段名。"""
    platform = normalize_platform(platform)
    if field is None:
        return None
    name = str(field).strip()
    table = _TICK_FIELD_MAP.get(platform, {})
    for canonical, platform_field in table.items():
        if platform_field == name:
            return canonical
    return name


def map_adjust(adjust, platform):
    """统一复权参数转换。"""
    platform = normalize_platform(platform)
    name = "pre" if adjust is None or adjust == "" else str(adjust).lower()
    if name in ("none", "no", "raw", "0", "adjust_none"):
        canonical = "none"
    elif name in ("pre", "prev", "front", "forward", "1", "adjust_prev"):
        canonical = "pre"
    elif name in ("post", "back", "backward", "2", "adjust_post"):
        canonical = "post"
    else:
        raise ValidationError("unsupported adjust: {0}".format(adjust))

    if platform == "goldminer":
        return {"none": "ADJUST_NONE", "pre": "ADJUST_PREV", "post": "ADJUST_POST"}[
            canonical
        ]
    if platform == "qmt":
        return {"none": "none", "pre": "front", "post": "back"}[canonical]
    if platform == "ptrade":
        return {"none": "none", "pre": "pre", "post": "post"}[canonical]
    return canonical
