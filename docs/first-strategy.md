# 第一个策略

这是一个**只做 dry-run** 的最小示例：读 5 根日线，最后两根收盘价上涨时打印一笔
100 股买入意图，不向柜台报单。它用于验证“策略入口、行情、下单 API、平台回调”
四件事是否接好，不是投资建议，也不是完整策略。

## 1. 策略函数

```python
def my_strategy(trade_mode, context_data):
    history = jingni_history(trade_mode, context_data, "600000.SH", "1d", 5)
    if history is None or len(history) < 2:
        print("[FIRST] history not ready")
        return

    prev_close = float(history["close"].iloc[-2])
    last_close = float(history["close"].iloc[-1])
    print("[FIRST] prev={0} last={1}".format(prev_close, last_close))

    if last_close <= prev_close:
        print("[FIRST] no signal")
        return

    ref = jingni_order_amount(
        trade_mode,
        context_data,
        "600000.SH",
        100,
        last_close,
        dry_run=True,
        remark="first-strategy",
    )
    print("[FIRST] dry-run order ref={0}".format(ref))
```

要点：

- `600000.SH` 是 JingniFlow 的规范代码；掘金订阅用 `SHSE.600000`，PTrade
  股票池用 `600000.SS`，这些由模板/适配器处理。
- `jingni_history` 的第 5 个参数是条数；这里取 5 根。
- `dry_run=True` 是显式安全开关；即使 `RuntimeConfig` 被改成 `False`，这一笔
  仍然只打印。
- 真正策略要加“当日只下一次”“目标持仓”“重复窗口”等约束，不要直接照搬
  这个示例反复报单。

## 2. 三种平台接法

### 掘金量化

```python
def init(context):
    subscribe(symbols="SHSE.600000", frequency="1d")
    jingni_main("goldminer", context, strategy=my_strategy)


def on_bar(context, bars):
    jingni_handle_data("goldminer", context)
```

策略文件末尾还要有 `run(...)` 启动块，见 `docs/getting-started.md`。

### QMT

```python
def init(C):
    ContextInfo.set_universe(["600000.SH"])
    jingni_main("qmt", C, strategy=my_strategy)


def handlebar(C):
    if not C.is_last_bar():
        return
    jingni_handle_data("qmt", C)
```

QMT 策略文件必须 GBK；`is_last_bar()` 守卫用于避免历史 K 线逐根重复执行。

### PTrade

```python
def initialize(context):
    set_universe(["600000.SS"])
    jingni_main("ptrade", context, strategy=my_strategy)


def handle_data(context, data):
    jingni_handle_data("ptrade", context)
```

PTrade 不能出现 `import sys` / `sys.`；`run_daily` 只能在 `initialize` 注册。

## 3. 第一次运行看什么

回测应看到：

```text
[JINGNI] platform=... mode=backtest python=...
[JINGNI] ready; platform events drive the strategy
[FIRST] prev=... last=...
[FIRST] dry-run order ref=...
```

同时：

- 终端委托列表不应出现新订单；
- `jingni_get_orders()` 不应新增订单；
- 日志出现 `[JINGNI_DRY_RUN]` 才算 dry-run 生效。

如果只看到：

```text
交易策略正在运行中，请写入你的策略逻辑
```

说明 `my_strategy` 没有绑定成功。检查：

1. `jingni_main` 是否传了 `strategy=my_strategy`；
2. 函数名是否拼错；
3. 单文件模式下，`my_strategy` 是否在平台回调执行前已经定义。

## 4. 从 dry-run 到模拟报单

确认 dry-run 输出正确后，按 `docs/config-and-risk.md` 操作：

1. 保持模拟账户；
2. 把 `dry_run=False` 只放在一笔 100 股限价单上；
3. 观察 `OrderRef`、`jingni_get_orders()`、终端委托列表；
4. 立即撤单；
5. 不要用这个示例直接做实盘批量交易。

完整真机步骤见 `docs/live-validation-checklist.md`。

## 5. 建议的下一步改造

- 用 `jingni_get_positions` / `jingni_order_target_amount` 改成目标持仓，不再
  每次信号都下单；
- 用 `jingni_get_trading_dates` / `jingni_is_trading_time` 控制交易时段；
- 用 `jingni_schedule` 把盘前/盘后任务与盘中信号分开；
- 用 `RuntimeConfig` 设置 `max_order_amount`、`max_daily_orders` 和
  `repeat_window_seconds`。
