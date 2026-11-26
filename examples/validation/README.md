# 三端仿真验证策略

这三份是**完整可粘贴**文件：已经把平台生命周期、验证脚本和 JingniFlow
单文件尾部拼在一起，不需要再手动追加单文件。

| 文件 | 平台 | 编码 |
|---|---|---|
| `goldminer_validation_full.py` | 掘金量化 | UTF-8 |
| `qmt_validation_full.py` | QMT | GBK |
| `ptrade_validation_full.py` | PTrade | UTF-8，无 `sys` |

## 直接跑 order_cancel 的版本

如果不想手动改 `VALIDATION_STAGE`，可以直接复制下面三份已设好的文件：

| 文件 | 平台 | 编码 |
|---|---|---|
| `goldminer_validation_order_cancel.py` | 掘金量化 | UTF-8 |
| `qmt_validation_order_cancel.py` | QMT | GBK |
| `ptrade_validation_order_cancel.py` | PTrade | UTF-8，无 `sys` |

这三份文件已经写死：

```python
VALIDATION_STAGE = "order_cancel"
```

复制后直接运行，不需要再改代码。注意：掘金/PTrade 会在仿真账户里真报一笔
100 股限价单然后撤单；QMT 版默认 `VALIDATION_QMT_ORDER_CANCEL_ENABLED=False`，
不会报单（原因见下方 QMT 段），只有确认柜台会保留未成交限价单时才改为 `True`。

这份文件的日志前缀是 `[VALIDATION]`，不是 `[SMOKE]`。

如果你看到的是 `[SMOKE]`、`[SMOKE][SUMMARY]` 或
`[JINGNI_SCHEDULE] ... schedule_run`，说明终端里跑的是旧的冒烟脚本
`dist/smoke/*_smoke_full.py`，不是本目录的验证脚本。把本目录的
`*_validation_full.py` 全量替换进去再运行；不要只替换文件开头。

## 使用顺序

### 第 1 步：dry-run，不报单

默认就是这一步：

```python
VALIDATION_STAGE = "dry_run"
```

在仿真账户里直接运行。它会执行：

- `jingni_doctor` / `jingni_capabilities`
- 账户、持仓、委托、成交查询
- 5 根日线
- 一笔 `dry_run=True` 的 100 股买入意图

预期看到：

```text
[VALIDATION][OK] doctor
[VALIDATION][OK] order dry-run: None
[VALIDATION][OK] dry-run added no order
[VALIDATION][RESULT] dry_run: ALL CHECKS PASSED
```

这一步不应在终端产生任何新委托。如果出现了新委托，停止，检查
`RuntimeConfig.dry_run` 和平台配置。

### 第 2 步：100 股挂单 + 撤单

确认当前是**仿真账户**后，只改一行：

```python
VALIDATION_STAGE = "order_cancel"
```

在连续竞价时段运行（09:30–11:30、13:00–15:00）。策略会：

1. 取**未复权**的最新日线收盘价，按 `last * 0.98` 计算限价；如果实时
   tick 返回 `9999.99` 这类异常哨兵值，会自动回退到历史价；如果参考价
   超出平台涨跌停区间，则改用跌停价，避免 PTrade 直接拒单；掘金/QMT 会
   再压到“跌停价 + 0.01”，确保是明显的非可成交买单；
2. 买入 100 股限价单；
3. 等待撤单延迟（掘金立即撤，QMT 为 0 秒，PTrade 默认 8 秒）；
4. 调用 `jingni_cancel_order`；
5. 查询订单状态，等待最终变为 `CANCELED`（最长 25 秒）；
6. 打印持仓和成交，输出 pass/fail 汇总。

预期关键日志：

```text
[VALIDATION][OK] place 100-share limit buy
[VALIDATION][WAIT] order placed; cancel after 8s
[VALIDATION][OK] cancel order: True
[VALIDATION][OK] order final status is CANCELED
[VALIDATION][RESULT] order_cancel: ALL CHECKS PASSED
```

如果状态是 `FILLED` 或 `PARTIAL`，脚本会判 FAIL 并提示不要当天卖出；
A 股 T+1，次日再处理。

### 第 3 步：记录

把 `[VALIDATION][SUMMARY]` 一行和终端委托/成交截图存到：

```text
evidence/<platform>/<yyyy-mm-dd>/
```

## 平台特别说明

### QMT

- 整个文件必须是 GBK/ANSI；不要用 UTF-8 保存。
- 如果 `doctor` 报 `QMT account is not configured`，把文件顶部的
  `VALIDATION_ACCOUNT_ID` 填成仿真资金账号；如果 `ContextInfo.account`
  已经可用，可以留空。
- `run_time` 在回测中无效，必须在仿真/交易环境运行。
- `handlebar` 已加 `is_last_bar()` 守卫，避免历史 K 线重复执行。
- QMT 的 `schedule_run` 是 `ContextInfo` 的方法，不是全局函数；本版已改为
  优先调用 `ContextInfo.schedule_run(...)`，只有方法不存在时才回退全局入口。
- QMT 的 `UpStopPrice/DownStopPrice` 以 `0.001` 元为单位返回；适配器已换算，
  否则会把 `8999.99/10999.99` 误当成 8999 元/10999 元的涨跌停。
- QMT 的 `get_full_tick` 在仿真环境可能返回 `lastPrice=9999.99` 这类无效值。
  验证脚本不会直接拿它算限价，而是优先用日线收盘价并校验涨跌停；看到
  `[SMOKE][OK] field close offset=0: 9999.99` 不代表要按 9999.99 报单。
- **运行模式必须是“实盘”，账户仍然选仿真/模拟账号。** 如果日志出现
  `[trade]start simulation mode`，QMT 当前是“模拟”运行模式；该模式只显示
  策略信号，不写委托，`get_orders` 永远看不到新单，撤单也无从验证。
- QMT 的 `passorder` 不返回柜台委托号，本版会先用 remark 查到
  `m_strOrderSysID` 再撤单；`get_orders` 也会按 remark 匹配新委托。验证状态
  机不再从 `init/run_time` 直接报单，而是等第一根 `handlebar` 到达后再启动，
  避免 QMT 接受调用但不生成柜台委托。
- 本版把 QMT 撤单延迟改为 **0 秒**，并在委托列表尚未回写时用
  `get_last_order_id` + `get_value_by_order_id` 核对 remark，抢在仿真撮合
  成交前拿到真实委托号；不会误撤账户里的旧单。
- **重要：QMT“国盛证券模拟”柜台实测按委托价直接撮合。** 2026-11-26 的
  `600000.SH` 100 股限价买单，在 `last=10.41`、限价 `9.01` 时仍回报
  `FILLED @ 9.01`，持仓从 500 股变为 600 股；14:59 再次运行后变为 700 股。
  因此 `VALIDATION_QMT_ORDER_CANCEL_ENABLED` 默认是 `False`，`order_cancel`
  只打印 `[SKIP]`，不写单。只有真实账户或确认使用交易所撮合的仿真账户，
  才把它改成 `True`；不要在这个模拟柜台上反复运行。
- QMT 的 `positions` 条数不等于持仓数量；验证现在会对比前后 `{code: amount}`
  和成交条数，持仓或成交发生变化会直接判 FAIL，不再只看 `2 items`。
- `passorder` 现在使用非空策略名 `JingniFlow`、`quickTrade=2`；官方文档要求
  传 `userOrderId` 时 `strategyName` 和 `quickTrade` 也必须有效，空策略名
  可能只产生信号而不产生委托。
- 100 股限价单会压在“跌停价 + 0.01”，在真实柜台应不可成交；但 QMT 模拟
  柜台不保证，默认不写单。如果 20 秒内委托仍未出现，会明确判 FAIL 并提示
  运行模式问题。
- 如果 QMT 本机历史数据不足（例如 `history range 2024` 只有 19 行），先在
  QMT 客户端“数据管理/补充行情”下载 `600000.SH` 的日线，再跑验证。

### PTrade

- 文件必须是 UTF-8；不要出现 `import sys` 或 `sys.`。
- 保持 Python 3.5 语法；本文件已避免 f-string 和变量注解。
- `run_interval` 最小 3 秒，只能在交易环境验证。
- 验证状态机不再从 `initialize/run_interval` 直接报单：PTrade 可能接受柜台
  委托，但这笔单不会进入 `get_orders()` 的策略订单列表，表现为“委托成功
  entrust_no=...”但 `get_orders` 永远查不到。本版会等第一次 `handle_data`
  后才启动报单，定时器只负责后续撤单推进。
- 适配器现在会把 `get_orders()`、`get_all_orders()` 以及本轮下单 id 的
  `get_order(order_id)` 合并；`get_order` 能在策略订单列表回写前直接查到
  新委托，避免把同代码/同数量/同价格的旧单误认为新单。
- 账户口径的委托用官方要求的 `cancel_order_ex(原始字典)` 撤单，不再只依赖
  策略订单列表。
- 已按 PTrade 官方状态码修正映射：`5` 部撤、`6` 已撤都映射为 `CANCELED`，
  `8` 已成才映射为 `FILLED`；旧版本把 `6` 误映射成 `FILLED`，会导致撤单
  成功却被判失败。
- `after_trading_end` 会检查是否还有未完成验证，未完成会判 FAIL。
- PTrade 的涨跌停校验使用**未复权**昨收。如果看到
  `[120162][超过涨跌停范围]`，说明策略侧数据源和柜台校验口径不一致；
  实机日志里出现过快照/日线 `9.78/11.96`、柜台 `7.97/9.74` 的情况。
  本版会在 PTrade 下把挂单价压到 `low_limit * 0.995`（当前样本约 `9.73`），
  落在柜台区间内，避免再次以 `120162` 拒单；日志里会打印
  `[VALIDATION][PRICE][PTRADE]` 的 snapshot 值和 low_ball 值。

### 掘金

- 文件是 UTF-8。
- 如果你是在掘金终端里新建策略并点击运行，不需要额外 `run(...)` 块；
  如果从外部 IDE 启动，按 `examples/demo_goldminer.py` 的 `run(...)` 写法补启动块。
- `on_bar` 使用 1 分钟订阅，`jingni_run_interval` 每 3 秒推进撤单状态机。
- 掘金 `order_volume` 返回 `list[Order]`；适配器取下单返回的第一笔。撤单优先用
  `Order.cl_ord_id`，通过 `order_cancel(wait_cancel_orders=[{"cl_ord_id": ...,
  "account_id": ...}])` 提交。官方要求两个字段都必填；本版优先从
  `context.raw.account().cash["account_id"]` 取真实账号，不能直接用
  `Order.account_id`（部分仿真环境它是 strategy_id），缺失时才回退到配置。
  订单有效期仍用 `OrderDuration_GFD`。
- 已按掘金官方状态码修正映射：`3` 已成、`5` 已撤、`12` 已过期；旧版本把
  `5` 误映射成 `EXPIRED`，所以“撤单返回 True 却显示 EXPIRED”有一部分是
  状态映射错误。现在只有最终状态 `CANCELED` 才算撤单通过，真正的
  `EXPIRED/REJECTED` 仍判失败。
- 掘金仿真对未成交限价单的存活时间可能很短，8 秒后再撤会看到 `EXPIRED`；
  本版在掘金下单成功后立即尝试一次撤单，失败则由 3 秒定时器继续重试。
  限价单会压到“跌停价 + 0.01”，避免 `last * 0.98` 被仿真柜台当成可成交价
  而先成交成 `PARTIAL`。

## 不要做的事

- 不要把 `VALIDATION_STAGE` 改成 `order_cancel` 后直接放到真实资金账户。
- 不要在非交易时段强行报单；脚本会等待连续竞价时段。
- 不要把 `VALIDATION_AMOUNT` 改成超过 100 股；验证只做最小链路。
- 不要在订单 `FILLED` 后为了“当天清仓”去卖出；A 股 T+1。
