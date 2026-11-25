# -*- coding: utf-8 -*-
"""生命周期 API。

v0.1 的 ``jingni_main`` 是一个墙钟 ``while True`` 主循环，与三家平台的
事件模型冲突。Phase 0 起它只做初始化并立即返回，由平台事件驱动策略；
``jingni_handle_data`` 也不再内部 sleep/循环。
"""

import datetime

from ..core.runtime import get_default_mode, resolve_context
from .runtime import jingni_setup


_ACTIVE_STRATEGY = None


def jingni_trade_strategy(trade_mode, context_data):
    """策略逻辑占位；未注册策略时使用，用户可覆盖或在此写入自己的信号。"""
    print("交易策略正在运行中，请写入你的策略逻辑")


def jingni_set_strategy(strategy):
    """注册默认策略函数；传 ``None`` 恢复占位实现。

    策略函数签名为 ``strategy(trade_mode, context_data)``。注册后，
    ``jingni_handle_data`` 每次触发都会调用它；也可以在
    ``jingni_main(..., strategy=...)`` 或 ``jingni_handle_data(...,
    strategy=...)`` 中显式传入，显式参数优先于默认注册。
    """
    global _ACTIVE_STRATEGY
    if strategy is not None and not callable(strategy):
        raise TypeError("strategy must be callable or None")
    _ACTIVE_STRATEGY = strategy
    return strategy


def jingni_get_strategy(trade_mode=None, context_data=None):
    """返回当前默认策略函数；参数保留用于兼容后续上下文扩展。"""
    return _ACTIVE_STRATEGY


def jingni_before_trading_start(trade_mode, context_data):
    print(datetime.datetime.now(), "开始运行盘前函数")
    print(datetime.datetime.now(), "结束运行盘前函数")


def _coerce_time(value):
    if value is None:
        return None
    if isinstance(value, datetime.time):
        return value
    if isinstance(value, datetime.datetime):
        return value.time()
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(text, fmt).time()
        except Exception:
            continue
    return None


def jingni_handle_data(
    trade_mode,
    context_data,
    trade_start_time=None,
    trade_end_time=None,
    trade_seconds=None,
    strategy=None,
):
    """执行一次盘中逻辑；是否在交易时段由平台事件决定。"""
    context = resolve_context(trade_mode, context_data)
    now_time = context.now().time()
    start = _coerce_time(trade_start_time)
    end = _coerce_time(trade_end_time)
    if start is not None and now_time < start:
        return
    if end is not None and now_time > end:
        return

    strategy_func = strategy
    if strategy_func is None:
        strategy_func = _ACTIVE_STRATEGY
    if strategy_func is None:
        strategy_func = jingni_trade_strategy
    if not callable(strategy_func):
        raise TypeError("strategy must be callable")
    return strategy_func(trade_mode, context_data)


def jingni_after_trading_end(trade_mode, context_data):
    print(datetime.datetime.now(), "开始运行盘后函数")
    print(datetime.datetime.now(), "结束运行盘后函数")


def jingni_main(trade_mode, context_data, config=None, strategy=None):
    """初始化入口；不再阻塞、不再自建交易日循环。"""
    if strategy is not None:
        jingni_set_strategy(strategy)
    context = jingni_setup(trade_mode or get_default_mode(), context_data, config)
    print("[JINGNI] ready; platform events drive the strategy")
    return context
