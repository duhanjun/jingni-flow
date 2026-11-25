# -*- coding: utf-8 -*-
"""适配器基类：只负责原生调用、字段映射和异常翻译。"""

import pandas as pd

from ..core.contract import (
    canonical_tick_field,
    normalize_code,
    normalize_frequency,
    normalize_platform,
)
from ..core.errors import DataError
from ..core.order import make_order


class BaseAdapter(object):
    platform = "base"

    def __init__(self, context):
        self.context = context
        self.platform = normalize_platform(context.platform) or context.platform

    def normalize_code(self, code):
        return normalize_code(code, self.platform)

    def normalize_frequency(self, frequency):
        return normalize_frequency(frequency)

    def get_history(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        raise NotImplementedError

    def get_history_native(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        """旧接口返回形态；默认与统一形态一致。"""
        return self.get_history(code, frequency, count, end_time, fields, adjust)

    def get_history_range(
        self, code, frequency="1d", start_time=None, end_time=None, fields=None, adjust=None
    ):
        """按时间范围取历史行情；子类必须显式实现。"""
        raise NotImplementedError

    def download_history(
        self, codes, frequency="1d", start_time=None, end_time=None
    ):
        """下载/预热本地历史数据；默认平台（GM/PTrade）无需下载。"""
        return None

    def get_instruments(self, codes):
        """批量取标的元数据，返回 ``{canonical_code: dict}``。"""
        raise NotImplementedError

    def get_stock_status(self, codes, query_type="ST", date=None):
        """批量取股票状态，返回 ``{canonical_code: bool/None}``。"""
        raise NotImplementedError

    def get_trading_dates(self, start_date=None, end_date=None, market="SH"):
        """取交易日列表，返回 ``YYYYMMDD`` 字符串列表。"""
        raise NotImplementedError

    def get_tick_raw(self, codes, fields=None):
        raise NotImplementedError

    def get_tick(self, codes, fields=None):
        """返回 ``{canonical_code: {canonical_field: value}}``。"""
        raw = self.get_tick_raw(codes, fields)
        if not raw:
            return {}
        if isinstance(raw, dict):
            items = list(raw.items())
        elif isinstance(raw, (list, tuple)):
            items = []
            for index, item in enumerate(raw):
                if not isinstance(item, dict):
                    continue
                key = item.get("symbol") or item.get("code") or (
                    codes[index] if isinstance(codes, (list, tuple)) else codes
                )
                items.append((key, item))
        else:
            raise DataError("unsupported tick payload: {0}".format(type(raw)))

        result = {}
        for key, item in items:
            if not isinstance(item, dict):
                continue
            try:
                canonical = normalize_code(key)
            except Exception:
                canonical = str(key)
            values = {}
            for raw_field, value in item.items():
                canonical_field = canonical_tick_field(raw_field, self.platform)
                values[canonical_field] = value
            if fields:
                wanted = []
                for field in fields:
                    wanted.append(str(field))
                values = dict((k, v) for k, v in values.items() if k in wanted)
            result[canonical] = values
        return result

    def get_portfolio(self, field):
        raise NotImplementedError

    def order(self, code, side, amount, price=None, order_type="limit", remark=None):
        raise NotImplementedError

    def cancel(self, order_ref):
        raise NotImplementedError

    def cancel_all(self):
        raise NotImplementedError

    def get_orders(self, status=None, include_finished=True):
        raise NotImplementedError

    def get_trades(self, order_ref=None):
        raise NotImplementedError

    def get_positions(self):
        return self.get_portfolio("positions")

    def get_account(self):
        return {
            "total_asset": self.get_portfolio("assets_value"),
            "cash": self.get_portfolio("cash"),
            "available": self.get_portfolio("cash"),
            "market_value": self.get_portfolio("market_value"),
            "frozen": None,
            "pnl": None,
            "raw": None,
        }

    def _make_order(self, raw, code=None, side=None, amount=None, price=None, remark=None):
        """由平台原始订单构造统一订单；子类可覆盖字段映射。"""
        if isinstance(raw, dict):
            platform_id = (
                raw.get("cl_ord_id")
                or raw.get("order_id")
                or raw.get("id")
                or raw.get("m_strOrderSysID")
            )
            created = raw.get("created_at") or raw.get("insert_time")
            filled = raw.get("filled_volume") or raw.get("filled") or 0
            status = raw.get("status")
        else:
            platform_id = getattr(raw, "cl_ord_id", None)
            created = getattr(raw, "created_at", None)
            filled = getattr(raw, "filled_volume", 0)
            status = getattr(raw, "status", None)
        return make_order(
            self.platform,
            platform_id=platform_id or remark,
            code=code,
            side=side,
            price=price,
            amount=amount,
            filled=filled,
            status=status,
            created_at=created,
            remark=remark,
            raw=raw,
        )

    def frame(self, data, code=None):
        """把平台返回统一成 DataFrame，并处理 QMT 的字典/多级列。"""
        if data is None:
            return pd.DataFrame()
        current = data
        if isinstance(current, dict):
            candidates = []
            if code is not None:
                candidates.append(code)
                try:
                    candidates.append(normalize_code(code, self.platform))
                    candidates.append(normalize_code(code))
                except Exception:
                    pass
            for key in candidates:
                if key in current:
                    current = current[key]
                    break
            else:
                if len(current) == 1:
                    current = list(current.values())[0]
                else:
                    raise DataError(
                        "history payload has multiple codes but none matched: {0}".format(
                            code
                        )
                    )
        if not isinstance(current, pd.DataFrame):
            try:
                current = pd.DataFrame(current)
            except Exception as exc:
                raise DataError("cannot convert history payload to DataFrame: {0}".format(exc))
        if isinstance(current.columns, pd.MultiIndex):
            try:
                if code is not None:
                    for level in range(current.columns.nlevels):
                        values = current.columns.get_level_values(level)
                        if code in values:
                            current = current.xs(code, axis=1, level=level)
                            break
                        try:
                            normalized = normalize_code(code, self.platform)
                        except Exception:
                            normalized = None
                        if normalized is not None and normalized in values:
                            current = current.xs(normalized, axis=1, level=level)
                            break
                if isinstance(current.columns, pd.MultiIndex):
                    current.columns = [
                        "_".join([str(part) for part in col if part not in ("", None)])
                        for col in current.columns
                    ]
            except Exception:
                pass
        try:
            if current.index.name in ("stime", "time", "date", "datetime"):
                current = current.sort_index()
        except Exception:
            pass
        return current

    def column(self, frame, field):
        """从 DataFrame 取字段列，兼容单列/多级列/字段别名。"""
        if frame is None or frame.empty:
            return pd.Series([], dtype=float)
        if field in frame.columns:
            return frame[field]
        lowered = dict((str(col).lower(), col) for col in frame.columns)
        if str(field).lower() in lowered:
            return frame[lowered[str(field).lower()]]
        if len(frame.columns) == 1:
            return frame[frame.columns[0]]
        raise DataError("field not found in history data: {0}".format(field))
