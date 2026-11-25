# -*- coding: utf-8 -*-
"""账户与持仓 API。"""

from ..adapters import get_adapter
from ..core.errors import JingniError, ValidationError

_VALID_FIELDS = ("assets_value", "market_value", "cash", "positions")


def jingni_portfolio(trade_mode, context_data, security_field, strict=False):
    """旧接口：查询账户资产/市值/可用资金/持仓原始对象。"""
    field = str(security_field).strip() if security_field is not None else ""
    if field not in _VALID_FIELDS:
        error = ValidationError("unsupported portfolio field: {0}".format(security_field))
        if strict:
            raise error
        print("[JINGNI_VALIDATION] {0}".format(error))
        return None
    try:
        adapter = get_adapter(trade_mode, context_data)
        return adapter.get_portfolio(field)
    except Exception as exc:
        if strict:
            if isinstance(exc, JingniError):
                raise
            raise JingniError("portfolio query failed: {0}".format(exc))
        print("[JINGNI_DATA_ERROR] portfolio query failed: {0}".format(exc))
        return None


def jingni_get_account(trade_mode, context_data, strict=False):
    """新接口：返回统一账户字典。"""
    try:
        adapter = get_adapter(trade_mode, context_data)
        return adapter.get_account()
    except Exception as exc:
        if strict:
            raise
        print("[JINGNI_DATA_ERROR] account query failed: {0}".format(exc))
        return {
            "total_asset": None,
            "cash": None,
            "available": None,
            "market_value": None,
            "frozen": None,
            "pnl": None,
            "raw": None,
        }


def jingni_get_positions(trade_mode, context_data, strict=False):
    """新接口：返回统一持仓 ``[{code, amount, available, cost, ...}]``。"""
    try:
        adapter = get_adapter(trade_mode, context_data)
        return adapter.get_positions()
    except Exception as exc:
        if strict:
            raise
        print("[JINGNI_DATA_ERROR] positions query failed: {0}".format(exc))
        return []
