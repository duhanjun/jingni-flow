# -*- coding: utf-8 -*-
"""核心契约模块的边界测试。"""

import datetime

from jingniflow.core.calendar import format_date, is_trading_session, normalize_date
from jingniflow.core.config import RuntimeConfig
from jingniflow.core.errors import UnsupportedFeature, ValidationError
from jingniflow.core.instrument import (
    bool_or_none,
    build_instrument,
    date_iso,
    records,
    to_float,
    to_int,
)
from jingniflow.core.order import (
    coerce_order_ref,
    make_order,
    normalize_side,
    normalize_status,
    order_ref,
    ref_matches,
)
from jingniflow.core.risk import calc_max_buy, calc_max_sell, check_order, set_kill_switch
from jingniflow.core.runtime import RuntimeContext


def test_status_mapping_all_platforms():
    assert normalize_status("goldminer", 0) == "PENDING"
    assert normalize_status("goldminer", 3) == "FILLED"
    assert normalize_status("goldminer", 5) == "CANCELED"
    assert normalize_status("goldminer", 12) == "EXPIRED"
    assert normalize_status("goldminer", "ORDERSTATUS_PARTIALLYFILLED") == "PARTIAL"
    assert normalize_status("qmt", 52) == "PARTIAL"
    assert normalize_status("qmt", 57) == "REJECTED"
    assert normalize_status("ptrade", "4") == "PARTIAL"
    assert normalize_status("ptrade", 6) == "CANCELED"
    assert normalize_status("unknown", 99) == "UNKNOWN"
    assert normalize_status("qmt", None) == "UNKNOWN"
    assert normalize_status("qmt", "NOT_A_STATUS") == "UNKNOWN"


def test_order_ref_coercion_and_matching():
    assert normalize_side("buy") == "BUY"
    assert normalize_side("卖出") == "SELL"
    assert normalize_side("unknown") is None

    ref = order_ref("qmt", 123, "r1")
    assert ref == {"platform": "qmt", "id": "123", "remark": "r1"}
    assert coerce_order_ref({"id": 10})["id"] == "10"
    assert coerce_order_ref({"platform_order_id": 11})["id"] == "11"
    assert coerce_order_ref(12)["id"] == "12"
    assert coerce_order_ref({"order_ref": ref}) is ref
    assert coerce_order_ref(None) is None
    assert ref_matches({"platform_order_id": "123", "remark": "r1"}, ref) is True
    assert ref_matches({"platform_order_id": "999"}, ref) is False


def test_make_order_handles_invalid_numbers():
    order = make_order(
        "qmt",
        platform_id=None,
        code="600000.SH",
        side=None,
        price="bad",
        amount="bad",
        filled="bad",
        status=99,
    )
    assert order["platform_order_id"] is None
    assert order["side"] is None
    assert order["price"] is None
    assert order["amount"] is None
    assert order["filled"] is None
    assert order["status"] == "UNKNOWN"


def test_instrument_helpers_and_defaults():
    assert date_iso("19700101") is None
    assert date_iso(datetime.date(2024, 1, 2)) == "2024-01-02"
    assert date_iso("2024/01/02") == "2024-01-02"
    assert date_iso("not-a-date") == "not-a-date"
    assert to_float("bad") is None
    assert to_int("1.9") == 1
    assert to_int("bad") is None
    assert bool_or_none("yes") is True
    assert bool_or_none("0") is False
    assert bool_or_none("unknown") is None

    assert records({"data": [{"code": "600000.SH"}]}) == [{"code": "600000.SH"}]
    assert len(records({"600000.SH": {"name": "浦发"}, "000001.SZ": None})) == 1
    assert records(None) == []

    instrument = build_instrument("600000.SH")
    assert instrument["lot_size"] == 100
    assert instrument["board"] == "主板"
    assert instrument["status"] == {"st": None, "suspend": None, "delisted": None}


def test_calendar_helpers_and_session_boundaries():
    assert normalize_date(None) is None
    assert normalize_date("20240102") == "20240102"
    assert normalize_date("bad") is None
    assert format_date("20240102") == "2024-01-02"
    assert is_trading_session(datetime.time(9, 29)) is False
    assert is_trading_session(datetime.time(9, 30)) is True
    assert is_trading_session(datetime.time(11, 30)) is True
    assert is_trading_session(datetime.time(12, 0)) is False
    assert is_trading_session(datetime.time(13, 0)) is True
    assert is_trading_session(datetime.time(15, 0)) is True
    assert is_trading_session(datetime.time(9, 20), include_auction=True) is True


def test_config_update_and_as_dict():
    config = RuntimeConfig(account_id="acct")
    assert config.as_dict()["dry_run"] is True
    config.update(max_order_amount=200000, unknown_field=1)
    assert config.max_order_amount == 200000
    assert not hasattr(config, "unknown_field")


def test_error_strings_and_unsupported_feature():
    error = ValidationError("bad input", platform="qmt", details={"field": "code"})
    assert "JINGNI_VALIDATION" in str(error)
    assert error.details["field"] == "code"
    unsupported = UnsupportedFeature("qmt", "futures")
    assert "futures" in str(unsupported)
    assert unsupported.feature == "futures"


def test_risk_edge_checks_and_helpers():
    context = RuntimeContext("goldminer", config=RuntimeConfig(max_daily_orders=1))
    assert set_kill_switch(context, True) is True
    assert check_order(context, "600000.SH", "BUY", 100, 10) == (
        False,
        "kill_switch is active",
    )
    set_kill_switch(context, False)
    assert check_order(context, "600000.SH", "UNKNOWN", 100, 10)[0] is False
    assert check_order(context, "600000.SH", "BUY", 1, 10)[1] == (
        "A-share buy amount must be a multiple of 100"
    )
    assert check_order(context, "600000.SH", "BUY", 100, 10, now=datetime.datetime(2024, 1, 2, 10))[0]
    assert check_order(context, "600000.SH", "BUY", 100, 10, now=datetime.datetime(2024, 1, 2, 10, 0, 1))[1] == (
        "daily order limit reached"
    )
    assert calc_max_buy({"available": 1000}, 10) == 100
    assert calc_max_buy({"available": 0}, 10) == 0
    assert calc_max_sell([{"code": "600000.SH", "available": 200}], "600000.SH") == 200
