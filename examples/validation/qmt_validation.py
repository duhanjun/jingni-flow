# encoding: gbk
"""QMT validation strategy for a simulation account.

STEP 1: keep VALIDATION_STAGE = "dry_run" and run once. It places no order.
STEP 2: after confirming this is a simulation account, change it to
        "order_cancel". The strategy places one 100-share limit buy below
        the market, waits, cancels it, and reconciles orders/positions.

The whole strategy file must be saved as GBK/ANSI.
"""

from __future__ import print_function

import time

try:
    from jingniflow import *
except ImportError:
    # Single-file mode: definitions are appended at the end.
    pass

trade_mode = "qmt"
VALIDATION_CODE = "600000.SH"
VALIDATION_SYMBOL = "600000.SH"
VALIDATION_STAGE = "dry_run"
VALIDATION_AMOUNT = 100
VALIDATION_CANCEL_DELAY = 0
VALIDATION_CANCEL_TIMEOUT = 25
VALIDATION_ACCOUNT_ID = ""
_VALIDATION_HANDLEBAR_SEEN = False
_VALIDATION_START_AT = 0


def _validation_interval_qmt(*args, **kwargs):
    # QMT may accept passorder from init/run_time without creating a
    # counter-visible order. Start only after the first handlebar arrives;
    # fall back to the timer after 15s in case the chart never calls back.
    if not _VALIDATION_HANDLEBAR_SEEN:
        if _VALIDATION_START_AT and time.time() - _VALIDATION_START_AT < 15:
            return
    _validation_interval(*args, **kwargs)


def init(ContextInfo):
    global _JINGNI_CONTEXT, _JINGNI_RUNTIME, _VALIDATION_START_AT
    _VALIDATION_START_AT = time.time()
    ContextInfo.set_universe([VALIDATION_SYMBOL])
    _JINGNI_CONTEXT = ContextInfo
    _JINGNI_RUNTIME = jingni_main(
        "qmt",
        ContextInfo,
        config=_validation_config(),
        strategy=_validation_strategy,
    )
    jingni_run_interval(_validation_interval_qmt, 3, "qmt", ContextInfo)


def handlebar(ContextInfo):
    global _JINGNI_CONTEXT, _VALIDATION_HANDLEBAR_SEEN
    if not ContextInfo.is_last_bar():
        return
    _VALIDATION_HANDLEBAR_SEEN = True
    _JINGNI_CONTEXT = ContextInfo
    jingni_handle_data("qmt", ContextInfo, strategy=_validation_strategy)


def on_backtest_finished(ContextInfo):
    _validation_finish_if_needed()
