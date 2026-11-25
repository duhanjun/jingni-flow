# -*- coding: utf-8 -*-
"""掘金策略模板：把本文件放到策略目录，或把 dist 单文件粘贴到策略末尾。"""

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：将 dist/jingniflow_single.py 全文粘贴到本文件末尾即可。
    pass


def my_strategy(trade_mode, context_data):
    """在这里写信号、下单和撤单逻辑。"""
    # 示例：先读行情，再调用 jingni_order_amount(..., dry_run=True)。
    pass


def init(context):
    jingni_main("goldminer", context, strategy=my_strategy)


def on_bar(context, bars):
    jingni_handle_data("goldminer", context)
