# -*- coding: utf-8 -*-
"""Goldminer validation strategy for a simulation account.

STEP 1: keep VALIDATION_STAGE = "dry_run" and run once. It places no order.
STEP 2: after confirming this is a simulation account, change it to
        "order_cancel". The strategy places one 100-share limit buy below
        the market, waits, cancels it, and reconciles orders/positions.
"""

from __future__ import print_function

try:
    from gm.api import *
except ImportError:
    pass

try:
    from jingniflow import *
except ImportError:
    # Single-file mode: definitions are appended at the end.
    pass

trade_mode = "goldminer"
VALIDATION_CODE = "600000.SH"
VALIDATION_SYMBOL = "SHSE.600000"
VALIDATION_STAGE = "dry_run"
VALIDATION_AMOUNT = 100
VALIDATION_CANCEL_DELAY = 8
VALIDATION_CANCEL_TIMEOUT = 25
VALIDATION_ACCOUNT_ID = ""


def init(context):
    global _JINGNI_CONTEXT, _JINGNI_RUNTIME
    subscribe(symbols=VALIDATION_SYMBOL, frequency="1m")
    _JINGNI_CONTEXT = context
    _JINGNI_RUNTIME = jingni_main(
        "goldminer",
        context,
        config=_validation_config(),
        strategy=_validation_strategy,
    )
    jingni_run_interval(_validation_interval, 3, "goldminer", context)


def on_bar(context, bars):
    global _JINGNI_CONTEXT
    _JINGNI_CONTEXT = context
    jingni_handle_data("goldminer", context, strategy=_validation_strategy)


def on_backtest_finished(context, indicator):
    _validation_finish_if_needed()
