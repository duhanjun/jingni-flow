# encoding: utf-8

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：把 dist/jingniflow_single.py 粘贴到本文件末尾。
    pass

trade_mode = "ptrade"


def my_strategy(trade_mode, context_data):
    # TODO: 在这里读行情、算信号、调用 jingni_order_amount(..., dry_run=True)。
    pass


def initialize(context):
    jingni_main(trade_mode, context, strategy=my_strategy)
    # 打新/新债/逆回购示例：默认 dry_run，只打印不委托。
    # run_daily(context, jingni_subscribe_new_stock, time="10:00")
    # run_daily(context, jingni_subscribe_new_bond, time="10:10")
    # run_daily(context, jingni_participate_reverse_repo, time="14:50")


def handle_data(context, data):
    jingni_handle_data(trade_mode, context)


###################################
# 以下为JingniFlow量化交易系统代码#
# 将 dist/jingniflow_single.py 的代码复制到尾部#
###################################
