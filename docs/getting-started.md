# 15 分钟上手

这份文档只回答一个问题：**第一次使用 JingniFlow，最少要做什么。**

JingniFlow 不是一个独立运行的量化平台，也不是 `python strategy.py` 就跑起来的
回测框架。它嵌在掘金 / QMT / PTrade 的策略运行环境里，由平台的
`init/on_bar`、`init/handlebar`、`initialize/handle_data` 事件驱动。

## 1. 先选路径

| 你的情况 | 推荐路径 | 先看 |
|---|---|---|
| 只用券商终端，不想配 Python 包 | 单文件粘贴 | 本文第 2、3 节 |
| 会 Python，要做研究/回测 | 包导入开发 | `docs/usage-modes.md` |
| 想先写一个能跑的策略 | 模板 + `strategy=` | `docs/first-strategy.md` |
| 已经跑通回测，准备模拟/实盘 | 分阶段验证 | `docs/config-and-risk.md`、`docs/live-validation-checklist.md` |

## 2. 构建单文件

在项目根目录执行：

```powershell
python tools/build_single.py --root
python tools/build_single.py --check --root
python tools/build_smoke.py
python tools/build_smoke.py --check
python tools/verify_release.py
```

产物选择：

| 平台 | 粘贴文件 | 编码 | Python |
|---|---|---|---|
| 掘金 | `dist/jingniflow_single.py` | UTF-8 | 终端实际解释器，本机实测 3.11.14 |
| QMT | `dist/jingniflow_single_gbk.py` | GBK | 3.6.8 |
| PTrade | `dist/jingniflow_single.py` | UTF-8 | 3.5.1，禁止 `sys` |

第一次不要直接改 `dist/` 里的单文件。改源码后重新构建，否则 `--check` 会报
`[STALE]`。

## 3. 三端最短路径

### 3.1 掘金量化

1. 新建策略，把 `jingniflow/templates/goldminer_strategy.py` 的内容复制进去。
2. 在策略文件末尾追加 `dist/jingniflow_single.py` 全文。
3. 在 `init` 里保留：

```python
jingni_main("goldminer", context, strategy=my_strategy)
```

4. 在 `on_bar` 里保留：

```python
jingni_handle_data("goldminer", context)
```

5. 策略文件末尾必须有 `run(...)` 启动块；`filename` 改成实际文件名，
   `strategy_id` / `token` 换成终端里的值。

预期启动日志：

```text
[JINGNI] platform=goldminer mode=backtest python=...
[JINGNI] ready; platform events drive the strategy
```

如果只看到“交易策略正在运行中，请写入你的策略逻辑”，说明还没有把
`my_strategy` 传给 `jingni_main`，或者策略函数是空的。

### 3.2 QMT

1. QMT 新建策略。
2. 复制 `jingniflow/templates/qmt_strategy.py` 的内容；该文件本身是 GBK。
3. 在末尾追加 `dist/jingniflow_single_gbk.py` 全文。
4. 整个策略文件必须以 **GBK/ANSI** 保存，不能粘 UTF-8 单文件。
5. 确认 `init` 中有：

```python
jingni_main("qmt", C, strategy=my_strategy)
```

6. `handlebar(C)` 中调用 `jingni_handle_data("qmt", C)`。

预期启动日志：

```text
[JINGNI] platform=qmt mode=backtest python=3.6.8
[JINGNI] ready; platform events drive the strategy
```

QMT 回测没有资金账号时，`positions/account/orders/trades` 返回空是正常降级；
实盘缺账号会严格报错。`run_interval` / `schedule` 在回测中跳过，必须在模拟或
交易环境验证。

### 3.3 PTrade

1. PTrade 新建策略。
2. 复制 `jingniflow/templates/ptrade_strategy.py` 的内容。
3. 在末尾追加 `dist/jingniflow_single.py` 全文。
4. 确认 `initialize` 中有：

```python
jingni_main("ptrade", context, strategy=my_strategy)
```

5. `handle_data(context, data)` 中调用 `jingni_handle_data("ptrade", context)`。

PTrade 的硬约束：

- Python 3.5.1，不能出现 f-string / 变量注解；
- 顶层不能出现 `import sys` / `sys.`；
- `get_history` 的成交额字段是 `money`，JingniFlow 内部统一为 `amount`；
- `get_price` 的 `fields` 必须传 list；
- `run_daily` 只能在 `initialize` 里注册。

预期不会出现：

```text
回测运行失败, 错误码:3 错误信息: sys被禁止使用
```

## 4. 第一次只跑回测

第一次不要打开真实报单。保持：

```python
SMOKE_REAL_ORDER = False
```

并且 `RuntimeConfig` 保持默认 `dry_run=True`。看到下面两行才算回测冒烟通过：

```text
[SMOKE][SUMMARY] stage=checks platform=... mode=backtest pass=... fail=0 skip=...
[SMOKE][RESULT] checks: ALL CHECKS PASSED; SMOKE VERIFICATION SUCCESS / 验证成功
```

`skip` 是当前环境无法验证的项，不能当作通过。回测里的真实报单、QMT 定时器、
PTrade `run_interval` 本来就是 skip，必须到模拟/交易环境补测。

## 5. 策略逻辑写在哪

推荐统一写成：

```python
def my_strategy(trade_mode, context_data):
    # 读行情、算信号、下单、撤单
    ...
```

然后二选一：

```python
# 推荐：初始化时显式绑定
jingni_main("qmt", C, strategy=my_strategy)
```

```python
# 也可以：先全局注册，再正常初始化
jingni_set_strategy(my_strategy)
jingni_main("qmt", C)
```

`jingni_handle_data` 每次被平台事件触发时，会调用这个函数。显式传给
`jingni_handle_data(..., strategy=...)` 的优先级最高。

旧的 `jingni_trade_strategy` 仍然保留为未注册时的占位实现；老的单文件策略
如果在尾部之后覆盖了它，也仍然可用。但新代码建议用 `strategy=`，不要依赖
覆盖位置。

## 6. 下一步

- 想看单文件、包导入、模板三种方式的取舍：`docs/usage-modes.md`
- 想直接复制一个可运行策略：`docs/first-strategy.md`
- 想从 dry-run 走到模拟/实盘：`docs/config-and-risk.md`
- 已经准备真机验证：`docs/live-validation-checklist.md`
- 遇到平台报错：先看 `docs/smoke-copy-paste.md` 的常见失败，再看
  `docs/live-validation-checklist.md` 的平台专项。
