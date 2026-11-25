# JingniFlow 代码评估与功能扩展规划方案

> **版本** v1.1（决策锁定版） ｜ **评估日期** 2026-11-19 ｜ **决策锁定** 2026-11-19 ｜ **评估对象** `jingniflow.py`（v0.1.16，约 760 行、18 个公开函数）、`examples/` 三个示例、`pyproject.toml`、`__init__.py`、`README.md`
> **文档性质** 规划方案，不含代码实施 ｜ **核实标记** ✔ 已核实（代码或官方文档直接证据）／△ 待实测（依赖客户端版本、券商权限或数据环境）

---

## 0. 结论摘要

1. **架构方向正确，但当前实现不具备可靠的实盘/回测能力。** 项目用"单文件 + 全局 `trade_mode` + 函数内 `if/elif` 分发"的方式，把掘金、QMT、PTrade 三套异构 API 拉到同一组 `jingni_*` 函数名下，这个产品思路是成立的；问题在于平台差异被塞进了每个函数的条件分支，缺少适配层、统一契约和错误边界。
2. **共识别 13 个阻断级（P0）、24 个语义级（P1）、12 个工程级（P2）问题。** 其中至少 3 个会让策略在启动或首次取数时直接崩溃（空值判断、未定义变量、QMT 索引用法），1 个会让进程永不退出（`jingni_main` 死循环），2 个会让 QMT 打新和定时任务失效或中断。
3. **最大的根因不是某个函数写错，而是运行模型错位。** 掘金是 `run()` + 事件回调，QMT 是 `init/after_init/handlebar` 逐 K 线驱动，PTrade 是 `initialize/handle_data/tick_data`；项目却自建了一个"墙钟 `while True` + `sleep`"的主循环来模拟交易日。这在回测中不按回测时钟走，在 QMT 中会阻塞同一线程上的所有策略，在 PTrade 中会拖慢 tick 处理。
4. **代码转换、取数窗口、可卖数量、订单回执是四个高频错误源。** 代码转换只覆盖沪深且方向不幂等；`get_field_n` 在掘金/QMT 的负偏移分支多取一条；掘金卖出用总持仓而非"总持仓−当日买入"；下单函数全部返回 `None`，没有订单号，撤单和对账无法闭环。
5. **现有 18 个函数约覆盖三家高频 API 的 10%。** 规划 63 个候选统一函数，但按"交易兼容优先"收敛为 **50 个首批核心函数、13 个延后项**：先止血（P0），再统一契约与订单闭环，再补与交易直接相关的取数与调度；L2、可转债、ETF、两融、期货期权以及财务/板块/分红等非交易能力全部转入 Backlog，默认不排期。首批目标是在股票现货的"取数—下单—撤单—持仓—账户—打新/逆回购—调度"闭环上覆盖 90% 以上。
6. **推荐交付形态：源码改为包结构，构建时生成单文件发行物。** 既解决可维护性/可测试性，又保留 QMT、PTrade 必须"复制到策略尾部"的现实约束；单文件由脚本生成，不再手工维护两份。

### 0.1 关键数字

| 指标 | 现状 | 首批目标（Phase 0—2） |
|---|---|---|
| 公开函数数 | 18 | 50 个核心统一函数（另 13 个延后，不计入首批） |
| 覆盖平台 | 3（名义上） | 3（契约级） |
| 有返回值的交易函数 | 0 / 2 | 全部返回 `OrderRef` |
| 有单元测试的函数 | 0 | 核心契约 ≥ 80% 覆盖率 |
| QMT Python 兼容 | 未验证（代码风格接近 3.8+） | 3.6 硬约束，CI 校验 |
| 单文件交付 | 手工复制 | 脚本生成 + 版本自检 |
| 已知 P0/P1/P2 | 13 / 24 / 12 | P0 清零、P1 清零、P2 收敛 |

### 0.3 已锁定决策（2026-11-19）

| 编号 | 决策 | 锁定结论 |
|---|---|---|
| D1 | 交付形态 | **包结构 + 构建单文件**：源码按 `core/adapters/api/compat/templates` 拆分，构建脚本生成 `dist/jingniflow_single.py` 与 GBK 版，保留复制粘贴体验 |
| D2 | 首批范围 | **股票现货 + 打新/逆回购**：原 P3 高级能力默认不做；P2 中与交易无直接关系的能力（板块/指数、财务、分红、通知等）一并延后 |
| D3 | QMT 兼容底线 | **Python 3.6 + GBK 硬约束**：CI 必须通过 3.6 编译与 GBK 解码；不使用 3.7+ 语法 |
| D4 | 旧接口策略 | **保留旧名 + 可选参数 + `legacy` 返回形态**：现有 `jingni_*` 签名与参数顺序不破坏；`legacy` 只保留旧返回形态，不保留已知错误行为 |
| D5 | PTrade 目标版本 | **以 `<INTERNAL_HOST>` 官方文档为准**；其他券商版本差异后置为单独兼容项 |
| D6 | 第三方依赖 | **零新增**：仅使用平台自带的 pandas/numpy，不引入 requests 等外部包 |
| D7 | 实盘安全默认 | **首次 `dry_run` + 限额默认开启**：单笔/单日限额、重复窗口、`kill_switch` 默认生效 |

> 以上决策直接约束第 5 节函数范围、第 6 节工期和第 8 节实施顺序；后文凡与本节冲突处，以本节为准。

---

## 1. 评估方法与依据

### 1.1 方法

- **逐行静态审查**：对 `jingniflow.py` 的 18 个函数、三个示例、包配置逐段阅读，按"输入—分支—取数—返回—异常"推演。
- **官方文档逐项对照**：对三家 SDK 的函数签名、参数语义、返回结构、运行限制做交叉核对；对无法从文档确认的客户端行为标注"△ 待实测"。
- **跨平台一致性推演**：同一策略意图（取最近 N 根、取当天、下单、撤单、打新、逆回购、定时）在三平台分别走一遍，比较语义差异。
- **未做**：未连接券商终端、未实盘下单、未跑三平台回测；因此涉及柜台行为、权限、版本差异的结论均标为待实测，不作为实施承诺。

### 1.2 主要依据

| 平台 | 文档 | 用途 |
|---|---|---|
| 掘金量化 | `https://www.myquant.cn/docs2/sdk/python/快速开始.html`；行情数据查询函数、交易函数、通用数据函数 | 事件模型、`history_n` 正整数约束、代码格式 `SHSE.600000`、平仓规则、交易日函数返回顺序 |
| QMT / 迅投 | `https://dict.thinktrader.net/innerApi/start_now.html?id=yzWK3j`；系统函数、行情函数、交易函数、常见问题 | Python 3.6、GBK、`subscribe=False`、`schedule_run` 重复次数、单线程阻塞、`passorder`/`quickTrade` |
| PTrade | `<INTERNAL_HOST>` | `get_history` count>0、单/多标的返回差异、`run_daily` 回测时点、逆回购 10 张门槛、打新 5 秒间隔 |

### 1.3 严重度定义

| 级别 | 定义 | 处理要求 |
|---|---|---|
| **P0 阻断** | 必然崩溃、死循环、必然错误结果、示例无法启动、构建/导入失败 | 第一批修复，修复前不建议任何人用于实盘 |
| **P1 语义** | 结果与官方语义不符、跨平台不一致、边界条件错误、特定品种/市场失效 | 第二批修复，修复前需在文档中标注限制 |
| **P2 工程** | 可维护性、可测试性、可观测性、安全、文档、版本管理 | 与 P0/P1 同步设计，随迭代收敛 |

---

## 2. 现状基线

### 2.1 文件与职责

| 文件 | 职责 | 现状评价 |
|---|---|---|
| `jingniflow.py` | 全部适配逻辑：代码转换、取数、账户/持仓、下单、打新、逆回购、时间、主循环 | 单文件约 760 行；18 个公开函数；平台分支以 `if/elif` 内联；异常基本被吞掉 |
| `examples/demo_goldminer.py` | 掘金示例：订阅 + 初始化 + 策略 + 定时 | 订阅 `1d` 却实现 `on_tick`，事件不会触发 |
| `examples/demo_qmt.py` | QMT 示例：初始化 + 定时打新/新债/逆回购 + 策略 | 缺 `import datetime`；编码声明与文件编码不符；无 `is_last_bar()` 守卫；`repeat_times` 语义错误 |
| `examples/demo_ptrade.py` | PTrade 示例：初始化 + 盘前 + 策略 + 盘后 | 结构最接近 PTrade 官方模板；但依赖复制 `jingniflow.py` 到尾部，且未设置 `trade_mode` |
| `__init__.py` | 包导出 | `from JingniFlow.jingniflow import *` 引用了不存在的包名，作为包入口导入即失败；而 `pyproject` 实际按单模块安装，包导出也不会生效 |
| `pyproject.toml` | 构建配置 | `dynamic=["version"]` 缺少 `[tool.setuptools.dynamic]`；`requires-python >=3.8` 与 QMT 3.6 冲突；`testpaths` 指向不存在的 `tests/` |
| `README.md` | 使用说明 | 函数签名与实现多处不一致（如 `jingni_order_amount` 多了 `direction`、`jingni_participate_reverse_repo` 多了两个参数） |

### 2.2 三平台真实运行模型 vs 当前实现

| 维度 | 掘金 gm | QMT | PTrade | 当前 `jingniflow` 的做法 |
|---|---|---|---|---|
| 策略入口 | `run(strategy_id, filename, mode, token, ...)` | 策略编辑器 / 模型交易，`init(C)` | `initialize(context)` | 三个示例各自定义入口，但都要求把源码复制到尾部 |
| 主事件 | `on_tick` / `on_bar`（需先订阅） | `handlebar(C)` 逐 K 线；盘中每个 tick 触发 | `handle_data(context, data)`；`tick_data` | `jingni_handle_data` 用墙钟 `while` 循环 |
| 定时 | `schedule(func, date_rule, time_rule)`；同一时间点后设定覆盖前设定 | `schedule_run(func, time_point, repeat_times, interval, name)`；`run_time`（回测无效） | `run_daily(context, func, time)`；`run_interval`（最小 3 秒，多线程） | 没有统一调度函数；示例直接调平台 API |
| 回测时钟 | `context.now` | `get_bar_timetag(barpos)` | `context.blotter.current_dt` | `datetime.now()` 墙钟 |
| 运行模式 | `context.mode`（1 实盘 / 2 回测） | `ContextInfo.do_back_test` | `is_trade()` | 读平台字段，但仅用于取数分支 |
| 账户 | `context.account()` | `get_trade_detail_data(account, type, 'account')` | `context.portfolio` | 读平台字段，返回结构不统一 |
| 下单 | `order_volume` / `order_value` / `order_percent` / `order_target_*` | `passorder(opType, orderType, account, code, prType, price, volume, strategyName, quickTrade, userOrderId, C)` | `order` / `order_value` / `order_target*` / `order_market` | `order_amount` / `order_value` 两个函数，全部返回 `None` |
| 订单查询 | `get_orders` / `get_unfinished_orders` / `get_execution_reports` | `get_trade_detail_data(..., 'order' / 'deal')` | `get_orders` / `get_open_orders` / `get_trades` | 无封装 |
| Python | 3.x（SDK 依赖） | **3.6（官方明确）** | 3.x（以官方文档为准） | 代码风格接近 3.8+，未做 3.6 校验 |
| 编码 | UTF-8 | **GBK，首行 `#coding:gbk`** | UTF-8 | `demo_qmt.py` 用 `# encoding: gbk` 但文件实际为 UTF-8 |
| 线程/阻塞 | 事件线程 | **所有策略同一线程，任何阻塞会影响全部策略** | 事件线程 + 定时器线程 | `jingni_main` 中 `sleep(3)` 长期阻塞 |

> 结论：当前实现不是"三平台适配"，而是"三平台函数名的并集 + 一个自建调度器"。平台机制差异没有下沉，导致每个函数都要处理三种时钟、三种返回结构、三种异常行为。

### 2.3 现有能力覆盖

| 能力域 | 现有函数 | 覆盖评价 |
|---|---|---|
| 历史/实时行情 | `jingni_get_history`、`jingni_get_field`、`jingni_get_field_n`、`jingni_get_current` | 仅 OHLC 与少量字段；无区间查询、无订阅管理、无 L2、无复权参数 |
| 交易 | `jingni_order_amount`、`jingni_order_value` | 无订单号、无撤单、无查询、无目标持仓、无市价单、无批量 |
| 账户/持仓 | `jingni_portfolio` | 返回平台原始对象/字典，字段不统一；未知字段会 `UnboundLocalError`；QMT 硬编码 `'stock'` 账户 |
| 打新 | `jingni_subscribe_new_stock`、`jingni_subscribe_new_bond` | gm 分支必失败；QMT `ContextInfo` 未定义；PTrade 缺间隔与黑名单；回测无守卫 |
| 逆回购 | `jingni_participate_reverse_repo` | 硬编码沪市 204001；README 参数未实现；无门槛校验 |
| 时间/日历 | `jingni_trading_dates`、`jingni_trading_times` | gm 正偏移取错；QMT 未实现；PTrade 日线时点差异未说明 |
| 代码转换 | `jingni_map_security_code` | 只覆盖沪深；方向不幂等；异常原样返回 |
| 事件/生命周期 | `jingni_trade_strategy`、`jingni_before_trading_start`、`jingni_handle_data`、`jingni_after_trading_end` | 与平台事件模型冲突；盘前/盘后靠墙钟触发 |
| 调度/控制 | `jingni_main` | 自建死循环；无跨日重置；无退出机制 |

按"高频、股票现货、日频/分钟"口径估算，当前覆盖约 **10%**；按"三家全部 API（含期货、期权、两融、ETF、L2）"口径，覆盖不足 **5%**。

---

## 3. 问题评估

### 3.1 阻断级（P0）

| ID | 位置 | 问题与触发条件 | 后果 | 证据 | 修复方向 |
|---|---|---|---|---|---|
| **P0-01** | `get_field` L372；`get_field_n` L492；`jingni_portfolio` L79—L125 | 空值判断写成 `if x is None and x.shape[0] == 0`。`x` 为 `None` 时先访问 `.shape` → `AttributeError`；`x` 非 `None` 时条件恒为 `False`，"无数据返回 0"的分支永远不进。`get_field_n` 在无数据时 `security_field_n` 从未赋值 → `UnboundLocalError`；`jingni_portfolio` 在 `security_field` 不属于四个分支时 `portfolio_data` 未赋值 → `UnboundLocalError`，QMT 无账户数据时 `[0]` 越界被 `except` 吞掉并返回 `None` | 停牌、新标的、非交易日、取数失败、未知账户字段时必崩或静默返回错误值；"返回 0/返回字段名"的设计完全失效 | 代码逻辑 ✔ | 拆成 `if x is None: ...` 与 `if len(x) == 0: ...`；返回值先初始化；未知字段抛 `ValidationError`；QMT 账户查询判空 |
| **P0-02** | L177—L181 | PTrade 分支使用 `securities_code_char_market`（多一个 `s`），实际变量是 `security_code_char_market` | 输入 `.XSHG` / `.XSHE` 时 `NameError`，被外层 `try` 吞掉后返回原代码，跨平台下单代码错误 | 代码 ✔ | 统一变量名；转换函数改为显式 `to_platform` / `from_platform`，校验失败抛错 |
| **P0-03** | L614、L656 | QMT 打新/新债调用 `passorder(..., ContextInfo)`，但函数入参是 `context_data`，模块内没有 `ContextInfo` 这个变量；两个函数也没有函数级 `try` | QMT 打新/新债必 `NameError`，定时任务直接中断，不会静默降级 | 代码 ✔ | 传 `context_data`；定时回调中 `quickTrade=2` |
| **P0-04** | L731—L758 | `jingni_main` 外层 `while True` 没有任何 `break`。15:00 后内层循环退出、盘后逻辑执行完，外层继续；此时两个时间分支都不命中，每 3 秒打印"程序等待运行" | 进程永不退出；不跨日重置状态；同一交易日内可能重复执行盘前/盘后；QMT 中直接阻塞策略线程 | 代码 ✔ | 删除自建主循环；改为平台事件骨架 + 调度器；提供 `jingni_run_once` 仅用于脚本化场景 |
| **P0-05** | L701—L715 | `jingni_handle_data` 用 `datetime.now()` 判断交易时段，并在时段内 `while True + sleep(3)` | 回测时真实时间不在 09:30—15:00，策略一次都不执行；若在窗口内，则阻塞回测引擎；QMT 单线程会阻塞所有策略；PTrade tick 处理超时可能丢 tick | 代码 + QMT FAQ ✔ | 由平台事件驱动；只保留"是否交易时段"纯函数；定时任务交给 `schedule` / `schedule_run` / `run_daily` |
| **P0-06** | L363—L369 | QMT `count<0` 分支：先用 `count = -security_count = N` 取 N 条，再取 `[security_count - 1] = [-(N+1)]`，越界；且 QMT 的 DataFrame 索引是整数时间戳 `stime`，`[-1]` 是按标签取，不是按位置取 | QMT 回测"取当天"必 `KeyError`；负偏移取数 `IndexError` | 代码 + QMT 数据结构 ✔ | 全部改用 `.iloc[-1]` / `.iloc[offset]`；按"正数 count + offset"重写取数 |
| **P0-07** | L401、L434 | 实时分支 `data[field].values`：掘金 `current()` 返回 `list[dict]`，用字符串索引直接 `TypeError`；PTrade `get_snapshot()` 取到的是 `float`，`float.values` 触发 `AttributeError`；QMT `get_full_tick` 返回 `dict[code][field]` 标量，却走同一分支 | 实时 `get_field_n` 必崩；QMT 实时返回标量而非序列，契约不一致 | 代码 + 文档结构 ✔ | 实时分支单独构造序列；统一返回 `list` / `Series`，长度固定 |
| **P0-08** | `demo_qmt.py` L1—L16 | 缺 `import datetime`；首行 `# encoding: gbk` 不是官方要求的 `#coding:gbk`，且文件实际保存为 UTF-8；`handlebar` 没有 `is_last_bar()` 守卫 | QMT 启动即 `NameError`；源码乱码；实盘对历史 K 线逐根执行策略，重复下单 | QMT 快速开始 ✔ | 重写三平台模板；GBK 保存 + CI 编码校验 + `is_last_bar` 守卫 |
| **P0-09** | `__init__.py` L3；`pyproject.toml` | `from JingniFlow.jingniflow import *` 引用了不存在的包（仓库是 `jingni-flow`，模块是 `jingniflow.py`），作为包入口导入即失败；`py-modules=["jingniflow"]` 又把它按单模块安装，包导出永远不生效。`dynamic=["version"]` 没有 `[tool.setuptools.dynamic]`；`testpaths=["tests"]` 但目录不存在 | 包入口不可用；`pip install` 构建阶段因缺少版本失败；`pytest` 直接报路径错误 | 配置 ✔ | 统一包名与目录布局；补版本来源；建立 `tests/`；CI 跑构建 |
| **P0-10** | `demo_qmt.py` L6—L10 | `schedule_run(..., repeat_times=1, interval=1天)`。官方语义是"首次触发后，按 interval 再触发 `repeat_times` 次"，`1` 表示总共 2 次，不是每日 | 打新/新债/逆回购只执行两天，之后不再执行 | QMT 系统函数 ✔ | `repeat_times=-1`；若只需一次，用 `0` |
| **P0-11** | L411、L485 | `get_field_n` 负偏移分支把 `security_count - 1` 传给取数函数：掘金/QMT 实际取 N+1 条，PTrade 取 N 条；三平台返回长度不一致 | 指标窗口整体偏移一根；跨平台回测结果不可比 | 代码 ✔ | 统一 `count=N`、`offset` 语义；三平台同一取数窗口 |
| **P0-12** | L32—L35 | 掘金 `get_next_n_trading_dates(...)[0]`：官方返回"从下一交易日起、升序排列的 n 个日期"，`[0]` 恒为 T+1，不是 T+n；`get_previous_n_trading_dates(...)[0]` 恰好是 T-n（正确） | `jingni_trading_dates(+5)` 在掘金返回 T+1，所有"未来第 n 个交易日"逻辑错位 | 掘金通用数据函数 ✔ | 正偏移取 `[-1]`；或用 `get_trading_dates` 区间切片统一实现 |
| **P0-13** | 全文件 | `global trade_mode` 与函数参数 `trade_mode` 双轨。`jingni_map_security_code`、`jingni_subscribe_new_stock`、`jingni_participate_reverse_repo` 只读全局，不接受参数 | 用户按文档调用 `jingni_main('qmt', ...)`，但全局仍是默认 `'软件名称'`，所有分支不命中，静默返回 `None` 或原代码 | 代码 ✔ | 单一上下文对象持有 `mode`；全局仅作兼容默认；所有函数显式接收或从上下文解析 |

### 3.2 语义级（P1）

| ID | 位置 | 问题与触发条件 | 后果 | 证据 | 修复方向 |
|---|---|---|---|---|---|
| **P1-01** | L237 | 掘金 `end_time` 只传 `%Y-%m-%d`（即 00:00:00）。日线的 `eob` 是交易日 00:00，可以包含当天；但 1m/60s 的 `eob` 是具体时刻，"前开后闭"会排除当天所有分钟线 | 盘中/回测取分钟线总是少当天；跨周期指标错位 | 掘金行情文档 ✔ | `end_time` 传 `%Y-%m-%d %H:%M:%S`，默认用当前 bar 时间 |
| **P1-02** | L253 | QMT 回测未传 `subscribe=False`，默认走订阅通道 | 回测依赖联网、受订阅上限影响、速度慢，结果可能混入实时行情 | QMT 快速开始 ✔ | 回测强制 `subscribe=False`；实盘按需 `True` |
| **P1-03** | L253 | QMT `end_time` 传当天日期（00:00:00），分钟线当天缺失；官方示例用 bar 时间 `%Y%m%d%H%M%S` | 当天分钟线取不到，边界不稳 | QMT 示例 ✔ | 统一 bar 时间，盘中用 `get_bar_timetag` |
| **P1-04** | L499—L524、L543—L556 | 掘金卖出固定 `PositionEffect_Close`（股票默认平昨仓），而 `jingni_order_value` 卖路径用 `position.volume`（含 `volume_today`）计算可卖量，`jingni_order_amount` 则完全不校验可卖量 | 当日买入被计入可卖，卖单被柜台拒绝；仓位越卖越错 | 掘金交易函数/数据结构 ✔ | 所有卖出入口统一走可卖量校验；`available = volume - volume_today` |
| **P1-05** | L530—L541 | `order_value`：`cash` 为 `None` 时 `security_value <= cash` 直接 `TypeError`；`price=0` 时除零；未预留手续费/印花税；未处理科创板 200 股、北交所 100 股起 1 股递增、可转债 10 张 | 资金边界、零价、特殊板块下报错或废单 | 三家文档 ✔（部分） | 统一整手规则 + 资金缓冲 + 参数校验 + 明确异常 |
| **P1-06** | L664—L686 | 逆回购硬编码 `204001`；README 声称的 `cash_ratio` / `reverse_repo_days` 未实现；未校验 10 张/1000 元门槛；深市 `131810` 未支持；回测中不可用却无守卫 | 参数无效、深市用户不可用、门槛以下废单、回测报错 | PTrade `order` 文档 ✔ | `days` / `market` / `cash_ratio` 参数化；门槛校验；回测跳过 |
| **P1-07** | L579—L585、L627—L633 | 掘金 `ipo_get_instruments(..., df=True)` 返回 `DataFrame`，`if ipo_stock:` 触发 `ValueError`（真值不明确）；随后按 `list[dict]` 遍历，实际迭代的是列名。新债分支同样 | 掘金打新/新债必失败 | 掘金新股文档 ✔ | `df=False` 或显式按 `DataFrame` 遍历 |
| **P1-08** | L573—L661 | 掘金 IPO 系列与 PTrade `ipo_stocks_order` 仅实盘/交易模块可用；回测中定时触发即报错，代码无模式守卫 | 回测日志报错、任务中断 | 掘金/PTrade 文档 ✔ | `is_backtest()` 直接跳过并提示；`dry_run` 只列标的 |
| **P1-09** | L591—L597 | PTrade 新股四个类别（`market_type=0—3`）连续调用无间隔，新债（`market_type=4`）另调；均未传 `black_stocks`；返回 `dict` 未解析状态 | 柜台限流、重复申购、失败不可见 | PTrade 文档 ✔ | 每次间隔 5 秒；黑名单；解析 `status` |
| **P1-10** | L614、L656 | QMT 在定时回调中 `quickTrade=1`；官方要求定时器/`after_init`/行情回调内用 `2` | 信号可能被丢弃，打新不成交 | QMT 常见问题 ✔ | 定时/回调内统一 `2` |
| **P1-11** | L128—L207 | 代码转换只覆盖沪深；无北交所；无输入校验（无 `.` 时 `find('.')` 返回 `-1`，下标变成 `-2`，取倒数第二位误判）；异常原样返回；PTrade `.SS` 被反转成 `.SH`，非幂等；`.XSHG` 映射到 `.SH` 而不是 `.SS`；QMT 分支全是恒等映射 | 北交所/指数/基金/债券代码错；转换失败不可感知 | 三平台代码规范 ✔ | 表驱动 + 显式方向 + 正则校验 + 失败抛 `ValidationError` |
| **P1-12** | L210—L229 | `get_current` 在 PTrade/QMT 分支忽略 `security_field`；三平台返回结构不同（`list[dict]` / `dict[code][field]` / `dict[code][field]`） | "统一接口"名不副实，换平台就要改策略 | 代码 ✔ | 统一 tick `dict`，字段映射后返回 |
| **P1-13** | L69—L72 | `trading_times` 的 PTrade 分支始终用 `datetime.now()`，回测中也返回墙钟；掘金返回 `context.now`（回测为回测时钟）；QMT 返回 bar 时间。注释却统一称"实时模式本地时间、回测模式回测时间" | 策略据此判断"现在几点"在 PTrade 回测中必错 | 代码 + 文档 ✔ | 明确"平台时钟"；另提供 `jingni_wall_now()`；回测禁用墙钟 |
| **P1-14** | L50—L55 | QMT 分支的 `±n` 交易日偏移直接返回 `None`，既未实现也未声明 | QMT 日期偏移不可用，调用方拿到 `None` 后二次报错 | QMT 系统函数 ✔ | 用 `get_trading_dates(stockcode, '', '', count, '1d')` 切片；或在 `after_init` 后可用 |
| **P1-15** | L379—L496 | 取数窗口三平台不一致：掘金/QMT 负偏移 N+1 条，PTrade N 条；实时分支掘金/PTrade 抛错、QMT 返回标量 | 同一策略三平台指标窗口不同，回测不可比 | 代码 ✔ | 统一 `count` 正数 + `offset`；所有分支返回同构序列 |
| **P1-16** | L237、L242、L253 | 复权硬编码：掘金 `ADJUST_PREV`、PTrade `fq='pre'`、QMT `dividend_type='front'`；无法选择不复权/后复权/等比前复权 | 回测口径不可配置，跨平台复权方式可能不同 | 三家文档 ✔ | `adjust` 参数 + 映射表；默认前复权但显式记录 |
| **P1-17** | 全文件 | 字段名三平台不同（`close` / `price` / `last_px` / `lastPrice`；`amount` / `money`）；频率写法不同（`60s` / `1h` / `60m` / `mo`）；无映射表；`fields='open,close'` 被 QMT 当成单个字段 | 取数字段为空/错列 | 三家文档 ✔ | 字段/频率映射表 + 字符串解析器 |
| **P1-18** | L499—L522 | 数量单位不一致：掘金股、PTrade 股/可转债张、QMT 股/手；`order_amount` 直接透传 | 可转债/期货数量 10 倍或 100 倍偏差 | 三家文档 ✔ | 增加 `unit` 参数与换算；股票默认股，可转债张，期货手 |
| **P1-19** | L701—L758 + 示例 | 定时语义差异：掘金同一时间点后设定覆盖前设定；QMT `run_time` 回测无效；PTrade 日线回测 `run_daily` 一律 15:00，分钟回测限 09:31—11:30 / 13:00—15:00 | 三平台同一策略执行时点不同，盘前/盘后逻辑错位 | 三家文档 ✔ | 统一调度抽象 + 单任务分发 + 能力说明 |
| **P1-20** | `demo_goldminer.py` L9 | 只订阅 `1d`，却定义 `on_tick` | tick 事件永不触发，示例看似运行实则无信号 | 掘金订阅文档 ✔ | 订阅 `tick` 或删除 `on_tick` |
| **P1-21** | L610—L614 | QMT 打新用 `opType=23` / `orderType=1101`，是否适用于新股申购未复核；`account` 依赖全局 | 可能废单或下成普通买入 | 待实测 △ | 按官方新股申购示例核对 `opType` / `prType` / `quickTrade` |
| **P1-22** | L237 | 掘金 `history_n` 只支持单标的，代码 `str(security_code)` 把 `list` 变成字符串 `"['600000.SH']"` | 传列表时查不到数据 | 掘金文档 ✔ | 单标的校验或循环；多标的在统一层展开 |
| **P1-23** | L242 | PTrade `get_history`：单标的（`str`）返回"字段列"，多标的（`list`，即使只有一个）返回"代码列"；代码固定按字段列取值 | 传列表时 `KeyError`；单元素列表也触发 | PTrade 文档 ✔ | 统一单标的/多标的返回结构；内部始终按标的循环 |
| **P1-24** | L56、L121、L204、L225、L254 | 关键路径 `except Exception: print(...)` 后返回 `None` / 原值；`NameError`、`TypeError`、网络错误、柜台拒绝不可区分 | 故障静默，二次错误难排查；P0-02/P0-03 就是这样被掩盖的 | 代码 ✔ | 错误分类；新接口默认抛出；旧接口 `legacy=True` 才降级返回 |

### 3.3 工程级（P2）

| ID | 问题 | 影响 | 修复方向 |
|---|---|---|---|
| **P2-01** | 交易函数无返回值、无订单号 | 无法撤单、无法对账、无法做目标持仓和幂等 | 统一 `OrderRef`；掘金取 `cl_ord_id`、PTrade 取返回 id、QMT 用投资备注关联 |
| **P2-02** | 无日志、无错误码、无回调 | 实盘故障只能看 `print`；无法接入告警 | `jingni_log` + `JingniError` 体系 + `on_error` 回调 |
| **P2-03** | 账户类型硬编码 `'stock'`；依赖全局 `account` | 两融、期货、多账户不可用 | `jingni_set_account(account_id, account_type, market)`；适配器持有账户上下文 |
| **P2-04** | 无风控层 | 可能超仓、超资金、重复下单、涨停买入/跌停卖出 | 下单前统一校验：整手、可用、资金缓冲、涨跌停、停牌、单笔上限、日累计上限、去重窗口 |
| **P2-05** | 无测试、无 CI；`pytest` 指向空目录 | 每次改动靠人工三平台试，回归不可控 | 假适配器 + 契约测试 + Golden 数据 + 三平台冒烟清单 + CI |
| **P2-06** | 无类型注解/docstring；README 与实现不一致 | 使用者按文档调用即报错 | 统一 docstring 模板；README 由函数表生成或校验 |
| **P2-07** | 字段映射重复 6 处；代码转换有死分支；魔法数字（`1010`、`204001`、`1000`、`10`） | 改一处漏五处 | 表驱动；常量集中到 `contract.py` |
| **P2-08** | 逐字段、逐 bar 重复请求；无缓存 | 分钟级策略 API 调用量成倍增加，易触发限流 | 每 bar 缓存 instrument/history；一次取多字段；批量查询 |
| **P2-09** | 单文件复制导致版本碎片化；`requires-python >=3.8` 与 QMT 3.6 冲突 | 用户手里的副本与仓库不一致；QMT 无法安装 | 包结构 + `build_single.py` 生成；`jingni_version()` 启动自检 |
| **P2-10** | 无能力声明/降级策略，不支持时静默 `None` | 用户不知道某平台不支持某功能 | `jingni_capabilities()` + `UnsupportedFeature` + 文档矩阵 |
| **P2-11** | 无状态持久化（委托注册表、去重、当日计数） | 进程重启后无法对账；重复下单 | `jingni_export_state` / `jingni_load_state`；QMT 用模块级字典而非 `ContextInfo` |
| **P2-12** | 无迁移指南、无变更日志、无示例矩阵 | 升级破坏旧策略 | `CHANGELOG`、`MIGRATION.md`、三平台最小示例 |

### 3.4 根因分析

1. **平台适配做成了函数内分支，而不是适配器。** 每个函数都要同时理解三套 API、三种返回结构、三种异常，导致字段映射重复、边界条件遗漏、修复无法收敛。
2. **事件驱动做成了墙钟主循环。** `jingni_main` 试图用一个 `while True` 模拟"盘前—盘中—盘后"，与三家引擎的时钟和线程模型直接冲突；这是 P0-04/P0-05 以及盘前盘后错位的共同根因。
3. **没有统一契约。** 代码格式、频率、字段、数量单位、时间语义、返回结构、错误类型都没有定义，调用方只能"按平台猜"。
4. **以"能跑"为目标，异常全部吞掉。** 这让 P0-02、P0-03 这类 `NameError` 变成静默失败，问题被推迟到实盘才暴露。
5. **交付方式倒逼单文件。** QMT/PTrade 不能 `pip install`，只能复制源码；于是仓库里没有包结构、没有测试、没有构建，形成"复制—改—再复制"的循环。

### 3.5 修复顺序与依赖

| 批次 | 内容 | 依赖 | 建议工期 |
|---|---|---|---|
| **Wave 1 纯逻辑止血** | P0-01、P0-02、P0-03、P0-06、P0-07、P0-11、P0-12、P0-13 | 无 | 2—3 人日 |
| **Wave 2 运行模型重写** | P0-04、P0-05、P0-08、P0-10，配套三平台模板 | Wave 1 的上下文与适配器骨架 | 2—3 人日 |
| **Wave 3 构建与包结构** | P0-09、P2-05、P2-09 | Wave 2 的模板 | 1—2 人日 |
| **Wave 4 语义对齐** | P1-01—P1-24 | Wave 1—3 | 5—7 人日 |
| **Wave 5 工程收敛** | P2 全部 | 持续 | 随迭代 |

> Wave 1—3 合计约 5—8 人日，对应 Phase 0 的主体；Wave 4 加集成、三平台冒烟约 8—10 人日，对应 Phase 1。两者不是重复计算，而是"P0 止血"与"P1 语义对齐 + 订单闭环"的边界。

> 不建议先做功能扩展。当前状态下每新增一个函数，都会复制一套平台分支和异常吞噬；先统一契约，扩展成本会下降一个数量级。

---

## 4. 修复方案设计（不写代码）

### 4.1 目标架构

```
┌──────────────────────────────────────────────────────────────┐
│  策略层：三平台模板（goldminer / qmt / ptrade）              │
│  - 只负责平台入口、事件绑定、调用 jingni_* 统一函数          │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  统一 API 层：jingniflow/api/*.py                            │
│  runtime / market / instrument / trade / account / events     │
│  ipo / repo / risk / diagnose                                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  核心层：core/*.py                                           │
│  contract（代码/频率/字段/枚举/返回结构）                    │
│  registry（适配器注册与能力探测）                            │
│  risk（下单前校验）  state（委托注册表/去重/持久化）          │
│  errors（异常体系）  config（账户/风控/日志配置）             │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  适配层：adapters/*.py                                       │
│  goldminer / qmt / ptrade                                    │
│  每个适配器只做：原生 API 调用、字段映射、异常翻译           │
└──────────────────────────┬───────────────────────────────────┘
                           │
              掘金 gm.api ／ QMT 内置 Python ／ PTrade API
```

**目录结构建议**

```
jingniflow/
├── __init__.py                 # 只导出公共 API 与版本
├── core/
│   ├── contract.py             # 代码/频率/字段/状态枚举/返回结构
│   ├── errors.py               # JingniError 体系
│   ├── config.py               # 账户、风控、日志、运行模式
│   ├── registry.py             # 适配器注册、能力探测
│   ├── risk.py                 # 下单前校验、整手、资金缓冲
│   └── state.py                # 委托注册表、去重、导入导出
├── adapters/
│   ├── base.py                 # BaseAdapter 接口
│   ├── goldminer.py
│   ├── qmt.py
│   └── ptrade.py
├── api/
│   ├── runtime.py              # setup/now/schedule/interval
│   ├── market.py               # history/range/tick/field/subscribe
│   ├── instrument.py           # 标的/日历/板块/指数/财务
│   ├── trade.py                # 下单/撤单/查询/目标持仓
│   ├── account.py              # 账户/持仓/资产
│   ├── events.py               # 订单/成交/账户/错误回调
│   ├── ipo.py                  # 打新/新债
│   ├── repo.py                 # 逆回购
│   └── diagnose.py             # capabilities/version/self-check
├── compat/
│   └── legacy.py               # v0.1.x 旧函数名与旧签名适配
├── templates/
│   ├── goldminer_main.py
│   ├── qmt_main.py
│   └── ptrade_main.py

dist/
└── jingniflow_single.py        # 构建产物，供复制到策略尾部
tools/
└── build_single.py             # 合并模块、剥离 import、校验 3.6/GBK
tests/
├── unit/
├── contract/
├── golden/
└── smoke/
```

**适配器接口（设计约束）**

| 方法 | 职责 | 备注 |
|---|---|---|
| `name` / `version` | 平台标识与适配器版本 | `jingni_version()` 输出 |
| `now()` | 返回平台时钟（回测用回测时钟） | 禁止 `datetime.now()` |
| `is_backtest()` | 运行模式判断 | 决定取数通道与打新守卫 |
| `get_bars(code, freq, count, end_time, fields, adjust)` | 统一 K 线 | 三平台返回同构 `DataFrame` |
| `get_tick(codes)` | 统一快照 | 返回统一字段 `dict` |
| `subscribe(codes, freq, callback)` / `unsubscribe` | 订阅管理 | 平台能力差异显式声明 |
| `order(request)` | 下单 | 返回 `OrderRef` |
| `cancel(ref)` / `cancel_all()` | 撤单 | 订单号/备注关联 |
| `get_orders(filter)` / `get_trades(ref)` | 委托/成交查询 | 统一状态枚举 |
| `get_positions()` / `get_account()` | 持仓/资产 | 统一可卖量语义 |
| `schedule(func, time_rule, date_rule)` | 定时注册 | 平台差异下沉 |
| `get_instruments(codes)` | 标的元数据 | 名称/板块/整手/涨跌停/上市日/状态 |
| `get_trading_dates(start, end)` | 交易日历 | 返回 `YYYY-MM-DD` 列表 |
| `capabilities()` | 能力矩阵 | 供 `jingni_capabilities()` 汇总 |

### 4.2 统一契约

#### 4.2.1 证券代码

- **规范格式**：`600000.SH`、`000001.SZ`、`430047.BJ`、`204001.SH`、`110043.SH`。
- **可接受输入**：`600000.SH`、`600000.SS`、`SHSE.600000`、`SZSE.000001`、`600000.XSHG`、`000001.XSHE`、纯 6 位数字（仅当能唯一推断市场时）。
- **输出**：统一函数一律返回规范格式；适配器内部再转平台格式。
- **规则**：
  - 显式 `to_platform(code, platform)` 与 `from_platform(code, platform)`，不再用"双向自动猜"。
  - 无法推断市场、代码长度不符、交易所不支持 → `ValidationError`，不再原样返回。
  - 北交所 `BJ`、可转债 `11/12/13` 开头、逆回购 `204/131` 开头、ETF/LOF `5/1` 开头，均纳入测试矩阵。

#### 4.2.2 频率

| 统一频率 | 掘金 | QMT | PTrade | 说明 |
|---|---|---|---|---|
| `tick` | `tick` | `tick` | `tick` / `tick_data` | 实时快照/逐笔 |
| `1m` | `60s` | `1m` | `1m` | |
| `5m` | `300s` | `5m` | `5m` | |
| `15m` | `900s` | `15m` | `15m` | |
| `30m` | `1800s` | `30m` | `30m` | |
| `60m` | `3600s` | `1h` | `60m` | |
| `1d` | `1d` | `1d` | `1d` | 默认 |
| `1w` | 需用 `1d` 合成（若 SDK 不支持） | `1w` | `1w` / `weekly` | 标记为"合成" |
| `1M` | 需用 `1d` 合成 | `1mon` | `mo` / `monthly` | 标记为"合成" |

> 原则：平台原生支持就直接映射；不支持就显式标注"合成"并返回 `synthetic=True` 的元信息，不静默改变频率。

#### 4.2.3 字段

| 统一字段 | 掘金 | QMT | PTrade | 备注 |
|---|---|---|---|---|
| `open` | `open` | `open` | `open` | |
| `high` | `high` | `high` | `high` | |
| `low` | `low` | `low` | `low` | |
| `close` | `close` | `close` | `close` | |
| `volume` | `volume` | `volume` | `volume` | 股/手需按品种换算 |
| `amount` | `amount` | `amount` | `money` | 成交额 |
| `preclose` | 待核对（`pre_close` / 快照字段） | `preClose` | `preclose` | 日线可用 |
| `limit_up` | 标的详情/快照 | `get_instrument_detail` 的 `UpStopPrice` | `high_limit` | 日线可用 |
| `limit_down` | 标的详情/快照 | `DownStopPrice` | `low_limit` | 日线可用 |
| `suspend` | 停牌标志 | `suspendFlag` / 状态 | `get_stock_status` | 停牌日处理 |
| `open_interest` | 期货字段 | `openInterest` | 期货字段 | 延后 |

> 字段解析器：支持 `fields='open,close'`、`fields=['open','close']`、`fields=None`；统一转成列表后再映射，禁止把逗号字符串直接传给 QMT。

#### 4.2.4 数量、时间与取数窗口

- **`count`**：正整数，表示"最近 N 根"，包含 `end_time` 所在 bar。
- **`offset`**：`0` 表示最新一根，`1` 表示上一根，依此类推；替代原来的 `security_count` 负数约定。
- **`end_time`**：bar 的结束时间；日线用 `YYYY-MM-DD`，分钟线用 `YYYY-MM-DD HH:MM:SS`；默认取平台当前 bar 时间，不使用墙钟。
- **兼容旧约定**：`security_count=0` 等价于 `count=1, offset=0`；`security_count=-n` 等价于 `count=n, offset=n-1`（仅旧接口内部转换，文档标注 deprecated）。
- **返回长度**：任何分支都返回恰好 `count` 条（数据不足时返回实际条数并带 `truncated=True` 元信息），不允许掘金/QMT 多一条、PTrade 少一条。

#### 4.2.5 返回结构

**Bar（`DataFrame`）**

| 项 | 约定 |
|---|---|
| 索引 | `DatetimeIndex`，名 `datetime` |
| 列 | 统一字段名，顺序固定 `open, high, low, close, volume, amount, preclose, limit_up, limit_down, suspend` |
| 元信息 | 不用 `df.attrs`（旧 pandas 不保证），另返回 `BarSet` 轻量对象或 `meta` 字典 |
| 空数据 | 返回空 `DataFrame`（列齐全），不返回 `None` |

**Tick（`dict`）**

```
{
  'code': '600000.SH', 'datetime': datetime, 'last': float,
  'open': float, 'high': float, 'low': float, 'preclose': float,
  'volume': float, 'amount': float,
  'bid1'..'bid5', 'ask1'..'ask5', 'bid_vol1'..'bid_vol5', 'ask_vol1'..'ask_vol5',
  'limit_up': float, 'limit_down': float, 'suspend': bool
}
```

**Order（`dict`）**

| 字段 | 说明 |
|---|---|
| `order_ref` | 统一引用：`{'platform': 'qmt', 'id': '...', 'remark': '...'}` |
| `platform_order_id` | 平台委托号（QMT 为 `m_strOrderSysID`，PTrade 为返回 id，掘金为 `cl_ord_id`） |
| `code` / `side` / `price` / `amount` / `filled` | 统一字段 |
| `status` / `status_code` | 统一枚举 + 平台原始码 |
| `created_at` / `updated_at` | 平台时间 |
| `remark` | 投资备注（QMT 关联键） |
| `raw` | 平台原始对象/字典，保留排查能力 |

**Position（`dict`）**：`code, amount, available, cost, market_value, pnl, raw`。
**Account（`dict`）**：`total_asset, cash, available, market_value, frozen, pnl, raw`。

#### 4.2.6 订单状态枚举

| 统一状态 | 含义 | 掘金 | QMT | PTrade |
|---|---|---|---|---|
| `PENDING` | 已报/待成交 | `OrderStatus_New` / `PendingNew` | 待报/已报 | `status='2'` 等 |
| `PARTIAL` | 部分成交 | `OrderStatus_PartiallyFilled` | 部分成交 | 部分成交 |
| `FILLED` | 全部成交 | `OrderStatus_Filled` | 全部成交 | 全部成交 |
| `CANCELED` | 已撤 | `OrderStatus_Canceled` | 已撤 | 已撤 |
| `REJECTED` | 废单/拒绝 | `OrderStatus_Rejected` | 废单 | 废单 |
| `EXPIRED` | 过期 | `OrderStatus_Expired` | 过期 | 过期 |
| `UNKNOWN` | 未识别 | 兜底 | 兜底 | 兜底 |

> 平台状态码差异较大，实施时建立"平台码 → 统一枚举"表，并在 `raw` 中保留原始码；未识别一律 `UNKNOWN`，不猜测。

#### 4.2.7 错误体系

```
JingniError
├── ValidationError        # 参数/代码/频率/数量非法
├── UnsupportedFeature     # 平台不支持（含 platform/feature）
├── DataUnavailable        # 取数失败/数据不足
├── OrderRejected          # 柜台/平台拒单（含 reason/raw）
└── PlatformError          # 平台 API 异常（含原始异常）
```

- 新接口默认 `strict=True`，异常向上抛；旧接口通过 `compat/legacy.py` 保留旧签名与返回形态（`None`/原值），但异常必须记录错误码，不再静默；P0/P1 的已知错误不因 `legacy` 回退。
- 禁止 `except Exception: pass`；至少 `except Exception as exc: raise PlatformError(...) from exc`。

### 4.3 关键修复设计

#### A. 空值与索引（P0-01 / P0-06 / P0-07 / P0-11 / P1-15）

- 统一取数内核 `_get_bars`：先校验 `count > 0`、`offset >= 0`，再按平台取 `count + offset` 条，最后用 `.iloc[-(count + offset):(-offset or None)]` 截取目标窗口（`offset=0` 时取末尾 `count` 条，`offset=1` 时排除最后一根）。
- 统一用 `.iloc`，禁止 `df[-1]` / `series[-1]`；QMT 的整数时间索引、PTrade 的日期索引都不再影响位置语义。
- 空数据统一返回空 `DataFrame`/空列表，字段齐全；不再返回 `None` 或字段名字符串。
- 实时分支单独实现：掘金 `list[dict]` → 取 `[0]`；QMT/PTrade `dict[code][field]` → 直接取值；统一构造成 `list` 或标量。

#### B. 代码转换（P0-02 / P1-11）

- 表驱动：`canonical → {gm: 'SHSE.600000', qmt: '600000.SH', ptrade: '600000.SS'}`。
- 输入解析：正则 `^(\d{6})\.(SH|SZ|BJ|SS|XSHG|XSHE)$` 或 `^(SHSE|SZSE|BSE)\.(\d{6})$`。纯 6 位只在无歧义时推断（`6` → SH，`0/3` → SZ，`4/8` → BJ）；`1/5/9` 及 `11/12/13`、`204/131` 等存在沪深或品种歧义，必须带交易所后缀，否则抛 `ValidationError`。
- 幂等：`to_platform(to_platform(code))` 不再翻转；`from_platform` 单独负责反向。
- 失败可感知：`ValidationError`，不再 `print` 后返回原值。

#### C. 历史行情（P1-01 / P1-02 / P1-03 / P1-16 / P1-17 / P1-22 / P1-23）

- 一个内核 `get_bars(code, freq, count, end_time, fields, adjust)`：
  - 掘金：`history_n(symbol=to_gm(code), frequency=map_freq, count=count, end_time=fmt(end_time), fields=fields, adjust=map_adjust, df=True)`；分钟线 `end_time` 带时分秒。
  - QMT：`get_market_data_ex(fields, [code], period=map_freq, start_time='', end_time=fmt(end_time), count=count, dividend_type=map_adjust, fill_data=True, subscribe=not is_backtest())`；回测强制 `False`。
  - PTrade：`get_history(count, map_freq, fields, security_list=code, fq=map_adjust, include=False)`；单标的始终传 `str`，多标的在统一层循环，避免"单元素列表也当多标的"的坑。
- 多标的一律在统一层展开为单标的循环（或批量接口），返回 `dict[code, DataFrame]`；不把列表直接塞给只支持单标的的平台。
- `adjust` 支持 `none / pre / post / dyn_pre`；默认 `pre`，并在返回元信息中记录。
- 当天数据：掘金日线 18:00 后入库，盘中取"当天日线"可能拿到昨日；统一层在实盘盘中优先用快照合成当日 bar，或明确返回 `is_stale=True` 提示。

#### D. 下单与订单闭环（P1-04 / P1-05 / P1-18 / P2-01 / P2-03 / P2-04）

- 统一 `OrderRequest`：`code, side, amount, price, order_type, unit, remark, target`。
- 统一 `OrderRef`：掘金 `cl_ord_id`；PTrade 返回值；QMT 生成短 `remark`（≤24 字符）并写入投资备注，`get_trade_detail_data(..., 'order')` 按 `m_strRemark` 关联。QMT 的 `passorder` 不返回委托号，这是必须接受的平台限制。
- 可卖量：掘金 `volume - volume_today`；QMT `m_nCanUseVolume`；PTrade `enable_amount`；统一为 `available`。
- 整手/门槛：股票 100 股（科创板 200 股、北交所 100 股起 1 股递增）；可转债 10 张；逆回购 10 张/1000 元；期货 1 手。统一 `calc_lot(code, amount)`，超出可用/资金时抛 `OrderRejected` 或按配置裁剪。
- 资金缓冲：买入按 `price * amount * (1 + fee_buffer)` 校验，默认 `fee_buffer=0.002`（可配置），避免"差几毛钱废单"。
- 市价单：掘金 `OrderType_Market`（沪市需传保护价）；QMT `prType=42`（沪市市价，价格填保护价）/ `5`（最新价）/ `14`（对手价）；PTrade `order_market(type=0..5)`；统一 `market_type` 参数并逐平台映射。
- 目标持仓：掘金/PTrade 有原生 `order_target_*`；QMT 无原生，需"当前持仓 + 在途委托 → 差额下单"的引擎，带超时撤单和重复抑制。这是 Phase 1 的重点。

#### E. 打新与逆回购（P1-06 / P1-07 / P1-08 / P1-09 / P1-10 / P1-21）

- 打新统一入口 `jingni_subscribe_new_stock(markets=None, blacklist=None, interval=5, dry_run=False)`：
  - 掘金：`ipo_get_instruments(sec_type1, df=False)` → 过滤黑名单 → `ipo_get_quota` → `ipo_buy`；仅实盘，回测/仿真直接跳过。
  - QMT：`get_ipo_data('STOCK')` → 过滤 → `passorder(opType, 1101, account, code, prType, price, volume, '', 2, remark, context)`；`quickTrade=2`；`opType`/`prType` 以官方新股示例为准（待实测）。
  - PTrade：按 `market_type` 分别调用 `ipo_stocks_order(market_type, black_stocks)`，每次 `sleep(5)`；解析返回 `dict` 的 `status`。
- 逆回购统一入口 `jingni_participate_reverse_repo(cash_ratio=1.0, days=1, market='SH', min_amount=1000)`：
  - 标的表：沪市 1 天 `204001`、2 天 `204002`、3 天 `204003`、4 天 `204004`、7 天 `204007`；深市 `131810`（1 天）等。
  - 数量：`qty = int(cash * cash_ratio / 1000) * 10`；`qty < 10` 时不报（不足 1000 元），不再用 `max(10, ...)` 强制凑单；价格取当前利率/最新价。
  - 回测跳过；实盘按 `position_effect=Close`（卖出方向）。
- 打新/逆回购都输出 `dry_run` 模式：只打印标的、额度、数量、预估金额，不报单，便于首次联调。

#### F. 运行模型与调度（P0-04 / P0-05 / P0-08 / P0-10 / P1-19）

- 三平台模板各自使用原生事件，不再自建主循环：

| 平台 | 模板入口 | 盘前 | 盘中 | 盘后 |
|---|---|---|---|---|
| 掘金 | `init` + `run` | `schedule` 09:15 | `on_bar` / `on_tick` | `schedule` 15:10 |
| QMT | `init` / `after_init` / `handlebar` / `stop` | `schedule_run` 09:15，`repeat_times=-1` | `handlebar` + `is_last_bar()` 守卫 | `schedule_run` 15:10 |
| PTrade | `initialize` / `before_trading_start` / `handle_data` / `after_trading_end` | 原生 `before_trading_start` | `handle_data` / `tick_data` | 原生 `after_trading_end` |

- 统一 `jingni_schedule(func, time_rule='09:31', date_rule='1d', name=None)`：
  - 掘金：内部用**一个** `schedule` 任务 + 自维护任务表，避免"同一时间点后设定覆盖前设定"。
  - QMT：`schedule_run(func, time_point, repeat_times=-1, interval=timedelta(days=1), name=name)`。
  - PTrade：`run_daily(context, func, time=time_rule)`；文档注明"日线回测固定 15:00、分钟回测限 09:31—11:30 / 13:00—15:00"。
- `jingni_run_interval(func, seconds=3)`：
  - 掘金 `timer`；QMT `run_time`（**回测无效**，显式提示）；PTrade `run_interval`（最小 3 秒，多线程，注意共享状态加锁）。
- 禁止在策略线程中 `sleep`；需要等待用调度器/状态机。

#### G. 账户、持仓与风控（P2-03 / P2-04 / P2-11）

- `jingni_set_account(account_id=None, account_type='stock', market='SH')`：QMT 设置 `account` / `accountType`；PTrade 用 `context`；掘金用 `set_account` / `context.account()`。
- `jingni_set_risk(config)`：`max_order_value`、`max_order_amount`、`max_daily_turnover`、`max_positions`、`price_limit_check`、`duplicate_window_sec`、`allow_st`、`allow_suspend`、`fee_buffer`、`dry_run`。
- `jingni_check_order` 返回 `(ok, reason)`；所有下单入口默认先过风控；`dry_run=True` 时只记录不报单。
- 委托注册表 `state.py`：内存字典 + 可选 JSON 持久化；QMT 不放 `ContextInfo`（会被逐 K 线回退），放模块级对象。

### 4.4 兼容性红线

| 红线 | 要求 | 校验方式 |
|---|---|---|
| QMT Python 3.6 | 不用 `dataclasses`、海象运算符、`from __future__ import annotations`、`typing.Protocol`、位置-only 参数、`dict` 合并运算符；f-string 可用但统一用 `.format`/`%` 降低差异 | CI 用 3.6 解释器 `py_compile` + `ast` 扫描禁用节点 |
| QMT GBK | 模板首行 `#coding:gbk`，文件以 GBK 保存；字符串不含 GBK 无法编码的字符 | CI 以 `gbk` 解码模板，失败即阻断 |
| QMT 单线程 | 策略内禁止 `sleep`、死循环、同步网络请求、大文件 IO | 静态扫描 `sleep` / `while True`；代码评审 |
| QMT ContextInfo 逐 K 线回退 | 订单状态、去重表、计数器放模块级全局，不放 `ContextInfo` 属性 | 代码评审 + 冒烟 |
| PTrade tick 处理 | `tick_data` 内只做轻量计算；重活放 `run_interval` 或盘后 | 冒烟时延测量 |
| 无第三方依赖 | 除平台自带 `pandas` / `numpy` 外不引入新依赖；单文件必须自包含 | 构建产物 import 扫描 |
| 旧接口兼容 | 旧 `jingni_*` 名称、参数顺序、默认值不变；`legacy=True` 只保留旧返回形态，已知错误修复不回退 | 兼容层回归用例；三个现有示例不改代码可运行 |
| 实盘安全 | 首次实盘默认 `dry_run`；单笔/单日限额默认开启；提供 `jingni_kill_switch()` | 冒烟 + 配置检查 |

### 4.5 验收标准

| 维度 | 验收项 | 通过标准 |
|---|---|---|
| 启动 | 三平台模板可启动 | 掘金仿真、QMT 模拟信号/回测、PTrade 回测均无异常退出；日志打印适配器名、版本、能力矩阵 |
| 取数 | `count` 语义 | 请求 5 条，三平台均返回 5 条；最后一根为 `end_time` 所在 bar；分钟线 10:00 查询包含 09:59 |
| 取数 | 空数据 | 停牌/非交易日/不存在代码返回空结构，不抛 `AttributeError`，不返回字段名 |
| 代码 | 转换矩阵 | 30 个代码用例（沪深北/指数/基金/债券/回购/错误输入）全部通过；幂等 |
| 交易 | 订单闭环 | 下单返回 `OrderRef`；`get_orders` 能查到；`cancel` 能撤；状态枚举正确 |
| 交易 | 可卖量 | 当日买入后卖出，掘金/QMT/PTrade 均按可用量校验，不出现"总持仓可卖"导致的废单 |
| 交易 | 目标持仓 | QMT 差额引擎在部分成交/在途/拒单下收敛到目标，重复下单窗口生效 |
| 打新 | 干跑 | `dry_run=True` 能列出三平台当日新股/新债、额度、黑名单过滤结果，不报单 |
| 逆回购 | 门槛/天数 | 1000 元 → 10 张；999 元 → 0 张并提示；1/2/3/4/7 天标的映射正确 |
| 调度 | 每日任务 | QMT `repeat_times=-1` 连续 3 个交易日触发；PTrade 日线回测在 15:00 触发并在文档中注明 |
| 静态 | 3.6/GBK | 单文件在 3.6 下编译通过；QMT 模板 GBK 解码通过 |
| 测试 | 覆盖率 | 核心契约（代码/频率/字段/整手/状态/风控）单测覆盖率 ≥ 80% |

---

## 5. 功能扩展规划

### 5.1 设计原则

1. **能力可声明，不支持可预期。** 每个函数在三平台的支持级别写入 `capabilities()`；不支持时抛 `UnsupportedFeature`，不返回 `None`。
2. **统一函数只做"语义统一"，不抹平平台特性。** 平台特有、且无法等价的能力（如 QMT 算法单、PTrade 盘后固定价）单独建函数，不硬塞进通用函数。
3. **先高频后长尾。** 股票现货的"取数—下单—查询—撤单—持仓—账户—调度"优先；期货、期权、两融、ETF、L2 默认进入 Backlog，不排期。
4. **交易闭环优先。** 首批只保留直接支撑股票现货交易的函数；财务、板块、分红、通知、状态导出等非交易能力延后，避免"为兼容而兼容"。
5. **向后兼容。** 旧 `jingni_*` 名称保留，新增参数给默认值；破坏性变更走大版本 + 迁移指南。
6. **单一事实来源。** 函数签名、参数、返回、支持级别只写在代码 docstring + 契约表，README 由构建脚本生成或校验，避免再次出现"文档与实现不一致"。

### 5.2 三平台可封装能力盘点

| 能力域 | 掘金 gm | QMT 内置 | PTrade | 现状 | 排期 |
|---|---|---|---|---|---|
| 历史 K 线 | `history` / `history_n` | `get_market_data_ex` / `get_local_data` | `get_history` / `get_price` | 部分封装 | P1 |
| 实时快照 | `current` / `current_price` | `get_full_tick` | `get_snapshot` | 部分封装 | P1 |
| 订阅推送 | `subscribe` / `unsubscribe` + `on_tick` / `on_bar` | `subscribe_quote` / `subscribe_whole_quote` / `unsubscribe_quote` | `set_universe` + `tick_data` | 未封装 | P2（交易相关） |
| L2 | `get_history_l2ticks` / `l2bars` / `l2transactions` / `l2orders` | `l2quote` / `l2order` / `l2transaction` / `l2orderqueue` | `get_individual_entrust` / `get_individual_transcation` / `get_tick_direction` | 未封装 | 延后 |
| 标的元数据 | `get_instruments` / `get_symbol_infos` / `get_history_instruments` | `get_instrument_detail` / `get_stock_name` / `get_open_date` | `get_stock_info` / `get_stock_name` / `get_stock_status` | 未封装 | P1 |
| 板块/指数 | `get_symbols` / 板块接口 | `get_stock_list_in_sector` / `create_sector` 系列 | `get_index_stocks` / `get_industry_stocks` / `get_stock_blocks` / `get_Ashares` | 未封装 | 延后（非交易） |
| 财务数据 | `get_fundamentals`（待核对表名） | `get_financial_data` / `get_raw_financial_data` | `get_fundamentals` | 未封装 | 延后（非交易） |
| 交易日历 | `get_trading_dates` / `get_previous_trading_date` / `get_next_trading_date` / `get_previous_n...` / `get_next_n...` | `ContextInfo.get_trading_dates`（`after_init`/`handlebar`） | `get_trading_day` / `get_all_trades_days` / `get_trade_days` | 部分封装 | P1 |
| 下单 | `order_volume` / `order_value` / `order_percent` / `order_target_*` / `order_batch` | `passorder` / `algo_passorder` / `smart_algo_passorder` | `order` / `order_value` / `order_target` / `order_target_value` / `order_market` / `order_tick` | 部分封装 | P0 |
| 撤单/查询 | `order_cancel` / `order_cancel_all` / `order_close_all` / `get_orders` / `get_unfinished_orders` / `get_execution_reports` | `cancel` / `get_trade_detail_data(order/deal)` / `order_callback` / `deal_callback` / `get_last_order_id` | `cancel_order` / `cancel_order_ex` / `get_orders` / `get_open_orders` / `get_trades` | 未封装 | P0 |
| 账户/持仓 | `context.account()` / `account.cash` / `account.positions` | `get_trade_detail_data(account/position)` | `context.portfolio` / `get_position` | 部分封装 | P0 |
| 定时/生命周期 | `schedule` / `timer` / `on_*` | `schedule_run` / `cancel_schedule_run` / `run_time` / `init` / `after_init` / `handlebar` / `stop` | `run_daily` / `run_interval` / `initialize` / `before_trading_start` / `handle_data` / `tick_data` / `after_trading_end` | 冲突 | P0 |
| 打新 | `ipo_get_instruments` / `ipo_get_quota` / `ipo_buy` / `ipo_get_lot_info` | `get_ipo_data` + `passorder` | `ipo_stocks_order` | 有但坏 | P1 |
| 逆回购 | `order_volume`（卖出） | `passorder`（卖出） | `order`（负数，10 张起） | 有但窄 | P1 |
| 可转债 | 转股/回售/赎回系列 | `passorder` 对应 opType | `debt_to_stock_order` / 可转债查询 | 未封装 | 延后 |
| ETF | 基金申赎/篮子 | `passorder` 60/61 + `get_etf_info` | `etf_basket_order` / `etf_purchase_redemption` / `get_etf_info` | 未封装 | 延后 |
| 两融 | 信用账户业务函数 | `passorder` 27—34 + 担保品查询 | `margin_trade` / `margincash_*` / `marginsec_*` / 查询 | 未封装 | 延后 |
| 期货/期权 | 期货下单 + `position_effect` | `passorder` 0/3/6、50/51 | `buy_open` / `sell_close` / 期权函数 | 未封装 | 延后 |
| 通知 | `log` / 参数 | 日志文件 / `print` | `send_email` / `send_qywx` | 未封装 | 延后 |

### 5.3 统一函数清单（首批 50 / 延后 13）

> 说明：**支持度** ✔ 完整（三平台语义一致）／△ 降级（可用但有平台限制，需在文档注明）／✖ 不支持（抛 `UnsupportedFeature`）／? 待实测（先隐藏或标灰）。**阶段** P0—P2 对应第 5.7 节路线图；`延后` 表示不进入首批（原 P3 全部 + 非交易类 P2），默认不排期、不验收。首批核心 **50 个**，延后 **13 个**。

#### R. 运行时与调度

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| R-01 | `jingni_setup(mode, ctx, config=None)` | `Context` | `run` 上下文、`set_token` | `init(C)` 上下文、`account` | `initialize(context)` | ✔ | P0 |
| R-02 | `jingni_now()` | `datetime` | `context.now` | `timetag_to_datetime(get_bar_timetag(barpos))` | `context.blotter.current_dt` | ✔ | P0 |
| R-03 | `jingni_wall_now()` | `datetime` | `datetime.now()` | 同左 | 同左 | ✔ | P1 |
| R-04 | `jingni_is_trading_time(now=None)` | `bool` | 本地日历 + 交易时段 | 同左 | 同左 | △（集合竞价/午休需配置） | P1 |
| R-05 | `jingni_schedule(func, time_rule='09:31', date_rule='1d', name=None)` | `task_id` | `schedule` + 单任务分发 | `schedule_run(repeat_times=-1)` | `run_daily(context, func, time)` | △（PTrade 时点受限） | P0 |
| R-06 | `jingni_schedule_once(func, time_point, name=None)` | `task_id` | `schedule` + 标志位 | `schedule_run(repeat_times=0)` | `run_daily` + 标志位 | △ | P2 |
| R-07 | `jingni_cancel_schedule(name_or_id)` | `bool` | 标志位（无原生取消） | `cancel_schedule_run` | 标志位（无原生取消） | △ | P2 |
| R-08 | `jingni_run_interval(func, seconds=3)` | `task_id` | `timer` | `run_time`（回测无效） | `run_interval`（最小 3 秒） | △ | P1 |

#### D. 行情数据

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| D-01 | `jingni_get_history(code, frequency='1d', count=1, end_time=None, fields=None, adjust='pre')` | `DataFrame` | `history_n`（单标的、count 正整数） | `get_market_data_ex`（回测 `subscribe=False`） | `get_history`（单标的传 `str`） | ✔ | P0 |
| D-02 | `jingni_get_history_range(code, frequency, start_time, end_time, fields=None, adjust='pre')` | `DataFrame` | `history` | `get_market_data_ex(start_time, end_time)` | `get_price`（待核对） | △（PTrade 待核对） | P1 |
| D-03 | `jingni_get_tick(codes)` | `dict[code, dict]` | `current` | `get_full_tick` | `get_snapshot`（仅交易） | △ | P1 |
| D-04 | `jingni_get_field(code, frequency, field, offset=0)` | `float` | D-01 内核 | D-01 内核 | D-01 内核 | ✔ | P0 |
| D-05 | `jingni_get_field_n(code, frequency, field, count, offset=0)` | `list` / `Series` | D-01 内核 | D-01 内核 | D-01 内核 | ✔ | P0 |
| D-06 | `jingni_subscribe(codes, frequency='tick', count=0, callback=None)` | `handle` | `subscribe` | `subscribe_quote` | `set_universe` + `tick_data` | △（PTrade 无逐标的回调） | P2 |
| D-07 | `jingni_unsubscribe(handle)` | `bool` | `unsubscribe` | `unsubscribe_quote` | 无原生 | △ | P2 |
| D-08 | `jingni_download_history(codes, frequency, start_time, end_time)` | `None` | 空操作（服务端数据） | `download_history_data` + 基础周期映射 | 空操作 | △ | P1 |
| D-09 | `jingni_get_l2(codes, data_type, start_time=None, end_time=None, count=None)` | `DataFrame` / `dict` | L2 系列（需权限） | `l2quote` / `l2order` / `l2transaction` / `l2orderqueue` | `get_individual_entrust` / `transcation` | ? | 延后 |

#### I. 标的、日历与基础数据

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| I-01 | `jingni_get_instrument(codes)` | `dict`：`name/board/lot_size/tick_size/limit_up/limit_down/listed_date/status` | `get_instruments` / `get_symbol_infos` | `get_instrument_detail` | `get_stock_info` + `get_stock_status` | ✔ | P1 |
| I-02 | `jingni_get_trading_dates(start_date=None, end_date=None, market='SH')` | `list[str]` | `get_trading_dates` | `ContextInfo.get_trading_dates`（`after_init` 后） | `get_trade_days` | ✔ | P1 |
| I-03 | `jingni_offset_trade_date(offset, date=None, market='SH')` | `str` | `get_previous/next_n`（修正 `[0]`） | `get_trading_dates` 切片 | `get_trading_day` | ✔ | P0 |
| I-04 | `jingni_is_trading_day(date=None)` | `bool` | 由 I-02 推导 | 由 I-02 推导 | 由 I-02 推导 | ✔ | P1 |
| I-05 | `jingni_get_index_stocks(index_code, date=None)` | `list[str]` | 待核对（`get_index_stocks` / 板块） | `get_stock_list_in_sector` | `get_index_stocks` | △ | 延后（非交易） |
| I-06 | `jingni_get_sector_stocks(sector_name)` | `list[str]` | `get_symbols` / 板块接口 | `get_stock_list_in_sector` | `get_stock_blocks` / `get_industry_stocks` | △ | 延后（非交易） |
| I-07 | `jingni_get_stock_status(codes)` | `dict`：`st/suspend/delisted/limit` | `get_instruments` 状态 / 快照 | `get_instrument_detail` / `get_st_stock_list`（待核对） | `get_stock_status` | △（QMT 名单接口待核对） | P1 |
| I-08 | `jingni_get_fundamentals(codes, fields, table='income', date=None)` | `DataFrame` | `get_fundamentals`（表名待核对） | `get_financial_data` | `get_fundamentals` | △ | 延后（非交易） |
| I-09 | `jingni_get_dividend(code, start_date, end_date)` | `DataFrame` | 待核对 | `get_dividend_data` | `get_stock_exrights` | ? | 延后 |

#### T. 交易、订单与持仓

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| T-01 | `jingni_order_amount(code, amount, price=None, order_type='limit', unit='share', remark=None)` | `OrderRef` | `order_volume` | `passorder(23/24, 1101, ...)` | `order` | ✔ | P0 |
| T-02 | `jingni_order_value(code, value, price=None, remark=None)` | `OrderRef` | `order_value` | `passorder(..., 1102, ...)` | `order_value` | ✔ | P1 |
| T-03 | `jingni_order_percent(code, percent, price=None, remark=None)` | `OrderRef` | `order_percent` | `passorder(..., 1113, ...)` | 计算市值后 `order_value` | △ | P2 |
| T-04 | `jingni_order_target_amount(code, target_amount, price=None, remark=None)` | `OrderRef` | `order_target_volume` | 差额引擎 | `order_target` | △（QMT 差额引擎） | P1 |
| T-05 | `jingni_order_target_value(code, target_value, price=None, remark=None)` | `OrderRef` | `order_target_value` | 差额引擎 | `order_target_value` | △（QMT 差额引擎） | P1 |
| T-06 | `jingni_order_target_percent(code, target_percent, price=None, remark=None)` | `OrderRef` | `order_target_percent` | 差额引擎 | 计算后 `order_target_value` | △ | P2 |
| T-07 | `jingni_order_market(code, amount, protect_price=None, market_type='best5', remark=None)` | `OrderRef` | `OrderType_Market`（沪市保护价） | `prType=42`（沪市）/ `5` / `14` | `order_market(0..5)` | ✔ | P1 |
| T-08 | `jingni_order_batch(orders)` | `list[OrderRef]` | `order_batch` | `set_basket` / 循环 | 循环 / `etf_basket_order` | △ | P2 |
| T-09 | `jingni_cancel_order(order_ref)` | `bool` | `order_cancel` | `cancel` | `cancel_order` | ✔ | P1 |
| T-10 | `jingni_cancel_all()` | `int` | `order_cancel_all` | 遍历委托 + `cancel` | 遍历 `get_open_orders` | ✔ | P1 |
| T-11 | `jingni_close_all()` | `int` | `order_close_all` | 遍历持仓 + 卖出 | 遍历持仓 + 卖出 | ✔ | P1 |
| T-12 | `jingni_get_orders(status=None, include_finished=True)` | `list[dict]` | `get_orders` | `get_trade_detail_data(..., 'order')` | `get_orders` / `get_all_orders` | ✔ | P1 |
| T-13 | `jingni_get_trades(order_ref=None)` | `list[dict]` | `get_execution_reports` | `get_trade_detail_data(..., 'deal')` | `get_trades` | ✔ | P1 |
| T-14 | `jingni_get_positions()` | `list[dict]` | `context.account().positions` | `get_trade_detail_data(..., 'position')` | `context.portfolio.positions` | ✔ | P0 |
| T-15 | `jingni_get_account()` | `dict` | `context.account().cash` | `get_trade_detail_data(..., 'account')` | `context.portfolio` | ✔ | P0 |

#### E. 事件与回报

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| E-01 | `jingni_on_order(callback)` | `None` | `on_order_status` | `order_callback` | `on_order_response` | △ | P2 |
| E-02 | `jingni_on_trade(callback)` | `None` | `on_execution_report` | `deal_callback` | `on_trade_response` | △ | P2 |
| E-03 | `jingni_on_account(callback)` | `None` | `on_account_status` | 无原生 | 无原生 | △ | 延后 |
| E-04 | `jingni_on_backtest_finished(callback)` | `None` | `on_backtest_finished` | 无原生 | 用 `after_trading_end` 近似 | △ | 延后 |
| E-05 | `jingni_on_error(callback)` | `None` | `on_error` | 无原生 | 无原生 | △ | 延后 |

#### B. 业务增强

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| B-01 | `jingni_subscribe_new_stock(markets=None, blacklist=None, interval=5, dry_run=False)` | `dict`：`{code: {quota, price, status}}` | `ipo_get_instruments(..., df=False)` / `ipo_get_quota` / `ipo_buy` | `get_ipo_data('STOCK')` + `passorder` | `ipo_stocks_order(market_type, black_stocks)` + `sleep(5)` | △（仅实盘） | P1 |
| B-02 | `jingni_subscribe_new_bond(blacklist=None, dry_run=False)` | `dict` | `ipo_get_instruments(sec_type1=1030, ...)` / `ipo_buy` | `get_ipo_data('BOND')` + `passorder` | `ipo_stocks_order(market_type=4, black_stocks)` | △（仅实盘） | P1 |
| B-03 | `jingni_participate_reverse_repo(cash_ratio=1.0, days=1, market='SH', min_amount=1000)` | `OrderRef` | `order_volume`（卖出） | `passorder`（卖出，参数待实测） | `order(code, -amount)` | △（QMT 参数待实测） | P1 |
| B-04 | `jingni_convert_bond(code, amount)` | `OrderRef` | 转债转股函数 | `passorder` 对应 opType | `debt_to_stock_order` | ? | 延后 |
| B-05 | `jingni_etf_basket_order(...)` | `list[OrderRef]` | 基金篮子接口 | `passorder` 60/61 | `etf_basket_order` | ? | 延后 |
| B-06 | `jingni_etf_purchase_redemption(...)` | `OrderRef` | 基金申赎 | `passorder` 60/61 | `etf_purchase_redemption` | ? | 延后 |
| B-07 | `jingni_margin_order(...)` | `OrderRef` | 信用账户业务 | `passorder` 27—34 | `margin_trade` / `margincash_*` / `marginsec_*` | ? | 延后 |

#### C. 风控、工具与诊断

| 编号 | 统一函数（签名要点） | 返回 | 掘金实现 | QMT 实现 | PTrade 实现 | 支持度 | 阶段 |
|---|---|---|---|---|---|---|---|
| C-01 | `jingni_set_risk(config)` | `None` | 统一层 | 统一层 | 统一层 | ✔ | P1 |
| C-02 | `jingni_check_order(code, side, amount, price=None)` | `(bool, str)` | 统一层 | 统一层 | 统一层 | ✔ | P1 |
| C-03 | `jingni_calc_max_buy(code, price=None)` | `int` | 统一层 | 统一层 | 统一层 | ✔ | P1 |
| C-04 | `jingni_calc_max_sell(code)` | `int` | 统一层 | 统一层 | 统一层 | ✔ | P1 |
| C-05 | `jingni_normalize_code(code, target=None)` | `str` | 表驱动 | 表驱动 | 表驱动 | ✔ | P0 |
| C-06 | `jingni_log(level, msg)` | `None` | `log` | `print` / 日志文件 | `log.info` | ✔ | P1 |
| C-07 | `jingni_capabilities()` | `dict` | 适配器汇总 | 适配器汇总 | 适配器汇总 | ✔ | P0 |
| C-08 | `jingni_export_state(path=None)` / `jingni_load_state(path)` | `bool` | 统一层 | 统一层 | 统一层 | ✔ | P2 |
| C-09 | `jingni_notify(msg, channel=None)` | `bool` | 待核对 | 无原生 | `send_email` / `send_qywx` | △ | 延后 |
| C-10 | `jingni_kill_switch()` | `None` | 撤单 + 禁下单 | 撤单 + 禁下单 | 撤单 + 禁下单 | ✔ | P1 |

### 5.4 首批范围裁剪

| 组 | 首批核心 | 数量 | 延后项 | 延后数量 |
|---|---|---|---|---|
| R 运行时与调度 | R-01—R-08 | 8 | 无 | 0 |
| D 行情数据 | D-01—D-08 | 8 | D-09（L2） | 1 |
| I 标的与日历 | I-01—I-04、I-07 | 5 | I-05（指数成分）、I-06（板块）、I-08（财务）、I-09（分红） | 4 |
| T 交易与订单 | T-01—T-15 | 15 | 无 | 0 |
| E 事件与回报 | E-01、E-02 | 2 | E-03—E-05 | 3 |
| B 业务增强 | B-01—B-03 | 3 | B-04—B-07（转债/ETF/两融） | 4 |
| C 风控与工具 | C-01—C-08、C-10 | 9 | C-09（通知） | 1 |
| **合计** |  | **50** |  | **13** |

> 裁剪原则：只保留"能直接支撑股票现货交易闭环"的函数。延后项不是删除，而是不进入 Phase 0—2 的排期与验收；后续如确需，按第 5.6 节的 Backlog 流程单独立项，避免拉长核心工期。

### 5.5 支持度与降级规则

| 级别 | 定义 | 用户可见行为 | 示例 |
|---|---|---|---|
| ✔ 完整 | 三平台语义一致 | 正常返回 | `get_history`、`order_amount`、`cancel_order`、`get_account` |
| △ 降级 | 可用，但平台有限制 | 返回结果 + `degraded=True` + `notes`；文档注明 | PTrade 无逐标的订阅；QMT 目标持仓为差额模拟；QMT `run_time` 回测无效 |
| ✖ 不支持 | 平台无对应能力 | 抛 `UnsupportedFeature(platform, feature)`；不返回 `None` | PTrade 无逐标的取消订阅；QMT 无账户状态推送 |
| ? 待实测 | 文档未能确认或依赖券商版本 | 默认隐藏，需 `enable_experimental=True`；冒烟通过后转正 | QMT 打新 `opType`；PTrade `get_price`；掘金 L2 权限 |

`jingni_capabilities()` 返回结构建议：

```
{
  'platform': 'qmt',
  'version': '0.2.0',
  'python': '3.6',
  'features': {
    'market.history': {'level': 'full', 'notes': ''},
    'market.subscribe': {'level': 'full', 'notes': ''},
    'trade.market_order': {'level': 'degraded', 'notes': '沪市需保护价'},
    'trade.target': {'level': 'degraded', 'notes': '差额引擎模拟'},
    'ipo.stock': {'level': 'experimental', 'notes': 'opType 待实测'}
  }
}
```

### 5.6 Backlog 管理

延后项统一登记在 `docs/backlog.md`（实施时创建），每条包含：能力、三平台支持度、触发条件、预估人日、依赖权限。默认不排期；只有同时满足以下三条才进入下一批：

1. 用户明确提出该项业务需求（不是"顺便补齐"）。
2. 对应柜台权限/数据权限已确认可用。
3. 不影响核心交易闭环的稳定性与工期。

原 Phase 3 不再作为默认阶段；期货、期权、两融、ETF、L2 等按 Backlog 单独立项。

### 5.7 扩展批次与路线图

| 阶段 | 目标 | 主要内容 | 产出 | 验收 | 工期 |
|---|---|---|---|---|---|
| **Phase 0 止血** | 能安全启动、能正确取数 | P0-01—P0-13；三平台模板；包骨架；旧接口兼容层；`build_single.py`；测试骨架；`jingni_version` / `capabilities` | 三平台可启动模板、P0 清零、单文件构建、CI | 第 4.5 节"启动/取数/代码/静态"全部通过 | 5—7 人日 |
| **Phase 1 契约与订单闭环** | 同一策略能下单、查单、撤单、看持仓 | 契约层；适配器骨架；T-01/02/04/05/07/09—15；D-01/04/05；I-03；C-01—06/10；B-03；R-01/02/05 | 统一 API v0.2；订单闭环；风控；三平台冒烟脚本 | 下单→查单→撤单→对账三平台通过；可卖量正确；目标持仓收敛 | 8—10 人日 |
| **Phase 2 数据与调度** | 补齐股票现货交易闭环的剩余能力 | D-02/03/06/07/08；I-01/02/04/07；R-03/04/06/07/08；T-03/06/08；B-01/02；E-01/02；C-08 | 参考策略（双均线 + 打新 + 逆回购 + 调仓）；完整文档 | 参考策略三平台回测/仿真通过；能力矩阵与文档一致 | 6—8 人日 |
| **Backlog（默认不排期）** | 用户明确要求且权限就绪后再评估 | D-09、I-05/06/08/09、B-04—B-07、E-03—E-05、C-09、期货/期权/两融/ETF/L2 | 单独立项，不进入核心版本 | 独立验收 + 权限说明 | 不计入核心工期 |

**Phase 0 任务分解（建议直接建 issue）**

| # | 任务 | 涉及文件/位置 | 产出 | 验收 |
|---|---|---|---|---|
| 0-1 | 统一模式与上下文 | `jingniflow.py` 全局 `trade_mode`、各函数入口 | `Context` 持有 mode/account/config；旧全局仅作默认 | `jingni_main('qmt', ...)` 与全局一致；无分支漏命中 |
| 0-2 | 空值/索引修复 | `get_field` L372、`get_field_n` L492、`jingni_portfolio` L79 | 空数据返回空结构；统一 `.iloc`；未知字段抛 `ValidationError` | 停牌/未知字段/空账户不崩、不返回字段名 |
| 0-3 | 代码转换重写 | `jingni_map_security_code` L128—L207 | 表驱动 `to_platform/from_platform`；正则校验 | 30 个代码用例通过；幂等 |
| 0-4 | QMT 取数修复 | `get_history` L253、`get_field` L363、`get_field_n` L485 | 正数 count + offset；回测 `subscribe=False`；bar 时间 | QMT 回测 5 条正确、最后一条为当前 bar |
| 0-5 | 实时分支统一 | `get_field_n` L401/L434、`get_current` L210 | 统一 tick dict；字段映射 | 三平台实时字段类型/键一致 |
| 0-6 | 主循环删除 + 三平台模板 | `jingni_main` L731、`examples/*` | 模板只保留平台事件；`is_last_bar`；GBK | 三平台启动/退出/调度正常 |
| 0-7 | QMT 打新/新债修复 | `subscribe_new_stock` L614、`subscribe_new_bond` L656 | `context_data`；`quickTrade=2`；`repeat_times=-1` | `dry_run` 列出标的；连续 3 日触发 |
| 0-8 | 包结构与单文件构建 | `__init__.py`、`pyproject.toml`、`tools/build_single.py` | 包布局 + `dist/jingniflow_single.py` | 3.6 编译通过；GBK 解码通过；`pip install` 成功 |
| 0-9 | 测试骨架 | `tests/unit`、`tests/contract` | 代码/频率/字段/整手/空值用例 | 核心契约覆盖率 ≥ 80% |
| 0-10 | 旧接口兼容层 | `compat/legacy.py`、`jingniflow.py` 旧名 | 旧 `jingni_*` 签名与默认值不变；`legacy=True` 只保留旧返回形态，不保留已知错误 | 现有三个示例不改代码可运行 |

**建议的首个参考策略（Phase 2 验收载体）**

1. 每日 09:15 盘前：检查标的池、除权除息、停牌、涨跌停价。
2. 09:31 / 14:50 定时：双均线信号，`order_target_percent` 调仓。
3. 11:00：逆回购（闲置资金）。
4. 14:55：打新（可配置开关，默认 `dry_run`）。
5. 盘后：输出订单/成交/持仓/资金日报，校验对账。

### 5.8 测试体系

| 测试类型 | 范围 | 工具/方法 | 门禁 |
|---|---|---|---|
| 单元测试 | 代码转换、频率/字段映射、整手、状态枚举、风控、空值/索引 | `pytest` + 参数化 | 覆盖率 ≥ 80%，PR 必过 |
| 契约测试 | 同一输入在三平台适配器（Mock）下返回同构结构 | 假适配器 + 固定夹具 | 三平台返回字段/长度/类型一致 |
| Golden 测试 | 用录制的平台返回（脱敏）比对解析结果 | JSON/CSV 夹具 | 关键字段零差异 |
| 静态兼容 | QMT 3.6 / GBK / 无阻塞 | `py_compile` + `ast` 扫描 + `gbk` 解码 | 阻断构建 |
| 冒烟测试 | 三平台真实终端 | 手工清单 + 日志断言 | 每版本三平台各跑一遍 |
| 回归测试 | 旧 `jingni_*` 签名与行为 | 兼容层用例 | 旧策略不改代码可运行 |

**冒烟清单（每平台 8 项）**

1. 启动打印 `platform / version / python / capabilities`。
2. `get_history(count=5)` 长度 5，最后一条为当前 bar。
3. `get_field(offset=0)` 与 `get_field(offset=1)` 各返回 `float`，且与历史最后两条一致。
4. `order_amount(100)` 返回 `OrderRef`，`get_orders` 可见。
5. `cancel_order(ref)` 后状态为 `CANCELED`。
6. `get_positions` 的 `available` 与柜台可用一致。
7. `schedule` 次日同一时点再次触发。
8. `subscribe_new_stock(dry_run=True)` 列出标的，不报单。

### 5.9 文档与发布

| 文档 | 内容 | 更新方式 |
|---|---|---|
| `README.md` | 三平台快速开始、能力矩阵、函数索引、常见坑 | 由 `docs/api/index.md` 生成或校验 |
| `docs/api/*.md` | 每个函数的签名、参数、返回、支持级别、示例 | 与 docstring 同步 |
| `docs/platform-notes.md` | QMT 3.6/GBK/单线程、PTrade 时点、掘金 18:00 入库 | 人工维护 |
| `docs/migration-v0.1-to-v0.2.md` | 旧签名 → 新签名、行为变化、弃用清单 | 大版本前 |
| `CHANGELOG.md` | 新增/修复/破坏性变更 | 每次发布 |
| `docs/smoke-checklist.md` | 三平台冒烟清单 | 每版本 |

**版本策略**

- SemVer：`0.x` 以新增和修复为主，旧 `jingni_*` 签名不破坏；确需破坏时统一放到 `1.0` 并写迁移说明。
- QMT 发行物首行保留 `#coding:gbk`，第二行写入 `__JINGNIFLOW_VERSION__` 与构建时间；启动时 `jingni_version()` 打印，便于排查"用户手里的副本是哪一版"。
- 发布物：`dist/jingniflow_single.py`（QMT/PTrade 复制用）、`dist/jingniflow_single_gbk.py`（QMT 专用 GBK）、pip 包（掘金/本地研究用）。

---

## 6. 工作量与里程碑

| 阶段 | 人日 | 关键假设 |
|---|---|---|
| Phase 0 止血 | 5—7 | 1 名熟悉三平台的工程师；不含券商终端等待 |
| Phase 1 契约与订单闭环 | 8—10 | 三平台模拟/仿真环境可用；QMT 差额引擎按简单版本（不含算法单） |
| Phase 2 数据与调度（交易相关） | 6—8 | 股票现货取数/调度接口可用；不含 L2、财务、板块 |
| **核心合计（Phase 0—2）** | **19—25 人日** | 不含实盘资金验证与运维 |
| Backlog（默认不排期） | 不计入 | 期货/期权/两融/ETF/L2 等按需单独立项，含权限与柜台联调 |

> 上述为纯开发估算，不含：券商终端版本确认、数据下载、权限申请、实盘小资金验证、用户培训。若三平台客户端版本差异大，联调时间另计。50 个函数中多数是契约转换/薄封装，主要不确定性集中在 QMT 差额引擎、QMT 逆回购参数实测、PTrade 打新/逆回购柜台联调。

---

## 7. 风险与待实测清单

### 7.1 风险登记

| 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|
| QMT Python 3.6 / GBK 约束被忽略 | 单文件在 QMT 无法运行/乱码 | 高 | CI 强制 3.6 编译 + GBK 解码；禁用语法清单 |
| QMT 单线程被阻塞 | 同一客户端所有策略卡死 | 高 | 禁止 `sleep`/死循环；重活放调度器；冒烟测响应 |
| PTrade 券商版本与文档不一致 | 函数不存在/参数不同/返回不同 | 中 | 启动时能力探测；`?` 项默认隐藏；券商环境冒烟 |
| 掘金当天日线 18:00 后入库 | 盘中取"当天日线"拿到昨日 | 中 | 盘中用快照合成；返回 `is_stale` 提示 |
| 券商权限不足（L2/两融/期货/期权） | 功能不可用 | 中 | 能力矩阵标注；`UnsupportedFeature`；不静默 |
| QMT 回测本地数据未下载 | 回测空数据/结果异常 | 高 | 启动自检 + `download_history_data` 指引 + 数据完整性检查 |
| 实盘误下单/超仓 | 资金损失 | 低但后果高 | 默认 `dry_run`、单笔/单日限额、重复窗口、`kill_switch` |
| 单文件与源码漂移 | 用户使用旧版本，问题无法复现 | 高 | `jingni_version()` 自检、构建产物校验、发布清单 |
| 平台 API 限流 | 分钟级策略请求失败 | 中 | 每 bar 缓存、批量取数、退避重试 |
| 范围蔓延（期货/期权/两融一起上） | 核心股票功能延期 | 高 | Backlog 默认不排期；只有明确业务需求且权限就绪才立项 |

### 7.2 待实测清单（实施前必须逐项确认）

| 编号 | 待实测项 | 平台 | 验证方法 | 影响 |
|---|---|---|---|---|
| V-01 | `get_market_data_ex` 的 `count`/`end_time` 边界、索引类型 | QMT | 取 1/5/10 条，打印 index 与最后时间 | D-01/D-04/D-05 |
| V-02 | `cancel` 的签名与返回值、委托号字段 | QMT | 模拟下单后撤单，打印 `m_strOrderSysID` | T-09/T-10 |
| V-03 | 打新 `opType`/`orderType`/`prType`/`quickTrade` | QMT | 新股日 `dry_run` + 模拟环境 | B-01/B-02 |
| V-04 | 逆回购 `passorder` 的 opType、数量单位、价格 | QMT | 1 天期小额模拟 | B-03 |
| V-05 | `order_market` 类型 0—5 的实际行为 | PTrade | 仿真逐类型下单 | T-07 |
| V-06 | `get_snapshot` 字段名与停牌/涨跌停字段 | PTrade | 打印一只股票完整快照 | D-03/I-01 |
| V-07 | `get_price` 是否支持起止日期与复权 | PTrade | 区间查询比对 | D-02 |
| V-08 | `ipo_stocks_order` 返回结构与失败原因 | PTrade | 新股日 `dry_run` | B-01 |
| V-09 | `history_n` 的 `end_time` 对分钟线/日线的包含性 | 掘金 | 10:00 查 1m/1d 各 5 条 | D-01 |
| V-10 | `position.volume_today` 与 `volume` 的实盘口径 | 掘金 | 当日买入后打印持仓 | T-01/T-14 |
| V-11 | 掘金 `get_instruments` 的表名与字段 | 掘金 | 打印 schema | I-01（I-08 已延后，不阻塞首批） |
| V-12 | 三平台 Python 精确版本与 pandas 版本 | 全部 | 启动打印 `sys.version` / `pd.__version__` | 兼容性 |

---

## 8. 决策记录与实施顺序

### 8.1 已锁定决策（2026-11-19）

| 编号 | 决策 | 锁定结论 | 落地影响 |
|---|---|---|---|
| **D1** | 交付形态 | **A. 包结构 + 构建单文件** | 源码可维护、可测试；`dist/jingniflow_single.py` 保留复制粘贴体验 |
| **D2** | 首批范围 | **A. 股票现货 + 打新/逆回购**；原 P3 高级能力默认不做，非交易类 P2 延后 | 首批 50 个核心函数、13 个延后项；核心工期 19—25 人日 |
| **D3** | QMT 兼容底线 | **A. Python 3.6 + GBK 硬约束** | CI 增加 3.6 编译与 GBK 解码；禁止 3.7+ 语法与 GBK 不可编码字符 |
| **D4** | 旧接口策略 | **A. 保留旧名 + 可选参数 + `legacy` 返回形态** | 现有策略不改代码可运行；`legacy` 不保留已知错误，新能力走新函数或可选参数 |
| **D5** | PTrade 目标版本 | **以 `<INTERNAL_HOST>` 官方文档为准**；其他券商版本差异后置 | `?` 项按该文档转正/降级；券商差异进 Backlog，不阻塞首批 |
| **D6** | 第三方依赖 | **A. 零新增（仅 pandas/numpy）** | QMT 离线环境可直接运行；不引入 requests 等外部包 |
| **D7** | 实盘安全默认 | **A. 首次 `dry_run` + 限额默认开启** | 单笔/单日限额、重复窗口、`kill_switch` 默认生效；首次实盘需显式关闭 `dry_run` |

### 8.2 实施顺序（决策后）

1. **冻结基线**：当前 `v0.1.16` 打 tag，修复全部在分支上做，避免用户手里的副本继续分叉。
2. **Phase 0（5—7 人日）**：执行 0-1—0-10 全量任务；产出三平台可启动模板、旧接口兼容层、`dist/jingniflow_single.py`、GBK 版、CI 与测试骨架。
3. **三平台冒烟**：各选一只股票跑"取 5 条 + 取当天 + 下单 100 股 + 查持仓 + 撤单"，记录 V-01/V-09/V-10 的实际返回；冒烟不通过不进入 Phase 1。
4. **Phase 1（8—10 人日）**：契约层、订单闭环、风控；T-01/02/04/05/07/09—15、D-01/04/05、I-03、B-03、R-01/02/05、C-01—06/10。
5. **Phase 2（6—8 人日）**：D-02/03/06/07/08、I-01/02/04/07、R-03/04/06/07/08、T-03/06/08、B-01/02、E-01/02、C-08；以参考策略做三平台验收。
6. **Backlog**：默认不排期；只有满足 5.6 节三条准入条件才单独立项，不纳入核心版本承诺。

---

## 附录 A 官方依据

| 平台 | 链接 | 本方案使用点 |
|---|---|---|
| 掘金快速开始 | `https://www.myquant.cn/docs2/sdk/python/快速开始.html` | 事件模型、`run`、`context.mode`、`schedule` 覆盖规则 |
| 掘金行情数据查询函数 | `https://www.myquant.cn/docs2/sdk/python/API介绍/行情数据查询函数（免费）.html` | `history_n` count 正整数、前开后闭、日线 eob、18:00 入库 |
| 掘金交易函数 | `https://www.myquant.cn/docs2/sdk/python/API介绍/交易函数.html` | `order_volume` 返回、平仓规则、`PositionEffect_Close` |
| 掘金通用数据函数 | `https://www.myquant.cn/docs2/sdk/python/API介绍/通用数据函数（免费）.html` | `get_trading_dates`、`get_previous/next_n_trading_dates` 返回顺序 |
| QMT 快速开始 | `https://dict.thinktrader.net/innerApi/start_now.html?id=yzWK3j` | Python 3.6、`subscribe=False`、`passorder`、`quickTrade` |
| QMT 系统函数 | `https://dict.thinktrader.net/innerApi/system_function.html?id=yzWK3j` | `init/after_init/handlebar`、`schedule_run`、`run_time` 回测无效 |
| QMT 行情函数 | `https://dict.thinktrader.net/innerApi/data_function.html?id=yzWK3j` | `get_market_data_ex`、`get_trading_dates`、字段/周期 |
| QMT 交易函数 | `https://dict.thinktrader.net/innerApi/trading_function.html` | `passorder` 参数、opType、prType、quickTrade |
| QMT 常见问题 | `https://dict.thinktrader.net/innerApi/question_answer.html` | 单线程阻塞、异步回报、`get_trade_detail_data` 缓存 |
| PTrade API | `<INTERNAL_HOST>` | `get_history`、`order`、`run_daily`、`ipo_stocks_order`、逆回购门槛 |

## 附录 B 三个容易被误判的点（评估中修正的常见判断）

1. **`int(-security_count)` 并不总是负数。** 旧约定 `security_count ≤ 0`，取负后是正数，所以掘金/PTrade 的 `count` 本身是合法的。真正的问题是：公开接口没有把"正数 count / 偏移"讲清楚，以及 `get_field_n` 在负偏移分支把 `security_count - 1` 再传给取数函数，导致多取一条。评估时不应把"传负数"当作主因。
2. **掘金日线的 `end_time=当天` 并不必然丢当天。** 掘金日线的 `eob` 是交易日 00:00，按"前开后闭"可以包含当天；真正会丢当天的是分钟线（`eob` 是具体时刻，`end_time` 给 00:00 会排除当天全部分钟线）。另外，当天日线在 18:00 后才入库，盘中通过历史接口取"当天日线"可能拿到昨日。
3. **`iloc[-1]` 在掘金分支是合法且正确的。** 它表示最后一根 bar，不存在"越界"；真正越界的是 QMT 分支的 `[security_count - 1]`（在负偏移时是 `[-N-1]`），以及 QMT 整数时间索引下 `[-1]` 被当作标签索引。把这两类问题混为一谈，会误导修复方向。

## 附录 C 术语表

| 术语 | 含义 |
|---|---|
| 统一契约 | 代码格式、频率、字段、数量、时间、返回结构、错误类型的统一定义 |
| 适配器 | 封装单一平台原生 API、字段映射、异常翻译的类 |
| 单文件发行物 | 由包源码构建生成、供 QMT/PTrade 复制到策略尾部的 `.py` |
| `OrderRef` | 跨平台统一的订单引用，含平台、平台委托号、投资备注 |
| 差额引擎 | QMT 无原生目标持仓接口时，用"当前持仓 + 在途委托 → 差额下单"模拟 |
| 降级 | 平台能力不完整但仍可用，返回结果带 `degraded/notes` |
| 能力矩阵 | `jingni_capabilities()` 输出的平台 × 功能支持级别 |
| 前开后闭 | 掘金行情区间语义：`start < eob <= end` |
| `quickTrade` | QMT `passorder` 的快速下单标记：0 逐 K 线、1 最新 K 线立即、2 任意时点立即 |

