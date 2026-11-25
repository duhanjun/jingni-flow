# -*- coding: utf-8 -*-
"""无平台依赖的订单风控。"""

from .order import SIDE_BUY, SIDE_SELL, normalize_side


def _state(context):
    state = getattr(context, "_jingni_risk_state", None)
    if state is None:
        state = {"last": {}, "date": None, "count": 0, "kill_switch": False}
        context._jingni_risk_state = state
    return state


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _available_from_positions(positions, code):
    available = 0
    for item in positions or []:
        if str(item.get("code") or "") != str(code):
            continue
        available = int(item.get("available") or 0)
        break
    return max(0, available)


def check_order(
    context,
    code,
    side,
    amount,
    price=None,
    account=None,
    positions=None,
    now=None,
    record=True,
    check_sell_available=True,
):
    """下单前统一风控；返回 ``(ok, reason)``。

    ``amount`` 为正数。买方向按股票 100 股整手校验；卖方向按统一
    ``available`` 校验。账户/持仓由调用方传入，避免本模块反向依赖适配器。
    ``record=False`` 用于 dry-run：只检查，不消耗每日笔数/重复窗口。
    """
    config = context.config
    state = _state(context)
    if config.kill_switch or state.get("kill_switch"):
        return False, "kill_switch is active"
    side = normalize_side(side)
    if side not in (SIDE_BUY, SIDE_SELL):
        return False, "invalid side"
    try:
        amount = int(amount)
    except Exception:
        return False, "amount must be an integer"
    if amount <= 0:
        return False, "amount must be positive"
    price_value = _to_float(price)
    if price is not None and (price_value is None or price_value <= 0):
        return False, "price must be positive"
    if side == SIDE_BUY and amount % 100 != 0:
        return False, "A-share buy amount must be a multiple of 100"
    if config.max_order_amount is not None and amount > int(config.max_order_amount):
        return False, "amount exceeds max_order_amount"
    if (
        side == SIDE_BUY
        and price_value is not None
        and config.max_order_value is not None
        and amount * price_value > float(config.max_order_value)
    ):
        return False, "value exceeds max_order_value"

    day = context.trade_date()
    if state.get("date") != day:
        state["date"] = day
        state["count"] = 0
        state["last"] = {}
    if config.max_daily_orders is not None and state["count"] >= int(
        config.max_daily_orders
    ):
        return False, "daily order limit reached"
    if config.repeat_window_seconds:
        key = (str(code), side, amount, price_value)
        now_value = now or context.now()
        last = state["last"].get(key)
        if last is not None:
            elapsed = (now_value - last).total_seconds()
            if elapsed < float(config.repeat_window_seconds):
                return False, "duplicate order within repeat window"

    if side == SIDE_SELL and check_sell_available:
        available = _available_from_positions(positions, code)
        if amount > available:
            return False, "amount exceeds available position"
    elif account is not None and price_value is not None:
        cash = _to_float(account.get("available", account.get("cash")))
        if cash is not None and amount * price_value > cash:
            return False, "insufficient cash"

    if record:
        state["count"] += 1
        if config.repeat_window_seconds and price_value is not None:
            state["last"][(str(code), side, amount, price_value)] = now or context.now()
    return True, "ok"


def calc_max_buy(account, price, lot_size=100):
    """按可用资金计算最大可买数量（整手向下取整）。"""
    cash = _to_float(account.get("available", account.get("cash"))) if account else 0
    price_value = _to_float(price)
    if not cash or not price_value or price_value <= 0:
        return 0
    return int((cash / price_value) / lot_size) * lot_size


def calc_max_sell(positions, code):
    """按统一持仓计算最大可卖数量。"""
    return _available_from_positions(positions, code)


def set_kill_switch(context, enabled=True):
    state = _state(context)
    state["kill_switch"] = bool(enabled)
    context.config.kill_switch = bool(enabled)
    return state["kill_switch"]
