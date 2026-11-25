# -*- coding: utf-8 -*-
"""行情 API 单元测试：用假平台函数验证统一形态。"""

import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from jingniflow.api.market import (
    jingni_get_current,
    jingni_get_field,
    jingni_get_field_n,
    jingni_get_history,
    jingni_get_tick,
)
from jingniflow.adapters.ptrade import PtradeAdapter
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


def _gm_frame():
    return pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [1, 2, 3, 4, 5],
            "low": [1, 2, 3, 4, 5],
            "close": [10, 20, 30, 40, 50],
            "volume": [100, 100, 100, 100, 100],
        }
    )


def test_goldminer_history_and_fields():
    set_default_mode("goldminer")

    def history_n(**kwargs):
        count = int(kwargs["count"])
        frame = _gm_frame().tail(count).reset_index(drop=True)
        return frame

    register_api({"history_n": history_n, "ADJUST_PREV": 1})
    context = GmContext()
    assert jingni_get_field("goldminer", context, "600000", "1d", "close") == 50
    assert jingni_get_field("goldminer", context, "600000", "1d", "close", 1) == 40
    assert (
        jingni_get_field(
            "goldminer", context, "600000", "1d", "close", -1, legacy=True
        )
        == 50
    )
    assert (
        jingni_get_field(
            "goldminer", context, "600000", "1d", "close", -2, legacy=True
        )
        == 40
    )
    series = jingni_get_field_n("goldminer", context, "600000", "1d", "close", 3)
    assert list(series) == [30, 40, 50]
    legacy_series = jingni_get_field_n(
        "goldminer", context, "600000", "1d", "close", -2, legacy=True
    )
    assert len(legacy_series) == 3
    native = jingni_get_history("goldminer", context, "600000", "1d", "close", 2)
    assert len(native) == 2


def test_goldminer_live_tick():
    set_default_mode("goldminer")
    register_api(
        {
            "current": lambda **kwargs: [
                {"symbol": "SHSE.600000", "price": 10.5, "volume": 100}
            ]
        }
    )
    context = GmContext()
    context.mode = 1
    assert jingni_get_field("goldminer", context, "600000", "1d", "close") == 10.5
    tick = jingni_get_tick("goldminer", context, "600000")
    assert tick["600000.SH"]["close"] == 10.5


class QmtContext(object):
    do_back_test = True
    barpos = 0

    def get_bar_timetag(self, barpos):
        return 1700000000000


def test_qmt_history_and_dict_frame():
    set_default_mode("qmt")
    calls = []

    def market_data(**kwargs):
        calls.append(kwargs)
        return {"600000.SH": pd.DataFrame({"close": [1, 2, 3]})}

    register_api(
        {
            "get_market_data_ex": market_data,
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )
    context = QmtContext()
    assert jingni_get_field("qmt", context, "600000", "1d", "close") == 3
    assert jingni_get_field("qmt", context, "600000", "1d", "close", 1) == 2
    assert calls[-1]["subscribe"] is False
    assert calls[-1]["count"] == 2


class PtradeContext(object):
    platform = "ptrade"
    blotter = SimpleNamespace(current_dt=datetime.datetime(2024, 1, 2, 10, 0, 0))


def test_ptrade_history_and_tick():
    set_default_mode("ptrade")
    register_api(
        {
            "is_trade": lambda: False,
            "get_history": lambda *args, **kwargs: pd.DataFrame(
                {"close": [1, 2, 3, 4]}
            ),
            "get_snapshot": lambda code: {
                "600000.SS": {"last_px": 10.2, "volume": 100}
            },
        }
    )
    context = PtradeContext()
    assert jingni_get_field("ptrade", context, "600000", "1d", "close") == 4
    tick = jingni_get_tick("ptrade", context, "600000")
    assert tick["600000.SH"]["close"] == 10.2
    assert jingni_get_current("ptrade", context, "600000") == {
        "600000.SS": {"last_px": 10.2, "volume": 100}
    }


def test_ptrade_amount_alias_and_trading_dates_array():
    set_default_mode("ptrade")
    calls = []

    def history(count, frequency, fields, code, **kwargs):
        calls.append(fields)
        return pd.DataFrame({"money": [1000.0, 2000.0]})

    register_api(
        {
            "get_history": history,
            "get_trade_days": lambda **kwargs: type(
                "NumpyLike", (object,), {"tolist": lambda self: ["20240102", "20240103"]}
            )(),
        }
    )
    adapter = PtradeAdapter(PtradeContext())
    frame = adapter.get_history("600000", count=2)
    assert frame["amount"].tolist() == [1000.0, 2000.0]
    assert calls == [["open", "high", "low", "close", "volume", "money"]]

    dates = adapter.get_trading_dates("2024-01-01", "2024-01-05")
    assert dates == ["20240102", "20240103"]


def test_ptrade_range_uses_list_fields():
    set_default_mode("ptrade")
    calls = []

    def price(code, **kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"money": [1000.0]})

    register_api({"get_price": price})
    adapter = PtradeAdapter(PtradeContext())
    frame = adapter.get_history_range(
        "600000", "1d", "2024-01-01", "2024-01-31"
    )
    assert isinstance(calls[0]["fields"], list)
    assert "money" in calls[0]["fields"]
    assert frame["amount"].tolist() == [1000.0]
