"""Shared validation body for the three broker terminals.

This file is not pasted alone. `tools/build_validation.py` puts it after the
platform head and before the JingniFlow single-file tail.
"""

import time

_JINGNI_CONTEXT = None
_JINGNI_RUNTIME = None
_STARTED = False
_DONE = False
_WAITING_PRINTED = False
_WAIT_CANCEL_PRINTED = False
_ORDER_REF = None
_ORDER_TIME = 0.0
_ORDER_PRICE = 0.0
_ORDERS_BEFORE_COUNT = 0
_CANCEL_SENT = False
_CANCEL_TIME = 0.0
_PASS = 0
_FAIL = 0
_SKIP = 0


def _validation_stage():
    return globals().get("VALIDATION_STAGE", "dry_run")


def _validation_value(value):
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


def _validation_check(name, func, validator=None):
    global _PASS, _FAIL
    try:
        result = func()
        if validator is not None and not validator(result):
            raise AssertionError("result did not satisfy validator")
        _PASS += 1
        print("[VALIDATION][OK] {0}: {1}".format(name, _validation_value(result)))
        return result
    except Exception as exc:
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] {0}: {1}: {2}".format(
                name, type(exc).__name__, exc
            )
        )
        return None


def _validation_skip(name, reason):
    global _SKIP
    _SKIP += 1
    print("[VALIDATION][SKIP] {0}: {1}".format(name, reason))


def _validation_is_backtest():
    return bool(getattr(_JINGNI_RUNTIME, "is_backtest", False))


def _validation_is_trading_time(context):
    try:
        return bool(jingni_is_trading_time(trade_mode, context))
    except Exception as exc:
        print(
            "[VALIDATION][WARN] is_trading_time failed: {0}: {1}".format(
                type(exc).__name__, exc
            )
        )
        return False


def _validation_config():
    stage = _validation_stage()
    try:
        return RuntimeConfig(
            account_id=(globals().get("VALIDATION_ACCOUNT_ID") or None),
            dry_run=(stage == "dry_run"),
            max_order_amount=globals().get("VALIDATION_AMOUNT", 100),
            max_order_value=20000.0,
            max_daily_orders=2,
            repeat_window_seconds=10,
            log_level="INFO",
            kill_switch=False,
        )
    except Exception as exc:
        print(
            "[VALIDATION][WARN] RuntimeConfig unavailable: {0}: {1}".format(
                type(exc).__name__, exc
            )
        )
        return None


def _validation_order_count(value):
    if value is None:
        return 0
    try:
        return len(value)
    except Exception:
        return 0


def _validation_ref_id(ref):
    if ref is None:
        return None
    if isinstance(ref, dict):
        nested = ref.get("order_ref")
        if isinstance(nested, dict):
            ref = nested
        return (
            ref.get("id")
            or ref.get("platform_order_id")
            or ref.get("remark")
        )
    return str(ref)


def _validation_find_order(orders, ref):
    target = _validation_ref_id(ref)
    if target is None or orders is None:
        return None
    for order in orders:
        if not isinstance(order, dict):
            continue
        if str(order.get("platform_order_id")) == str(target):
            return order
        if str(_validation_ref_id(order)) == str(target):
            return order
        # QMT passorder 返回 None，适配器只能用投资备注生成占位 ref；
        # 柜台委托号是 m_strOrderSysID，必须再用 remark 匹配一次。
        if str(order.get("remark")) == str(target):
            return order
    # PTrade 可能出现返回的 order_id 与 get_orders() 的 order_id 口径
    # 不一致；QMT 的 remark 也可能被柜台留空。只有委托总数比验证前多
    # 恰好一笔时才允许按“代码 + 数量 + 价格”回退，避免误认旧委托。
    if trade_mode in ("qmt", "ptrade") and len(orders) == _ORDERS_BEFORE_COUNT + 1:
        matches = []
        for order in orders:
            if not isinstance(order, dict):
                continue
            if str(order.get("code")) != str(ref.get("code")):
                continue
            if str(order.get("amount")) != str(ref.get("amount")):
                continue
            try:
                if round(float(order.get("price")), 2) != round(
                    float(ref.get("price")), 2
                ):
                    continue
            except Exception:
                continue
            matches.append(order)
        if len(matches) == 1:
            return matches[0]
    return None


def _validation_cancel_delay():
    # 掘金仿真对未成交限价单的存活时间可能很短，等到 8 秒再撤会直接
    # 看到 EXPIRED；掘金必须在下一 tick 立刻尝试撤单。
    if trade_mode == "goldminer":
        return 0
    return globals().get("VALIDATION_CANCEL_DELAY", 8)


def _validation_merge_actual_ref(order):
    """把查到的真实柜台委托号回填到 _ORDER_REF。"""
    global _ORDER_REF
    if not isinstance(order, dict) or not isinstance(_ORDER_REF, dict):
        return
    actual = order.get("platform_order_id")
    if not actual:
        return
    updated = dict(_ORDER_REF)
    updated["platform_order_id"] = str(actual)
    nested = updated.get("order_ref")
    if isinstance(nested, dict):
        nested = dict(nested)
        nested["id"] = str(actual)
        updated["order_ref"] = nested
    _ORDER_REF = updated


def _validation_reconcile(context):
    _validation_check(
        "positions after", lambda: jingni_get_positions(trade_mode, context)
    )
    _validation_check(
        "trades after", lambda: jingni_get_trades(trade_mode, context)
    )


def _validation_summary(stage):
    global _DONE
    _DONE = True
    mode = "backtest" if _validation_is_backtest() else "sim/live"
    print(
        "[VALIDATION][SUMMARY] stage={0} platform={1} mode={2} pass={3} fail={4} skip={5}".format(
            stage, trade_mode, mode, _PASS, _FAIL, _SKIP
        )
    )
    if _FAIL == 0:
        print(
            "[VALIDATION][RESULT] {0}: ALL CHECKS PASSED; VALIDATION SUCCESS".format(
                stage
            )
        )
    else:
        print(
            "[VALIDATION][RESULT] {0}: VALIDATION FAILED; failed={1}".format(
                stage, _FAIL
            )
        )


def _validation_dry_run(context, before_orders):
    global _PASS, _FAIL
    ref = _validation_check(
        "order dry-run",
        lambda: jingni_order_amount(
            trade_mode,
            context,
            VALIDATION_CODE,
            globals().get("VALIDATION_AMOUNT", 100),
            10.0,
            dry_run=True,
            remark="validation-dry-run",
        ),
        validator=lambda result: result is None,
    )
    try:
        after_orders = jingni_get_orders(trade_mode, context, include_finished=True)
    except Exception as exc:
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] orders after dry-run: {0}: {1}".format(
                type(exc).__name__, exc
            )
        )
    else:
        if _validation_order_count(after_orders) == _validation_order_count(before_orders):
            _PASS += 1
            print("[VALIDATION][OK] dry-run added no order")
        else:
            _FAIL += 1
            print(
                "[VALIDATION][FAIL] dry-run added orders: before={0} after={1}".format(
                    _validation_order_count(before_orders),
                    _validation_order_count(after_orders),
                )
            )
    if ref is not None:
        _FAIL += 1
        print("[VALIDATION][FAIL] dry-run returned an order reference")
    _validation_summary("dry_run")


def _validation_instrument_info(instrument):
    """兼容 instrument 平台返回 ``{code: fields}`` 和 ``fields`` 两种形状。"""
    if not isinstance(instrument, dict):
        return {}
    nested = instrument.get(VALIDATION_CODE)
    if isinstance(nested, dict):
        return nested
    return instrument


def _validation_price_is_plausible(price):
    try:
        price = float(price)
    except Exception:
        return False
    if price <= 0:
        return False
    if price != price:
        return False
    # A 股现货没有 5000 元以上的价格；该上限主要拦截 QMT 的 9999.99 哨兵值。
    if price >= 5000:
        return False
    return True


def _validation_price_is_sane(price, instrument):
    if not _validation_price_is_plausible(price):
        return False
    info = _validation_instrument_info(instrument)
    limit_up = info.get("limit_up")
    limit_down = info.get("limit_down")
    try:
        if limit_up is not None and float(price) > float(limit_up) * 1.01:
            return False
    except Exception:
        pass
    try:
        if limit_down is not None and float(price) < float(limit_down) * 0.99:
            return False
    except Exception:
        pass
    return True


def _validation_enrich_limits(context, instrument):
    """PTrade 的 get_instrument 不带涨跌停；从快照/日线补。"""
    info = _validation_instrument_info(instrument)
    if not isinstance(info, dict):
        return
    if info.get("limit_down") is not None and info.get("limit_up") is not None:
        return
    if trade_mode == "ptrade":
        try:
            tick = jingni_get_tick(
                trade_mode,
                context,
                [VALIDATION_CODE],
                ["close", "up_px", "down_px", "preclose_px"],
            )
            values = tick.get(VALIDATION_CODE) or {}
            print(
                "[VALIDATION][PRICE][PTRADE] snapshot close={0} up_px={1} "
                "down_px={2} preclose_px={3}".format(
                    values.get("close"),
                    values.get("up_px"),
                    values.get("down_px"),
                    values.get("preclose_px"),
                )
            )
            if info.get("limit_up") is None:
                info["limit_up"] = values.get("up_px")
            if info.get("limit_down") is None:
                info["limit_down"] = values.get("down_px")
            if info.get("pre_close") is None:
                info["pre_close"] = values.get("preclose_px")
        except Exception:
            pass
    if info.get("limit_down") is not None and info.get("limit_up") is not None:
        return
    try:
        frame = jingni_history(
            trade_mode,
            context,
            VALIDATION_CODE,
            "1d",
            5,
            fields=["close", "high_limit", "low_limit", "preclose"],
            adjust="none",
        )
        for field, key in (
            ("high_limit", "limit_up"),
            ("low_limit", "limit_down"),
            ("preclose", "pre_close"),
        ):
            if info.get(key) is not None:
                continue
            try:
                series = frame[field].dropna()
                if len(series):
                    info[key] = float(series.iloc[-1])
            except Exception:
                pass
        if info.get("limit_down") is None and info.get("pre_close") is not None:
            info["limit_down"] = round(float(info["pre_close"]) * 0.9, 2)
        if info.get("limit_up") is None and info.get("pre_close") is not None:
            info["limit_up"] = round(float(info["pre_close"]) * 1.1, 2)
    except Exception as exc:
        print(
            "[VALIDATION][PRICE][WARN] limit enrich failed: {0}: {1}".format(
                type(exc).__name__, exc
            )
        )


def _validation_reference_price(context, instrument, history):
    """优先用历史收盘价，实时 tick 异常时回退到前一 bar。

    QMT 盘中最后一根日线可能返回 9999.99 哨兵值，因此从最后一根开始
    逐根向前找，而不是只取 iloc[-1]；仍无有效价时再用 1 分钟线兜底。
    """
    candidates = []

    def _collect(frame):
        try:
            if frame is not None and "close" in frame:
                for value in frame["close"].dropna().iloc[::-1].tolist():
                    candidates.append(value)
        except Exception:
            pass

    def _first_plausible():
        for value in candidates:
            if _validation_price_is_plausible(value):
                return float(value)
        return 0.0

    _collect(history)
    price = _first_plausible()
    if price > 0:
        return price
    try:
        minute = jingni_history(
            trade_mode, context, VALIDATION_CODE, "1m", 5, adjust="none"
        )
        _collect(minute)
        price = _first_plausible()
        if price > 0:
            return price
    except Exception:
        pass
    for offset in (1, 0):
        try:
            candidates.append(
                jingni_get_field(
                    trade_mode, context, VALIDATION_CODE, "1d", "close", offset=offset
                )
            )
        except Exception:
            pass
    price = _first_plausible()
    if price > 0:
        return price
    info = _validation_instrument_info(instrument)
    print(
        "[VALIDATION][PRICE][WARN] no valid close; candidates={0} "
        "limit_down={1} limit_up={2}".format(
            candidates[:6], info.get("limit_down"), info.get("limit_up")
        )
    )
    return 0.0


def _validation_place_order(context, instrument, history):
    global _ORDER_REF, _ORDER_TIME, _ORDER_PRICE, _FAIL
    global _CANCEL_SENT, _CANCEL_TIME, _PASS
    last = _validation_reference_price(context, instrument, history)
    if last <= 0:
        _FAIL += 1
        print("[VALIDATION][FAIL] last price is unavailable or outside limit band")
        _validation_summary("order_cancel")
        return

    price = round(last * 0.98, 2)
    info = _validation_instrument_info(instrument)
    floor = info.get("limit_down")
    cap = info.get("limit_up")
    try:
        floor = None if floor is None else float(floor)
        cap = None if cap is None else float(cap)
    except Exception:
        floor = None
        cap = None
    if floor is not None and price < floor:
        price = floor
    if cap is not None and price > cap:
        # 参考价已经超出涨跌停时，宁可挂跌停价，避免 PTrade 直接以
        # “超过涨跌停范围”拒单。
        price = floor if floor is not None else cap
    if trade_mode == "ptrade" and floor is not None:
        # 实机日志里 PTrade 快照/日线的 low_limit=9.78，但柜台下单校验
        # 实际用的是 p_up=9.74/p_down=7.97。9.78*0.995=9.73，落在
        # 柜台 7.97~9.74 区间内，也仍高于 9.78*0.99 的本地 sanity 下限。
        low_ball = round(floor * 0.995, 2)
        if low_ball > 0 and price > low_ball:
            price = low_ball
        print(
            "[VALIDATION][PRICE][PTRADE] snapshot_floor={0} low_ball={1}; "
            "counter p_up/p_down may differ".format(floor, low_ball)
        )
    elif trade_mode in ("goldminer", "qmt") and floor is not None:
        # 仿真柜台可能把 2% 的低挂价当成可成交价；挂到跌停价上方
        # 一个最小价位，确保是明显的非可成交买单，撤单才有意义。
        low_ball = round(floor + 0.01, 2)
        if low_ball > 0 and price > low_ball:
            price = low_ball
        print(
            "[VALIDATION][PRICE][LOW] limit_down={0} low_ball={1}".format(
                floor, low_ball
            )
        )
    if price <= 0 or not _validation_price_is_sane(price, instrument):
        _FAIL += 1
        print("[VALIDATION][FAIL] invalid limit price: {0}".format(price))
        _validation_summary("order_cancel")
        return
    print(
        "[VALIDATION][PRICE] last={0} limit={1} limit_down={2} limit_up={3}".format(
            last, price, info.get("limit_down"), info.get("limit_up")
        )
    )

    remark = "validation-{0}".format(time.strftime("%H%M%S"))
    ref = _validation_check(
        "place 100-share limit buy",
        lambda: jingni_order_amount(
            trade_mode,
            context,
            VALIDATION_CODE,
            100,
            price,
            dry_run=False,
            remark=remark,
        ),
        validator=lambda result: result is not None,
    )
    if ref is None:
        _validation_summary("order_cancel")
        return

    _ORDER_REF = ref
    _ORDER_TIME = time.time()
    _ORDER_PRICE = price
    print(
        "[VALIDATION][WAIT] order placed; cancel after {0}s; ref={1} price={2}".format(
            _validation_cancel_delay(), _validation_ref_id(ref), price
        )
    )
    # 掘金仿真的未成交限价单可能在数秒内自动进入 EXPIRED；这里下单后
    # 立即尝试一次撤单，失败则交给下一 tick 重试。
    if trade_mode == "goldminer":
        try:
            if jingni_cancel_order(trade_mode, context, _ORDER_REF) is True:
                _CANCEL_SENT = True
                _CANCEL_TIME = time.time()
                _PASS += 1
                print("[VALIDATION][OK] cancel order: True (immediate)")
        except Exception as exc:
            print(
                "[VALIDATION][WAIT] immediate cancel failed: {0}: {1}".format(
                    type(exc).__name__, exc
                )
            )


def _validation_drive_order(context):
    global _CANCEL_SENT, _CANCEL_TIME, _WAIT_CANCEL_PRINTED, _PASS, _FAIL
    if _ORDER_REF is None:
        return
    now = time.time()
    if not _CANCEL_SENT:
        if now - _ORDER_TIME < _validation_cancel_delay():
            if not _WAIT_CANCEL_PRINTED:
                _WAIT_CANCEL_PRINTED = True
                print("[VALIDATION][WAIT] waiting before cancel")
            return
        # 先确认委托已经出现在委托列表里，再撤单。QMT 的 passorder 不返回
        # 柜台委托号，必须先把 remark 解析成 m_strOrderSysID；否则撤单
        # 一定失败，随后只会看到 EXPIRED。
        try:
            orders = jingni_get_orders(trade_mode, context, include_finished=True)
        except Exception as exc:
            _FAIL += 1
            print(
                "[VALIDATION][FAIL] orders before cancel: {0}: {1}".format(
                    type(exc).__name__, exc
                )
            )
            _validation_summary("order_cancel")
            return
        order = _validation_find_order(orders, _ORDER_REF)
        if order is None:
            if trade_mode == "qmt" and not _CANCEL_SENT:
                # QMT 仿真撮合快于委托列表回写；先用备注向
                # get_last_order_id / cancel 抢一次撤单窗口。
                try:
                    accepted = jingni_cancel_order(trade_mode, context, _ORDER_REF)
                except Exception:
                    accepted = False
                if accepted is True:
                    _CANCEL_SENT = True
                    _CANCEL_TIME = now
                    _PASS += 1
                    print("[VALIDATION][OK] cancel order: True (before list visible)")
                    return
            if now - _ORDER_TIME >= globals().get(
                "VALIDATION_ORDER_TIMEOUT", 20
            ):
                _FAIL += 1
                if trade_mode == "qmt":
                    print(
                        "[VALIDATION][FAIL] order never appeared after placement; "
                        "QMT is likely in signal-only simulation mode (日志 "
                        "[trade]start simulation mode). Switch 运行模式 to 实盘 "
                        "while keeping the simulation account"
                    )
                else:
                    print(
                        "[VALIDATION][FAIL] order not visible before cancel"
                    )
                _validation_summary("order_cancel")
            else:
                print("[VALIDATION][WAIT] order not visible before cancel; waiting")
            return
        _validation_merge_actual_ref(order)
        status = order.get("status")
        if status in ("FILLED", "PARTIAL", "REJECTED", "EXPIRED"):
            print(
                "[VALIDATION][ORDER] id={0} status={1} code={2} amount={3} price={4}".format(
                    _validation_ref_id(_ORDER_REF),
                    status,
                    order.get("code"),
                    order.get("amount"),
                    order.get("price"),
                )
            )
            _FAIL += 1
            print(
                "[VALIDATION][FAIL] order {0} before cancel; cancel was not "
                "confirmed as CANCELED".format(status)
            )
            _validation_reconcile(context)
            _validation_summary("order_cancel")
            return
        try:
            accepted = jingni_cancel_order(trade_mode, context, _ORDER_REF)
        except Exception as exc:
            accepted = False
            print(
                "[VALIDATION][WAIT] cancel request error: {0}: {1}".format(
                    type(exc).__name__, exc
                )
            )
        if accepted is True:
            _CANCEL_SENT = True
            _CANCEL_TIME = now
            _PASS += 1
            print("[VALIDATION][OK] cancel order: True")
        else:
            print("[VALIDATION][WAIT] cancel request not accepted; retry next tick")
            if now - _ORDER_TIME >= globals().get(
                "VALIDATION_ORDER_TIMEOUT", 20
            ):
                _FAIL += 1
                print("[VALIDATION][FAIL] cancel request was never accepted")
                _validation_summary("order_cancel")
        return

    if now - _CANCEL_TIME < 3:
        return

    try:
        orders = jingni_get_orders(trade_mode, context, include_finished=True)
    except Exception as exc:
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] orders after cancel: {0}: {1}".format(
                type(exc).__name__, exc
            )
        )
        _validation_summary("order_cancel")
        return

    order = _validation_find_order(orders, _ORDER_REF)
    if order is None:
        if now - _CANCEL_TIME >= globals().get("VALIDATION_CANCEL_TIMEOUT", 25):
            _FAIL += 1
            print("[VALIDATION][FAIL] order not found after cancel")
            _validation_summary("order_cancel")
        else:
            print("[VALIDATION][WAIT] order not visible yet")
        return

    status = order.get("status")
    print(
        "[VALIDATION][ORDER] id={0} status={1} code={2} amount={3} price={4}".format(
            _validation_ref_id(_ORDER_REF),
            status,
            order.get("code"),
            order.get("amount"),
            order.get("price"),
        )
    )
    if status == "CANCELED":
        _PASS += 1
        print("[VALIDATION][OK] order final status is CANCELED")
        _validation_reconcile(context)
        _validation_summary("order_cancel")
        return
    if status in ("FILLED", "PARTIAL"):
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] order {0}; do not sell on the same day; record it".format(
                status
            )
        )
        _validation_reconcile(context)
        _validation_summary("order_cancel")
        return
    if status in ("REJECTED", "EXPIRED"):
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] order {0}; cancel was not confirmed as CANCELED".format(
                status
            )
        )
        _validation_reconcile(context)
        _validation_summary("order_cancel")
        return
    if now - _CANCEL_TIME >= globals().get("VALIDATION_CANCEL_TIMEOUT", 25):
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] cancel not confirmed; status={0}".format(status)
        )
        _validation_summary("order_cancel")
    else:
        print("[VALIDATION][WAIT] cancel pending; status={0}".format(status))


def _validation_bootstrap(context):
    global _WAITING_PRINTED, _FAIL, _ORDERS_BEFORE_COUNT
    _WAITING_PRINTED = False
    print("=" * 64)
    print(
        "[VALIDATION] start platform={0} stage={1} code={2}".format(
            trade_mode, _validation_stage(), VALIDATION_CODE
        )
    )
    print(
        "[VALIDATION][SAFETY] stage={0}; dry_run places no order; "
        "order_cancel places one 100-share limit buy and cancels it".format(
            _validation_stage()
        )
    )
    _validation_check(
        "doctor",
        lambda: jingni_doctor(trade_mode, context, verbose=True),
        validator=lambda report: isinstance(report, dict) and report.get("ok") is True,
    )
    _validation_check(
        "capabilities", lambda: jingni_capabilities(trade_mode)
    )
    _validation_check(
        "account strict",
        lambda: jingni_get_account(trade_mode, context, strict=True),
    )
    _validation_check(
        "positions",
        lambda: jingni_get_positions(trade_mode, context, strict=True),
    )
    try:
        before_orders = jingni_get_orders(trade_mode, context, include_finished=True)
    except Exception as exc:
        print("[VALIDATION][WARN] order list unavailable: {0}".format(exc))
        before_orders = _validation_check(
            "orders before",
            lambda: jingni_get_orders(trade_mode, context, include_finished=True),
        )
    else:
        print("[VALIDATION][OK] orders before: {0}".format(_validation_value(before_orders)))
    try:
        _ORDERS_BEFORE_COUNT = len(before_orders)
    except Exception:
        _ORDERS_BEFORE_COUNT = 0
    history = _validation_check(
        "history 5 bars",
        lambda: jingni_history(
            trade_mode, context, VALIDATION_CODE, "1d", 5, adjust="none"
        ),
    )
    instrument = _validation_check(
        "instrument",
        lambda: jingni_get_instrument(trade_mode, context, VALIDATION_CODE),
    )
    _validation_enrich_limits(context, instrument)
    stage = _validation_stage()
    if stage == "dry_run":
        _validation_dry_run(context, before_orders)
    elif stage == "order_cancel":
        if _validation_is_backtest():
            _validation_skip("order/cancel", "backtest has no counter")
            _validation_summary("backtest_skip")
            return
        _validation_place_order(context, instrument, history)
    else:
        _validation_skip("unknown stage", stage)
        _FAIL += 1
        print(
            "[VALIDATION][FAIL] unknown stage {0}; expected dry_run or order_cancel".format(
                stage
            )
        )
        _validation_summary("unknown_stage")


def _validation_tick(context):
    global _STARTED, _WAITING_PRINTED
    if _DONE:
        return
    if _JINGNI_RUNTIME is None:
        return
    if not _STARTED:
        if not _validation_is_trading_time(context):
            if not _WAITING_PRINTED:
                _WAITING_PRINTED = True
                print("[VALIDATION][WAIT] outside continuous trading; waiting")
            return
        _STARTED = True
        _validation_bootstrap(context)
        return
    if _validation_stage() == "order_cancel":
        _validation_drive_order(context)


def _validation_strategy(strategy_trade_mode, context_data):
    global _JINGNI_CONTEXT
    _JINGNI_CONTEXT = context_data
    _validation_tick(context_data)


def _validation_interval(*args, **kwargs):
    if _JINGNI_CONTEXT is None:
        return
    _validation_tick(_JINGNI_CONTEXT)


def _validation_finish_if_needed():
    global _FAIL
    if not _STARTED or _DONE:
        return
    _FAIL += 1
    print("[VALIDATION][RESULT] incomplete at platform end")
    _validation_summary("platform_end")
