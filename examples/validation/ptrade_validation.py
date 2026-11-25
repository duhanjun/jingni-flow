# -*- coding: utf-8 -*-
"""PTrade validation strategy for a simulation account.

STEP 1: keep VALIDATION_STAGE = "dry_run" and run once. It places no order.
STEP 2: after confirming this is a simulation account, change it to
        "order_cancel". The strategy places one 100-share limit buy below
        the market, waits, cancels it, and reconciles orders/positions.

Must remain Python 3.5 compatible: no f-strings, no annotations, no sys usage.
"""

from __future__ import print_function

try:
    from jingniflow import *
except ImportError:
    # Single-file mode: definitions are appended at the end.
    pass

trade_mode = "ptrade"
VALIDATION_CODE = "600000.SH"
VALIDATION_SYMBOL = "600000.SS"
VALIDATION_STAGE = "dry_run"
VALIDATION_AMOUNT = 100
VALIDATION_CANCEL_DELAY = 8
VALIDATION_CANCEL_TIMEOUT = 25
VALIDATION_ACCOUNT_ID = ""
_VALIDATION_HANDLE_SEEN = False


def _validation_interval_ptrade(*args, **kwargs):
    # PTrade 在 initialize/定时器里下单，柜台可能接受，但 get_orders()
    # 不会把这笔委托归入策略订单列表；必须等 handle_data 后再报单。
    if not _VALIDATION_HANDLE_SEEN:
        return
    _validation_interval(*args, **kwargs)


def initialize(context):
    global _JINGNI_CONTEXT, _JINGNI_RUNTIME
    try:
        set_universe([VALIDATION_SYMBOL])
    except Exception:
        pass
    _JINGNI_CONTEXT = context
    _JINGNI_RUNTIME = jingni_main(
        "ptrade",
        context,
        config=_validation_config(),
        strategy=_validation_strategy,
    )
    jingni_run_interval(_validation_interval_ptrade, 3, "ptrade", context)


def handle_data(context, data):
    global _JINGNI_CONTEXT, _VALIDATION_HANDLE_SEEN
    _VALIDATION_HANDLE_SEEN = True
    _JINGNI_CONTEXT = context
    jingni_handle_data("ptrade", context, strategy=_validation_strategy)


def after_trading_end(context, data):
    _validation_finish_if_needed()
