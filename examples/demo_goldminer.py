# coding=utf-8
from __future__ import print_function, absolute_import

from gm.api import *

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：把 dist/jingniflow_single.py 粘贴到本文件末尾。
    pass

trade_mode = "goldminer"


def my_strategy(trade_mode, context_data):
    # TODO: 在这里读行情、算信号、调用 jingni_order_amount(..., dry_run=True)。
    pass


def init(context):
    subscribe(symbols="SHSE.600000", frequency="1d")
    jingni_main(trade_mode, context, strategy=my_strategy)
    # 打新/新债/逆回购示例：默认 dry_run，只打印不委托；确认后去掉 dry_run=False。
    # jingni_subscribe_new_stock(context)
    # jingni_subscribe_new_bond(context)
    # jingni_participate_reverse_repo(context, cash_ratio=0.5)


def on_bar(context, bars):
    jingni_handle_data(trade_mode, context)


if __name__ == "__main__":
    run(
        strategy_id="xxxxxxxxxx",
        filename="main.py",
        mode=MODE_BACKTEST,
        token="yyyyyyyyyy",
        backtest_start_time="2025-09-01 08:00:00",
        backtest_end_time="2025-09-01 16:00:00",
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1,
    )


###################################
# 以下为JingniFlow量化交易系统代码#
# 将 dist/jingniflow_single.py 的代码复制到尾部#
###################################
