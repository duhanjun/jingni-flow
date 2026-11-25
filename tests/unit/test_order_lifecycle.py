# -*- coding: utf-8 -*-
"""订单生命周期、统一持仓与风控测试。"""

import datetime
from types import SimpleNamespace

import pytest

from jingniflow.api.account import jingni_get_account, jingni_get_positions
from jingniflow.adapters.qmt import QmtAdapter
from jingniflow.api.risk import (
    jingni_calc_max_sell,
    jingni_check_order,
    jingni_kill_switch,
)
from jingniflow.api.trade import (
    jingni_cancel_order,
    jingni_get_orders,
    jingni_get_trades,
    jingni_order_amount,
    jingni_order_market,
    jingni_order_target_amount,
)
from jingniflow.core.config import RuntimeConfig
from jingniflow.core.runtime import (
    RuntimeContext,
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
        cash = {
            "nav": 100000,
            "market_value": 50000,
            "balance": 100000,
            "available": 100000,
        }

        def positions(self):
            return [
                SimpleNamespace(
                    symbol="SHSE.600000",
                    volume=300,
                    volume_today=100,
                    vwap=9,
                    market_value=2700,
                    unrealized_pnl=200,
                )
            ]

    def account(self):
        return self.Account()


def _gm_order_api(calls):
    def order_volume(**kwargs):
        calls.append(("order", kwargs))
        return [
            {
                "cl_ord_id": "gm-1",
                "account_id": "gm-account",
                "symbol": "SHSE.600000",
                "side": kwargs["side"],
                "volume": kwargs["volume"],
                "price": kwargs["price"],
                "status": 0,
            }
        ]

    register_api(
        {
            "order_volume": order_volume,
            "OrderSide_Buy": 1,
            "OrderSide_Sell": 2,
            "OrderType_Limit": 3,
            "OrderType_Market": 4,
            "PositionEffect_Open": 5,
            "PositionEffect_Close": 6,
            "get_orders": lambda: [
                {
                    "cl_ord_id": "gm-1",
                    "symbol": "SHSE.600000",
                    "side": 1,
                    "volume": 200,
                    "filled_volume": 100,
                    "price": 10,
                    "status": 0,
                }
            ],
            "get_execution_reports": lambda: [
                {
                    "cl_ord_id": "gm-1",
                    "symbol": "SHSE.600000",
                    "side": 1,
                    "volume": 100,
                    "price": 10,
                }
            ],
            "order_cancel": lambda wait_cancel_orders: calls.append(("cancel", wait_cancel_orders)) or True,
            "order_cancel_all": lambda: calls.append(("cancel_all",)) or 1,
        }
    )


def test_gm_order_lifecycle_and_unified_positions():
    set_default_mode("goldminer")
    calls = []
    _gm_order_api(calls)
    context = GmContext()
    runtime = RuntimeContext("goldminer", context, RuntimeConfig(dry_run=False))

    ref = jingni_order_amount(runtime, context, "600000", 100, 10)
    assert ref["platform_order_id"] == "gm-1"
    assert ref["status"] == "PENDING"
    assert jingni_cancel_order(runtime, context, ref) is True
    assert calls[-1] == (
        "cancel",
        [{"cl_ord_id": "gm-1", "account_id": "gm-account"}],
    )

    orders = jingni_get_orders(runtime, context)
    assert len(orders) == 1
    assert orders[0]["filled"] == 100
    assert orders[0]["status"] == "PENDING"
    trades = jingni_get_trades(runtime, context, ref)
    assert len(trades) == 1
    assert trades[0]["amount"] == 100

    positions = jingni_get_positions(runtime, context)
    assert positions[0]["code"] == "600000.SH"
    assert positions[0]["amount"] == 300
    assert positions[0]["available"] == 200
    account = jingni_get_account(runtime, context)
    assert account["available"] == 100000


def test_gm_cancel_prefers_real_account_id_over_strategy_id():
    """Order.account_id 可能是 strategy_id，撤单必须用 Cash 的真实账号。"""

    class RealAccountContext(GmContext):
        class Account(GmContext.Account):
            cash = dict(GmContext.Account.cash, account_id="gm-real-account")

    set_default_mode("goldminer")
    calls = []
    _gm_order_api(calls)
    context = RealAccountContext()
    runtime = RuntimeContext("goldminer", context, RuntimeConfig(dry_run=False))
    ref = jingni_order_amount(runtime, context, "600000", 100, 10)
    assert jingni_cancel_order(runtime, context, ref) is True
    assert calls[-1] == (
        "cancel",
        [{"cl_ord_id": "gm-1", "account_id": "gm-real-account"}],
    )


class QmtObj(object):
    pass


class QmtContext(object):
    do_back_test = True
    barpos = 0
    account = "test-account"

    class Account(object):
        pass


def _qmt_obj(**kwargs):
    obj = QmtObj()
    for key, value in kwargs.items():
        setattr(obj, key, value)
    return obj


def test_qmt_backtest_without_account_returns_empty_details():
    raw = SimpleNamespace(do_back_test=True, account=None)
    context = RuntimeContext("qmt", raw)
    adapter = QmtAdapter(context)
    assert adapter.get_orders() == []
    assert adapter.get_trades() == []
    assert adapter.get_positions() == []
    account = adapter.get_account()
    assert account["cash"] is None
    assert adapter.get_portfolio("positions") == []


def test_qmt_order_query_positions():
    set_default_mode("qmt")
    orders = [
        _qmt_obj(
            m_strOrderSysID="qmt-1",
            m_strInstrumentID="600000",
            m_strExchangeID="SH",
            m_nDirection=23,
            m_dLimitPrice=10,
            m_nVolumeTotalOriginal=200,
            m_nVolumeTraded=0,
            m_nOrderStatus=50,
            m_strRemark="r1",
        )
    ]
    deals = [
        _qmt_obj(
            m_strOrderSysID="qmt-1",
            m_strInstrumentID="600000",
            m_strExchangeID="SH",
            m_dPrice=10,
            m_nVolume=100,
            m_nDirection=23,
        )
    ]
    positions = [
        _qmt_obj(
            m_strInstrumentID="600000",
            m_strExchangeID="SH",
            m_nVolume=300,
            m_nCanUseVolume=200,
            m_dOpenPrice=9,
            m_dMarketValue=2700,
            m_dFloatProfit=200,
        )
    ]
    accounts = [
        _qmt_obj(
            m_dBalance=100000,
            m_dAvailable=50000,
            m_dInstrumentValue=50000,
        )
    ]

    def detail(account, account_type, kind):
        return {"order": orders, "deal": deals, "position": positions, "account": accounts}[kind]

    register_api(
        {
            "get_trade_detail_data": detail,
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )
    context = QmtContext()
    runtime = RuntimeContext("qmt", context, RuntimeConfig(dry_run=False))
    order = jingni_get_orders(runtime, context)[0]
    assert order["code"] == "600000.SH"
    assert order["side"] == "BUY"
    assert order["status"] == "PENDING"
    assert order["remark"] == "r1"
    pos = jingni_get_positions(runtime, context)[0]
    assert pos["available"] == 200
    assert jingni_calc_max_sell("600000", runtime, context) == 200
    assert jingni_get_account(runtime, context)["available"] == 50000


def test_risk_limits_and_kill_switch():
    set_default_mode("goldminer")
    calls = []
    _gm_order_api(calls)
    context = GmContext()
    runtime = RuntimeContext(
        "goldminer",
        context,
        RuntimeConfig(
            dry_run=False,
            max_order_amount=200,
            max_daily_orders=1,
            repeat_window_seconds=2,
        ),
    )
    ok, reason = jingni_check_order("600000", "BUY", 150, 10, runtime, context)
    assert not ok
    assert "multiple of 100" in reason

    ok, reason = jingni_check_order("600000", "BUY", 300, 10, runtime, context)
    assert not ok
    assert "max_order_amount" in reason

    ok, _ = jingni_check_order("600000", "BUY", 100, 10, runtime, context)
    assert ok
    ok, reason = jingni_check_order("600000", "BUY", 100, 10, runtime, context)
    assert not ok
    assert "daily" in reason

    jingni_kill_switch(runtime, context)
    assert runtime.config.kill_switch is True
    ok, reason = jingni_check_order("600000", "BUY", 100, 10, runtime, context)
    assert not ok
    assert "kill_switch" in reason


def test_target_amount_difference_engine():
    set_default_mode("goldminer")
    calls = []
    _gm_order_api(calls)
    context = GmContext()
    runtime = RuntimeContext("goldminer", context, RuntimeConfig(dry_run=False))
    ref = jingni_order_target_amount(
        runtime, context, "600000", 500, security_price=10
    )
    assert ref["platform_order_id"] == "gm-1"
    assert calls[-1][1]["volume"] == 100


def test_qmt_order_placement_and_market_prtype():
    set_default_mode("qmt")
    calls = []

    def passorder(*args):
        calls.append(args)
        return "qmt-order-1"

    account_rows = [
        _qmt_obj(m_dBalance=100000, m_dAvailable=100000, m_dInstrumentValue=0)
    ]
    position_rows = []

    def detail(account, account_type, kind):
        return {"account": account_rows, "position": position_rows}.get(kind, [])

    register_api(
        {
            "passorder": passorder,
            "get_trade_detail_data": detail,
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )
    context = QmtContext()
    runtime = RuntimeContext(
        "qmt",
        context,
        RuntimeConfig(dry_run=False, repeat_window_seconds=0),
    )
    ref = jingni_order_amount(runtime, context, "600000", 100, 10)
    assert ref["platform_order_id"] == "qmt-order-1"
    assert calls[-1][0] == 23
    assert calls[-1][1] == 1101
    assert calls[-1][3] == "600000.SH"
    assert calls[-1][4] == 11
    assert calls[-1][7] == "JingniFlow"
    assert calls[-1][8] == 2

    ref = jingni_order_market(runtime, context, "600000", 100, protect_price=10)
    assert ref["platform_order_id"] == "qmt-order-1"
    assert calls[-1][0] == 23
    assert calls[-1][4] == 42


def test_qmt_cancel_resolves_remark_to_order_sys_id():
    set_default_mode("qmt")
    calls = []

    def detail(account, account_type, kind):
        if kind == "order":
            return [
                _qmt_obj(
                    m_strOrderSysID="qmt-actual-1",
                    m_strInstrumentID="600000",
                    m_strExchangeID="SH",
                    m_nDirection=23,
                    m_dLimitPrice=10,
                    m_nVolumeTotalOriginal=100,
                    m_nVolumeTraded=0,
                    m_nOrderStatus=50,
                    m_strRemark="validation-1",
                )
            ]
        return []

    def cancel(order_id, account, account_type, context):
        calls.append(("cancel", order_id))
        return True

    register_api(
        {
            "passorder": lambda *args: None,
            "get_trade_detail_data": detail,
            "cancel": cancel,
        }
    )
    context = QmtContext()
    adapter = QmtAdapter(RuntimeContext("qmt", context, RuntimeConfig(dry_run=False)))
    ref = adapter.order("600000", "BUY", 100, 10, remark="validation-1")
    assert ref["platform_order_id"] == "validation-1"
    assert adapter.cancel(ref) is True


def test_qmt_cancel_uses_last_order_id_before_order_list_visible():
    set_default_mode("qmt")
    calls = []
    register_api(
        {
            "passorder": lambda *args: None,
            "get_trade_detail_data": lambda *args: [],
            "get_last_order_id": lambda *args: "1096",
            "get_value_by_order_id": lambda *args: _qmt_obj(
                m_strRemark="validation-2"
            ),
            "cancel": lambda order_id, *args: calls.append(("cancel", order_id))
            or True,
        }
    )
    context = QmtContext()
    adapter = QmtAdapter(RuntimeContext("qmt", context, RuntimeConfig(dry_run=False)))
    ref = adapter.order("600000", "BUY", 100, 10, remark="validation-2")
    assert adapter.cancel(ref) is True
    assert calls[-1] == ("cancel", "1096")


class PtradePortfolio(object):
    portfolio_value = 100000
    positions_value = 0
    cash = 100000
    positions = {}


class PtradeContext(object):
    portfolio = PtradePortfolio()


def test_ptrade_order_and_account():
    set_default_mode("ptrade")
    calls = []
    register_api(
        {
            "is_trade": lambda: False,
            "order": lambda *args, **kwargs: calls.append((args, kwargs)) or "pt-1",
        }
    )
    context = PtradeContext()
    runtime = RuntimeContext("ptrade", context, RuntimeConfig(dry_run=False))
    ref = jingni_order_amount(runtime, context, "600000", 100, 10)
    assert ref["platform_order_id"] == "pt-1"
    assert calls[-1][0][0] == "600000.SS"
    assert calls[-1][0][1] == 100
    account = jingni_get_account(runtime, context)
    assert account["available"] == 100000


def test_ptrade_pending_order_uses_get_order_not_stale_list():
    set_default_mode("ptrade")
    register_api(
        {
            "is_trade": lambda: False,
            "order": lambda *args, **kwargs: "pt-strategy-1",
            "get_order": lambda order_id: [
                {
                    "id": "pt-strategy-1",
                    "symbol": "600000.SS",
                    "amount": 100,
                    "entrust_bs": 1,
                    "price": 9.63,
                    "status": "2",
                    "filled_amount": 0,
                    "entrust_no": "pt-entrust-1",
                }
            ],
            "get_orders": lambda: [
                {
                    "id": "pt-old-1",
                    "symbol": "600000.SS",
                    "amount": 100,
                    "entrust_bs": 1,
                    "price": 9.63,
                    "status": "8",
                    "filled_amount": 100,
                }
            ],
            "get_all_orders": lambda: [],
        }
    )
    context = PtradeContext()
    runtime = RuntimeContext("ptrade", context, RuntimeConfig(dry_run=False))
    ref = jingni_order_amount(runtime, context, "600000", 100, 9.63)
    assert ref["platform_order_id"] == "pt-strategy-1"
    orders = jingni_get_orders(runtime, context)
    assert orders[0]["platform_order_id"] == "pt-strategy-1"
    assert orders[0]["status"] == "PENDING"


def test_ptrade_get_orders_merges_all_orders_and_cancels_ex():
    set_default_mode("ptrade")
    calls = []
    all_order = {
        "symbol": "600000.SS",
        "entrust_no": "pt-entrust-1",
        "amount": 100,
        "entrust_bs": 1,
        "price": 9.63,
        "status": "2",
        "filled_amount": 0,
        "entrust_time": "2026-11-24 09:30:02",
    }
    register_api(
        {
            "is_trade": lambda: False,
            "get_orders": lambda: [],
            "get_all_orders": lambda: [all_order],
            "cancel_order": lambda order_id: calls.append(("cancel_order", order_id))
            or (_ for _ in ()).throw(RuntimeError("not in strategy orders")),
            "cancel_order_ex": lambda row: calls.append(("cancel_order_ex", row)),
        }
    )
    context = PtradeContext()
    runtime = RuntimeContext("ptrade", context, RuntimeConfig(dry_run=False))
    orders = jingni_get_orders(runtime, context)
    assert len(orders) == 1
    assert orders[0]["platform_order_id"] == "pt-entrust-1"
    assert jingni_cancel_order(runtime, context, orders[0]) is True
    assert calls[-1][0] == "cancel_order_ex"
