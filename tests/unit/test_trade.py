# -*- coding: utf-8 -*-
"""交易/生命周期兼容层单元测试。"""

import datetime
from types import SimpleNamespace

import pytest

from jingniflow.api.lifecycle import jingni_handle_data, jingni_main
from jingniflow.api.trade import jingni_order_amount, jingni_order_value
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

    class Account(object):
        cash = {"nav": 100000, "market_value": 50000, "balance": 100000}

        def positions(self):
            return [
                SimpleNamespace(
                    symbol="SHSE.600000", volume=200, volume_today=100
                )
            ]

    def account(self):
        return self.Account()


def test_gm_order_amount_and_value():
    set_default_mode("goldminer")
    calls = []

    def order_volume(**kwargs):
        calls.append(kwargs)
        return {
            "cl_ord_id": "order-1",
            "symbol": "SHSE.600000",
            "side": kwargs["side"],
            "volume": kwargs["volume"],
            "price": kwargs["price"],
            "status": 0,
        }

    register_api(
        {
            "order_volume": order_volume,
            "OrderSide_Buy": 1,
            "OrderSide_Sell": 2,
            "OrderType_Limit": 3,
            "PositionEffect_Open": 4,
            "PositionEffect_Close": 5,
        }
    )
    context = GmContext()
    result = jingni_order_amount(
        "goldminer", context, "600000", 100, 10, dry_run=False
    )
    assert result["platform_order_id"] == "order-1"
    assert result["side"] == "BUY"
    assert calls[-1]["symbol"] == "SHSE.600000"
    assert calls[-1]["volume"] == 100
    assert calls[-1]["side"] == 1

    result = jingni_order_value(
        "goldminer", context, "600000", -2000, 10, dry_run=False
    )
    assert result["platform_order_id"] == "order-1"
    # 可卖量是 200-100=100，金额 2000/10=200 股，但只能卖 100 股。
    assert calls[-1]["volume"] == 100
    assert calls[-1]["position_effect"] == 5


def test_default_dry_run_blocks_order():
    set_default_mode("goldminer")
    calls = []
    register_api(
        {
            "order_volume": lambda **kwargs: calls.append(kwargs),
            "OrderSide_Buy": 1,
            "OrderSide_Sell": 2,
            "OrderType_Limit": 3,
            "PositionEffect_Open": 4,
            "PositionEffect_Close": 5,
        }
    )
    context = GmContext()
    assert (
        jingni_order_amount("goldminer", context, "600000", 100, 10) is None
    )
    assert calls == []


def test_lifecycle_returns_without_loop():
    set_default_mode("qmt")

    class Context(object):
        do_back_test = True
        barpos = 0

        def get_bar_timetag(self, barpos):
            return 0

    context = Context()
    result = jingni_main("qmt", context)
    assert result is not None
    jingni_handle_data("qmt", context)
