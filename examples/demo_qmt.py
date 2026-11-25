# encoding: gbk
import datetime

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：把 dist/jingniflow_single_gbk.py 粘贴到本文件末尾。
    pass

trade_mode = "qmt"


def my_strategy(trade_mode, context_data):
    """在这里写信号、下单和撤单逻辑。"""
    # 示例：先读行情，再调用 jingni_order_amount(..., dry_run=True)。
    pass


def init(ContextInfo):
    jingni_main(trade_mode, ContextInfo, strategy=my_strategy)
    # 需要定时任务时再打开；repeat_times=0 表示按日规则持续触发。
    # ContextInfo.schedule_run(
    #     jingni_subscribe_new_stock,
    #     datetime.datetime.now().strftime("%Y%m%d") + "100000",
    #     0,
    #     datetime.timedelta(days=1),
    #     "jingni_subscribe_new_stock",
    # )


def handlebar(ContextInfo):
    jingni_handle_data(trade_mode, ContextInfo)


###################################
# 以下为JingniFlow量化交易系统代码#
# 将 dist/jingniflow_single_gbk.py 的代码复制到尾部#
###################################
