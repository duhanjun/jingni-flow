# 配置与风险：从 dry-run 到实盘

JingniFlow 的默认运行配置是“安全态”：`dry_run=True`，单笔数量/金额、每日笔数、
重复下单窗口都有限制。实盘不是改一个 `dry_run=False` 就结束，而是按阶段放开。

## 1. 默认配置

```python
from jingniflow import RuntimeConfig

config = RuntimeConfig(
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
)
```

| 字段 | 作用 | 实盘建议 |
|---|---|---|
| `dry_run` | 只检查/打印，不报单 | 默认 True；只在专门的真实报单步骤改 False |
| `max_order_amount` | 单笔最大股数 | 首次真机验证压到 100 |
| `max_order_value` | 单笔最大金额 | 首次压到 20000 或更低 |
| `max_daily_orders` | 每日新增委托数 | 首次压到 2 |
| `repeat_window_seconds` | 同方向/同数量/同价格重复窗口 | 保持 3–10 秒 |
| `kill_switch` | 撤单并禁止后续下单 | 测试时手动打开，确认后复位 |
| `account_id` | QMT 等需要显式资金账号的平台 | 实盘必须配置 |

## 2. 在策略里设置

初始化时传：

```python
def init(context):
    config = RuntimeConfig(
        dry_run=True,
        max_order_amount=100,
        max_order_value=20000.0,
        max_daily_orders=2,
        repeat_window_seconds=10,
    )
    jingni_main("qmt", context, config=config, strategy=my_strategy)
```

运行中调整：

```python
jingni_set_risk(
    {"dry_run": False, "max_order_amount": 100, "max_daily_orders": 2},
    trade_mode="qmt",
    context_data=context,
)
```

注意：`RuntimeConfig` 是运行上下文配置，单文件模式下不要把它写成模块级可变
全局；不同平台/账户分别设置。

## 3. 四个阶段

| 阶段 | dry_run | 账户 | 允许做什么 | 禁止做什么 |
|---|---|---|---|---|
| 回测 | True | 回测资金 | 行情、日历、dry-run、订单意图 | 真实报单、依赖柜台成交 |
| 模拟 dry-run | True | 模拟 | 验证策略逻辑、风控拒绝 | 真实报单 |
| 模拟真实报单 | False | 模拟 | 100 股限价挂单/撤单/成交 | 市价单、批量平仓、扩量 |
| 实盘只读 | True | 实盘 | 账户/持仓/行情/权限核对 | 任何报单 |
| 实盘 100 股 | False | 实盘（授权） | 100 股限价挂单/撤单 | 市价单、批量、无人旁站 |

每一阶段通过后再进入下一阶段；失败就回到上一阶段，不跳步。

## 4. kill switch

```python
count = jingni_kill_switch(trade_mode="qmt", context_data=context)
```

行为：

1. 把 kill switch 置为 ON；
2. 撤掉未完成委托；
3. 后续下单被风控拒绝。

测试顺序：

1. 挂一笔不会成交的买单；
2. 调用 `jingni_kill_switch()`；
3. 确认终端委托变成 `CANCELED`；
4. 再调用下单，确认被拒绝；
5. 确认无未完成委托后，复位：

```python
jingni_set_risk({"kill_switch": False}, trade_mode="qmt", context_data=context)
```

不要在还有持仓/在途委托时把 kill switch 当成“平仓工具”；它只负责撤单和禁单。

## 5. 第一次真实报单的参数

```python
ref = jingni_order_amount(
    "qmt",
    C,
    "600000.SH",
    100,
    limit_price,
    dry_run=False,
    order_type="limit",
    remark="live-rest-YYYYMMDD",
)
```

规则：

- 只做 **100 股、限价单**；
- 买入价挂在买盘下方（例如 `last * 0.98`，按 tick 对齐），目的是挂单后撤单，
  不是成交；
- 若意外成交，不要为了当天清仓去卖；A 股 T+1，记录持仓，次日再卖；
- 撤单后核对 `jingni_get_orders(include_finished=False)` 为空；
- 账户资金冻结恢复后再做下一笔。

## 6. 常见错误

| 现象 | 原因 | 处理 |
|---|---|---|
| 日志只有 `[JINGNI_DRY_RUN]` | 没显式传 `dry_run=False`，或配置仍是 True | 只在真实报单步骤显式传 False |
| 下单被拒 `max_order_amount` | 限额仍是 100000 但数量/金额超限 | 调整配置，不要绕过风控 |
| 下单被拒 `repeat_window` | 短时间重复同方向同数量同价格 | 改价格/数量，或等待窗口 |
| 下单被拒 `kill_switch` | 之前打开过 kill switch 未复位 | 确认无未完成委托后复位 |
| QMT 报 account not configured | 没有 `account_id` 或终端账号 | 配置 `RuntimeConfig(account_id=...)` |
| PTrade 错误码 3 | 单文件里有 `sys` | 用最新单文件并跑 `verify_release.py` |

完整真机步骤、证据记录和 GO/NO-GO 判定见 `docs/live-validation-checklist.md`。
