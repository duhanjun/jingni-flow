# -*- coding: utf-8 -*-
"""PTrade 策略模板：PTrade 由平台事件驱动，不要自建循环。"""

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：将 dist/jingniflow_single.py 全文粘贴到本文件末尾即可。
    pass


def my_strategy(trade_mode, context_data):
    """在这里写信号、下单和撤单逻辑。"""
    # 示例：先读行情，再调用 jingni_order_amount(..., dry_run=True)。
    pass


def initialize(context):
    jingni_main("ptrade", context, strategy=my_strategy)


def handle_data(context, data):
    jingni_handle_data("ptrade", context)
