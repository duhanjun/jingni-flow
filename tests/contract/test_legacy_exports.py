# -*- coding: utf-8 -*-
"""旧接口导出契约测试。"""

import jingniflow

OLD_API = [
    "jingni_trading_dates",
    "jingni_trading_times",
    "jingni_portfolio",
    "jingni_map_security_code",
    "jingni_get_current",
    "jingni_get_history",
    "jingni_get_field",
    "jingni_get_field_n",
    "jingni_order_amount",
    "jingni_order_value",
    "jingni_subscribe_new_stock",
    "jingni_subscribe_new_bond",
    "jingni_participate_reverse_repo",
    "jingni_trade_strategy",
    "jingni_before_trading_start",
    "jingni_handle_data",
    "jingni_after_trading_end",
    "jingni_main",
]


def test_all_v01_names_are_exported():
    for name in OLD_API:
        assert hasattr(jingniflow, name), name
        assert name in jingniflow.__all__, name


def test_new_diagnostics_are_exported():
    assert jingniflow.jingni_version() == jingniflow.__version__
    capabilities = jingniflow.jingni_capabilities("qmt")
    assert capabilities["platform"] == "qmt"
    assert "market.history" in capabilities["features"]
    assert hasattr(jingniflow, "jingni_doctor")
    assert "jingni_doctor" in jingniflow.__all__


def test_phase2_names_are_exported():
    phase2_api = [
        "jingni_get_history_range",
        "jingni_download_history",
        "jingni_get_instrument",
        "jingni_get_stock_status",
        "jingni_get_trading_dates",
        "jingni_is_trading_day",
        "jingni_is_trading_time",
        "jingni_run_interval",
    ]
    for name in phase2_api:
        assert hasattr(jingniflow, name), name
        assert name in jingniflow.__all__, name


def test_strategy_registration_names_are_exported():
    for name in ("jingni_set_strategy", "jingni_get_strategy"):
        assert hasattr(jingniflow, name), name
        assert name in jingniflow.__all__, name

