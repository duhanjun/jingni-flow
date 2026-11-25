# -*- coding: utf-8 -*-
"""v0.1.x 兼容层：旧函数名、旧签名、旧返回形态。"""

from ..api.account import (
    jingni_get_account,
    jingni_get_positions,
    jingni_portfolio,
)
from ..api.calendar import (
    jingni_get_trading_dates,
    jingni_is_trading_day,
    jingni_is_trading_time,
)
from ..api.diagnose import jingni_capabilities, jingni_doctor, jingni_version
from ..api.instrument import jingni_get_instrument, jingni_get_stock_status
from ..api.ipo import jingni_subscribe_new_bond, jingni_subscribe_new_stock
from ..api.lifecycle import (
    jingni_after_trading_end,
    jingni_before_trading_start,
    jingni_get_strategy,
    jingni_handle_data,
    jingni_main,
    jingni_set_strategy,
    jingni_trade_strategy,
)
from ..api.market import (
    jingni_download_history,
    jingni_get_current,
    jingni_get_field,
    jingni_get_field_n,
    jingni_get_history,
    jingni_get_history_range,
    jingni_get_tick,
    jingni_history,
    jingni_tick,
)
from ..api.repo import jingni_participate_reverse_repo
from ..api.risk import (
    jingni_calc_max_buy,
    jingni_calc_max_sell,
    jingni_check_order,
    jingni_kill_switch,
    jingni_log,
    jingni_set_risk,
)
from ..api.runtime import (
    jingni_now,
    jingni_offset_trade_date,
    jingni_run_interval,
    jingni_schedule,
    jingni_setup,
    jingni_trading_dates,
    jingni_trading_times,
    jingni_wall_now,
)
from ..api.trade import (
    jingni_cancel_all,
    jingni_cancel_order,
    jingni_close_all,
    jingni_get_orders,
    jingni_get_trades,
    jingni_order_amount,
    jingni_order_market,
    jingni_order_target_amount,
    jingni_order_target_value,
    jingni_order_value,
)
from ..core.config import RuntimeConfig
from ..core.contract import normalize_code
from ..core.runtime import get_default_mode, normalize_platform

trade_mode = globals().get("trade_mode", "软件名称")


def jingni_map_security_code(security_code, trade_mode=None):
    """旧接口：按平台转换证券代码；非法输入抛 ValidationError。"""
    mode = normalize_platform(trade_mode) or get_default_mode()
    return normalize_code(security_code, mode)


__all__ = [
    "RuntimeConfig",
    "trade_mode",
    "jingni_trading_dates",
    "jingni_trading_times",
    "jingni_portfolio",
    "jingni_map_security_code",
    "jingni_get_current",
    "jingni_get_history",
    "jingni_history",
    "jingni_get_field",
    "jingni_get_field_n",
    "jingni_get_tick",
    "jingni_tick",
    "jingni_get_account",
    "jingni_get_positions",
    "jingni_get_instrument",
    "jingni_get_stock_status",
    "jingni_get_trading_dates",
    "jingni_is_trading_day",
    "jingni_is_trading_time",
    "jingni_download_history",
    "jingni_get_history_range",
    "jingni_order_amount",
    "jingni_order_value",
    "jingni_order_market",
    "jingni_order_target_amount",
    "jingni_order_target_value",
    "jingni_cancel_order",
    "jingni_cancel_all",
    "jingni_close_all",
    "jingni_get_orders",
    "jingni_get_trades",
    "jingni_subscribe_new_stock",
    "jingni_subscribe_new_bond",
    "jingni_participate_reverse_repo",
    "jingni_set_risk",
    "jingni_check_order",
    "jingni_calc_max_buy",
    "jingni_calc_max_sell",
    "jingni_kill_switch",
    "jingni_log",
    "jingni_trade_strategy",
    "jingni_set_strategy",
    "jingni_get_strategy",
    "jingni_before_trading_start",
    "jingni_handle_data",
    "jingni_after_trading_end",
    "jingni_main",
    "jingni_setup",
    "jingni_now",
    "jingni_wall_now",
    "jingni_offset_trade_date",
    "jingni_run_interval",
    "jingni_schedule",
    "jingni_version",
    "jingni_capabilities",
    "jingni_doctor",
]
