# -*- coding: utf-8 -*-
"""掘金量化适配器。"""

import datetime

from ..core.calendar import normalize_date
from ..core.contract import (
    map_adjust,
    map_history_fields,
    map_tick_field,
    normalize_code,
    normalize_frequency,
)
from ..core.errors import PlatformApiMissing
from ..core.instrument import (
    board_from_code,
    build_instrument,
    bool_or_none,
    first_value,
    records,
)
from ..core.order import (
    SIDE_BUY,
    coerce_order_ref,
    make_order,
    normalize_side,
    ref_matches,
)
from ..core.runtime import get_platform_constant, platform_call
from .base import BaseAdapter


class GoldminerAdapter(BaseAdapter):
    platform = "goldminer"

    def get_history(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        code = self.normalize_code(code)
        freq = normalize_frequency(frequency)
        fields = map_history_fields(fields, self.platform)
        end = end_time or self.context.now()
        if isinstance(end, datetime.datetime):
            fmt = "%Y-%m-%d" if freq in ("1d", "1w", "1M") else "%Y-%m-%d %H:%M:%S"
            end_text = end.strftime(fmt)
        else:
            end_text = str(end)
        data = platform_call(
            "history_n",
            symbol=code,
            frequency=freq,
            count=int(count),
            end_time=end_text,
            fields=",".join(fields),
            adjust=get_platform_constant(map_adjust(adjust, self.platform)),
            df=True,
        )
        return self.frame(data, code)

    def get_history_native(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        return self.get_history(code, frequency, count, end_time, fields, adjust)

    def get_history_range(
        self, code, frequency="1d", start_time=None, end_time=None, fields=None, adjust=None
    ):
        code = self.normalize_code(code)
        freq = normalize_frequency(frequency)
        fields = map_history_fields(fields, self.platform)
        start = _range_time_text(start_time)
        end = _range_time_text(end_time or self.context.now())
        data = platform_call(
            "history",
            symbol=code,
            frequency=freq,
            start_time=start,
            end_time=end,
            fields=",".join(fields),
            adjust=get_platform_constant(map_adjust(adjust, self.platform)),
            df=True,
        )
        return self.frame(data, code)

    def get_instruments(self, codes):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        symbols = [self.normalize_code(code) for code in codes]
        data = None
        try:
            data = platform_call("get_instruments", symbols=symbols, df=True)
        except Exception:
            data = None
        if data is None:
            try:
                data = platform_call(
                    "get_symbol_infos",
                    sec_type1=1010,
                    symbols=symbols,
                    df=True,
                )
            except Exception:
                data = None
        result = {}
        for row in records(data):
            raw_code = first_value(row, ("symbol", "sec_id", "sec_code", "code"))
            if raw_code is None:
                continue
            try:
                canonical = normalize_code(raw_code)
            except Exception:
                continue
            listed = first_value(row, ("listed_date", "open_date", "list_date"))
            delisted = first_value(row, ("delisted_date", "de_listed_date"))
            result[canonical] = build_instrument(
                canonical,
                name=first_value(row, ("sec_name", "symbol_name", "instrument_name", "name")),
                board=first_value(row, ("board", "sector")) or board_from_code(canonical),
                lot_size=first_value(row, ("lot_size", "volume_multiple", "round_lot"), 100),
                tick_size=first_value(row, ("price_tick", "tick_size")),
                limit_up=first_value(row, ("limit_up", "upper_limit", "up_limit")),
                limit_down=first_value(row, ("limit_down", "lower_limit", "down_limit")),
                listed_date=listed,
                status={
                    "st": _state_bool(first_value(row, ("is_st", "st", "st_status"))),
                    "suspend": _state_bool(
                        first_value(row, ("is_suspended", "suspended", "is_suspend"))
                    ),
                    "delisted": _is_delisted(delisted),
                },
            )
        for code in codes:
            canonical = normalize_code(code)
            if canonical not in result:
                result[canonical] = build_instrument(canonical)
        return result

    def get_stock_status(self, codes, query_type="ST", date=None):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        instruments = self.get_instruments(codes)
        key = {
            "ST": "st",
            "HALT": "suspend",
            "SUSPEND": "suspend",
            "DELISTING": "delisted",
            "DELISTED": "delisted",
        }.get(str(query_type).upper(), "st")
        return dict(
            (code, (instruments.get(code) or {}).get("status", {}).get(key))
            for code in [normalize_code(item) for item in codes]
        )

    def get_trading_dates(self, start_date=None, end_date=None, market="SH"):
        current = self.context.trade_date()
        start = normalize_date(start_date) or current
        end = normalize_date(end_date) or start
        exchange = _exchange(market)
        rows = None
        api_available = False
        try:
            rows = platform_call(
                "get_trading_dates_by_year",
                exchange=exchange,
                start_year=int(start[:4]),
                end_year=int(end[:4]),
            )
            api_available = True
        except Exception:
            rows = None
        values = []
        for row in records(rows):
            if isinstance(row, (datetime.date, datetime.datetime)):
                values.append(normalize_date(row))
                continue
            if isinstance(row, str):
                values.append(normalize_date(row))
                continue
            value = first_value(row, ("trade_date", "date", "trade_day"))
            if value is not None:
                values.append(normalize_date(value))
        if not values:
            try:
                native = platform_call(
                    "get_trading_dates",
                    exchange=exchange,
                    start_date=start,
                    end_date=end,
                )
                api_available = True
                for item in native or []:
                    values.append(normalize_date(item))
            except Exception:
                pass
        if not api_available:
            raise PlatformApiMissing("goldminer trading calendar is unavailable")
        return sorted(set(item for item in values if item and start <= item <= end))

    def get_tick_raw(self, codes, fields=None):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        symbols = [self.normalize_code(code) for code in codes]
        platform_fields = None
        if fields:
            platform_fields = [
                map_tick_field(field, self.platform) for field in fields
            ]
        kwargs = {"symbols": ",".join(symbols)}
        if platform_fields:
            kwargs["fields"] = ",".join(platform_fields)
        return platform_call("current", **kwargs)

    def get_portfolio(self, field):
        try:
            account = self.context.raw.account()
        except Exception as exc:
            raise PlatformApiMissing("goldminer account() failed: {0}".format(exc))
        cash = account.cash
        positions = account.positions()
        if field == "assets_value":
            return cash["nav"]
        if field == "market_value":
            return cash["market_value"]
        if field == "cash":
            return cash["balance"]
        if field == "positions":
            return positions
        raise PlatformApiMissing("unsupported portfolio field: {0}".format(field))

    def _normalize_order(self, raw, code=None, side=None, amount=None, price=None, remark=None):
        if isinstance(raw, dict):
            data = raw
        else:
            data = {}
            for key in (
                "cl_ord_id",
                "order_id",
                "ord_id",
                "symbol",
                "side",
                "price",
                "volume",
                "filled_volume",
                "status",
                "created_at",
                "insert_time",
                "order_remark",
            ):
                value = getattr(raw, key, None)
                if value is not None:
                    data[key] = value
        raw_code = data.get("symbol") or code
        try:
            raw_code = normalize_code(raw_code)
        except Exception:
            pass
        return make_order(
            self.platform,
            platform_id=data.get("cl_ord_id")
            or data.get("order_id")
            or data.get("ord_id")
            or remark,
            code=raw_code,
            side=data.get("side") or side,
            price=data.get("price", price),
            amount=data.get("volume", amount),
            filled=data.get("filled_volume", 0),
            status=data.get("status"),
            status_code=data.get("status"),
            created_at=data.get("created_at") or data.get("insert_time"),
            remark=remark or data.get("order_remark"),
            raw=raw,
        )

    def order(self, code, side, amount, price=None, order_type="limit", remark=None):
        code = self.normalize_code(code)
        side = str(side).upper()
        side_value = get_platform_constant(
            "OrderSide_Buy" if side == SIDE_BUY else "OrderSide_Sell"
        )
        order_type_value = get_platform_constant(
            "OrderType_Market" if order_type == "market" else "OrderType_Limit"
        )
        effect = get_platform_constant(
            "PositionEffect_Open" if side == SIDE_BUY else "PositionEffect_Close"
        )
        duration = get_platform_constant("OrderDuration_GFD", 3)
        raw = platform_call(
            "order_volume",
            symbol=code,
            volume=int(amount),
            price=float(price or 0),
            side=side_value,
            order_type=order_type_value,
            position_effect=effect,
            order_duration=duration,
        )
        # 掘金 order_volume 返回 list[Order]；取第一笔，避免把 list 丢掉后
        # 只能拿 remark 当 platform_order_id。
        if isinstance(raw, (list, tuple)):
            raw = raw[0] if raw else None
        return self._normalize_order(
            raw, code=normalize_code(code), side=side, amount=amount, price=price, remark=remark
        )

    def cancel(self, order_ref):
        ref = coerce_order_ref(order_ref)
        if not isinstance(ref, dict):
            return False
        raw_order = order_ref.get("raw") if isinstance(order_ref, dict) else None
        # 优先使用原始 Order 的 cl_ord_id；ref["id"] 在下单返回对象不完整时
        # 可能只是 remark，直接拿去撤单会被柜台当成未知委托。
        order_id = None
        if raw_order is not None:
            if isinstance(raw_order, dict):
                order_id = raw_order.get("cl_ord_id")
            else:
                order_id = getattr(raw_order, "cl_ord_id", None)
        order_id = order_id or ref.get("platform_order_id") or ref.get("id") or ref.get("remark")
        if not order_id:
            return False
        # 掘金 order_cancel 的每个字典必须同时包含 cl_ord_id 和 account_id。
        # 注意：Order.account_id 在部分仿真环境会被填成 strategy_id，不能
        # 直接当账户号；优先从 Account/Cash 对象取真实 account_id。
        account_id = None
        try:
            account = self.context.raw.account()
            cash = getattr(account, "cash", None)
            if isinstance(cash, dict):
                account_id = cash.get("account_id")
            if not account_id:
                account_id = getattr(cash, "account_id", None)
            if not account_id:
                account_id = getattr(account, "id", None)
            if not account_id:
                account_id = getattr(account, "account_id", None)
        except Exception:
            account_id = None
        if not account_id:
            account_id = getattr(self.context.config, "account_id", None)
        if not account_id and raw_order is not None:
            if isinstance(raw_order, dict):
                account_id = raw_order.get("account_name") or raw_order.get("account_id")
            else:
                account_id = getattr(raw_order, "account_name", None) or getattr(
                    raw_order, "account_id", None
                )
        if not account_id:
            return False
        payload = {"cl_ord_id": str(order_id), "account_id": str(account_id)}
        # 掘金 Python SDK 的 order_cancel 接收单个字典，也接受字典列表。
        result = platform_call("order_cancel", wait_cancel_orders=[payload])
        return bool(result) if result is not None else True

    def cancel_all(self):
        result = platform_call("order_cancel_all")
        return result

    def get_orders(self, status=None, include_finished=True):
        try:
            rows = platform_call("get_orders")
        except Exception:
            rows = None
        if rows is None and not include_finished:
            try:
                rows = platform_call("get_unfinished_orders")
            except Exception:
                rows = []
        result = []
        for row in rows or []:
            order = self._normalize_order(row)
            if status is not None and order["status"] != str(status).upper():
                continue
            if not include_finished and order["status"] in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
                continue
            result.append(order)
        return result

    def get_trades(self, order_ref=None):
        try:
            rows = platform_call("get_execution_reports")
        except Exception:
            rows = []
        result = []
        for row in rows or []:
            if isinstance(row, dict):
                data = row
            else:
                data = {}
                for key in (
                    "cl_ord_id",
                    "order_id",
                    "symbol",
                    "price",
                    "volume",
                    "side",
                    "created_at",
                ):
                    value = getattr(row, key, None)
                    if value is not None:
                        data[key] = value
            ref = coerce_order_ref(order_ref)
            if ref is not None:
                ids = (
                    str(data.get("cl_ord_id") or ""),
                    str(data.get("order_id") or ""),
                )
                if isinstance(ref, dict) and ref.get("id") and str(ref["id"]) not in ids:
                    continue
            result.append(
                {
                    "code": self._safe_code(data.get("symbol")),
                    "order_id": data.get("cl_ord_id") or data.get("order_id"),
                    "price": data.get("price"),
                    "amount": data.get("volume"),
                    "side": normalize_side(data.get("side")),
                    "created_at": data.get("created_at"),
                    "raw": row,
                }
            )
        return result

    def get_positions(self):
        positions = []
        for item in self.get_portfolio("positions") or []:
            data = item if isinstance(item, dict) else getattr(item, "__dict__", {})
            code = self._safe_code(
                data.get("symbol") or getattr(item, "symbol", None)
            )
            total = int(data.get("volume") or getattr(item, "volume", 0) or 0)
            today = int(
                data.get("volume_today") or getattr(item, "volume_today", 0) or 0
            )
            positions.append(
                {
                    "code": code,
                    "amount": total,
                    "available": max(0, total - today),
                    "cost": data.get("vwap") or getattr(item, "vwap", None),
                    "market_value": data.get("market_value")
                    or getattr(item, "market_value", None),
                    "pnl": data.get("unrealized_pnl")
                    or getattr(item, "unrealized_pnl", None),
                    "raw": item,
                }
            )
        return positions

    def get_account(self):
        cash = self.context.raw.account().cash
        return {
            "total_asset": cash.get("nav"),
            "cash": cash.get("balance"),
            "available": cash.get("available", cash.get("balance")),
            "market_value": cash.get("market_value"),
            "frozen": cash.get("frozen"),
            "pnl": cash.get("pnl"),
            "raw": cash,
        }

    def _safe_code(self, code):
        try:
            return normalize_code(code)
        except Exception:
            return code

    def _matches(self, order, ref):
        return ref_matches(order, ref)


def _exchange(market):
    return {"SH": "SHSE", "SZ": "SZSE", "BJ": "BJSE"}.get(
        str(market or "SH").upper(), "SHSE"
    )


def _range_time_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip()
    compact = text.replace("-", "").replace("/", "")
    if len(compact) >= 8 and compact[:8].isdigit() and len(text) <= 10:
        return "{0}-{1}-{2}".format(compact[:4], compact[4:6], compact[6:8])
    return text


def _state_bool(value):
    """GM 状态字段可能是 bool、0/1、'ST'/'正常'，统一为 bool/None。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("st", "*st", "true", "1", "yes"):
        return True
    if text in ("normal", "false", "0", "no", "none"):
        return False
    return bool_or_none(value)


def _is_delisted(value):
    if value is None or value == "":
        return None
    text = str(value).replace("-", "")[:8]
    if not text.isdigit():
        return bool_or_none(value)
    today = datetime.date.today().strftime("%Y%m%d")
    return text <= today
