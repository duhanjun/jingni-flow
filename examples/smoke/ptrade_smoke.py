# -*- coding: utf-8 -*-
"""JingniFlow PTrade smoke strategy.

Usage:
  1. Create a strategy in the PTrade terminal.
  2. Paste this file into the strategy.
  3. Paste the full contents of dist/jingniflow_single.py at the end.
  4. Run in simulation first. SMOKE_REAL_ORDER is False by default.
"""

from __future__ import print_function

import datetime

try:
    from jingniflow import *
except ImportError:
    # Single-file mode: definitions are appended at the end of this file.
    pass

trade_mode = "ptrade"
SMOKE_CODE = "600000.SH"
SMOKE_SYMBOL = "600000.SS"
SMOKE_REAL_ORDER = False
_SMOKE_DONE = False
_INTERVAL_DONE = False
_SMOKE_PASS = 0
_SMOKE_FAIL = 0
_SMOKE_SKIP = 0
_JINGNI_RUNTIME = None
_SMOKE_SUMMARY_READY = False


def _smoke_value(value):
    if value is None:
        return "None"
    if hasattr(value, "shape"):
        return "shape={0}".format(value.shape)
    if isinstance(value, dict):
        keys = sorted([str(item) for item in value.keys()])[:8]
        return "dict count={0} keys={1}".format(len(value), keys)
    if isinstance(value, (list, tuple)):
        return "{0} items".format(len(value))
    return str(value)


def _smoke_call(name, func, validator=None):
    global _SMOKE_PASS, _SMOKE_FAIL
    try:
        result = func()
        if validator is not None and not validator(result):
            raise AssertionError("result did not satisfy validator")
        _SMOKE_PASS += 1
        print("[SMOKE][OK] {0}: {1}".format(name, _smoke_value(result)))
        return result
    except Exception as exc:
        _SMOKE_FAIL += 1
        print("[SMOKE][FAIL] {0}: {1}: {2}".format(name, type(exc).__name__, exc))
        return None


def _smoke_skip(name, reason):
    global _SMOKE_SKIP
    _SMOKE_SKIP += 1
    print("[SMOKE][SKIP] {0}: {1}".format(name, reason))


def _smoke_is_backtest():
    return bool(getattr(_JINGNI_RUNTIME, "is_backtest", False))


def _smoke_summary(stage):
    global _SMOKE_SUMMARY_READY
    _SMOKE_SUMMARY_READY = True
    mode = "backtest" if _smoke_is_backtest() else "live/unknown"
    print(
        "[SMOKE][SUMMARY] stage={0} platform={1} mode={2} pass={3} fail={4} skip={5}".format(
            stage, trade_mode, mode, _SMOKE_PASS, _SMOKE_FAIL, _SMOKE_SKIP
        )
    )
    if _SMOKE_FAIL == 0:
        print(
            "[SMOKE][RESULT] {0}: ALL CHECKS PASSED; SMOKE VERIFICATION SUCCESS / \u9a8c\u8bc1\u6210\u529f".format(
                stage
            )
        )
    else:
        print(
            "[SMOKE][RESULT] {0}: SMOKE VERIFICATION FAILED; failed={1}".format(
                stage, _SMOKE_FAIL
            )
        )


def _smoke_interval(*args, **kwargs):
    global _INTERVAL_DONE
    if _INTERVAL_DONE:
        return
    _INTERVAL_DONE = True
    print("[SMOKE][OK] interval fired")


def _smoke_scheduled(*args, **kwargs):
    print("[SMOKE][OK] scheduled task fired")


def _smoke_run(context):
    global _SMOKE_DONE
    if _SMOKE_DONE:
        return
    _SMOKE_DONE = True
    print("=" * 64)
    print("[SMOKE] start platform={0} code={1}".format(trade_mode, SMOKE_CODE))

    _smoke_call(
        "doctor",
        lambda: jingni_doctor(trade_mode, context, verbose=True),
        validator=lambda report: isinstance(report, dict) and report.get("ok") is True,
    )
    _smoke_call("version", lambda: jingni_version())
    _smoke_call("capabilities", lambda: jingni_capabilities(trade_mode))

    history = _smoke_call(
        "history 5 bars",
        lambda: jingni_history(trade_mode, context, SMOKE_CODE, "1d", 5),
    )
    _smoke_call(
        "field close offset=0",
        lambda: jingni_get_field(
            trade_mode, context, SMOKE_CODE, "1d", "close", offset=0
        ),
    )
    _smoke_call(
        "field close offset=1",
        lambda: jingni_get_field(
            trade_mode, context, SMOKE_CODE, "1d", "close", offset=1
        ),
    )
    _smoke_call(
        "history range 2024",
        lambda: jingni_get_history_range(
            trade_mode, context, SMOKE_CODE, "1d", "2024-01-01", "2024-12-31"
        ),
    )
    _smoke_call(
        "download history",
        lambda: jingni_download_history(
            trade_mode, context, [SMOKE_CODE], "1d", "2024-01-01", "2024-12-31"
        ),
    )
    instrument = _smoke_call(
        "instrument",
        lambda: jingni_get_instrument(trade_mode, context, SMOKE_CODE),
    )
    if isinstance(instrument, dict):
        print("[SMOKE] instrument keys={0}".format(sorted(instrument.keys())))

    _smoke_call(
        "stock status ST",
        lambda: jingni_get_stock_status(trade_mode, context, SMOKE_CODE, "ST"),
    )
    _smoke_call(
        "trading dates 2024-01",
        lambda: jingni_get_trading_dates(
            trade_mode, context, "2024-01-01", "2024-01-31"
        ),
    )
    _smoke_call(
        "is trading day",
        lambda: jingni_is_trading_day(
            trade_mode, context, datetime.date(2024, 1, 2)
        ),
    )
    _smoke_call(
        "is trading time",
        lambda: jingni_is_trading_time(
            trade_mode, context, datetime.datetime(2024, 1, 2, 10, 0)
        ),
    )
    if _smoke_is_backtest():
        _smoke_skip("run interval 3s", "PTrade run_interval is trading-only")
    else:
        _smoke_call(
            "run interval 3s",
            lambda: jingni_run_interval(_smoke_interval, 3, trade_mode, context),
        )
    if trade_mode == "ptrade":
        # PTrade 的 run_daily 只能在 initialize/before_trading_start 注册，
        # 这里已在 initialize 中完成；handle_data 阶段不再重复调用。
        pass
    else:
        _smoke_call(
            "schedule 09:31",
            lambda: jingni_schedule(
                _smoke_scheduled,
                "09:31",
                "1d",
                trade_mode=trade_mode,
                context_data=context,
            ),
            validator=lambda result: result is not None,
        )

    _smoke_call(
        "positions",
        lambda: jingni_get_positions(trade_mode, context),
    )
    _smoke_call(
        "account",
        lambda: jingni_get_account(trade_mode, context),
    )
    _smoke_call(
        "orders",
        lambda: jingni_get_orders(trade_mode, context),
    )
    _smoke_call(
        "trades",
        lambda: jingni_get_trades(trade_mode, context),
    )

    price = jingni_get_field(
        trade_mode, context, SMOKE_CODE, "1d", "close", offset=0
    )
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = 10.0
    if price <= 0:
        price = 10.0

    _smoke_call(
        "order dry-run",
        lambda: jingni_order_amount(
            trade_mode,
            context,
            SMOKE_CODE,
            100,
            price,
            dry_run=True,
            remark="smoke",
        ),
    )
    _smoke_call(
        "new stock dry-run",
        lambda: jingni_subscribe_new_stock(
            context, dry_run=True, trade_mode=trade_mode
        ),
    )
    _smoke_call(
        "new bond dry-run",
        lambda: jingni_subscribe_new_bond(
            context, dry_run=True, trade_mode=trade_mode
        ),
    )
    _smoke_call(
        "reverse repo dry-run",
        lambda: jingni_participate_reverse_repo(
            context, cash_ratio=0.1, dry_run=True, trade_mode=trade_mode
        ),
    )

    if SMOKE_REAL_ORDER:
        if _smoke_is_backtest():
            _smoke_skip("real order/cancel", "backtest does not verify real counter")
        else:
            print("[SMOKE][WARN] real order enabled: 100 shares, then cancel")
            ref = _smoke_call(
                "real order",
                lambda: jingni_order_amount(
                    trade_mode,
                    context,
                    SMOKE_CODE,
                    100,
                    price,
                    dry_run=False,
                    remark="smoke-real",
                ),
            )
            if ref:
                _smoke_call(
                    "cancel order",
                    lambda: jingni_cancel_order(trade_mode, context, ref),
                )
    else:
        _smoke_skip("real order/cancel", "SMOKE_REAL_ORDER=False")

    if history is not None:
        print("[SMOKE] history result: {0}".format(_smoke_value(history)))
    _smoke_summary("checks")
    print("=" * 64)


def initialize(context):
    global _JINGNI_RUNTIME
    try:
        set_universe([SMOKE_SYMBOL])
    except Exception:
        pass
    _JINGNI_RUNTIME = jingni_main(trade_mode, context)
    _smoke_call(
        "schedule 09:31",
        lambda: jingni_schedule(
            _smoke_scheduled, "09:31", "1d", trade_mode=trade_mode, context_data=context
        ),
        validator=lambda result: result is not None,
    )


def handle_data(context, data):
    _smoke_run(context)


def after_trading_end(context, data):
    if _SMOKE_DONE and _SMOKE_SUMMARY_READY:
        _smoke_summary("daily_end")
