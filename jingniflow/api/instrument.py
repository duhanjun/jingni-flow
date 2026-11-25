# -*- coding: utf-8 -*-
"""标的元数据 API。"""

from ..adapters import get_adapter
from ..core.contract import normalize_code
from ..core.errors import ValidationError
from ..core.runtime import get_default_mode


def _adapter(trade_mode, context_data):
    mode = trade_mode or get_default_mode()
    return get_adapter(mode, context_data)


def _codes(value):
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    if not items:
        raise ValidationError("security_codes is empty")
    return [normalize_code(item) for item in items]


def jingni_get_instrument(
    trade_mode,
    context_data,
    security_codes,
    fields=None,
):
    """I-01：批量返回标的元数据。

    返回 ``{canonical_code: {code,name,board,lot_size,tick_size,
    limit_up,limit_down,listed_date,status}}``。``fields`` 可选，用于
    只保留部分键；缺失字段由平台能力决定，不用猜测值填充。
    """
    adapter = _adapter(trade_mode, context_data)
    codes = _codes(security_codes)
    result = adapter.get_instruments(codes)
    if fields:
        wanted = (
            [str(item).strip() for item in fields.split(",") if str(item).strip()]
            if isinstance(fields, str)
            else [str(item).strip() for item in fields]
        )
        filtered = {}
        for code, item in (result or {}).items():
            filtered[code] = dict(
                (key, value) for key, value in item.items() if key in wanted
            )
        return filtered
    return result


def jingni_get_stock_status(
    trade_mode,
    context_data,
    security_codes,
    query_type="ST",
    date=None,
):
    """I-07：批量查询股票状态。

    ``query_type='ST'/'HALT'/'DELISTING'`` 返回 ``{code: bool/None}``；
    ``query_type=None`` 或 ``'ALL'`` 时一次性合并三类状态，返回
    ``{code: {'st': ..., 'suspend': ..., 'delisted': ...}}``。
    PTrade 原生支持该接口；QMT/GM 使用标的详情降级推导，无法判断时
    返回 None（不伪造 False）。
    """
    adapter = _adapter(trade_mode, context_data)
    codes = _codes(security_codes)
    query = str(query_type).upper() if query_type is not None else "ALL"
    if query == "ALL":
        result = dict((code, {}) for code in codes)
        for name, key in (
            ("ST", "st"),
            ("HALT", "suspend"),
            ("DELISTING", "delisted"),
        ):
            values = adapter.get_stock_status(codes, query_type=name, date=date)
            for code in codes:
                result[code][key] = (values or {}).get(code)
        return result
    return adapter.get_stock_status(codes, query_type=query_type, date=date)
