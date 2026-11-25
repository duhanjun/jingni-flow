# -*- coding: utf-8 -*-
"""Phase 2 交易周边 API 测试：范围行情、标的、日历、定时器。"""

import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from jingniflow.api.calendar import (
    jingni_get_trading_dates,
    jingni_is_trading_day,
    jingni_is_trading_time,
)
from jingniflow.api.instrument import (
    jingni_get_instrument,
    jingni_get_stock_status,
)
from jingniflow.api.market import (
    jingni_download_history,
    jingni_get_history_range,
)
from jingniflow.api.runtime import jingni_run_interval
from jingniflow.core.runtime import (
    clear_api_registry,
    register_api,
    set_default_mode,
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_api_registry()
    set_default_mode("软件名称")
    yield
    clear_api_registry()
    set_default_mode("软件名称")


class GmContext(object):
    mode = 2
    now = datetime.datetime(2024, 1, 2, 10, 0, 0)


class QmtRaw(object):
    do_back_test = True
    barpos = 0

    def __init__(self):
        self.downloads = []
        self.run_times = []

    def get_bar_timetag(self, barpos):
        return 1700000000000

    def get_market_data_ex(self, **kwargs):
        self.market_kwargs = kwargs
        return {"600000.SH": pd.DataFrame({"open": [10], "close": [11]})}

    def get_instrument_detail(self, code, iscomplete=False):
        return {
            "InstrumentName": "浦发银行",
            "LotSize": 100,
            "PriceTick": 0.01,
            "UpStopPrice": 12.0,
            "DownStopPrice": 8.0,
            "OpenDate": "19991110",
            "ExpireDate": "99999999",
            "IsTrading": 1,
            "IsST": 0,
        }

    def download_history_data(self, code, period, start, end):
        self.downloads.append((code, period, start, end))

    def get_trading_dates(self, stockcode, start, end, count, period="1d"):
        self.calendar_args = (stockcode, start, end, count, period)
        return ["20240102", "20240103", "20240104"]

    def run_time(self, name, period, start):
        self.run_times.append((name, period, start))
        return "timer-1"


class PtradeContext(object):
    blotter = SimpleNamespace(current_dt=datetime.datetime(2024, 1, 2, 10, 0, 0))


def test_goldminer_range_instrument_and_calendar():
    set_default_mode("goldminer")
    calls = {}

    def history(**kwargs):
        calls["history"] = kwargs
        return pd.DataFrame({"open": [10], "close": [11]})

    register_api(
        {
            "history": history,
            "get_instruments": lambda **kwargs: [
                {
                    "symbol": "SHSE.600000",
                    "sec_name": "浦发银行",
                    "lot_size": 100,
                    "price_tick": 0.01,
                    "limit_up": 12.0,
                    "limit_down": 8.0,
                    "listed_date": "1999-11-10",
                    "is_st": False,
                }
            ],
            "get_trading_dates_by_year": lambda **kwargs: [
                {"trade_date": "2024-01-02"},
                {"trade_date": "2024-01-03"},
            ],
            "ADJUST_PREV": 1,
        }
    )
    context = GmContext()
    frame = jingni_get_history_range(
        "goldminer", context, "600000", "1d", "2024-01-01", "2024-01-31"
    )
    assert frame["close"].iloc[-1] == 11
    assert calls["history"]["symbol"] == "SHSE.600000"
    assert calls["history"]["start_time"] == "2024-01-01"
    assert calls["history"]["adjust"] == 1

    instruments = jingni_get_instrument("goldminer", context, ["600000"])
    item = instruments["600000.SH"]
    assert item["name"] == "浦发银行"
    assert item["board"] == "主板"
    assert item["lot_size"] == 100
    assert item["tick_size"] == 0.01
    assert item["listed_date"] == "1999-11-10"
    assert item["status"]["st"] is False

    assert jingni_get_stock_status("goldminer", context, "600000") == {
        "600000.SH": False
    }
    status = jingni_get_stock_status(
        "goldminer", context, "600000", query_type=None
    )
    assert status["600000.SH"]["st"] is False
    assert jingni_get_trading_dates(
        "goldminer", context, "2024-01-01", "2024-01-05"
    ) == ["20240102", "20240103"]
    assert jingni_download_history(
        "goldminer", context, "600000", "1d", "2024-01-01", "2024-01-31"
    ) is None


def test_qmt_range_download_instrument_and_calendar():
    set_default_mode("qmt")
    raw = QmtRaw()
    register_api({"timetag_to_datetime": lambda *args: "2024-01-02 10:00:00"})

    frame = jingni_get_history_range(
        "qmt", raw, "600000", "1d", "2024-01-01", "2024-01-05"
    )
    assert frame["close"].iloc[-1] == 11
    assert raw.market_kwargs["count"] == -1
    assert raw.market_kwargs["start_time"] == "20240101"
    assert raw.market_kwargs["end_time"] == "20240105"
    assert raw.market_kwargs["subscribe"] is False

    jingni_download_history(
        "qmt", raw, ["600000", "000001"], "1d", "2024-01-01", "2024-01-05"
    )
    assert raw.downloads == [
        ("600000.SH", "1d", "20240101", "20240105"),
        ("000001.SZ", "1d", "20240101", "20240105"),
    ]

    instruments = jingni_get_instrument("qmt", raw, ["600000"])
    item = instruments["600000.SH"]
    assert item["name"] == "浦发银行"
    assert item["lot_size"] == 100
    assert item["tick_size"] == 0.01
    assert item["limit_up"] == 12.0
    assert item["status"]["suspend"] is False

    dates = jingni_get_trading_dates("qmt", raw, "2024-01-01", "2024-01-05")
    assert dates == ["20240102", "20240103", "20240104"]
    assert raw.calendar_args[3] > 0

    assert jingni_is_trading_day("qmt", raw, "2024-01-02") is True
    assert jingni_is_trading_day("qmt", raw, "2024-01-06") is False
    assert jingni_is_trading_time(
        "qmt", raw, datetime.datetime(2024, 1, 2, 10, 0)
    ) is True
    assert jingni_is_trading_time(
        "qmt", raw, datetime.datetime(2024, 1, 2, 12, 0)
    ) is False
    assert jingni_is_trading_time(
        "qmt",
        raw,
        datetime.datetime(2024, 1, 2, 9, 20),
        include_auction=True,
    ) is True


def test_ptrade_range_instrument_status_and_calendar():
    set_default_mode("ptrade")
    calls = {}

    def get_price(code, **kwargs):
        calls["price"] = (code, kwargs)
        return pd.DataFrame({"open": [10], "close": [11]})

    register_api(
        {
            "is_trade": lambda: False,
            "get_price": get_price,
            "get_stock_info": lambda codes, field=None: {
                "600000.SS": {
                    "stock_name": "浦发银行",
                    "listed_date": "1999-11-10",
                    "de_listed_date": "9999-12-31",
                }
            },
            "get_stock_status": lambda code, query, date=None: {
                "600000.SS": True
            },
            "get_trade_days": lambda **kwargs: [
                datetime.date(2024, 1, 2),
                datetime.date(2024, 1, 3),
            ],
        }
    )
    context = PtradeContext()
    frame = jingni_get_history_range(
        "ptrade", context, "600000", "1d", "2024-01-01", "2024-01-31"
    )
    assert frame["close"].iloc[-1] == 11
    assert calls["price"][0] == "600000.SS"
    assert calls["price"][1]["start_date"] == "2024-01-01"
    assert calls["price"][1]["end_date"] == "2024-01-31"

    instruments = jingni_get_instrument("ptrade", context, ["600000"])
    item = instruments["600000.SH"]
    assert item["name"] == "浦发银行"
    assert item["listed_date"] == "1999-11-10"
    assert item["status"]["delisted"] is False

    assert jingni_get_stock_status("ptrade", context, "600000") == {
        "600000.SH": True
    }
    assert jingni_get_trading_dates(
        "ptrade", context, "2024-01-01", "2024-01-05"
    ) == ["20240102", "20240103"]
    assert jingni_download_history(
        "ptrade", context, "600000", "1d", "2024-01-01", "2024-01-31"
    ) is None


def test_run_interval_three_platforms():
    calls = []
    register_api(
        {
            "timer": lambda **kwargs: calls.append(("gm", kwargs)) or "timer-gm",
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )

    def task():
        pass

    assert jingni_run_interval(
        task, 3, trade_mode="goldminer", context_data=GmContext()
    ) == "timer-gm"
    assert calls[-1][1]["period"] == 3000
    assert calls[-1][1]["start_delay"] == 0

    raw = QmtRaw()
    live = SimpleNamespace(do_back_test=False, run_time=raw.run_time)
    assert jingni_run_interval(
        task, 3, trade_mode="qmt", context_data=live
    ) == "timer-1"
    assert raw.run_times[-1] == (
        "task",
        "3nSecond",
        "1970-01-01 00:00:00",
    )

    pt_calls = []
    register_api(
        {
            "is_trade": lambda: True,
            "run_interval": lambda *args, **kwargs: pt_calls.append((args, kwargs)),
        }
    )
    assert jingni_run_interval(
        task, 1, trade_mode="ptrade", context_data=PtradeContext()
    ) is None
    assert pt_calls[-1][1]["seconds"] == 3


def test_calendar_fallback_without_context():
    assert jingni_is_trading_time(
        now=datetime.datetime(2024, 1, 2, 10, 0)
    ) is True
    assert jingni_is_trading_time(
        now=datetime.datetime(2024, 1, 6, 10, 0)
    ) is False


def test_history_range_requires_start():
    from jingniflow.core.errors import ValidationError

    with pytest.raises(ValidationError):
        jingni_get_history_range(
            "goldminer", GmContext(), "600000", "1d", None, "2024-01-31"
        )
