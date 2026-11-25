# -*- coding: utf-8 -*-
"""QMT / 迅投适配器。"""

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
    bool_or_none,
    first_value,
)
from ..core.order import SIDE_BUY, coerce_order_ref, make_order, normalize_side
from ..core.runtime import platform_call
from .base import BaseAdapter


class QmtAdapter(BaseAdapter):
    platform = "qmt"

    def _account_id(self):
        account = self.context.account_id()
        if not account and self.context.raw is not None:
            account = getattr(self.context.raw, "account", None)
        if not account:
            raise PlatformApiMissing("QMT account is not configured")
        return account

    def get_history(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        code = self.normalize_code(code)
        freq = _qmt_frequency(normalize_frequency(frequency))
        fields = map_history_fields(fields, self.platform)
        end = end_time or self.context.now()
        if isinstance(end, datetime.datetime):
            fmt = "%Y%m%d" if freq in ("1d", "1w", "1M") else "%Y%m%d%H%M%S"
            end_text = end.strftime(fmt)
        else:
            end_text = str(end).replace("-", "")
        kwargs = {
            "fields": fields,
            "stock_code": [code],
            "period": freq,
            "start_time": "",
            "end_time": end_text,
            "count": int(count),
            "dividend_type": map_adjust(adjust, self.platform),
            "fill_data": True,
            "subscribe": False,
        }
        if self.context.raw is not None and hasattr(
            self.context.raw, "get_market_data_ex"
        ):
            data = self.context.raw.get_market_data_ex(**kwargs)
        else:
            data = platform_call("get_market_data_ex", **kwargs)
        return self.frame(data, code)

    def get_history_native(
        self, code, frequency="1d", count=1, end_time=None, fields=None, adjust=None
    ):
        """QMT 旧接口返回 ``{code: DataFrame}``，保持兼容。"""
        code = self.normalize_code(code)
        freq = _qmt_frequency(normalize_frequency(frequency))
        fields = map_history_fields(fields, self.platform)
        end = end_time or self.context.now()
        if isinstance(end, datetime.datetime):
            fmt = "%Y%m%d" if freq in ("1d", "1w", "1M") else "%Y%m%d%H%M%S"
            end_text = end.strftime(fmt)
        else:
            end_text = str(end).replace("-", "")
        kwargs = {
            "fields": fields,
            "stock_code": [code],
            "period": freq,
            "start_time": "",
            "end_time": end_text,
            "count": int(count),
            "dividend_type": map_adjust(adjust, self.platform),
            "fill_data": True,
            "subscribe": False,
        }
        if self.context.raw is not None and hasattr(
            self.context.raw, "get_market_data_ex"
        ):
            return self.context.raw.get_market_data_ex(**kwargs)
        return platform_call("get_market_data_ex", **kwargs)

    def get_history_range(
        self, code, frequency="1d", start_time=None, end_time=None, fields=None, adjust=None
    ):
        code = self.normalize_code(code)
        freq = _qmt_frequency(normalize_frequency(frequency))
        fields = map_history_fields(fields, self.platform)
        end = _qmt_time_text(end_time or self.context.now(), freq)
        kwargs = {
            "fields": fields,
            "stock_code": [code],
            "period": freq,
            "start_time": _qmt_time_text(start_time, freq),
            "end_time": end,
            "count": -1,
            "dividend_type": map_adjust(adjust, self.platform),
            "fill_data": True,
            "subscribe": False,
        }
        if self.context.raw is not None and hasattr(
            self.context.raw, "get_market_data_ex"
        ):
            data = self.context.raw.get_market_data_ex(**kwargs)
        else:
            data = platform_call("get_market_data_ex", **kwargs)
        return self.frame(data, code)

    def download_history(self, codes, frequency="1d", start_time=None, end_time=None):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        period = _qmt_frequency(normalize_frequency(frequency), download=True)
        start = _qmt_time_text(start_time or "", "1d")
        end = _qmt_time_text(end_time or self.context.now(), "1d")
        for code in codes:
            platform_code = self.normalize_code(code)
            if self.context.raw is not None and hasattr(
                self.context.raw, "download_history_data"
            ):
                self.context.raw.download_history_data(
                    platform_code, period, start, end
                )
            else:
                platform_call(
                    "download_history_data", platform_code, period, start, end
                )
        return None

    def get_instruments(self, codes):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        result = {}
        for code in codes:
            platform_code = self.normalize_code(code)
            detail = None
            try:
                if self.context.raw is not None and hasattr(
                    self.context.raw, "get_instrument_detail"
                ):
                    detail = self.context.raw.get_instrument_detail(
                        platform_code, iscomplete=True
                    )
                else:
                    detail = platform_call(
                        "get_instrument_detail", platform_code, iscomplete=True
                    )
            except Exception:
                try:
                    if self.context.raw is not None and hasattr(
                        self.context.raw, "get_instrument_detail"
                    ):
                        detail = self.context.raw.get_instrument_detail(platform_code)
                    else:
                        detail = platform_call(
                            "get_instrument_detail", platform_code
                        )
                except Exception:
                    detail = None
            canonical = normalize_code(code)
            if not detail:
                result[canonical] = build_instrument(canonical)
                continue
            expire = first_value(detail, ("ExpireDate", "expire_date"))
            is_trading = bool_or_none(
                first_value(detail, ("IsTrading", "is_trading"))
            )
            result[canonical] = build_instrument(
                canonical,
                name=first_value(
                    detail, ("InstrumentName", "instrument_name", "name")
                ),
                board=board_from_code(canonical),
                lot_size=first_value(detail, ("LotSize", "lot_size"), 100),
                tick_size=first_value(detail, ("PriceTick", "price_tick")),
                limit_up=_qmt_price(first_value(detail, ("UpStopPrice", "up_stop_price"))),
                limit_down=_qmt_price(
                    first_value(detail, ("DownStopPrice", "down_stop_price"))
                ),
                listed_date=first_value(detail, ("OpenDate", "open_date")),
                status={
                    "st": bool_or_none(first_value(detail, ("IsST", "is_st"))),
                    "suspend": None if is_trading is None else not is_trading,
                    "delisted": _delisted_from_expire(expire),
                },
            )
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
            (normalize_code(code), (instruments.get(normalize_code(code)) or {}).get("status", {}).get(key))
            for code in codes
        )

    def get_trading_dates(self, start_date=None, end_date=None, market="SH"):
        raw = self.context.raw
        start = normalize_date(start_date) or ""
        end = normalize_date(end_date) or self.context.trade_date()
        if start and start > end:
            return []
        if raw is not None and hasattr(raw, "get_trading_dates"):
            data = raw.get_trading_dates("", start, end, 10000, "1d")
        else:
            data = platform_call(
                "get_trading_dates", "", start, end, 10000, "1d"
            )
        values = []
        for item in data or []:
            value = normalize_date(item)
            if value and (not start or value >= start) and value <= end:
                values.append(value)
        return sorted(set(values))

    def get_tick_raw(self, codes, fields=None):
        if not isinstance(codes, (list, tuple)):
            codes = [codes]
        stock_code = [self.normalize_code(code) for code in codes]
        if self.context.raw is not None and hasattr(
            self.context.raw, "get_full_tick"
        ):
            return self.context.raw.get_full_tick(stock_code)
        return platform_call("get_full_tick", stock_code)

    def get_portfolio(self, field):
        try:
            account = self._account_id()
        except PlatformApiMissing:
            if self.context.is_backtest:
                print(
                    "[JINGNI_DATA_WARN] QMT backtest account unavailable; "
                    "portfolio {0}=None".format(field)
                )
                return [] if field == "positions" else None
            raise
        account_type = self.context.config.account_type or "stock"
        if field == "assets_value":
            data = platform_call(
                "get_trade_detail_data", account, account_type, "account"
            )
            return data[0].m_dBalance if data else None
        if field == "market_value":
            data = platform_call(
                "get_trade_detail_data", account, account_type, "account"
            )
            return data[0].m_dInstrumentValue if data else None
        if field == "cash":
            data = platform_call(
                "get_trade_detail_data", account, account_type, "account"
            )
            return data[0].m_dAvailable if data else None
        if field == "positions":
            return platform_call(
                "get_trade_detail_data", account, account_type, "position"
            )
        raise PlatformApiMissing("unsupported portfolio field: {0}".format(field))

    def _detail(self, kind):
        try:
            account = self._account_id()
        except PlatformApiMissing:
            if self.context.is_backtest:
                print(
                    "[JINGNI_DATA_WARN] QMT backtest account unavailable; "
                    "return empty {0}".format(kind)
                )
                return []
            raise
        account_type = self.context.config.account_type or "stock"
        rows = platform_call(
            "get_trade_detail_data", account, account_type, kind
        )
        return rows or []

    def order(self, code, side, amount, price=None, order_type="limit", remark=None):
        account = self._account_id()
        code = self.normalize_code(code)
        side = str(side).upper()
        op_type = 23 if side == SIDE_BUY else 24
        if order_type == "market":
            # 沪市市价单使用保护价类型；深市用最新价。最终参数以 QMT
            # 版本为准，V-02 冒烟时再确认。
            pr_type = 42 if str(code).endswith(".SH") else 5
        else:
            pr_type = 11
        raw = platform_call(
            "passorder",
            op_type,
            1101,
            str(account),
            code,
            pr_type,
            float(price or 0),
            int(amount),
            "JingniFlow",
            2,
            remark or "",
            self.context.raw,
        )
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

    def _latest_order_id(self, remark):
        """用 get_last_order_id 抢在委托列表回写前拿到柜台委托号。

        passorder 不返回委托号；仿真撮合可能在几秒内成交，等
        get_orders 可见时已经来不及撤单。这里只接受备注与本次
        remark 完全一致的最新委托，避免误撤账户里的旧单。
        """
        try:
            account = self._account_id()
        except Exception:
            return None
        account_type = str(self.context.config.account_type or "stock").lower()
        last_id = None
        try:
            last_id = platform_call(
                "get_last_order_id", account, account_type, "ORDER", "JingniFlow"
            )
        except Exception:
            try:
                last_id = platform_call(
                    "get_last_order_id", account, account_type, "ORDER"
                )
            except Exception:
                return None
        if last_id is None or str(last_id) == "-1":
            return None
        try:
            raw = platform_call(
                "get_value_by_order_id",
                str(last_id),
                account,
                account_type,
                "ORDER",
            )
        except Exception:
            return None
        raw_remark = None
        if isinstance(raw, dict):
            raw_remark = raw.get("m_strRemark") or raw.get("order_remark")
        else:
            raw_remark = getattr(raw, "m_strRemark", None) or getattr(
                raw, "order_remark", None
            )
        if not raw_remark or str(raw_remark) != str(remark):
            return None
        return str(last_id)

    def _resolve_cancel_order_id(self, order_ref):
        """把下单时的 remark 解析成 QMT 柜台真正的 m_strOrderSysID。

        QMT 的 passorder 不返回柜台委托号，order() 只能用 remark 占位。
        撤单必须用 get_trade_detail_data 里的 m_strOrderSysID，否则
        cancel(remark, ...) 会失败，委托随后会变成 EXPIRED。
        """
        raw_ref = order_ref if isinstance(order_ref, dict) else {}
        target = (
            raw_ref.get("platform_order_id")
            or raw_ref.get("id")
            or raw_ref.get("remark")
        )
        if target is None:
            return None
        target = str(target)
        # 先按 remark / 当前引用查找；找到后返回真实柜台委托号。
        try:
            orders = self.get_orders(include_finished=False)
        except Exception:
            orders = []
        for order in orders:
            if not isinstance(order, dict):
                continue
            values = (
                str(order.get("platform_order_id") or ""),
                str(order.get("remark") or ""),
            )
            if target in values:
                actual = order.get("platform_order_id")
                if actual:
                    return str(actual)
        # 如果调用方已经给了真实委托号，直接使用。
        if not target.startswith("validation-"):
            return target
        # 委托列表尚未回写时，用 get_last_order_id 抢撤单窗口。
        latest = self._latest_order_id(target)
        if latest:
            return latest
        return None

    def cancel(self, order_ref):
        order_id = self._resolve_cancel_order_id(order_ref)
        if not order_id:
            return False
        account = self._account_id()
        account_type = self.context.config.account_type or "stock"
        result = platform_call(
            "cancel", order_id, account, account_type, self.context.raw
        )
        return bool(result) if result is not None else True

    def cancel_all(self):
        count = 0
        for order in self.get_orders(include_finished=False):
            if self.cancel(order):
                count += 1
        return count

    def get_orders(self, status=None, include_finished=True):
        result = []
        for row in self._detail("order"):
            order = self._normalize_order(row)
            if status is not None and order["status"] != str(status).upper():
                continue
            if not include_finished and order["status"] in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
                continue
            result.append(order)
        return result

    def _normalize_order(self, row):
        instrument = getattr(row, "m_strInstrumentID", "")
        exchange = getattr(row, "m_strExchangeID", "")
        try:
            code = normalize_code("{0}.{1}".format(instrument, exchange))
        except Exception:
            code = "{0}.{1}".format(instrument, exchange)
        return make_order(
            self.platform,
            platform_id=getattr(row, "m_strOrderSysID", None),
            code=code,
            side=getattr(row, "m_nDirection", None),
            price=getattr(row, "m_dLimitPrice", None),
            amount=getattr(row, "m_nVolumeTotalOriginal", None),
            filled=getattr(row, "m_nVolumeTraded", 0),
            status=getattr(row, "m_nOrderStatus", None),
            status_code=getattr(row, "m_nOrderStatus", None),
            created_at=getattr(row, "m_strInsertDate", None),
            remark=getattr(row, "m_strRemark", None),
            raw=row,
        )

    def get_trades(self, order_ref=None):
        ref = coerce_order_ref(order_ref)
        result = []
        for row in self._detail("deal"):
            order_id = getattr(row, "m_strOrderSysID", None)
            if ref is not None and isinstance(ref, dict) and ref.get("id"):
                if str(order_id) != str(ref["id"]):
                    continue
            instrument = getattr(row, "m_strInstrumentID", "")
            exchange = getattr(row, "m_strExchangeID", "")
            try:
                code = normalize_code("{0}.{1}".format(instrument, exchange))
            except Exception:
                code = "{0}.{1}".format(instrument, exchange)
            result.append(
                {
                    "code": code,
                    "order_id": order_id,
                    "price": getattr(row, "m_dPrice", None),
                    "amount": getattr(row, "m_nVolume", None),
                    "side": normalize_side(getattr(row, "m_nDirection", None)),
                    "created_at": getattr(row, "m_strTradeTime", None),
                    "raw": row,
                }
            )
        return result

    def get_positions(self):
        result = []
        for row in self._detail("position"):
            instrument = getattr(row, "m_strInstrumentID", "")
            exchange = getattr(row, "m_strExchangeID", "")
            try:
                code = normalize_code("{0}.{1}".format(instrument, exchange))
            except Exception:
                code = "{0}.{1}".format(instrument, exchange)
            result.append(
                {
                    "code": code,
                    "amount": int(getattr(row, "m_nVolume", 0) or 0),
                    "available": int(getattr(row, "m_nCanUseVolume", 0) or 0),
                    "cost": getattr(row, "m_dOpenPrice", None)
                    or getattr(row, "m_dAvgPrice", None),
                    "market_value": getattr(row, "m_dMarketValue", None),
                    "pnl": getattr(row, "m_dFloatProfit", None),
                    "raw": row,
                }
            )
        return result

    def get_account(self):
        rows = self._detail("account")
        if not rows:
            return {
                "total_asset": None,
                "cash": None,
                "available": None,
                "market_value": None,
                "frozen": None,
                "pnl": None,
                "raw": None,
            }
        row = rows[0]
        return {
            "total_asset": getattr(row, "m_dBalance", None),
            "cash": getattr(row, "m_dAvailable", None),
            "available": getattr(row, "m_dAvailable", None),
            "market_value": getattr(row, "m_dInstrumentValue", None),
            "frozen": getattr(row, "m_dFrozen", None),
            "pnl": getattr(row, "m_dFloatProfit", None),
            "raw": row,
        }


def _qmt_frequency(frequency, download=False):
    """统一频率转 QMT 周期；下载时按最小可用周期聚合。"""
    mapping = {"60m": "1h", "1M": "1mon"}
    if download:
        mapping.update(
            {
                "15m": "5m",
                "30m": "5m",
                "60m": "5m",
                "1w": "1d",
                "1M": "1d",
            }
        )
    return mapping.get(frequency, frequency)


def _qmt_time_text(value, frequency):
    if value is None or value == "":
        return ""
    if isinstance(value, datetime.datetime):
        if frequency in ("1d", "1w", "1M", "1mon"):
            return value.strftime("%Y%m%d")
        return value.strftime("%Y%m%d%H%M%S")
    text = str(value).strip()
    compact = (
        text.replace("-", "")
        .replace("/", "")
        .replace(":", "")
        .replace(" ", "")
    )
    if len(compact) >= 14:
        return compact[:14]
    if len(compact) >= 8:
        return compact[:8]
    return text


def _qmt_price(value):
    """QMT 的 UpStopPrice/DownStopPrice 以 0.001 元为单位返回。"""
    if value is None:
        return None
    try:
        price = float(value)
    except Exception:
        return value
    if abs(price) >= 1000:
        price = price / 1000.0
    return round(price, 3)


def _delisted_from_expire(value):
    if value is None or value == "" or str(value) in ("0", "19700101"):
        return None
    text = str(value).replace("-", "")[:8]
    if not text.isdigit():
        return None
    if text in ("99999999", "99991231"):
        return False
    return text <= datetime.date.today().strftime("%Y%m%d")
