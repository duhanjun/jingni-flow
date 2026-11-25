# -*- coding: utf-8 -*-
"""交易日历与交易时段 API。"""

import datetime

from ..adapters import get_adapter
from ..core.calendar import is_trading_session, is_weekday, normalize_date
from ..core.runtime import get_default_mode, resolve_context

# 交易日历在交易日内是静态数据；按 (平台, 起, 止, 市场) 缓存，避免
# 每次 handle_data 都向柜台/行情服务查询。只缓存显式日期范围。
_CALENDAR_CACHE = {}
_CALENDAR_CACHE_LIMIT = 256


def _calendar_key(trade_mode, context_data, start_date, end_date, market):
    start = normalize_date(start_date)
    end = normalize_date(end_date)
    if start is None or end is None:
        return None
    mode = trade_mode or get_default_mode()
    context_token = id(context_data) if context_data is not None else None
    return (
        str(mode).lower(),
        context_token,
        start,
        end,
        str(market or "SH").upper(),
    )


def jingni_get_trading_dates(
    trade_mode,
    context_data,
    start_date=None,
    end_date=None,
    market="SH",
):
    """I-02：返回指定范围的交易日，格式 ``YYYYMMDD``。

    三家平台差异：
    - 掘金：``get_trading_dates_by_year``，失败时降级 ``get_trading_dates``；
    - QMT：``get_trading_dates``，``count`` 必须大于 0；
    - PTrade：``get_trade_days``。
    """
    key = _calendar_key(trade_mode, context_data, start_date, end_date, market)
    if key is not None and key in _CALENDAR_CACHE:
        return list(_CALENDAR_CACHE[key])
    adapter = get_adapter(trade_mode or get_default_mode(), context_data)
    try:
        result = adapter.get_trading_dates(
            start_date=start_date, end_date=end_date, market=market
        )
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] trading_dates failed: {0}".format(exc))
        return []
    if key is not None:
        if len(_CALENDAR_CACHE) >= _CALENDAR_CACHE_LIMIT:
            _CALENDAR_CACHE.clear()
        _CALENDAR_CACHE[key] = list(result or [])
    return result


def jingni_is_trading_day(trade_mode=None, context_data=None, date=None):
    """I-04：判断指定日期是否为交易日；默认使用策略当前日期。"""
    target = normalize_date(date)
    if target is None:
        try:
            target = resolve_context(
                trade_mode or get_default_mode(), context_data
            ).trade_date()
        except Exception:
            target = datetime.date.today().strftime("%Y%m%d")
    dates = jingni_get_trading_dates(
        trade_mode,
        context_data,
        start_date=target,
        end_date=target,
    )
    if dates:
        return target in dates
    # 平台日历不可用时按工作日降级；日历可用但返回空，说明是非交易日。
    try:
        adapter = get_adapter(trade_mode or get_default_mode(), context_data)
        dates = adapter.get_trading_dates(target, target)
    except Exception:
        return is_weekday(target)
    return target in (dates or [])


def jingni_is_trading_time(
    trade_mode=None,
    context_data=None,
    now=None,
    include_auction=False,
):
    """R-04：判断当前/指定时间是否处于 A 股交易时段。

    默认只包含连续竞价 09:30—11:30、13:00—15:00；
    ``include_auction=True`` 时额外包含 09:15—09:25。
    节假日优先使用平台交易日历；无平台上下文时仅按工作日降级。
    """
    if now is None:
        try:
            current = resolve_context(
                trade_mode or get_default_mode(), context_data
            ).now()
        except Exception:
            current = datetime.datetime.now()
    elif not isinstance(now, datetime.datetime):
        text = str(now).strip().replace("-", "").replace("/", "")
        parsed = None
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
            try:
                parsed = datetime.datetime.strptime(text[: len(fmt)], fmt)
                break
            except ValueError:
                continue
        current = parsed or datetime.datetime.now()
    else:
        current = now

    if not is_trading_session(current, include_auction=include_auction):
        return False
    if trade_mode is not None or context_data is not None:
        try:
            if not jingni_is_trading_day(
                trade_mode, context_data, current.date()
            ):
                return False
        except Exception:
            return is_weekday(current)
        return True
    return is_weekday(current)
