# -*- coding: utf-8 -*-
"""交易 API：下单、目标持仓、撤单、订单/成交查询。

Phase 1 起所有下单入口先经过统一风控；默认返回统一 ``OrderRef``，
旧代码可传 ``legacy=True`` 取平台原始返回值。``dry_run`` 仍默认继承
``RuntimeConfig.dry_run``。
"""

from ..adapters import get_adapter
from ..core.contract import normalize_code
from ..core.errors import JingniError, ValidationError
from ..core.order import SIDE_BUY, SIDE_SELL
from ..core.risk import check_order
from ..core.runtime import resolve_context


def _effective_dry_run(context, dry_run):
    return context.config.dry_run if dry_run is None else bool(dry_run)


def _account_positions(adapter):
    account = None
    positions = []
    try:
        account = adapter.get_account()
    except Exception:
        account = None
    try:
        positions = adapter.get_positions()
    except Exception:
        positions = []
    return account, positions


def _wrap_order(ref, legacy):
    if legacy:
        return ref.get("raw")
    return ref


def jingni_order_amount(
    trade_mode,
    context_data,
    security_code,
    security_amount,
    security_price,
    dry_run=None,
    order_type="limit",
    remark=None,
    legacy=False,
    unit="share",
    check_sell_available=True,
):
    """按数量下单：正数买入，负数卖出；返回 OrderRef。

    ``unit`` 首批只支持 ``share``（股票/ETF/可转债统一按“股/张”语义）；
    期货/期权单位延后，不在这里做隐式换算。
    """
    try:
        if unit != "share":
            raise ValidationError("only unit='share' is supported in this release")
        amount = int(security_amount)
        price = None if security_price is None else float(security_price)
        if amount == 0:
            print("[JINGNI_ORDER] amount is zero, skip")
            return None
        if order_type != "market" and (price is None or price <= 0):
            raise ValidationError("security_price must be positive")
        context = resolve_context(trade_mode, context_data)
        adapter = get_adapter(trade_mode, context_data)
        account, positions = _account_positions(adapter)
        side = SIDE_BUY if amount > 0 else SIDE_SELL
        dry = _effective_dry_run(context, dry_run)
        ok, reason = check_order(
            context,
            normalize_code(security_code),
            side,
            abs(amount),
            price,
            account=account,
            positions=positions,
            record=not dry,
            check_sell_available=check_sell_available,
        )
        if not ok:
            print("[JINGNI_RISK] {0}".format(reason))
            return None
        if dry:
            print(
                "[JINGNI_DRY_RUN] {0} {1} x {2} @ {3}".format(
                    context.platform, side, abs(amount), price
                )
            )
            return None
        ref = adapter.order(
            security_code,
            side,
            abs(amount),
            price,
            order_type=order_type,
            remark=remark,
        )
        return _wrap_order(ref, legacy)
    except Exception as exc:
        print("[JINGNI_ORDER_ERROR] amount order failed: {0}".format(exc))
        if isinstance(exc, JingniError):
            raise
        raise JingniError("amount order failed: {0}".format(exc))


def jingni_order_value(
    trade_mode,
    context_data,
    security_code,
    security_value,
    security_price,
    dry_run=None,
    order_type="limit",
    remark=None,
    legacy=False,
    unit="share",
):
    """按金额下单：正数买入，负数卖出；返回 OrderRef。"""
    try:
        if unit != "share":
            raise ValidationError("only unit='share' is supported in this release")
        value = float(security_value)
        price = None if security_price is None else float(security_price)
        if price is None or price <= 0:
            raise ValidationError("security_price must be positive")
        context = resolve_context(trade_mode, context_data)
        adapter = get_adapter(trade_mode, context_data)
        account, positions = _account_positions(adapter)
        if value >= 0:
            cash = (account or {}).get("available", (account or {}).get("cash"))
            if cash is None:
                print("[JINGNI_ORDER_ERROR] cash is unavailable, skip buy")
                return None
            budget = min(value, float(cash))
            amount = int((budget // (price * 100)) * 100)
            if amount <= 0:
                return None
            ref = jingni_order_amount(
                context,
                context.raw,
                security_code,
                amount,
                price,
                dry_run=dry_run,
                order_type=order_type,
                remark=remark,
                legacy=False,
            )
            return _wrap_order(ref, legacy) if ref else None

        available = 0
        target = normalize_code(security_code)
        for item in positions:
            if item.get("code") == target:
                available = int(item.get("available") or 0)
                break
        requested = int(((-value) // (price * 100)) * 100)
        amount = min(requested, available)
        if amount <= 0:
            print("[JINGNI_ORDER_ERROR] no available position to sell")
            return None
        ref = jingni_order_amount(
            context,
            context.raw,
            security_code,
            -amount,
            price,
            dry_run=dry_run,
            order_type=order_type,
            remark=remark,
            legacy=False,
        )
        return _wrap_order(ref, legacy) if ref else None
    except Exception as exc:
        print("[JINGNI_ORDER_ERROR] value order failed: {0}".format(exc))
        if isinstance(exc, JingniError):
            raise
        raise JingniError("value order failed: {0}".format(exc))


def _position_amount(positions, code):
    for item in positions or []:
        if item.get("code") == code:
            return int(item.get("amount") or 0)
    return 0


def _open_exposure(orders, code):
    total = 0
    for order in orders or []:
        if order.get("code") != code:
            continue
        if order.get("status") in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
            continue
        remaining = int(order.get("amount") or 0) - int(order.get("filled") or 0)
        if order.get("side") == SIDE_BUY:
            total += remaining
        elif order.get("side") == SIDE_SELL:
            total -= remaining
    return total


def jingni_order_target_amount(
    trade_mode,
    context_data,
    security_code,
    target_amount,
    security_price=None,
    dry_run=None,
    remark=None,
):
    """目标持仓差额引擎：当前持仓 + 在途委托 → 差额下单。"""
    try:
        context = resolve_context(trade_mode, context_data)
        adapter = get_adapter(trade_mode, context_data)
        positions = adapter.get_positions()
        orders = adapter.get_orders(include_finished=False)
        code = normalize_code(security_code)
        target = int(target_amount)
        current = _position_amount(positions, code)
        exposure = _open_exposure(orders, code)
        delta = target - current - exposure
        if delta > 0:
            delta = int(delta / 100) * 100
        if delta == 0:
            return None
        price = security_price
        if price is None:
            frame = adapter.get_history(code, "1d", 1)
            series = adapter.column(frame, "close")
            if len(series) == 0:
                raise ValidationError("target order requires a price")
            price = float(series.iloc[-1])
        return jingni_order_amount(
            context,
            context.raw,
            code,
            delta,
            price,
            dry_run=dry_run,
            remark=remark,
        )
    except Exception as exc:
        print("[JINGNI_ORDER_ERROR] target amount failed: {0}".format(exc))
        if isinstance(exc, JingniError):
            raise
        raise JingniError("target amount failed: {0}".format(exc))


def jingni_order_target_value(
    trade_mode,
    context_data,
    security_code,
    target_value,
    security_price=None,
    dry_run=None,
    remark=None,
):
    """目标市值：按目标金额换算目标股数后走差额引擎。"""
    price = security_price
    if price is None:
        adapter = get_adapter(trade_mode, context_data)
        frame = adapter.get_history(normalize_code(security_code), "1d", 1)
        series = adapter.column(frame, "close")
        if len(series) == 0:
            raise ValidationError("target order requires a price")
        price = float(series.iloc[-1])
    target_amount = int(float(target_value) / float(price) / 100) * 100
    return jingni_order_target_amount(
        trade_mode,
        context_data,
        security_code,
        target_amount,
        price,
        dry_run=dry_run,
        remark=remark,
    )


def jingni_order_market(
    trade_mode,
    context_data,
    security_code,
    security_amount,
    protect_price=None,
    dry_run=None,
    remark=None,
):
    """市价单；保护价按平台能力传入。"""
    context = resolve_context(trade_mode, context_data)
    adapter = get_adapter(trade_mode, context_data)
    account, positions = _account_positions(adapter)
    side = SIDE_BUY if int(security_amount) > 0 else SIDE_SELL
    dry = _effective_dry_run(context, dry_run)
    ok, reason = check_order(
        context,
        normalize_code(security_code),
        side,
        abs(int(security_amount)),
        protect_price,
        account=account,
        positions=positions,
        record=not dry,
    )
    if not ok:
        print("[JINGNI_RISK] {0}".format(reason))
        return None
    if dry:
        print("[JINGNI_DRY_RUN] {0} market {1} x {2}".format(context.platform, side, abs(int(security_amount))))
        return None
    return adapter.order(
        security_code,
        side,
        abs(int(security_amount)),
        protect_price,
        order_type="market",
        remark=remark,
    )


def jingni_cancel_order(trade_mode, context_data, order_ref):
    adapter = get_adapter(trade_mode, context_data)
    return bool(adapter.cancel(order_ref))


def jingni_cancel_all(trade_mode, context_data):
    adapter = get_adapter(trade_mode, context_data)
    return adapter.cancel_all()


def jingni_close_all(trade_mode, context_data, dry_run=None):
    context = resolve_context(trade_mode, context_data)
    adapter = get_adapter(trade_mode, context_data)
    count = 0
    for position in adapter.get_positions():
        amount = int(position.get("available") or 0)
        if amount <= 0:
            continue
        code = position.get("code")
        frame = adapter.get_history(code, "1d", 1)
        series = adapter.column(frame, "close")
        if len(series) == 0:
            continue
        ref = jingni_order_amount(
            context,
            context.raw,
            code,
            -amount,
            float(series.iloc[-1]),
            dry_run=dry_run,
            remark="close_all",
        )
        if ref:
            count += 1
    return count


def jingni_get_orders(trade_mode, context_data, status=None, include_finished=True):
    adapter = get_adapter(trade_mode, context_data)
    return adapter.get_orders(status=status, include_finished=include_finished)


def jingni_get_trades(trade_mode, context_data, order_ref=None):
    adapter = get_adapter(trade_mode, context_data)
    return adapter.get_trades(order_ref=order_ref)


def jingni_portfolio_value(context, field):
    """内部辅助：避免 order_value 依赖旧函数签名。"""
    try:
        adapter = get_adapter(context, context.raw)
        return adapter.get_portfolio(field)
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] portfolio {0} failed: {1}".format(field, exc))
        return None
