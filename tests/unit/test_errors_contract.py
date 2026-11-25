# -*- coding: utf-8 -*-
"""异常路径与跨平台契约测试。"""

import datetime

import pandas as pd
import pytest

from jingniflow.adapters import get_adapter
from jingniflow.api.calendar import (
    jingni_get_trading_dates,
    jingni_is_trading_day,
)
from jingniflow.api.instrument import (
    jingni_get_instrument,
    jingni_get_stock_status,
)
from jingniflow.api.market import (
    jingni_get_history_range,
    jingni_history,
)
from jingniflow.api.runtime import jingni_run_interval
from jingniflow.core.contract import normalize_code, normalize_frequency
from jingniflow.core.errors import DataError, PlatformApiMissing, ValidationError
from jingniflow.core.runtime import (
    clear_api_registry,
    platform_call,
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


class PtradeContext(object):
    blotter = type(
        "Blotter", (object,), {"current_dt": datetime.datetime(2024, 1, 2, 10, 0, 0)}
    )()


class QmtRaw(object):
    def __init__(self):
        self.calendar_args = None
        self.run_times = []

    def get_trading_dates(self, stockcode, start, end, count, period="1d"):
        self.calendar_args = (stockcode, start, end, count, period)
        return []

    def get_market_data_ex(self, **kwargs):
        return {}

    def get_instrument_detail(self, code, iscomplete=False):
        return None

    def run_time(self, name, period, start):
        self.run_times.append((name, period, start))
        return "timer"


def test_invalid_code_and_frequency_raise_validation_error():
    with pytest.raises(ValidationError):
        normalize_code("600000.XX")
    with pytest.raises(ValidationError):
        normalize_code("")
    with pytest.raises(ValidationError):
        normalize_frequency("2m")
    with pytest.raises(ValidationError):
        normalize_frequency(None)


def test_empty_history_is_empty_not_error():
    set_default_mode("goldminer")
    register_api({"history_n": lambda **kwargs: None})
    context = GmContext()
    frame = jingni_history("goldminer", context, "600000", "1d", 1)
    assert frame.empty
    assert jingni_get_none_field(context) == 0


def jingni_get_none_field(context):
    from jingniflow.api.market import jingni_get_field

    return jingni_get_field("goldminer", context, "600000", "1d", "close")


def test_multiindex_frame_selects_canonical_code():
    set_default_mode("goldminer")
    columns = pd.MultiIndex.from_tuples(
        [("close", "SHSE.600000"), ("volume", "SHSE.600000")],
        names=["field", "symbol"],
    )
    register_api(
        {"history_n": lambda **kwargs: pd.DataFrame([[10.0, 100]], columns=columns)}
    )
    frame = jingni_history("goldminer", GmContext(), "600000", "1d", 1)
    assert list(frame.columns) == ["close", "volume"]
    assert frame["close"].iloc[0] == 10.0


def test_multi_code_payload_rejects_unmatched_code():
    set_default_mode("goldminer")
    frame = pd.DataFrame({"close": [1.0]})
    register_api(
        {
            "history_n": lambda **kwargs: {
                "600000.SH": frame,
                "000001.SZ": frame,
            }
        }
    )
    with pytest.raises(DataError):
        jingni_history("goldminer", GmContext(), "300001", "1d", 1)


def test_column_missing_field_raises_data_error():
    set_default_mode("goldminer")
    adapter = get_adapter("goldminer", GmContext())
    with pytest.raises(DataError):
        adapter.column(
            pd.DataFrame({"close": [1.0], "volume": [100]}),
            "open",
        )


def test_missing_platform_api_raises_platform_error():
    with pytest.raises(PlatformApiMissing):
        platform_call("jingni_definitely_missing_api")


def test_gm_calendar_empty_trade_date_falls_back():
    set_default_mode("goldminer")
    register_api(
        {
            "get_trading_dates_by_year": lambda **kwargs: [
                {"trade_date": "", "date": ""}
            ],
            "get_trading_dates": lambda **kwargs: ["2024-01-02"],
        }
    )
    context = GmContext()
    assert jingni_get_trading_dates(
        "goldminer", context, "2024-01-01", "2024-01-05"
    ) == ["20240102"]


def test_gm_calendar_unavailable_does_not_crash():
    set_default_mode("goldminer")
    context = GmContext()
    assert jingni_get_trading_dates(
        "goldminer", context, "2024-01-01", "2024-01-05"
    ) == []
    assert jingni_is_trading_day("goldminer", context, "2024-01-02") is True
    assert jingni_is_trading_day("goldminer", context, "2024-01-06") is False


def test_qmt_calendar_count_positive_and_empty_response():
    set_default_mode("qmt")
    raw = QmtRaw()
    assert jingni_get_trading_dates(
        "qmt", raw, "2024-03-01", "2024-03-05"
    ) == []
    assert raw.calendar_args is not None
    assert raw.calendar_args[3] > 0


def test_qmt_instrument_missing_detail_preserves_unknown_status():
    set_default_mode("qmt")
    raw = QmtRaw()
    result = jingni_get_instrument("qmt", raw, ["600000"])
    assert result["600000.SH"]["name"] is None
    status = jingni_get_stock_status("qmt", raw, "600000", query_type=None)
    assert status["600000.SH"] == {
        "st": None,
        "suspend": None,
        "delisted": None,
    }


def test_qmt_run_interval_skips_backtest():
    set_default_mode("qmt")

    class BacktestRaw(QmtRaw):
        do_back_test = True

    raw = BacktestRaw()

    def task():
        pass

    assert jingni_run_interval(task, 3, "qmt", raw) is None
    assert raw.run_times == []


def test_ptrade_price_dict_payload_and_mixed_instruments():
    set_default_mode("ptrade")
    register_api(
        {
            "is_trade": lambda: False,
            "get_price": lambda code, **kwargs: {
                "600000.SS": pd.DataFrame({"close": [11.0]})
            },
            "get_stock_info": lambda codes, field=None: {
                "600000.SS": {"stock_name": "浦发银行"},
                "000001.SZ": None,
            },
        }
    )
    context = PtradeContext()
    frame = jingni_get_history_range(
        "ptrade", context, "600000", "1d", "2024-01-01", "2024-01-31"
    )
    assert frame["close"].iloc[-1] == 11.0

    result = jingni_get_instrument("ptrade", context, ["600000", "000001"])
    assert result["600000.SH"]["name"] == "浦发银行"
    assert result["000001.SZ"]["name"] is None


def test_calendar_cache_hit_and_returns_copy():
    set_default_mode("goldminer")
    calls = {"count": 0}

    def dates(**kwargs):
        calls["count"] += 1
        return [{"trade_date": "2024-04-01"}]

    register_api({"get_trading_dates_by_year": dates})
    context = GmContext()
    first = jingni_get_trading_dates(
        "goldminer", context, "2024-04-01", "2024-04-05"
    )
    second = jingni_get_trading_dates(
        "goldminer", context, "2024-04-01", "2024-04-05"
    )
    assert calls["count"] == 1
    assert first == second == ["20240401"]
    first.append("20240402")
    assert second == ["20240401"]


def test_get_instrument_rejects_empty_code_list():
    set_default_mode("goldminer")
    with pytest.raises(ValidationError):
        jingni_get_instrument("goldminer", GmContext(), [])
