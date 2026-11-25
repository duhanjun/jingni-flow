# -*- coding: utf-8 -*-
"""业务函数（打新/逆回购/交易日）单元测试。"""

import datetime

import pandas as pd
import pytest

from jingniflow.api.ipo import jingni_subscribe_new_bond, jingni_subscribe_new_stock
from jingniflow.api.repo import jingni_participate_reverse_repo
from jingniflow.api.runtime import jingni_trading_dates
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
            return []

    def account(self):
        return self.Account()


def test_gm_next_trading_date_uses_nth_not_first():
    set_default_mode("goldminer")
    register_api(
        {
            "get_next_n_trading_dates": lambda **kwargs: [
                datetime.datetime(2024, 1, 3),
                datetime.datetime(2024, 1, 4),
            ]
        }
    )
    assert jingni_trading_dates("goldminer", GmContext(), 2) == "20240104"
    assert jingni_trading_dates("goldminer", GmContext(), 0) == "20240102"


def test_gm_repo_dry_run_does_not_order():
    set_default_mode("goldminer")
    calls = []
    register_api(
        {
            "history_n": lambda **kwargs: pd.DataFrame({"close": [3.5]}),
            "order_volume": lambda **kwargs: calls.append(kwargs),
            "OrderSide_Sell": 2,
            "OrderType_Limit": 3,
            "PositionEffect_Close": 5,
        }
    )
    assert jingni_participate_reverse_repo(GmContext(), cash_ratio=1.0) is None
    assert calls == []


def test_gm_repo_real_order_bypasses_stock_available_check():
    set_default_mode("goldminer")
    calls = []

    def order_volume(**kwargs):
        calls.append(kwargs)
        return {
            "cl_ord_id": "repo-1",
            "symbol": "SHSE.204001",
            "side": kwargs["side"],
            "price": kwargs["price"],
            "volume": kwargs["volume"],
            "status": 0,
        }

    register_api(
        {
            "history_n": lambda **kwargs: pd.DataFrame({"close": [3.5]}),
            "order_volume": order_volume,
            "OrderSide_Sell": 2,
            "OrderType_Limit": 3,
            "PositionEffect_Close": 5,
        }
    )
    result = jingni_participate_reverse_repo(
        GmContext(), cash_ratio=1.0, dry_run=False
    )
    assert result["platform_order_id"] == "repo-1"
    assert calls[-1]["symbol"] == "SHSE.204001"
    assert calls[-1]["volume"] >= 10


class QmtContext(object):
    do_back_test = True
    barpos = 0

    def get_bar_timetag(self, barpos):
        return 0


def test_qmt_ipo_dry_run_reads_data_but_does_not_order():
    set_default_mode("qmt")
    register_api(
        {
            "get_ipo_data": lambda kind: {
                "600000.SH": {"issuePrice": 10, "maxPurchaseNum": 100}
            },
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )
    result = jingni_subscribe_new_stock(QmtContext())
    assert result.get("600000.SH") == "dry_run"
    result_bond = jingni_subscribe_new_bond(QmtContext())
    assert result_bond.get("600000.SH") == "dry_run"
