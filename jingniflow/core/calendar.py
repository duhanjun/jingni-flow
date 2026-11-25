# -*- coding: utf-8 -*-
"""交易日历与会话时间的无平台依赖工具。"""

import datetime


def normalize_date(value):
    """把日期/时间/字符串统一为 ``YYYYMMDD``；无法识别返回 None。"""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, datetime.date):
        return value.strftime("%Y%m%d")
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return text[:8]


def format_date(value, sep="-"):
    """统一为 ``YYYY-MM-DD``（sep='' 时为 YYYYMMDD）。"""
    text = normalize_date(value)
    if text is None:
        return None
    if sep == "":
        return text
    return "{0}{1}{2}{1}{3}".format(
        text[:4], sep, text[4:6], text[6:8]
    )


def is_trading_session(value, include_auction=False):
    """判断时间是否落在 A 股连续竞价/集合竞价时段。

    默认只判断连续竞价：09:30—11:30、13:00—15:00。
    ``include_auction=True`` 时额外包含 09:15—09:25 开盘集合竞价。
    不判断节假日；节假日由交易日历接口负责。
    """
    if isinstance(value, datetime.datetime):
        current = value.time()
    elif isinstance(value, datetime.time):
        current = value
    else:
        return False
    if include_auction:
        if datetime.time(9, 15) <= current <= datetime.time(9, 25):
            return True
    if datetime.time(9, 30) <= current <= datetime.time(11, 30):
        return True
    if datetime.time(13, 0) <= current <= datetime.time(15, 0):
        return True
    return False


def is_weekday(value):
    if isinstance(value, datetime.datetime):
        return value.weekday() < 5
    if isinstance(value, datetime.date):
        return value.weekday() < 5
    text = normalize_date(value)
    if text is None:
        return False
    try:
        return datetime.datetime.strptime(text, "%Y%m%d").weekday() < 5
    except ValueError:
        return False
