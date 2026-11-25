# -*- coding: utf-8 -*-
"""标的元数据的无平台依赖归一化工具。"""

import datetime

from .calendar import format_date
from .contract import normalize_code, split_code


def board_from_code(code):
    """根据规范代码推断板块名称。"""
    try:
        digits, market = split_code(code)
    except Exception:
        return None
    if market == "BJ" or digits.startswith(("4", "8", "920")):
        return "北交所"
    if digits.startswith(("688", "689")):
        return "科创板"
    if digits.startswith(("300", "301")):
        return "创业板"
    return "主板"


def date_iso(value):
    """平台日期字段统一为 ``YYYY-MM-DD``；QMT 特殊值原样保留为 None。"""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text in ("0", "19700101"):
        return None
    # QMT 使用 19700101—19700106 表示新股/新债等特殊状态。
    if text.startswith("1970010"):
        return None
    compact = text.replace("-", "").replace("/", "")
    if len(compact) >= 8 and compact[:8].isdigit():
        return format_date(compact[:8])
    return text or None


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def bool_or_none(value):
    """平台布尔/数值状态转 bool；未知保持 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "t"):
        return True
    if text in ("0", "false", "no", "n", "f"):
        return False
    return None


def first_value(data, keys, default=None):
    """从 dict/对象中按候选字段名取第一个非空值。"""
    if data is None:
        return default
    for key in keys:
        if isinstance(data, dict):
            value = data.get(key)
        else:
            value = getattr(data, key, None)
        if value is not None and value != "":
            return value
    return default


def records(payload):
    """把 DataFrame / list / dict 统一成记录列表。"""
    if payload is None:
        return []
    if hasattr(payload, "to_dict"):
        try:
            return payload.to_dict("records")
        except Exception:
            pass
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), (list, tuple)):
            return list(payload["data"])
        # 平台可能返回 {code: detail}；只把 detail 值当记录。
        if payload and any(isinstance(v, dict) for v in payload.values()):
            rows = []
            for key, value in payload.items():
                if not isinstance(value, dict):
                    continue
                row = dict(value)
                row.setdefault("symbol", key)
                row.setdefault("sec_id", key)
                rows.append(row)
            if rows:
                return rows
        return [payload]
    if isinstance(payload, (list, tuple)):
        return list(payload)
    return [payload]


def build_instrument(
    code,
    name=None,
    board=None,
    lot_size=None,
    tick_size=None,
    limit_up=None,
    limit_down=None,
    listed_date=None,
    status=None,
):
    """构造统一标的元数据；status 为 st/suspend/delisted 的 dict。"""
    canonical = normalize_code(code)
    current = {
        "st": None,
        "suspend": None,
        "delisted": None,
    }
    if isinstance(status, dict):
        current.update(status)
    return {
        "code": canonical,
        "name": name,
        "board": board or board_from_code(canonical),
        "lot_size": to_int(lot_size) or 100,
        "tick_size": to_float(tick_size),
        "limit_up": to_float(limit_up),
        "limit_down": to_float(limit_down),
        "listed_date": date_iso(listed_date),
        "status": current,
    }
