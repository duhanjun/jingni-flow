# 模拟 / 实盘真机验证清单

- 版本：`0.2.0.dev0`
- 适用：掘金量化、QMT、PTrade 的股票现货、打新/新债、国债逆回购
- 前置：三端回测冒烟已通过（掘金 `23/0/1`、QMT `21/0/3`、PTrade `22/0/2`）
- 原则：先模拟、后实盘；先只读、后报单；先 100 股、后扩量；所有真实报单必须有人工授权和终端旁站

> 这份清单只覆盖“真机交易链路”。回测已经证明代码能启动、行情/日历可用、
> dry-run 不报单；它没有证明柜台报单、撤单、成交回报、账户权限和实时定时器。
> 三端回测里的 `real order/cancel`、QMT 的 `run interval/schedule`、PTrade 的
> `run interval` 都是 skip，必须在这里补齐。

## 0. 准入与安全门

### 0.1 环境准入

- [ ] 模拟账户已开通，且能独立于实盘账户登录。
- [ ] 实盘账户只在模拟全绿后使用；实盘首日只做“只读 + 100 股挂单/撤单”，不做市价单、不做批量平仓。
- [ ] 终端版本、Python 版本、账户类型、资金账号别名已记录；不要把完整账号写进日志或文档。
- [ ] 交易时段内有人旁站；非交易时段只做静态/只读检查。
- [ ] 已确认当日不是节假日、不是标的停牌/ST/退市整理期；标的选流动性好的主板股票（默认 `600000.SH`）。

### 0.2 统一风控配置

真实报单前，先把运行配置压到最小，再显式打开 `dry_run=False`。测试结束后立刻恢复
`dry_run=True`。

```python
# 进入真实报单测试前
jingni_set_risk(
    {
        "dry_run": False,
        "max_order_amount": 100,       # 只允许 100 股
        "max_order_value": 20000.0,    # 防止价格异常放大金额
        "max_daily_orders": 2,         # 只够“报单 + 撤单/补单”
        "repeat_window_seconds": 10,   # 防重复下单
        "kill_switch": False,
    },
    trade_mode=trade_mode,
    context_data=context,
)

# 测试结束后恢复安全态
jingni_set_risk(
    {"dry_run": True, "max_order_amount": 100000, "max_daily_orders": 100},
    trade_mode=trade_mode,
    context_data=context,
)
```

规则：

- `dry_run=False` 只允许在专门的“真实报单”步骤出现；不要把它写进策略默认配置。
- 真实报单只允许 **100 股、限价单**；不使用市价单、不一次性平掉多只持仓。
- 若挂单成交，不要为了“当天清仓”去卖；A 股 T+1，当天买入不可卖。记录持仓，次一交易日再卖。
- `jingni_kill_switch` 会撤掉未完成委托并阻止后续下单；测试完确认无未完成委托后，
  才可用 `jingni_set_risk({"kill_switch": False}, ...)` 复位。

### 0.3 冻结构建产物

在项目根目录执行并记录输出：

```powershell
python tools/build_single.py --root
python tools/build_single.py --check --root
python tools/build_smoke.py
python tools/build_smoke.py --check
python tools/build_validation.py
python tools/build_validation.py --check
python tools/verify_release.py
Get-FileHash dist/jingniflow_single.py, dist/jingniflow_single_gbk.py -Algorithm SHA256
```

记录字段：`version`、`Source-SHA256`、`Build-UTC`、两个单文件的 SHA256。三端只使用
本次冻结的产物，不要在测试中途重新构建。

| 产物 | 用途 | 必须核对 |
|---|---|---|
| `dist/jingniflow_single.py` | 掘金 / PTrade | UTF-8、无 `sys`（PTrade） |
| `dist/jingniflow_single_gbk.py` | QMT | GBK、`# coding: gbk`、Python 3.6 |
| `dist/smoke/goldminer_smoke_full.py` | 掘金完整粘贴版 | UTF-8、`trade_mode=goldminer` |
| `dist/smoke/qmt_smoke_full.py` | QMT 完整粘贴版 | GBK、`trade_mode=qmt` |
| `dist/smoke/ptrade_smoke_full.py` | PTrade 完整粘贴版 | UTF-8、无 `sys`、`trade_mode=ptrade` |
| `dist/validation/goldminer_validation_full.py` | 掘金仿真验证 | UTF-8、`[VALIDATION]`、默认 dry-run |
| `dist/validation/qmt_validation_full.py` | QMT 仿真验证 | GBK、`[VALIDATION]`、默认 dry-run |
| `dist/validation/ptrade_validation_full.py` | PTrade 仿真验证 | UTF-8、无 `sys`、`[VALIDATION]` |

### 0.4 可粘贴验证代码

三端完整文件已生成到 `dist/validation/`，直接复制，不需要再追加单文件：

| 文件 | 平台 | 用途 |
|---|---|---|
| `goldminer_validation_full.py` | 掘金 | dry-run + 100 股挂单/撤单 |
| `qmt_validation_full.py` | QMT | dry-run + 100 股挂单/撤单；GBK |
| `ptrade_validation_full.py` | PTrade | dry-run + 100 股挂单/撤单；UTF-8 无 `sys` |
| `goldminer_validation_order_cancel.py` | 掘金 | 已设 `order_cancel`，直接运行 |
| `qmt_validation_order_cancel.py` | QMT | 已设 `order_cancel`，GBK |
| `ptrade_validation_order_cancel.py` | PTrade | 已设 `order_cancel`，UTF-8 无 `sys` |

默认 `VALIDATION_STAGE = "dry_run"`，不会报单；确认是仿真账户后改为
`"order_cancel"`。详细步骤见 `dist/validation/README.md`。

先看日志前缀：`[VALIDATION]` 才是本节要跑的验证脚本；`[SMOKE]` 是回测冒烟脚本。
如果三端终端里看到 `[SMOKE][SUMMARY]`，不要拿来判定 GO/NO-GO，替换为
`dist/validation/*_validation_full.py` 后重跑。

QMT 仿真环境有两个已见现象，不要误判为适配层失败：

- `[SMOKE][OK] field close offset=0: 9999.99` 是 QMT `get_full_tick` 的无效哨兵值；
  validation 优先用日线收盘价并按涨跌停区间校验，不会按 9999.99 报单。
- `[JINGNI_PLATFORM_API_MISSING] platform api not found: schedule_run` 是旧 smoke
  路径；当前实现优先调用 `ContextInfo.schedule_run(...)`，QMT 的 `schedule_run`
  不是全局函数。

PTrade 如果报 `[120162][超过涨跌停范围]`，先看 `[VALIDATION][PRICE]` 的
`last/limit` 与平台 `p_up_price/p_down_price`。PTrade 的涨跌停校验使用未复权
昨收，validation 已改为取 `adjust="none"` 的日线，并从
`high_limit/low_limit/preclose` 补齐涨跌停；参考价越界时挂跌停价。

## 1. 三端基线（已由回测冒烟证明）| 端 | 实测 Python | 回测结果 | 已跳过项 | 本轮必须补测 |
|---|---|---|---|---|
| 掘金 | `3.11.14` | `pass=23 fail=0 skip=1` | `real order/cancel` | 真实报单/撤单、仿真定时器、柜台成交 |
| QMT | `3.6.8` | `pass=21 fail=0 skip=3` | `run interval 3s`、`schedule 09:31`、`real order/cancel` | 实盘定时器、真实报单/撤单、账户权限 |
| PTrade | `3.5.1` | `pass=22 fail=0 skip=2` | `run interval 3s`、`real order/cancel` | 交易环境 `run_interval`、真实报单/撤单、柜台回报 |

回测阶段已确认的硬约束，真机阶段继续适用：

- 掘金：`schedule` 的 `time_rule` 必须是 `HH:MM:SS`；适配器会把 `09:31` 转成
  `09:31:00`。直接调平台原生 `schedule` 时不要只写 `09:31`，否则错误码 1027。
- QMT：策略文件必须 GBK；回测没有资金账号时 `orders/trades/positions/account`
  会降级为空，这是正常的；实盘缺账号必须严格报错。
- PTrade：顶层不得出现 `import sys` / `sys.`；`get_history` 的成交额字段是
  `money`；`get_price` 的 `fields` 必须传 list；`run_daily` 只能在 `initialize`
  注册；回调会额外传入 `context`。

## 2. 模拟环境验证（先全绿）

模拟环境使用仿真资金，允许走完整报单链路。每一步都记录日志和终端截图。

### 2.1 启动与自检

- [ ] `jingni_doctor(trade_mode=..., context_data=context, verbose=True)`：`errors=0`；
      QMT 模拟账户不得再出现“account is not configured”；PTrade/掘金无异常警告。
- [ ] `jingni_capabilities()`：`platform` 正确，`features` 为 8 项；不出现 `unsupported`。
- [ ] 启动日志出现 `[JINGNI] version=0.2.0.dev0 python=... platform=...`。
- [ ] QMT 日志无 `platform=????????`、无 GBK 解码错误；PTrade 日志无“sys被禁止使用”。

### 2.2 行情、日历、标的与定时器

- [ ] `jingni_history(trade_mode, context, "600000.SH", "1d", 5)`：5 条，字段为统一
      `open/high/low/close/volume/amount`（PTrade 内部已把 `money` 改回 `amount`）。
- [ ] `jingni_get_field(..., "close", offset=0/1)`：返回 float，且与历史最后两条一致。
- [ ] `jingni_get_history_range(..., "2024-01-01", "2024-01-31")`：DataFrame 首尾在区间内；
      掘金实测 242 行、QMT 实测 242 行、PTrade 实测 242 行（以终端为准）。
- [ ] `jingni_download_history(...)`：QMT 逐只落盘且返回 `None`；掘金/PTrade 返回 `None` 不报错。
- [ ] `jingni_get_instrument(...)`：`name/board/lot_size/tick_size/limit_up/limit_down/listed_date/status`
      存在；PTrade 缺失字段为 `None` 或 100 股兜底，不伪造。
- [ ] `jingni_get_stock_status(...)`：PTrade 返回 bool；掘金/QMT 可判断时 bool，不可判断时 `None`。
- [ ] `jingni_get_trading_dates("2024-01-01", "2024-01-31")`：`YYYYMMDD` 升序；
      掘金 22 项、QMT 22 项、PTrade 31 项（这是各平台日历口径差异，记录不判错）。
- [ ] `jingni_is_trading_day` / `jingni_is_trading_time`：节假日 False；`09:20` 默认 False，
      `include_auction=True` 为 True；`12:00` 为 False。
- [ ] `jingni_run_interval(func, 3)`：交易时段每 3 秒至少触发一次；记录 5 个连续时间戳。
- [ ] `jingni_schedule(func, "09:31")`：次一交易日 09:31 触发；记录触发日志。
      QMT/PTrade 的回测跳过项，必须在模拟/交易环境观察；掘金确认 `09:31:00` 归一化生效。

### 2.3 dry-run（不报单）

- [ ] `jingni_order_amount(..., 100, price, dry_run=True)`：只打印 `[JINGNI_DRY_RUN]`，
      `jingni_get_orders()` 不新增订单。
- [ ] `jingni_order_value(..., 1000, price, dry_run=True)`：打印金额换算后的股数，
      不报单；不足 100 股的取整规则符合预期。
- [ ] `jingni_order_target_amount(..., target_amount=100, dry_run=True)`：只打印差额，
      不报单；重复调用不产生新订单。
- [ ] `jingni_order_market(..., 100, dry_run=True)`：打印保护价/市价参数，不报单。
- [ ] 超额、重复窗口、kill switch 三类风控拒绝均能在 dry-run 下看到明确 reason。
- [ ] `jingni_subscribe_new_stock(dry_run=True)` / `jingni_subscribe_new_bond(dry_run=True)`：
      列出标的/额度/状态，不报单。
- [ ] `jingni_participate_reverse_repo(context, cash_ratio=0.1, dry_run=True)`：
      打印代码、张数、价格；无现金时 `[JINGNI_SKIP]`，不报错。

### 2.4 真实报单：挂单 + 撤单（模拟）

目标：验证 `OrderRef`、订单查询、撤单、状态映射，不让它成交。

- [ ] 取 `last`，买入限价设为 `last * 0.98`（或更低，按 tick 对齐），确保挂在买盘下方。
- [ ] 调用 `jingni_order_amount(..., 100, limit_price, dry_run=False, remark="sim-rest")`。
- [ ] 返回 `OrderRef`，含 `platform/order id/status`；`jingni_get_orders()` 能看到该单。
- [ ] 在终端委托列表核对：代码、方向、数量、价格、备注一致。
- [ ] `jingni_cancel_order(..., ref)` 返回 True；订单最终状态为 `CANCELED`。
- [ ] `jingni_get_orders(include_finished=True)` 中该单状态为 `CANCELED`；无残留未完成委托。
- [ ] 若价格意外成交：不要再次撤单；记录成交，按 T+1 规则次日卖出。

### 2.5 真实成交：100 股买入 + 次日卖出（模拟）

只在模拟环境做；实盘必须单独授权。

- [ ] 买入限价设为 `last * 1.01`（或卖一价附近），100 股；等待成交。
- [ ] `jingni_get_orders()` 状态最终 `FILLED`；`jingni_get_trades()` 有对应成交记录，
      数量、价格、手续费方向正确。
- [ ] `jingni_get_positions()` 出现 100 股；`available` 当日为 0（T+1），总持仓为 100。
- [ ] 次一交易日：确认 `available=100` 后，卖出 100 股（限价/保护价），状态 `FILLED`；
      持仓归零，账户现金与终端一致。
- [ ] 记录买入/卖出两次成交的订单号、成交号、时间、价格、数量。

### 2.6 目标持仓差额引擎（模拟）

- [ ] 空仓时 `jingni_order_target_amount(..., target_amount=100)`：只下 100 股买单。
- [ ] 已有 100 股、目标仍 100：不下单（差额为 0）。
- [ ] 已有 100 股、目标 0：下 100 股卖单（需 `available=100`）。
- [ ] 有未完成买单时再次调用同一目标：差额扣除在途委托，不重复下单。
- [ ] 部分成交后再次调用：差额收敛，不超买/超卖。
- [ ] 以上每一步都用 `jingni_get_orders()` 和终端委托列表双核对。

### 2.7 账户、持仓、订单、成交对账（模拟）

- [ ] `jingni_get_account(..., strict=True)` 返回 7 个字段：
      `total_asset/cash/available/frozen/market_value/pnl/raw`。
- [ ] 与终端“资金账户”逐项核对；差异记录绝对值与原因（浮点/冻结/在途）。
- [ ] `jingni_get_positions(..., strict=True)` 的 `amount/available/cost/market_value`
      与终端持仓一致；当日买入的 `available=0` 不被误判为可卖。
- [ ] `jingni_get_orders()` 与终端委托列表的订单号、状态、数量、价格一致。
- [ ] `jingni_get_trades()` 与终端成交列表的成交号、数量、价格、时间一致。
- [ ] 订单状态映射覆盖：`SUBMITTED/PARTIAL/FILLED/CANCELED/REJECTED/EXPIRED/UNKNOWN`
      至少各观察一次（没有的记 N/A，不强行造单）。

### 2.8 撤单、全撤、kill switch（模拟）

- [ ] 同时挂两笔不会成交的买单（不同价格，100 股/笔），`jingni_cancel_all()`
      返回撤单数量（平台不支持计数时记录原始返回值），终端无未完成委托。
- [ ] 重新挂一笔不会成交的买单，调用 `jingni_kill_switch()`：
      返回撤单数量（以平台返回为准，至少确认目标单被撤）；该单变 `CANCELED`。
- [ ] kill switch 开启后再调用 `jingni_order_amount`：被拒绝，reason 含 kill switch；
      终端不出现新委托。
- [ ] 确认无未完成委托后，`jingni_set_risk({"kill_switch": False}, ...)` 复位；
      再下一笔 dry-run 单确认恢复正常。
- [ ] `jingni_close_all(dry_run=True)` 只打印计划，不报单；真实 `close_all` 不在本次
      冒烟中使用（除非有专门授权和持仓）。

### 2.9 打新 / 新债 / 逆回购（模拟）

- [ ] 新股：`jingni_subscribe_new_stock(dry_run=True)` 列出代码/额度；真实申购只在
      模拟环境、按终端额度执行一次；记录返回状态。
- [ ] 新债：`jingni_subscribe_new_bond(dry_run=True)` 同上；确认黑名单生效。
- [ ] 逆回购：`jingni_participate_reverse_repo(context, cash_ratio=0.1, dry_run=False)`
      在模拟环境执行一次；确认代码 `204001.SH`、张数、价格、冻结资金、到期返还。
- [ ] 逆回购不要在 15:00 后、不要在可用资金不足时执行；失败时记录平台原始错误。
- [ ] 打新/逆回购的真实结果与终端“委托/成交/资金”三处一致。

### 2.10 重启与幂等（模拟）

- [ ] 盘中重启策略：已有持仓/在途委托可查询；目标持仓再次调用不重复下单。
- [ ] 断开终端/网络 30 秒再恢复：查询恢复，未完成委托状态正确；不出现重复成交。
- [ ] 重复窗口内同方向同数量同价格连续下单：第二笔被风控拒绝。
- [ ] 进程重启后 `kill_switch` 状态符合预期（默认 OFF；若为 ON，明确记录并复位）。

## 3. 实盘验证（只读 → 100 股）

实盘阶段分两段：先只读，确认账户和行情；再 100 股挂单/撤单。任何一段失败都停止，
不进入下一段。

### 3.1 实盘只读

- [ ] 登录实盘账户，`jingni_doctor` 的 account 检查为 ok（不能是 backtest 的
      “account unavailable”降级）。
- [ ] `jingni_get_account(strict=True)`、`jingni_get_positions(strict=True)` 与终端一致。
- [ ] `jingni_history`、`jingni_get_field`、`jingni_get_history_range`、`jingni_tick`
      返回实时/当日数据；时间戳、最新价合理。
- [ ] `jingni_is_trading_day/time` 与交易所状态一致；集合竞价/连续竞价边界正确。
- [ ] 不下任何单；只读阶段至少观察一个完整交易时段。

### 3.2 实盘 100 股挂单 + 撤单

必须满足：模拟阶段全绿、有人旁站、账户资金充足、标的不在停牌/ST/涨跌停附近。

- [ ] 记录时间、`last`、买一/卖一、可用资金、可用持仓。
- [ ] 买入限价 `last * 0.98`（按 tick 对齐），100 股，`dry_run=False`，备注
      `live-rest-<date>`；确认委托出现在终端。
- [ ] 5 秒内 `jingni_cancel_order`；返回 True；终端状态 `CANCELED`。
- [ ] 若已成交：立即停止后续报单，记录成交；按 T+1 次日卖出，不尝试当日卖出。
- [ ] `jingni_get_orders()` / `jingni_get_trades()` 与终端逐笔核对。
- [ ] 撤单后 `jingni_get_orders(include_finished=False)` 为空；账户冻结资金恢复。

### 3.3 实盘成交与次日卖出（可选，需单独授权）

- [ ] 仅在模拟成交测试通过、且实盘授权明确时执行；买入 100 股，限价接近卖一。
- [ ] 成交后记录订单/成交/持仓；确认 `available=0`。
- [ ] 次一交易日确认 `available=100` 后卖出 100 股；成交后持仓归零。
- [ ] 计算实际佣金、滑点、成交价与预期差异；记录到验证报告。

### 3.4 实盘 kill switch（仅在无持仓/无未完成委托时）

- [ ] 挂一笔不会成交的买单；`jingni_kill_switch()`；确认撤单和后续拒绝。
- [ ] 复位前确认终端无未完成委托；复位后再用 dry-run 验证恢复。
- [ ] 若当天有持仓，不做 `close_all`；kill switch 只做撤单/禁单，不主动平仓。

## 4. 平台专项检查

### 4.1 掘金量化

- 策略解释器必须指向已安装 `gm` 的 Python；本机实测 `3.11.14`，`gm` 位于
  `D:\codebuddy\jingni-gateway\.venv\Lib\site-packages\gm`（以实际终端为准）。
- 策略文件末尾必须有 `run(...)` 启动块；`filename` 与实际文件名一致；`run` 必须
  在所有函数定义之后。
- 代码格式：规范代码 `600000.SH`；订阅/股票池 `SHSE.600000`；不要只改一个。
- `schedule` 直接调原生 API 时用 `HH:MM:SS`；JingniFlow 的 `jingni_schedule` 接受
  `09:31` 并归一化。
- 核对 `order_volume` 的返回对象、`order_cancel` 的订单号、`get_orders` 的状态字段；
  `volume_today` 是可卖量口径，不是总持仓。
- 错误码 1027 表示 `schedule` 入参无效；先查 `time_rule` 是否缺秒。
- 官方文档：
  - 快速开始：https://www.myquant.cn/docs2/sdk/python/%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.html
  - 基本函数（含 `schedule`）：https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%9F%BA%E6%9C%AC%E5%87%BD%E6%95%B0.html
  - 错误码：https://www.myquant.cn/docs2/sdk/python/%E9%94%99%E8%AF%AF%E7%A0%81.html
  - FAQ：https://www.myquant.cn/docs2/faq/

### 4.2 QMT

- 内置 Python `3.6.8`；策略文件必须 GBK，文件头保留 `# encoding: gbk`；不要粘 UTF-8
  单文件。若日志出现 `platform=????????`，先查单文件尾部 legacy `trade_mode` 是否覆盖。
- 账户：`RuntimeConfig(account_id=...)` 或终端 `ContextInfo.account` 必须配置；
  回测无账号时 `positions/account/orders/trades` 返回空是预期，实盘缺账号是错误。
- 报单：`passorder` 的 `opType`（买/卖）、`prType`（限价/市价）由适配器映射；
  真实报单前在终端确认参数含义，不要手改 `prType` 猜值。
- 撤单：适配器调用 `cancel(order_id, account, account_type, ContextInfo)`；核对
  订单号和账号类型（`stock`）。
- 查询：`get_trade_detail_data(account, account_type, "account"/"position"/"order"/"deal")`；
  对比终端字段，注意 QMT 金额/数量单位。
- 定时器：`ContextInfo.run_time` 的回调函数必须在策略全局命名空间；回测无效，
  只在模拟/实盘验证。`schedule` 回测也 skip，实盘观察 09:31 是否触发。
- `handlebar` 必须用 `ContextInfo.is_last_bar()` 守卫，避免历史 K 线逐根重复下单。
- 日志：GBK 控制台，不要输出 UTF-8 专用字符；异常信息保留原始订单号。
- 官方文档：https://dict.thinktrader.net/innerApi/start_now.html?id=yzWK3j

### 4.3 PTrade

- 实测 Python `3.5.1`：不能用 f-string、变量注解、async comprehension；用 `.format`。
- 顶层禁止 `sys`：不写 `import sys` / `sys.`；报错码 3“sys被禁止使用”时先查单文件。
- 生命周期：`initialize` 注册 `run_daily`/`run_interval`；`before_trading_start` 做准备；
  `handle_data` 做盘中逻辑；`after_trading_end` 做盘后对账。不要在校验阶段调用
  `run_daily`。
- `run_interval` 最小 3 秒，回测不支持；交易环境观察实际触发间隔。
- `get_history` 成交额字段是 `money`，适配器统一改回 `amount`；`get_price` 的 `fields`
  必须传 list；`get_trade_days` 可能是 numpy 数组，适配器已 `tolist()`。
- 回调会额外传 `context`：`def _smoke_scheduled(*args, **kwargs)` 这类签名才安全。
- 报单/撤单：核对 `order_market` 的 `limit_price`、`cancel_order` 的订单号、
  `get_orders/get_trades` 的返回结构；`get_snapshot` 字段以终端为准。
- 官方 API：<INTERNAL_HOST>

## 5. 结果记录模板

每个平台至少填一张；同一天多个账户分开记录。证据文件建议放
`evidence/<platform>/<yyyy-mm-dd>/`，不要提交账号密码。

| 字段 | 内容 |
|---|---|
| 平台 / 终端版本 |  |
| Python 版本 |  |
| 环境 | 模拟 / 实盘 |
| 账户别名 |  |
| 策略版本 / Source-SHA256 |  |
| 单文件 SHA256 |  |
| 测试日期 / 操作人 |  |
| 启动自检 | pass / fail，errors/warnings |
| 行情/日历 | pass / fail，异常项 |
| dry-run | pass / fail，是否零报单 |
| 真实挂单/撤单 | pass / fail，订单号/状态 |
| 成交/持仓对账 | pass / fail，差异 |
| 定时器 | pass / fail / N/A，触发时间 |
| 打新/逆回购 | pass / fail / N/A |
| kill switch | pass / fail，撤单数/拒绝原因 |
| 总体结论 | GO / NO-GO |

### 5.1 用例结果表

| 编号 | 平台 | 环境 | 用例 | 预期 | 证据 | 结果 |
|---|---|---|---|---|---|---|
| GM-SIM-01 | 掘金 | 模拟 | 启动/doctor | errors=0 | 日志 |  |
| GM-SIM-02 | 掘金 | 模拟 | 挂单+撤单 | 状态 CANCELED | 日志+截图 |  |
| GM-SIM-03 | 掘金 | 模拟 | 成交+次日卖出 | 持仓归零 | 成交单 |  |
| QMT-SIM-01 | QMT | 模拟 | GBK 启动 | 无乱码 | 日志 |  |
| QMT-SIM-02 | QMT | 模拟 | 挂单+撤单 | 状态 CANCELED | 日志+截图 |  |
| QMT-SIM-03 | QMT | 模拟 | 定时器 | 09:31 触发 | 日志 |  |
| PT-SIM-01 | PTrade | 模拟 | 无 sys 启动 | 无错误码 3 | 日志 |  |
| PT-SIM-02 | PTrade | 模拟 | 挂单+撤单 | 状态 CANCELED | 日志+截图 |  |
| PT-SIM-03 | PTrade | 模拟 | run_interval | ≥3 秒触发 | 日志 |  |
| GM-LIVE-01 | 掘金 | 实盘 | 只读对账 | 账户/持仓一致 | 截图 |  |
| QMT-LIVE-01 | QMT | 实盘 | 只读对账 | 账户/持仓一致 | 截图 |  |
| PT-LIVE-01 | PTrade | 实盘 | 只读对账 | 账户/持仓一致 | 截图 |  |

## 6. GO / NO-GO 判定

必须全部满足才可 GO：

- [ ] 三端模拟环境的启动、行情/日历、dry-run、真实挂单/撤单、账户/持仓/订单/成交对账全部通过。
- [ ] 至少一端完成“100 股成交 + 次日卖出”的模拟闭环；另外两端至少完成挂单/撤单。
- [ ] QMT 的 GBK/账号/定时器、PTrade 的 sys/3.5 语法/`run_interval`、掘金的 `schedule`
      秒格式均无未解决项。
- [ ] kill switch 能撤单并阻断后续下单；复位后有明确记录。
- [ ] 实盘只读对账通过，且真实挂单/撤单在旁站下完成。
- [ ] 所有 P0 问题关闭；P1 问题有明确降级说明和负责人。

出现以下任一情况立即 NO-GO：

- 报单后终端查不到，或订单号/状态不一致。
- 撤单后仍有未完成委托，或撤单返回成功但终端未撤。
- 持仓/可用量与终端不一致，或出现重复下单/超买超卖。
- QMT 出现 GBK 解码错误、PTrade 出现“sys被禁止使用”、掘金 `schedule` 报 1027。
- kill switch 无法阻断后续下单。
- 真实报单成交后无法在次日按计划卖出，或账户资金出现非预期冻结。

## 7. 失败处理顺序

1. 立即停止新报单；需要时 `jingni_kill_switch()`，再人工在终端核对未完成委托。
2. 保存终端日志、策略日志、订单/成交截图；记录时间、订单号、标的、数量、价格。
3. 先排查平台侧（账号权限、交易时段、标的限制、资金/持仓冻结），再排查适配器字段。
4. 修复后从“dry-run → 模拟挂单/撤单 → 模拟成交 → 实盘只读 → 实盘 100 股”重新走，
   不跳步。
5. 任何真实报单失败都要在验证报告里写根因、修复 commit、复测结果。

## 8. 本轮不覆盖

- 期货、期权、融资融券、港股通、美股；只覆盖 A 股股票现货。
- 大额/批量/高频策略；本清单只做 100 股链路验证。
- 券商柜台特殊字段、佣金/印花税精算；以终端成交单为准。
- QMT/PTrade 的完整实盘权限矩阵；以券商开通和终端提示为准。
