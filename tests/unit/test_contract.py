# -*- coding: utf-8 -*-
"""契约层单元测试。"""

import pytest

from jingniflow.core.contract import (
    infer_market,
    map_adjust,
    map_history_fields,
    normalize_code,
    normalize_frequency,
)
from jingniflow.core.errors import ValidationError
from jingniflow.core.order import make_order, normalize_side, normalize_status


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("600000", None, "600000.SH"),
        ("SHSE.600000", None, "600000.SH"),
        ("600000.SH", "goldminer", "SHSE.600000"),
        ("000001.SZ", "qmt", "000001.SZ"),
        ("600000.SH", "ptrade", "600000.SS"),
        ("430047.BJ", "qmt", "430047.BJ"),
        ("BJSE.430047", "goldminer", "BJSE.430047"),
    ],
)
def test_normalize_code(source, target, expected):
    assert normalize_code(source, target) == expected


def test_invalid_code_raises():
    with pytest.raises(ValidationError):
        normalize_code("60000")
    with pytest.raises(ValidationError):
        normalize_code("600000.XX")


def test_frequency_and_adjust():
    assert normalize_frequency("daily") == "1d"
    assert normalize_frequency("60min") == "60m"
    assert map_adjust(None, "qmt") == "front"
    assert map_adjust("none", "ptrade") == "none"


def test_ptrade_history_field_aliases():
    assert map_history_fields("amount", "ptrade") == ["money"]
    assert map_history_fields("pre_close", "ptrade") == ["preclose"]
    assert map_history_fields("amount", "qmt") == ["amount"]


def test_infer_market():
    assert infer_market("600000") == "SH"
    assert infer_market("000001") == "SZ"
    assert infer_market("430047") == "BJ"
    assert infer_market("920001") == "BJ"


def test_order_side_and_status_mapping():
    assert normalize_side("OrderSide_Buy") == "BUY"
    assert normalize_side("24") == "SELL"
    assert normalize_status("goldminer", "OrderStatus_PartiallyFilled") == "PARTIAL"
    assert normalize_status("qmt", 56) == "FILLED"
    order = make_order("ptrade", platform_id="p1", code="600000.SS", status="6")
    assert order["status"] == "CANCELED"
    order = make_order("ptrade", platform_id="p2", code="600000.SS", status="8")
    assert order["status"] == "FILLED"
