# coding: gbk
"""QMT 策略模板。

重要：
1. QMT 内置 Python 3.6，本文件必须保存为 GBK/ANSI；
2. 将 dist/jingniflow_single_gbk.py 全文粘贴到本文件末尾（推荐），
   或把 jingniflow 包安装到 QMT 可访问的 Python 路径；
3. 不要在本文件里写 while True / time.sleep 主循环。
"""

try:
    from jingniflow import jingni_handle_data, jingni_main
except ImportError:
    # 单文件模式：粘贴 dist/jingniflow_single_gbk.py 后，函数已在全局命名空间。
    pass


def my_strategy(trade_mode, context_data):
    """在这里写信号、下单和撤单逻辑。"""
    # 示例：先读行情，再调用 jingni_order_amount(..., dry_run=True)。
    pass


def init(C):
    jingni_main("qmt", C, strategy=my_strategy)


def handlebar(C):
    jingni_handle_data("qmt", C)
