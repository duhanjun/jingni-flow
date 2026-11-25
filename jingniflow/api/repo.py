# -*- coding: utf-8 -*-
"""国债逆回购 API。"""

from ..core.contract import normalize_code
from ..core.errors import ValidationError
from ..core.runtime import get_default_mode, resolve_context
from .account import jingni_portfolio
from .market import jingni_get_field
from .trade import jingni_order_amount

_REPO_CODES = {
    "SH": {
        1: "204001.SH",
        2: "204002.SH",
        3: "204003.SH",
        4: "204004.SH",
        7: "204007.SH",
        14: "204014.SH",
        28: "204028.SH",
        91: "204091.SH",
        182: "204182.SH",
    },
    "SZ": {
        1: "131810.SZ",
        2: "131811.SZ",
        3: "131800.SZ",
        4: "131809.SZ",
        7: "131801.SZ",
        14: "131802.SZ",
        28: "131803.SZ",
        91: "131805.SZ",
        182: "131806.SZ",
    },
}


def _repo_code(days, market):
    market = str(market).upper()
    if market not in _REPO_CODES:
        raise ValidationError("unsupported repo market: {0}".format(market))
    code = _REPO_CODES[market].get(int(days))
    if code is None:
        raise ValidationError("unsupported repo days: {0}".format(days))
    return normalize_code(code)


def jingni_participate_reverse_repo(
    context_data,
    cash_ratio=1.0,
    reverse_repo_days=1,
    market="SH",
    min_amount=1000,
    dry_run=None,
    trade_mode=None,
):
    """参与国债逆回购；数量按 ``int(cash*ratio/1000)*10`` 计算。

    不足 ``min_amount`` 或不足 10 张时不报单，返回 None。
    """
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    effective_dry_run = context.config.dry_run if dry_run is None else bool(dry_run)
    cash = jingni_portfolio(context, context.raw, "cash")
    if cash is None:
        if getattr(context, "is_backtest", False):
            print("[JINGNI_SKIP] reverse repo: cash is unavailable in backtest")
        else:
            print("[JINGNI_ORDER_ERROR] cash is unavailable")
        return None
    try:
        cash = float(cash)
        ratio = float(cash_ratio)
    except Exception:
        raise ValidationError("cash_ratio must be numeric")
    if cash <= 0 or ratio <= 0:
        return None
    code = _repo_code(reverse_repo_days, market)
    amount = int((cash * ratio) / 1000) * 10
    if amount < 10 or cash * ratio < float(min_amount):
        print("[JINGNI_REPO] cash below minimum, skip")
        return None
    price = jingni_get_field(context, context.raw, code, "1d", "close", 0)
    try:
        price = float(price)
    except Exception:
        price = 0.0
    if price <= 0:
        print("[JINGNI_REPO] repo price unavailable, skip")
        return None
    if effective_dry_run:
        print("[JINGNI_REPO] dry_run: {0} x {1} @ {2}".format(code, amount, price))
        return None
    return jingni_order_amount(
        context,
        context.raw,
        code,
        -amount,
        price,
        dry_run=False,
        remark="reverse_repo",
        check_sell_available=False,
    )
