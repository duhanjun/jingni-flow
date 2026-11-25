# -*- coding: utf-8 -*-
"""Phase 1 运行/调度 API 测试。"""

import datetime

import pytest

from jingniflow.api.runtime import (
    jingni_now,
    jingni_offset_trade_date,
    jingni_schedule,
    jingni_wall_now,
)
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


class QmtContext(object):
    do_back_test = True
    barpos = 0

    def get_bar_timetag(self, barpos):
        return 0


class QmtRawScheduleContext(QmtContext):
    def __init__(self):
        self.schedule_calls = []

    def schedule_run(self, *args):
        self.schedule_calls.append(args)


def test_qmt_schedule_prefers_context_method():
    context = QmtRawScheduleContext()

    def task():
        pass

    assert jingni_schedule(task, "09:31", trade_mode="qmt", context_data=context) == "task"
    assert len(context.schedule_calls) == 1
    assert context.schedule_calls[0][1].endswith("093100")
    assert context.schedule_calls[0][2] == -1


def test_schedule_dispatch_on_three_platforms():
    calls = []
    register_api(
        {
            "schedule": lambda **kwargs: calls.append(("gm", kwargs)),
            "schedule_run": lambda *args: calls.append(("qmt", args)),
            "run_daily": lambda *args, **kwargs: calls.append(("pt", args, kwargs)),
            "timetag_to_datetime": lambda *args: "2024-01-02 10:00:00",
        }
    )

    def task():
        pass

    assert jingni_schedule(task, "09:31", trade_mode="goldminer", context_data=GmContext()) == "task"
    assert calls[-1][0] == "gm"
    assert calls[-1][1]["time_rule"] == "09:31:00"

    assert jingni_schedule(task, "9:31:0", trade_mode="goldminer", context_data=GmContext()) == "task"
    assert calls[-1][1]["time_rule"] == "09:31:00"

    assert jingni_schedule(task, "09:31", trade_mode="qmt", context_data=QmtContext()) == "task"
    assert calls[-1][0] == "qmt"
    assert calls[-1][1][1].endswith("093100")
    assert calls[-1][1][2] == -1

    context = RuntimeContext("ptrade", object())
    assert jingni_schedule(task, "09:31", trade_mode="ptrade", context_data=context) == "task"
    assert calls[-1][0] == "pt"
    assert calls[-1][2]["time"] == "09:31"


def test_now_and_offset_trade_date_gm_anchor():
    register_api(
        {
            "get_next_n_trading_dates": lambda **kwargs: [datetime.datetime(2024, 1, 4)],
            "get_previous_n_trading_dates": lambda **kwargs: [datetime.datetime(2023, 12, 29)],
        }
    )
    context = GmContext()
    runtime = RuntimeContext("goldminer", context)
    assert jingni_now(runtime, context) == datetime.datetime(2024, 1, 2, 10, 0, 0)
    assert jingni_offset_trade_date(1, "2024-01-03", "goldminer", context) == "20240104"
    assert jingni_offset_trade_date(-1, "2024-01-02", "goldminer", context) == "20231229"
    assert isinstance(jingni_wall_now(), datetime.datetime)
