# -*- coding: utf-8 -*-
"""PTrade 适配器。"""

import datetime

from ..core.calendar import normalize_date
from ..core.contract import (
    map_adjust,
    map_history_fields,
    normalize_code,
    normalize_frequency,
)
from ..core.errors import PlatformApiMissing
from ..core.instrument import (
    board_from_code,
    build_instrument,
    first_value,
    records,
)
from ..core.order import SIDE_BUY, coerce_order_ref, make_order, normalize_side
from ..core.runtime import platform_call
from .base import BaseAdapter


class PtradeAdapter(BaseAdapter):
    platform = "ptrade"

    def __init__(self, context):
        super(PtradeAdapter, self).__init__(context)
        # order() 返回策略订单 id；get_orders() 可能还没回写这笔新单。
        # 适配器每次调用都会重建，因此把待查 id 挂在长期存活的 context 上。
        pending = getattr(context, "_ptrade_pending_order_ids", None)
        if pending is None:
            pending = set()
            setattr(context, "_ptrade_pending_order_ids", pending)
        self._pending_order_ids = pending

    def _history_frame(self, data, code):
        frame = self.frame(data, code)
        if "money" in frame.columns and "amount" not in frame.columns:
            frame = frame.rename(columns={"money": "amount"})
        return frame

    def get_history(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        code = self.normalize_code(code)
        freq = normalize_frequency(frequency)
        fields = map_history_fields(fields, self.platform)
        data = platform_call(
            "get_history",
            int(count),
            freq,
            fields,
            code,
            fq=map_adjust(adjust, self.platform),
            include=True,
        )
        frame = self._history_frame(data, code)
        if end_time is not None and not frame.empty:
            end = end_time
            if not isinstance(end, datetime.datetime):
                try:
                    end = datetime.datetime.strptime(str(end)[:10], "%Y-%m-%d")
                except Exception:
                    end = None
            if end is not None:
                try:
                    frame = frame[frame.index <= end]
                except Exception:
                    pass
        return frame

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
        start = _ptrade_time_text(start_time)
        end = _ptrade_time_text(end_time)
        data = platform_call(
            "get_price",
            code,
            start_date=start,
            end_date=end,
            frequency=freq,
            fields=fields,
            fq=map_adjust(adjust, self.platform),
        )
        return self._history_frame(data, code)

    def download_history(self, codes, frequency="1d", start_time=None, end_time=None):
        # PTrade 历史行情由服务端按需提供，无本地下载接口。
        return None

    def get_instruments(self, codes):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        platforms = [self.normalize_code(code) for code in codes]
        try:
            data = platform_call(
                "get_stock_info",
                platforms,
                field=["stock_name", "listed_date", "de_listed_date"],
            )
        except Exception:
            data = None
        result = {}
        for row in records(data):
            raw_code = first_value(row, ("symbol", "sec_id", "code", "security"))
            if raw_code is None:
                continue
            try:
                canonical = normalize_code(raw_code)
            except Exception:
                continue
            delisted = first_value(row, ("de_listed_date", "delisted_date"))
            result[canonical] = build_instrument(
                canonical,
                name=first_value(row, ("stock_name", "name", "sec_name")),
                board=board_from_code(canonical),
                lot_size=100,
                listed_date=first_value(row, ("listed_date", "list_date")),
                status={
                    "st": None,
                    "suspend": None,
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
        result = {}
        query = str(query_type or "ST").upper()
        for code in codes:
            platform_code = self.normalize_code(code)
            try:
                data = platform_call(
                    "get_stock_status", platform_code, query, date
                )
            except Exception:
                data = None
            if isinstance(data, dict):
                if platform_code in data:
                    value = data.get(platform_code)
                elif normalize_code(code) in data:
                    value = data.get(normalize_code(code))
                elif len(data) == 1:
                    value = list(data.values())[0]
                else:
                    value = None
            else:
                value = data
            result[normalize_code(code)] = _status_bool(value)
        return result

    def get_trading_dates(self, start_date=None, end_date=None, market="SH"):
        end = normalize_date(end_date) or self.context.trade_date()
        start = normalize_date(start_date) or end
        if start > end:
            return []
        data = platform_call(
            "get_trade_days", start_date=start, end_date=end
        )
        if data is None:
            data = []
        elif hasattr(data, "tolist"):
            data = data.tolist()
        values = []
        for item in data:
            value = normalize_date(item)
            if value and start <= value <= end:
                values.append(value)
        return sorted(set(values))

    def get_tick_raw(self, codes, fields=None):
        if isinstance(codes, (list, tuple)):
            code = codes[0] if codes else None
        else:
            code = codes
        if code is None:
            return {}
        return platform_call("get_snapshot", self.normalize_code(code))

    def get_portfolio(self, field):
        try:
            portfolio = self.context.raw.portfolio
        except Exception as exc:
            raise PlatformApiMissing("PTrade portfolio failed: {0}".format(exc))
        if field == "assets_value":
            return portfolio.portfolio_value
        if field == "market_value":
            return portfolio.positions_value
        if field == "cash":
            return portfolio.cash
        if field == "positions":
            return portfolio.positions
        raise PlatformApiMissing("unsupported portfolio field: {0}".format(field))

    def order(self, code, side, amount, price=None, order_type="limit", remark=None):
        code = self.normalize_code(code)
        side = str(side).upper()
        signed_amount = int(amount) if side == SIDE_BUY else -int(amount)
        if order_type == "market":
            try:
                raw = platform_call(
                    "order_market", code, signed_amount, limit_price=price
                )
            except Exception:
                raw = platform_call("order", code, signed_amount, limit_price=price)
        else:
            raw = platform_call(
                "order", code, signed_amount, limit_price=float(price or 0)
            )
        raw_id = raw if isinstance(raw, str) else getattr(raw, "id", None)
        if raw_id:
            self._pending_order_ids.add(str(raw_id))
        return make_order(
            self.platform,
            platform_id=raw or remark,
            code=normalize_code(code),
            side=side,
            price=price,
            amount=amount,
            status="PENDING",
            status_code=raw,
            remark=remark,
            raw=raw,
        )

    def _all_order_rows(self):
        try:
            rows = platform_call("get_all_orders")
        except Exception:
            rows = []
        if isinstance(rows, dict):
            rows = rows.values()
        return list(rows or [])

    def _find_all_order(self, ref):
        code = str(ref.get("code") or "")
        amount = str(ref.get("amount") or "")
        price = str(ref.get("price") or "")
        order_id = str(ref.get("id") or "")
        for row in self._all_order_rows():
            order = self._normalize_order(row)
            if order_id and order_id in (
                str(order.get("platform_order_id") or ""),
                str(order.get("id") or ""),
            ):
                return row
            if (
                code
                and amount
                and str(order.get("code")) == code
                and str(order.get("amount")) == amount
                and (not price or str(order.get("price")) == price)
            ):
                return row
        return None

    def cancel(self, order_ref):
        ref = coerce_order_ref(order_ref)
        if not isinstance(ref, dict):
            return False
        order_id = ref.get("id") or ref.get("platform_order_id")
        if order_id:
            try:
                result = platform_call("cancel_order", order_id)
                if result is None or bool(result):
                    return True
            except Exception:
                pass
        # get_all_orders() 中的账户口径委托不在策略订单列表里，
        # 官方要求必须用 cancel_order_ex 传原始字典撤单。
        row = self._find_all_order(ref)
        if row is None:
            return False
        try:
            result = platform_call("cancel_order_ex", row)
            return result is None or bool(result)
        except Exception:
            return False

    def cancel_all(self):
        count = 0
        for order in self.get_orders(include_finished=False):
            if order.get("platform_order_id"):
                self.cancel(order)
                count += 1
        return count

    def _pending_order_rows(self):
        rows = []
        for order_id in list(self._pending_order_ids):
            try:
                data = platform_call("get_order", str(order_id))
            except Exception:
                continue
            if data is None:
                continue
            if isinstance(data, dict):
                rows.append(data)
            elif isinstance(data, (list, tuple)):
                rows.extend(data)
            else:
                rows.append(data)
        return rows

    def get_orders(self, status=None, include_finished=True):
        try:
            source = platform_call("get_orders") if include_finished else platform_call("get_open_orders")
        except Exception:
            source = {}
        rows = source.values() if isinstance(source, dict) else source or []
        all_rows = []
        if include_finished:
            # 本轮下单返回的 order id 直接走 get_order，避免 get_orders()
            # 尚未回写新单时把同代码/同数量/同价格的旧单当成新单。
            rows = self._pending_order_rows() + list(rows or [])
            try:
                all_rows = platform_call("get_all_orders")
            except Exception:
                all_rows = []
            if isinstance(all_rows, dict):
                all_rows = all_rows.values()
        result = []
        seen = set()
        for row in list(rows) + list(all_rows or []):
            order = self._normalize_order(row)
            if status is not None and order["status"] != str(status).upper():
                continue
            if not include_finished and order["status"] in (
                "FILLED",
                "CANCELED",
                "REJECTED",
                "EXPIRED",
            ):
                continue
            order_key = order.get("platform_order_id") or (
                str(order.get("code")),
                str(order.get("amount")),
                str(order.get("price")),
                str(order.get("status")),
            )
            if order_key in seen:
                continue
            seen.add(order_key)
            result.append(order)
        return result

    def _safe_code(self, code):
        try:
            return normalize_code(code)
        except Exception:
            return code

    def _normalize_order(self, row):
        data = row if isinstance(row, dict) else getattr(row, "__dict__", {})
        code = (
            data.get("security")
            or data.get("code")
            or data.get("symbol")
            or data.get("stock_code")
        )
        return make_order(
            self.platform,
            platform_id=data.get("id") or data.get("order_id") or data.get("entrust_no"),
            code=self._safe_code(code),
            side=data.get("side") or data.get("entrust_bs"),
            price=data.get("price") or data.get("limit_price"),
            amount=data.get("amount") or data.get("entrust_amount"),
            filled=data.get("filled")
            or data.get("filled_amount")
            or data.get("business_amount"),
            status=data.get("status"),
            status_code=data.get("status"),
            created_at=data.get("created_at")
            or data.get("entrust_time")
            or data.get("order_time"),
            remark=data.get("remark"),
            raw=row,
        )

    def get_trades(self, order_ref=None):
        try:
            source = platform_call("get_trades")
        except Exception:
            source = {}
        rows = source.values() if isinstance(source, dict) else source or []
        ref = coerce_order_ref(order_ref)
        result = []
        for row in rows:
            data = row if isinstance(row, dict) else getattr(row, "__dict__", {})
            order_id = data.get("order_id") or data.get("id")
            if ref is not None and isinstance(ref, dict) and ref.get("id"):
                if str(order_id) != str(ref["id"]):
                    continue
            result.append(
                {
                    "code": self._safe_code(
                        data.get("security") or data.get("code")
                    ),
                    "order_id": order_id,
                    "price": data.get("price"),
                    "amount": data.get("amount") or data.get("business_amount"),
                    "side": normalize_side(data.get("side") or data.get("entrust_bs")),
                    "created_at": data.get("created_at") or data.get("business_time"),
                    "raw": row,
                }
            )
        return result

    def get_positions(self):
        raw_positions = self.get_portfolio("positions") or {}
        if isinstance(raw_positions, dict):
            items = raw_positions.items()
        else:
            items = [(None, item) for item in raw_positions]
        result = []
        for key, item in items:
            data = item if isinstance(item, dict) else getattr(item, "__dict__", {})
            code = data.get("security") or data.get("code") or key
            try:
                code = normalize_code(code)
            except Exception:
                pass
            total = int(data.get("amount") or data.get("total_amount") or 0)
            available = int(data.get("enable_amount") or data.get("available") or 0)
            result.append(
                {
                    "code": code,
                    "amount": total,
                    "available": available,
                    "cost": data.get("cost_basis") or data.get("cost"),
                    "market_value": data.get("market_value"),
                    "pnl": data.get("pnl"),
                    "raw": item,
                }
            )
        return result

    def get_account(self):
        portfolio = self.context.raw.portfolio
        return {
            "total_asset": getattr(portfolio, "portfolio_value", None),
            "cash": getattr(portfolio, "cash", None),
            "available": getattr(portfolio, "cash", None),
            "market_value": getattr(portfolio, "positions_value", None),
            "frozen": getattr(portfolio, "frozen", None),
            "pnl": getattr(portfolio, "pnl", None),
            "raw": portfolio,
        }


def _ptrade_time_text(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip()
    compact = text.replace("-", "").replace("/", "").replace(":", "").replace(" ", "")
    if len(compact) >= 14:
        return "{0}-{1}-{2} {3}:{4}:{5}".format(
            compact[:4], compact[4:6], compact[6:8],
            compact[8:10], compact[10:12], compact[12:14],
        )
    if len(compact) >= 8:
        return "{0}-{1}-{2}".format(compact[:4], compact[4:6], compact[6:8])
    return text


def _is_delisted(value):
    if value is None or value == "":
        return None
    text = str(value).replace("-", "")[:8]
    if not text.isdigit():
        return None
    return text <= datetime.date.today().strftime("%Y%m%d")


def _status_bool(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        for key in ("status", "is_st", "is_suspended", "is_delisted", "value"):
            if key in value:
                return _status_bool(value[key])
        return None
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "st", "halt", "delisting", "delisted"):
        return True
    if text in ("0", "false", "no", "normal"):
        return False
    return None
