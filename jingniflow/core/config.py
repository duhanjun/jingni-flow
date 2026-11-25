# -*- coding: utf-8 -*-
"""运行配置。"""


class RuntimeConfig(object):
    """一次策略运行的配置；默认值按 D7 的安全口径。"""

    def __init__(
        self,
        account_id=None,
        account_type="stock",
        dry_run=True,
        max_order_amount=100000,
        max_order_value=1000000.0,
        max_daily_orders=100,
        repeat_window_seconds=3,
        log_level="INFO",
        legacy=False,
        kill_switch=False,
    ):
        self.account_id = account_id
        self.account_type = account_type
        self.dry_run = bool(dry_run)
        self.max_order_amount = max_order_amount
        self.max_order_value = max_order_value
        self.max_daily_orders = max_daily_orders
        self.repeat_window_seconds = repeat_window_seconds
        self.log_level = log_level
        self.legacy = bool(legacy)
        self.kill_switch = bool(kill_switch)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def as_dict(self):
        return {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "dry_run": self.dry_run,
            "max_order_amount": self.max_order_amount,
            "max_order_value": self.max_order_value,
            "max_daily_orders": self.max_daily_orders,
            "repeat_window_seconds": self.repeat_window_seconds,
            "log_level": self.log_level,
            "legacy": self.legacy,
            "kill_switch": self.kill_switch,
        }
