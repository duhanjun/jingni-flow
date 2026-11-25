# -*- coding: utf-8 -*-
"""版本、能力矩阵与启动自检。"""

from ..adapters import get_adapter
from ..core.runtime import (
    get_default_mode,
    normalize_platform,
    python_version_text,
    resolve_context,
)
from ..version import __version__


# 能力矩阵只描述“JingniFlow 已实现并承诺的统一语义”，不是对平台全部
# 函数的复刻。level: full / degraded / unsupported；degraded 表示有降级
# 或字段仍待实机核对。
_CAPABILITIES = {
    "market.history": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": {
            "goldminer": "history_n；分钟线边界待实测",
            "qmt": "get_market_data_ex；count/end_time 边界待实测",
            "ptrade": "get_history；时点与复权参数待实测",
        },
    },
    "market.tick": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": {
            "goldminer": "current 快照",
            "qmt": "get_full_tick",
            "ptrade": "get_snapshot；字段形态待实测",
        },
    },
    "trade.order_amount": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "统一 OrderRef + 风控；成交状态待实机核对",
    },
    "trade.order_value": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "按金额换算数量；整手与风控复用 order_amount",
    },
    "trade.order_target": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "目标持仓差额引擎；在途委托已计入",
    },
    "trade.order_market": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": {
            "goldminer": "order_type=Market；交易所行为待实测",
            "qmt": "沪市 prType=42、深市 prType=5；待实测",
            "ptrade": "order_market 失败时回退 order；类型待实测",
        },
    },
    "trade.cancel": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "degraded", "ptrade": "full"},
        "notes": {
            "goldminer": "order_cancel / order_cancel_all",
            "qmt": "cancel 签名与委托号字段待实测",
            "ptrade": "cancel_order",
        },
    },
    "trade.query": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": "订单/成交字段为尽力映射，待实机核对",
    },
    "account.unified": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "统一账户/持仓字段；柜台口径待实机核对",
    },
    "risk": {
        "phase": 1,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "kill switch/限额/重复窗口；默认 dry_run",
    },
    "ipo.stock": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": {
            "goldminer": "ipo_get_instruments / ipo_buy",
            "qmt": "get_ipo_data + passorder；参数待实测",
            "ptrade": "ipo_stocks_order；返回结构待实测",
        },
    },
    "ipo.bond": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": {
            "goldminer": "ipo_get_instruments / ipo_buy",
            "qmt": "get_ipo_data + passorder；参数待实测",
            "ptrade": "ipo_stocks_order；返回结构待实测",
        },
    },
    "repo.reverse": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": {
            "goldminer": "按金额下单；逆回购可卖量已跳过",
            "qmt": "passorder 参数待实测",
            "ptrade": "order/order_market 行为待实测",
        },
    },
    "schedule": {
        "phase": 1,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "full",
        },
        "notes": {
            "goldminer": "timer 回测不生效",
            "qmt": "run_time 需要全局函数名，回测不生效",
            "ptrade": "run_daily / run_interval",
        },
    },
    "market.history_range": {
        "phase": 2,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": {
            "goldminer": "history 起止时间；分钟线边界待实测",
            "qmt": "get_market_data_ex(count=-1)；边界待实测",
            "ptrade": "get_price 起止日期；多股票返回结构待实测",
        },
    },
    "data.download": {
        "phase": 2,
        "levels": {
            "goldminer": "unsupported",
            "qmt": "degraded",
            "ptrade": "unsupported",
        },
        "notes": {
            "goldminer": "无本地下载接口，函数为空操作",
            "qmt": "download_history_data；周期降级规则待实测",
            "ptrade": "服务端按需提供，函数为空操作",
        },
    },
    "instrument.meta": {
        "phase": 2,
        "levels": {
            "goldminer": "degraded",
            "qmt": "full",
            "ptrade": "degraded",
        },
        "notes": {
            "goldminer": "get_instruments 失败时降级 get_symbol_infos",
            "qmt": "get_instrument_detail(iscomplete=True)",
            "ptrade": "get_stock_info 仅原生提供名称/上市/退市日期",
        },
    },
    "instrument.status": {
        "phase": 2,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "full",
        },
        "notes": {
            "goldminer": "由标的详情推导，无法判断返回 None",
            "qmt": "由 IsST/IsTrading/ExpireDate 推导",
            "ptrade": "原生 get_stock_status",
        },
    },
    "calendar.trading_dates": {
        "phase": 2,
        "levels": {
            "goldminer": "degraded",
            "qmt": "full",
            "ptrade": "full",
        },
        "notes": {
            "goldminer": "get_trading_dates_by_year，失败降级旧接口",
            "qmt": "get_trading_dates，count 必须大于 0",
            "ptrade": "get_trade_days",
        },
    },
    "calendar.trading_day": {
        "phase": 2,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "degraded",
        },
        "notes": "平台日历不可用时按工作日降级，无法识别节假日",
    },
    "calendar.trading_time": {
        "phase": 2,
        "levels": {"goldminer": "full", "qmt": "full", "ptrade": "full"},
        "notes": "本地判断连续竞价；include_auction 仅覆盖开盘集合竞价",
    },
    "schedule.interval": {
        "phase": 2,
        "levels": {
            "goldminer": "degraded",
            "qmt": "degraded",
            "ptrade": "full",
        },
        "notes": {
            "goldminer": "timer，秒转毫秒，回测不生效",
            "qmt": "run_time 需要全局函数名，回测不生效",
            "ptrade": "run_interval 最小 3 秒",
        },
    },
}

_PHASE2_FEATURES = (
    "market.history_range",
    "data.download",
    "instrument.meta",
    "instrument.status",
    "calendar.trading_dates",
    "calendar.trading_day",
    "calendar.trading_time",
    "schedule.interval",
)


def _platform_name(trade_mode):
    return normalize_platform(trade_mode or get_default_mode()) or str(
        trade_mode or get_default_mode()
    )


def jingni_version():
    """打印并返回当前版本号。"""
    info = {
        "version": __version__,
        "python": python_version_text(),
        "platform": _platform_name(None),
    }
    print("[JINGNI] version={version} python={python} platform={platform}".format(**info))
    return __version__


def jingni_capabilities(trade_mode=None):
    """返回当前平台的能力矩阵。

    ``features`` 保留 ``level/notes`` 兼容字段，并新增 ``phase`` 与
    ``platform_levels``，便于策略或诊断工具按平台判断支持级别。
    """
    platform = _platform_name(trade_mode)
    features = {}
    for name, spec in _CAPABILITIES.items():
        levels = spec["levels"]
        notes = spec["notes"]
        level = levels.get(platform, "unsupported")
        if isinstance(notes, dict):
            note = notes.get(platform, "该平台未声明此能力")
        else:
            note = notes
        features[name] = {
            "phase": spec["phase"],
            "level": level,
            "notes": note,
            "platform_levels": dict(levels),
        }
    return {
        "platform": platform,
        "version": __version__,
        "python": python_version_text(),
        "features": features,
    }


def _check(name, status, message):
    return {"name": name, "status": status, "message": message}


def _positive_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def jingni_doctor(trade_mode=None, context_data=None, config=None, verbose=True):
    """启动自检：检查版本、平台、配置和 Phase 2 能力是否齐全。

    只做静态/配置检查，不主动调用柜台或行情接口；返回结构化报告，
    ``ok=False`` 表示存在必须处理的错误。
    """
    checks = []
    try:
        context = resolve_context(trade_mode, context_data, config=config)
        platform = normalize_platform(context.platform) or str(context.platform)
        effective_config = context.config
    except Exception as exc:
        platform = _platform_name(trade_mode)
        effective_config = config
        checks.append(_check("context", "error", str(exc)))

    python_text = python_version_text()
    if python_text == "unknown":
        checks.append(_check("python", "warn", "Python version is unavailable"))
    else:
        checks.append(_check("python", "ok", python_text))
    if platform == "qmt" and python_text != "unknown" and not python_text.startswith("3.6"):
        checks.append(
            _check(
                "qmt_python",
                "warn",
                "QMT 内置解释器通常为 Python 3.6；当前 {0} 仅适合本地开发/回测".format(
                    python_text
                ),
            )
        )

    if platform in ("goldminer", "qmt", "ptrade"):
        checks.append(_check("platform", "ok", platform))
        try:
            get_adapter(platform, context_data, config=config)
            checks.append(_check("adapter", "ok", "adapter loaded"))
        except Exception as exc:
            checks.append(_check("adapter", "error", str(exc)))
    else:
        checks.append(_check("platform", "error", "unsupported platform: {0}".format(platform)))

    if effective_config is None:
        checks.append(_check("config", "warn", "RuntimeConfig is unavailable"))
    else:
        if effective_config.dry_run:
            checks.append(_check("dry_run", "ok", "dry_run enabled"))
        else:
            checks.append(
                _check("dry_run", "warn", "dry_run disabled; real orders are enabled")
            )
        if effective_config.kill_switch:
            checks.append(
                _check("kill_switch", "warn", "kill switch is ON; orders will be blocked")
            )
        else:
            checks.append(_check("kill_switch", "ok", "kill switch is OFF"))
        for field in ("max_order_amount", "max_order_value", "max_daily_orders"):
            value = getattr(effective_config, field, None)
            if _positive_number(value):
                checks.append(_check(field, "ok", str(value)))
            else:
                checks.append(
                    _check(field, "error", "must be a positive number: {0}".format(value))
                )
        repeat = getattr(effective_config, "repeat_window_seconds", None)
        if isinstance(repeat, (int, float)) and not isinstance(repeat, bool) and repeat >= 0:
            checks.append(_check("repeat_window_seconds", "ok", str(repeat)))
        else:
            checks.append(
                _check(
                    "repeat_window_seconds",
                    "error",
                    "must be a non-negative number: {0}".format(repeat),
                )
            )

    if platform == "qmt":
        try:
            account = context.account_id()
        except Exception:
            account = None
        if account:
            checks.append(_check("account", "ok", "configured"))
        else:
            checks.append(
                _check(
                    "account",
                    "warn",
                    "QMT account_id is not configured; "
                    "backtest queries return empty, live orders will fail",
                )
            )

    capabilities = jingni_capabilities(platform)
    missing = [
        name for name in _PHASE2_FEATURES
        if name not in capabilities["features"]
    ]
    if missing:
        checks.append(
            _check("phase2_features", "error", "missing: {0}".format(",".join(missing)))
        )
    else:
        checks.append(
            _check(
                "phase2_features",
                "ok",
                "{0} features registered".format(len(_PHASE2_FEATURES)),
            )
        )

    errors = [item for item in checks if item["status"] == "error"]
    warnings = [item for item in checks if item["status"] == "warn"]
    report = {
        "ok": not errors,
        "platform": platform,
        "version": __version__,
        "python": python_text,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "capabilities": capabilities,
    }
    if verbose:
        for item in checks:
            print(
                "[JINGNI_DOCTOR] {status} {name}: {message}".format(**item)
            )
        print(
            "[JINGNI_DOCTOR] {result} errors={errors} warnings={warnings}".format(
                result="OK" if report["ok"] else "ATTENTION",
                errors=len(errors),
                warnings=len(warnings),
            )
        )
    return report
