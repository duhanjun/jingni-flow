# -*- coding: utf-8 -*-
"""打新与逆回购 API。"""

import time

from ..core.contract import normalize_code
from ..core.errors import JingniError, ValidationError
from ..core.runtime import get_default_mode, platform_call, resolve_context


def _gm_account(context):
    return context.config.account_id or ""


def _qmt_ipo_data(context, kind):
    raw = context.raw
    if raw is not None and hasattr(raw, "get_ipo_data"):
        return raw.get_ipo_data(kind)
    return platform_call("get_ipo_data", kind)


def jingni_subscribe_new_stock(
    context_data, blacklist=None, dry_run=None, trade_mode=None
):
    """申购新股；返回 ``{code: status}``。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    effective_dry_run = context.config.dry_run if dry_run is None else bool(dry_run)
    result = {}
    try:
        if context.platform == "goldminer":
            data = platform_call(
                "ipo_get_instruments", 1010, account_id=_gm_account(context), df=False
            )
            for item in data or []:
                code = item.get("symbol")
                if not code or (blacklist and code in blacklist):
                    continue
                if effective_dry_run:
                    result[code] = "dry_run"
                    continue
                platform_call(
                    "ipo_buy",
                    code,
                    item.get("max_vol", 0),
                    item.get("price", 0),
                    account_id=_gm_account(context),
                )
                result[code] = "submitted"
        elif context.platform == "ptrade":
            markets = (0, 1, 2, 3)
            for index, market_type in enumerate(markets):
                if effective_dry_run:
                    result[str(market_type)] = "dry_run"
                else:
                    kwargs = {"market_type": market_type}
                    if blacklist:
                        kwargs["black_stocks"] = blacklist
                    result[str(market_type)] = platform_call(
                        "ipo_stocks_order", **kwargs
                    )
                if index < len(markets) - 1:
                    time.sleep(5)
        elif context.platform == "qmt":
            data = _qmt_ipo_data(context, "STOCK")
            for code, item in (data or {}).items():
                if blacklist and code in blacklist:
                    continue
                if effective_dry_run:
                    result[code] = "dry_run"
                    continue
                account = context.account_id()
                if not account:
                    raise JingniError("QMT account is not configured")
                platform_call(
                    "passorder",
                    23,
                    1101,
                    str(account),
                    normalize_code(code, "qmt"),
                    11,
                    float(item.get("issuePrice", 0)),
                    int(item.get("maxPurchaseNum", 0)),
                    "",
                    2,
                    "",
                    context.raw,
                )
                result[code] = "submitted"
        else:
            raise ValidationError("unsupported platform: {0}".format(context.platform))
    except Exception as exc:
        print("[JINGNI_ORDER_ERROR] new stock failed: {0}".format(exc))
        result["error"] = str(exc)
    return result


def jingni_subscribe_new_bond(
    context_data, blacklist=None, dry_run=None, trade_mode=None
):
    """申购新债/可转债；返回 ``{code: status}``。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    effective_dry_run = context.config.dry_run if dry_run is None else bool(dry_run)
    result = {}
    try:
        if context.platform == "goldminer":
            data = platform_call(
                "ipo_get_instruments", 1030, account_id=_gm_account(context), df=False
            )
            for item in data or []:
                code = item.get("symbol")
                if not code or (blacklist and code in blacklist):
                    continue
                if effective_dry_run:
                    result[code] = "dry_run"
                    continue
                platform_call(
                    "ipo_buy",
                    code,
                    item.get("max_vol", 0),
                    item.get("price", 0),
                    account_id=_gm_account(context),
                )
                result[code] = "submitted"
        elif context.platform == "ptrade":
            if effective_dry_run:
                result["4"] = "dry_run"
            else:
                kwargs = {"market_type": 4}
                if blacklist:
                    kwargs["black_stocks"] = blacklist
                result["4"] = platform_call("ipo_stocks_order", **kwargs)
        elif context.platform == "qmt":
            data = _qmt_ipo_data(context, "BOND")
            for code, item in (data or {}).items():
                if blacklist and code in blacklist:
                    continue
                if effective_dry_run:
                    result[code] = "dry_run"
                    continue
                account = context.account_id()
                if not account:
                    raise JingniError("QMT account is not configured")
                platform_call(
                    "passorder",
                    23,
                    1101,
                    str(account),
                    normalize_code(code, "qmt"),
                    11,
                    float(item.get("issuePrice", 0)),
                    int(item.get("maxPurchaseNum", 0)),
                    "",
                    2,
                    "",
                    context.raw,
                )
                result[code] = "submitted"
        else:
            raise ValidationError("unsupported platform: {0}".format(context.platform))
    except Exception as exc:
        print("[JINGNI_ORDER_ERROR] new bond failed: {0}".format(exc))
        result["error"] = str(exc)
    return result
