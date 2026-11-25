# -*- coding: utf-8 -*-
"""风控 API。"""

from ..adapters import get_adapter
from ..core.contract import normalize_code
from ..core.risk import calc_max_buy, calc_max_sell, check_order, set_kill_switch
from ..core.runtime import get_default_mode, resolve_context


def jingni_set_risk(config, trade_mode=None, context_data=None):
    """更新当前运行上下文的风控配置；支持 dict 或 RuntimeConfig。"""
    from ..core.config import RuntimeConfig

    context = resolve_context(trade_mode or get_default_mode(), context_data)
    if isinstance(config, RuntimeConfig):
        context.config = config
    elif isinstance(config, dict):
        context.config.update(**config)
    else:
        raise TypeError("config must be dict or RuntimeConfig")
    return context.config


def jingni_check_order(
    code,
    side,
    amount,
    price=None,
    trade_mode=None,
    context_data=None,
):
    """下单前风控检查，返回 ``(ok, reason)``。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    adapter = get_adapter(context, context.raw)
    account = adapter.get_account()
    positions = adapter.get_positions()
    return check_order(
        context,
        normalize_code(code),
        side,
        amount,
        price,
        account=account,
        positions=positions,
    )


def jingni_calc_max_buy(
    code,
    price=None,
    trade_mode=None,
    context_data=None,
):
    """按可用资金计算最大可买股数（100 股整手）。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    adapter = get_adapter(context, context.raw)
    if price is None:
        frame = adapter.get_history(normalize_code(code), "1d", 1)
        series = adapter.column(frame, "close")
        if len(series) == 0:
            return 0
        price = float(series.iloc[-1])
    return calc_max_buy(adapter.get_account(), price)


def jingni_calc_max_sell(code, trade_mode=None, context_data=None):
    """按统一持仓计算最大可卖股数。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    adapter = get_adapter(context, context.raw)
    return calc_max_sell(adapter.get_positions(), normalize_code(code))


def jingni_kill_switch(trade_mode=None, context_data=None, cancel_orders=True):
    """启用 kill switch：撤掉未完成委托并禁止后续下单。"""
    context = resolve_context(trade_mode or get_default_mode(), context_data)
    set_kill_switch(context, True)
    adapter = get_adapter(context, context.raw)
    count = 0
    if cancel_orders:
        count = adapter.cancel_all()
    print("[JINGNI_RISK] kill switch enabled; cancelled={0}".format(count))
    return count


def jingni_log(level, msg):
    print("[{0}] {1}".format(str(level).upper(), msg))
