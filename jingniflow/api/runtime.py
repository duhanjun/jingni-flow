# -*- coding: utf-8 -*-
"""运行时 API：交易日、交易时间、初始化。"""

import datetime

from ..core.config import RuntimeConfig
from ..core.contract import normalize_platform
from ..core.runtime import (
    get_default_mode,
    platform_call,
    resolve_context,
    set_default_mode,
)


def jingni_setup(trade_mode, context_data, config=None):
    """初始化并返回 RuntimeContext；不启动任何循环。"""
    mode = normalize_platform(trade_mode) or get_default_mode()
    set_default_mode(mode)
    if config is None:
        config = RuntimeConfig()
    context = resolve_context(mode, context_data, config=config)
    print(
        "[JINGNI] platform={0} mode={1} python={2}".format(
            context.platform, context.mode, _python_version()
        )
    )
    return context


def _python_version():
    from ..core.runtime import python_version_text

    return python_version_text()


def jingni_trading_dates(trade_mode, context_data, trading_dates_count):
    """返回相对当前交易日的第 N 个交易日，格式 YYYYMMDD。"""
    context = resolve_context(trade_mode, context_data)
    count = int(trading_dates_count)
    try:
        if context.platform == "goldminer":
            if count == 0:
                return context.trade_date()
            day = context.trade_date("%Y-%m-%d")
            if count > 0:
                dates = platform_call(
                    "get_next_n_trading_dates",
                    exchange="SHSE",
                    date=day,
                    n=count,
                )
                if not dates:
                    return None
                return dates[-1].strftime("%Y%m%d") if hasattr(dates[-1], "strftime") else str(dates[-1]).replace("-", "")[:8]
            dates = platform_call(
                "get_previous_n_trading_dates",
                exchange="SHSE",
                date=day,
                n=abs(count),
            )
            if not dates:
                return None
            return dates[0].strftime("%Y%m%d") if hasattr(dates[0], "strftime") else str(dates[0]).replace("-", "")[:8]
        if context.platform == "ptrade":
            value = platform_call("get_trading_day", count)
            if value is None:
                return None
            if hasattr(value, "strftime"):
                return value.strftime("%Y%m%d")
            return str(value).replace("-", "")[:8]
        if context.platform == "qmt":
            if count == 0:
                return context.trade_date()
            raw = context.raw
            if raw is None or not hasattr(raw, "get_trading_dates"):
                return None
            # QMT 官方要求 count 必须大于 0，不能用 -1。
            dates = raw.get_trading_dates("", "", "", abs(count) + 1, "1d")
            if not dates:
                return None
            current = context.trade_date()
            texts = []
            for item in dates:
                if hasattr(item, "strftime"):
                    texts.append(item.strftime("%Y%m%d"))
                else:
                    texts.append(str(item).replace("-", "")[:8])
            if current not in texts:
                return None
            index = texts.index(current)
            target = index + count
            if target < 0 or target >= len(texts):
                return None
            return texts[target]
        return None
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] trading_dates failed: {0}".format(exc))
        return None


def jingni_trading_times(trade_mode, context_data):
    """返回策略时钟的 ``datetime.time``。"""
    try:
        return resolve_context(trade_mode, context_data).now().time()
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] trading_times failed: {0}".format(exc))
        return None


def jingni_now(trade_mode, context_data):
    """返回平台策略时钟；回测返回回测时间。"""
    return resolve_context(trade_mode, context_data).now()


def jingni_wall_now():
    """返回本机墙钟；仅用于日志/提示，不用于回测决策。"""
    return datetime.datetime.now()


def _date_text(value):
    text = str(value).strip().replace("-", "")
    if len(text) < 8:
        raise ValueError("date must be YYYYMMDD")
    return text[:8]


def jingni_offset_trade_date(offset, date=None, trade_mode=None, context_data=None):
    """相对 date/当前交易日偏移 N 个交易日，返回 YYYYMMDD。

    掘金直接使用 ``get_previous/next_n_trading_dates`` 的 date 参数；
    QMT 从完整交易日历中定位；PTrade 只支持相对当前交易日，跨日期
    锚点返回 ``None`` 并提示，不做自然日近似。
    """
    mode = normalize_platform(trade_mode or get_default_mode())
    context = resolve_context(mode, context_data)
    count = int(offset)
    if date is None:
        return jingni_trading_dates(mode, context_data, count)
    anchor = _date_text(date)
    if count == 0:
        return anchor
    try:
        if mode == "goldminer":
            if count > 0:
                dates = platform_call(
                    "get_next_n_trading_dates",
                    exchange="SHSE",
                    date=anchor,
                    n=count,
                )
                return _format_trade_date(dates[-1]) if dates else None
            dates = platform_call(
                "get_previous_n_trading_dates",
                exchange="SHSE",
                date=anchor,
                n=abs(count),
            )
            return _format_trade_date(dates[0]) if dates else None
        if mode == "qmt":
            raw = context.raw
            if raw is None or not hasattr(raw, "get_trading_dates"):
                return None
            dates = raw.get_trading_dates("", "", "", 10000, "1d")
            texts = [_format_trade_date(item) for item in dates or []]
            if anchor not in texts:
                return None
            index = texts.index(anchor) + count
            if index < 0 or index >= len(texts):
                return None
            return texts[index]
        if anchor == context.trade_date():
            return jingni_trading_dates(mode, context_data, count)
        print("[JINGNI_DATA_ERROR] PTrade date anchor not supported: {0}".format(anchor))
        return None
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] offset_trade_date failed: {0}".format(exc))
        return None


def _format_trade_date(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")[:8]


def _schedule_clock(value):
    """把 ``09:31`` / ``9:31:0`` 统一成 (时, 分, 秒)。"""
    text = str(value).strip().replace("：", ":")
    parts = text.split(":")
    if len(parts) < 2:
        raise ValueError("time_rule must be HH:MM or HH:MM:SS: {0}".format(value))
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError("time_rule out of range: {0}".format(value))
    return hour, minute, second


def _schedule_time_text(value, mode):
    hour, minute, second = _schedule_clock(value)
    if mode == "goldminer":
        return "{0:02d}:{1:02d}:{2:02d}".format(hour, minute, second)
    if mode == "qmt":
        return "{0:02d}{1:02d}{2:02d}".format(hour, minute, second)
    if mode == "ptrade":
        return "{0:02d}:{1:02d}".format(hour, minute)
    return "{0:02d}:{1:02d}:{2:02d}".format(hour, minute, second)


def jingni_schedule(
    func,
    time_rule="09:31",
    date_rule="1d",
    name=None,
    trade_mode=None,
    context_data=None,
):
    """注册平台定时任务；返回 task_id/name。

    掘金：``schedule``；QMT：``schedule_run(repeat_times=-1)``；
    PTrade：``run_daily(context, func, time)``。不创建本地线程。
    """
    mode = normalize_platform(trade_mode or get_default_mode())
    context = resolve_context(mode, context_data)
    task_name = name or getattr(func, "__name__", "jingni_task")
    try:
        clock = _schedule_time_text(time_rule, mode)
        date_text = str(date_rule or "1d").strip().lower()
        if mode == "goldminer":
            platform_call(
                "schedule",
                schedule_func=func,
                date_rule=date_text,
                time_rule=clock,
            )
            return task_name
        if mode == "qmt":
            trade_date = context.trade_date()
            raw = context.raw
            if raw is not None and hasattr(raw, "schedule_run"):
                raw.schedule_run(
                    func,
                    "{0}{1}".format(trade_date, clock),
                    -1,
                    datetime.timedelta(days=1),
                    task_name,
                )
                return task_name
            platform_call(
                "schedule_run",
                func,
                "{0}{1}".format(trade_date, clock),
                -1,
                datetime.timedelta(days=1),
                task_name,
            )
            return task_name
        if mode == "ptrade":
            platform_call("run_daily", context.raw, func, time=clock)
            return task_name
        raise ValueError("unsupported platform: {0}".format(mode))
    except Exception as exc:
        print("[JINGNI_SCHEDULE] failed: {0}".format(exc))
        return None


def jingni_run_interval(
    func,
    seconds=3,
    trade_mode=None,
    context_data=None,
):
    """R-08：按秒级间隔注册定时器。

    平台差异：
    - 掘金 ``timer`` 的 period 单位是毫秒，本函数把 seconds 转毫秒；
    - QMT ``ContextInfo.run_time`` 只接受函数名字符串，且回测无效；
    - PTrade ``run_interval`` 最小 3 秒，本函数自动下限到 3。
    返回平台定时器句柄；QMT 回测返回 None。
    """
    mode = normalize_platform(trade_mode or get_default_mode())
    context = resolve_context(mode, context_data)
    interval = max(1, int(seconds))
    try:
        if mode == "goldminer":
            return platform_call(
                "timer",
                timer_func=func,
                period=interval * 1000,
                start_delay=0,
            )
        if mode == "qmt":
            if context.is_backtest:
                print("[JINGNI_SCHEDULE] QMT run_time is not effective in backtest")
                return None
            name = func if isinstance(func, str) else getattr(func, "__name__", None)
            if not name:
                raise ValueError("QMT run_time requires a named function")
            raw = context.raw
            if raw is None or not hasattr(raw, "run_time"):
                raise ValueError("QMT ContextInfo.run_time is unavailable")
            return raw.run_time(
                name,
                "{0}nSecond".format(interval),
                "1970-01-01 00:00:00",
            )
        if mode == "ptrade":
            return platform_call(
                "run_interval", context.raw, func, seconds=max(3, interval)
            )
        raise ValueError("unsupported platform: {0}".format(mode))
    except Exception as exc:
        print("[JINGNI_SCHEDULE] run_interval failed: {0}".format(exc))
        return None
