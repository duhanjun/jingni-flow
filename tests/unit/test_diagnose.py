# -*- coding: utf-8 -*-
"""能力矩阵与启动自检测试。"""

import pytest

from jingniflow.api.diagnose import jingni_capabilities, jingni_doctor
from jingniflow.core.config import RuntimeConfig
from jingniflow.core.runtime import clear_api_registry, set_default_mode


@pytest.fixture(autouse=True)
def clean_registry():
    clear_api_registry()
    set_default_mode("软件名称")
    yield
    clear_api_registry()
    set_default_mode("软件名称")


class QmtRaw(object):
    do_back_test = False
    account = "test-account"


def test_capabilities_include_phase2_and_platform_levels():
    caps = jingni_capabilities("ptrade")
    assert caps["platform"] == "ptrade"
    assert caps["features"]["market.history_range"]["phase"] == 2
    assert caps["features"]["market.history_range"]["level"] == "full"
    assert caps["features"]["market.history_range"]["platform_levels"]["qmt"] == "full"
    assert caps["features"]["data.download"]["level"] == "unsupported"
    assert caps["features"]["instrument.status"]["level"] == "full"
    assert "calendar.trading_time" in caps["features"]


def test_capabilities_unknown_platform_is_explicit():
    caps = jingni_capabilities("unknown-broker")
    assert caps["platform"] == "unknown-broker"
    assert caps["features"]["market.history"]["level"] == "unsupported"


def test_doctor_reports_safe_defaults():
    report = jingni_doctor(
        "qmt",
        QmtRaw(),
        config=RuntimeConfig(account_id="test-account"),
        verbose=False,
    )
    assert report["ok"] is True
    assert report["platform"] == "qmt"
    assert any(item["name"] == "phase2_features" for item in report["checks"])
    assert not report["errors"]


def test_doctor_reports_unsafe_config():
    config = RuntimeConfig(
        account_id="test-account",
        dry_run=False,
        max_order_amount=0,
        kill_switch=True,
    )
    report = jingni_doctor("qmt", QmtRaw(), config=config, verbose=False)
    assert report["ok"] is False
    assert any(
        item["name"] == "max_order_amount" and item["status"] == "error"
        for item in report["errors"]
    )
    assert any(
        item["name"] == "dry_run" and item["status"] == "warn"
        for item in report["warnings"]
    )
    assert any(
        item["name"] == "kill_switch" and item["status"] == "warn"
        for item in report["warnings"]
    )


def test_doctor_rejects_unknown_platform():
    report = jingni_doctor("unknown-broker", verbose=False)
    assert report["ok"] is False
    assert any(
        item["name"] == "platform" and item["status"] == "error"
        for item in report["errors"]
    )
