# -*- coding: utf-8 -*-
"""统一订单对象与状态映射。"""

import datetime

ORDER_STATUSES = (
    "PENDING",
    "PARTIAL",
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
    "UNKNOWN",
)

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

_GM_STATUS = {
    0: "PENDING",  # Unknown/尚未回报，按待处理展示
    1: "PENDING",  # New
    2: "PARTIAL",  # PartiallyFilled
    3: "FILLED",  # Filled
    5: "CANCELED",  # Canceled
    6: "PENDING",  # PendingCancel
    8: "REJECTED",  # Rejected
    9: "UNKNOWN",  # Suspended
    10: "PENDING",  # PendingNew
    12: "EXPIRED",  # Expired
    15: "PENDING",  # PendingTrigger
    16: "PENDING",  # Triggered
}

_QMT_STATUS = {
    48: "PENDING",
    49: "PENDING",
    50: "PENDING",
    51: "PENDING",
    52: "PARTIAL",
    53: "CANCELED",
    54: "CANCELED",
    55: "PARTIAL",
    56: "FILLED",
    57: "REJECTED",
}

_PTRADE_STATUS = {
    "0": "PENDING",  # 未报
    "1": "PENDING",  # 待报
    "2": "PENDING",  # 已报
    "3": "PENDING",  # 已报待撤
    "4": "PARTIAL",  # 部成待撤
    "5": "CANCELED",  # 部撤
    "6": "CANCELED",  # 已撤
    "7": "PARTIAL",  # 部成
    "8": "FILLED",  # 已成
    "9": "REJECTED",  # 废单
    "+": "PENDING",  # 已受理
    "-": "PENDING",  # 已确认
}

_GM_STATUS_NAMES = {
    "ORDERSTATUS_NEW": "PENDING",
    "ORDERSTATUS_PARTIALLYFILLED": "PARTIAL",
    "ORDERSTATUS_FILLED": "FILLED",
    "ORDERSTATUS_CANCELED": "CANCELED",
    "ORDERSTATUS_REJECTED": "REJECTED",
    "ORDERSTATUS_EXPIRED": "EXPIRED",
}


def normalize_side(value):
    """把平台方向值/文本统一为 BUY/SELL。"""
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in ("BUY", "B", "买", "买入", "23", "1", "ORDER_SIDE_BUY", "ORDERSIDE_BUY"):
        return SIDE_BUY
    if text in ("SELL", "S", "卖", "卖出", "24", "2", "ORDER_SIDE_SELL", "ORDERSIDE_SELL"):
        return SIDE_SELL
    return None


def normalize_status(platform, value):
    """平台状态码转统一枚举；未知返回 UNKNOWN，不猜测。"""
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        text = value.strip().upper()
        if text in ORDER_STATUSES:
            return text
        if platform == "ptrade" and text in _PTRADE_STATUS:
            return _PTRADE_STATUS[text]
        if platform == "goldminer" and text in _GM_STATUS_NAMES:
            return _GM_STATUS_NAMES[text]
        if text.isdigit():
            value = int(text)
        else:
            # 掘金可能返回 OrderStatus_New 这类常量名。
            for candidate in ORDER_STATUSES:
                if text.endswith(candidate):
                    return candidate
            return "UNKNOWN"
    try:
        number = int(value)
    except Exception:
        return "UNKNOWN"
    if platform == "goldminer":
        return _GM_STATUS.get(number, "UNKNOWN")
    if platform == "qmt":
        return _QMT_STATUS.get(number, "UNKNOWN")
    if platform == "ptrade":
        return _PTRADE_STATUS.get(str(number), "UNKNOWN")
    return "UNKNOWN"


def order_ref(platform, platform_id=None, remark=None):
    """构造统一订单引用。"""
    return {
        "platform": platform,
        "id": None if platform_id is None else str(platform_id),
        "remark": None if remark is None else str(remark),
    }


def coerce_order_ref(value):
    """接受 OrderRef/dict/字符串，返回可比较的订单引用。"""
    if value is None:
        return None
    if isinstance(value, dict):
        if "order_ref" in value:
            return value["order_ref"]
        if "platform" in value and "id" in value:
            return value
        if "id" in value:
            return order_ref(value.get("platform"), value["id"], value.get("remark"))
        if "platform_order_id" in value:
            return order_ref(
                value.get("platform"), value["platform_order_id"], value.get("remark")
            )
        return value
    return order_ref(None, value, None)


def make_order(
    platform,
    platform_id=None,
    code=None,
    side=None,
    price=None,
    amount=None,
    filled=0,
    status=None,
    status_code=None,
    created_at=None,
    updated_at=None,
    remark=None,
    raw=None,
):
    """构造统一订单字典。"""
    return {
        "order_ref": order_ref(platform, platform_id, remark),
        "platform_order_id": None if platform_id is None else str(platform_id),
        "code": code,
        "side": normalize_side(side),
        "price": _to_float(price),
        "amount": _to_int(amount),
        "filled": _to_int(filled),
        "status": normalize_status(platform, status),
        "status_code": status_code if status_code is not None else status,
        "created_at": created_at,
        "updated_at": updated_at,
        "remark": remark,
        "raw": raw,
    }


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value):
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def ref_matches(order, ref):
    """判断订单是否匹配某个 OrderRef/字符串。"""
    if ref is None:
        return True
    target = coerce_order_ref(ref)
    if isinstance(target, str):
        target = order_ref(None, target, None)
    if not isinstance(target, dict):
        return False
    order_id = str(order.get("platform_order_id") or "")
    order_remark = str(order.get("remark") or "")
    target_id = str(target.get("id") or "")
    target_remark = str(target.get("remark") or "")
    if target_id and target_id == order_id:
        return True
    if target_remark and target_remark == order_remark:
        return True
    return False


def now_text(value=None):
    value = value or datetime.datetime.now()
    return value.strftime("%Y-%m-%d %H:%M:%S")
