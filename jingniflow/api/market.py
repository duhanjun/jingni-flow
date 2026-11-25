# -*- coding: utf-8 -*-
"""行情 API：历史、实时、单字段、多字段。"""

import pandas as pd

from ..adapters import get_adapter
from ..core.contract import normalize_code, normalize_frequency
from ..core.errors import ValidationError
from ..core.runtime import resolve_context

_EMPTY_SERIES = pd.Series([], dtype=float)


def _as_count(value):
    if value is None:
        return 1
    try:
        count = int(value)
    except Exception:
        raise ValidationError("count must be an integer: {0}".format(value))
    if count == 0:
        return 1
    return abs(count)


def _field_offset(security_count, offset, legacy):
    """旧接口的 security_count 语义：
    - 0 表示当前 bar；
    - 负数沿用 v0.1 的“倒数第 N 根”（-1 为当前，-2 为前一根）；
    - 正数按“向前 N 根”解释（v0.1 的正数分支未实现）。
    新代码建议直接传 offset：0 为当前，1 为前一根。
    """
    if offset is not None:
        return int(offset)
    value = int(security_count or 0)
    if value == 0:
        return 0
    if value < 0:
        return abs(value) - 1 if legacy else abs(value)
    return value


def _series_count(security_count, offset, legacy):
    if offset is not None:
        return abs(int(security_count or 0)) or 1, int(offset)
    value = int(security_count or 0)
    if value == 0:
        return 1, 0
    if value > 0:
        return value, 0
    if legacy:
        return abs(value) + 1, 0
    return abs(value), 0


def _empty_scalar():
    return 0


def jingni_get_current(trade_mode, context_data, security_code, security_field=None):
    """旧接口：返回平台原生实时行情。

    新代码请使用适配器的 ``get_tick`` 或后续的 ``jingni_get_tick``；
    这里保留原生返回形态，避免破坏已有策略。
    """
    adapter = get_adapter(trade_mode, context_data)
    return adapter.get_tick_raw(security_code, security_field)


def jingni_get_history(
    trade_mode,
    context_data,
    security_code,
    security_frequency,
    security_field,
    security_count,
    end_time=None,
    adjust=None,
):
    """旧接口：返回平台原生历史行情（gm/PTrade 为 DataFrame，QMT 为 dict）。

    ``security_count`` 取绝对值，正负号不再影响条数；旧代码的负号调用
    保持可用。新代码建议使用后续的 ``jingni_history``。
    """
    adapter = get_adapter(trade_mode, context_data)
    count = _as_count(security_count)
    return adapter.get_history_native(
        security_code,
        frequency=security_frequency,
        count=count,
        end_time=end_time,
        fields=security_field,
        adjust=adjust,
    )


def jingni_get_field(
    trade_mode,
    context_data,
    security_code,
    security_frequency,
    security_field,
    security_count=0,
    offset=None,
    legacy=False,
):
    """提取单字段数值。

    offset=0 为当前 bar，offset=1 为前一根；不传 offset 时按旧
    ``security_count`` 语义解释（见 ``_field_offset``）。空数据返回 0。
    """
    if security_field is None or str(security_field).strip() == "":
        raise ValidationError("security_field is required")
    context = resolve_context(trade_mode, context_data)
    adapter = get_adapter(trade_mode, context_data)
    code = normalize_code(security_code)
    freq = normalize_frequency(security_frequency)
    field = str(security_field).strip()
    bar_offset = _field_offset(security_count, offset, legacy)

    if bar_offset == 0 and context.is_live:
        tick = adapter.get_tick([code], [field])
        values = tick.get(code) or {}
        if field in values:
            try:
                return float(values[field])
            except Exception:
                return values[field]
        # 实时快照没有该字段时退回历史，避免返回字段名/None。
    try:
        frame = adapter.get_history(
            code, frequency=freq, count=bar_offset + 1, fields=[field]
        )
        series = adapter.column(frame, field)
        if len(series) == 0:
            return _empty_scalar()
        return series.iloc[-(bar_offset + 1)]
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] get_field failed: {0}".format(exc))
        return _empty_scalar()


def jingni_get_field_n(
    trade_mode,
    context_data,
    security_code,
    security_frequency,
    security_field,
    security_count=0,
    offset=None,
    legacy=False,
):
    """提取多字段序列。

    默认 ``security_count`` 的绝对值为条数（0 视为 1）；``legacy=True``
    时负数的 -N 仍返回 N+1 条（v0.1 行为）。返回 pandas.Series。
    """
    if security_field is None or str(security_field).strip() == "":
        raise ValidationError("security_field is required")
    context = resolve_context(trade_mode, context_data)
    adapter = get_adapter(trade_mode, context_data)
    code = normalize_code(security_code)
    freq = normalize_frequency(security_frequency)
    field = str(security_field).strip()
    count, bar_offset = _series_count(security_count, offset, legacy)

    if count == 1 and bar_offset == 0 and context.is_live:
        tick = adapter.get_tick([code], [field])
        values = tick.get(code) or {}
        if field in values:
            return pd.Series([values[field]], dtype=float)
    try:
        frame = adapter.get_history(
            code, frequency=freq, count=count + bar_offset, fields=[field]
        )
        series = adapter.column(frame, field)
        if len(series) == 0:
            return _EMPTY_SERIES
        if bar_offset:
            series = series.iloc[: -bar_offset]
        return series.reset_index(drop=True)
    except Exception as exc:
        print("[JINGNI_DATA_ERROR] get_field_n failed: {0}".format(exc))
        return _EMPTY_SERIES


def jingni_get_tick(trade_mode, context_data, security_codes, fields=None):
    """新接口：返回 ``{canonical_code: {field: value}}``。"""
    adapter = get_adapter(trade_mode, context_data)
    if isinstance(security_codes, (list, tuple)):
        codes = [normalize_code(code) for code in security_codes]
    else:
        codes = [normalize_code(security_codes)]
    return adapter.get_tick(codes, fields)


def jingni_history(
    trade_mode,
    context_data,
    security_code,
    security_frequency="1d",
    security_count=1,
    end_time=None,
    fields=None,
    adjust="pre",
):
    """新接口：统一 DataFrame；count 始终为正整数。"""
    adapter = get_adapter(trade_mode, context_data)
    return adapter.get_history(
        security_code,
        frequency=security_frequency,
        count=_as_count(security_count),
        end_time=end_time,
        fields=fields,
        adjust=adjust,
    )


def jingni_tick(trade_mode, context_data, security_codes, fields=None):
    """D-03 别名。"""
    return jingni_get_tick(trade_mode, context_data, security_codes, fields)


def jingni_get_history_range(
    trade_mode,
    context_data,
    security_code,
    security_frequency="1d",
    start_time=None,
    end_time=None,
    fields=None,
    adjust="pre",
):
    """D-02：按时间范围取历史行情，统一返回 DataFrame。

    与 ``jingni_history`` 的区别：本函数传起止时间，不依赖条数；
    PTrade 的 ``start_date`` 与 ``count`` 互斥，因此 ``start_time``
    必填，``end_time`` 为空时由平台取到最新。
    """
    if start_time is None or str(start_time).strip() == "":
        raise ValidationError("start_time is required for get_history_range")
    adapter = get_adapter(trade_mode, context_data)
    return adapter.get_history_range(
        security_code,
        frequency=security_frequency,
        start_time=start_time,
        end_time=end_time,
        fields=fields,
        adjust=adjust,
    )


def jingni_download_history(
    trade_mode,
    context_data,
    security_codes,
    security_frequency="1d",
    start_time=None,
    end_time=None,
):
    """D-08：下载/预热历史数据；GM/PTrade 为无操作，QMT 逐只下载。"""
    adapter = get_adapter(trade_mode, context_data)
    if isinstance(security_codes, (list, tuple, set)):
        codes = [normalize_code(item) for item in security_codes]
    else:
        codes = [normalize_code(security_codes)]
    return adapter.download_history(
        codes,
        frequency=security_frequency,
        start_time=start_time,
        end_time=end_time,
    )

