# 项目简介

**项目名称**：JingniFlow

**项目描述**：JingniFlow是一个基于Python的量化交易开发框架，致力于提供兼容中国券商交易软件的量化解决方案。

**项目版权**：Copyright (c) 2024-present, Hanjun Du

**项目作者**：Hanjun Du (hanjun.du@outlook.com)

**项目贡献**：项目长期招募贡献者，有意向请邮件联系项目作者。

**免责声明**：本项目仅用于教育目的，不保证任何交易的成功。请自行承担风险。

**关于本项目的信息和反馈请访问GitHub存储库**：https://github.com/duhanjun/JingniFlow

**关于本项目的学习和实践请访问在线课程目录**：https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MjM5MTU2NDA3OQ==&action=getalbum&album_id=4151851070626693141#wechat_redirect

# 快速开始

- 完全不知道怎么选路径：先看 `docs/getting-started.md`。
- 单文件 / 包导入 / 模板三种方式对比：`docs/usage-modes.md`。
- 第一个可运行的策略（含 `strategy=` 绑定）：`docs/first-strategy.md`。
- dry-run、限额、kill switch、模拟到实盘：`docs/config-and-risk.md`。
- 文档总索引：`docs/README.md`。
- 仿真账户三端可粘贴验证策略：`dist/validation/README.md`。

# v0.2.0 Phase 0 / Phase 1 / Phase 2 迁移说明

- 代码已从单文件 `jingniflow.py` 迁移为 `jingniflow/` 包；旧函数名全部保留，旧参数可用，`legacy=True` 可恢复旧字段偏移/旧返回形态（已知错误行为不回退）。
- `jingni_main` 不再执行 `while True` 主循环，只做初始化并立即返回；盘中逻辑由 `jingni_handle_data` 执行，由平台事件（掘金 `on_bar`、QMT `handlebar`、PTrade `handle_data`）驱动。新增策略注册入口：`jingni_main(trade_mode, context_data, strategy=my_strategy)`、`jingni_handle_data(..., strategy=...)` 或 `jingni_set_strategy(my_strategy)`；未注册时仍调用旧的 `jingni_trade_strategy` 占位实现。
- 默认 `RuntimeConfig` 已按 D7 开启安全口径：`dry_run=True`、单笔数量/金额、每日笔数、重复下单窗口均默认生效。实盘前显式传 `RuntimeConfig(dry_run=False)`，并按账户规模调整限额。
- **Phase 1 订单闭环**：`jingni_order_amount` / `jingni_order_value` 默认返回统一 `OrderRef`，并新增目标持仓、市价单、撤单、全撤、平仓、订单/成交查询、统一账户/持仓、风控 API。旧策略可继续使用旧签名；需要旧返回值时传 `legacy=True`。
- **QMT 差分引擎**：`jingni_order_target_amount` 会扣除当前持仓与在途委托，部分成交/拒单场景可重复调用收敛；QMT 目标单走 `passorder`。
- **风控**：所有新增下单入口先过 `core/risk.check_order`；`jingni_kill_switch` 会撤掉未完成委托并阻止后续下单；`dry_run=True` 只检查、不消耗每日笔数。
- **Phase 2 交易周边**：新增范围行情 `jingni_get_history_range`、历史数据预热 `jingni_download_history`、标的元数据 `jingni_get_instrument` / `jingni_get_stock_status`、交易日历 `jingni_get_trading_dates` / `jingni_is_trading_day`、交易时段 `jingni_is_trading_time`、秒级定时器 `jingni_run_interval`。范围行情统一返回 DataFrame；日历返回 `YYYYMMDD` 列表；标的元数据返回以规范代码为键的 dict。
- QMT 兼容内置 Python 3.6 + GBK：`dist/jingniflow_single_gbk.py` 可直接粘贴到策略末尾；包模式请把仓库根目录加入 QMT 的 Python 路径。PTrade 实测 Python 3.5.1，单文件顶层不得出现 `sys`。
- 生成单文件：`python tools/build_single.py`；同时刷新根目录旧文件用 `python tools/build_single.py --root`。
- 构建治理：`python tools/build_single.py --check --root` 校验版本、源码 SHA256、构建时间、产物 SHA256 和 `dist/build-manifest.json`；`python tools/build_smoke.py --check` 校验三端 full 冒烟文件；`python tools/verify_release.py` 校验 QMT GBK/Python 3.6、PTrade 禁 sys/Python 3.5 约束和三端 `trade_mode`。详细设计见 `docs/build-governance-ci.md`。
- CI：`.github/workflows/ci.yml` 跑 pytest、pyflakes、核心覆盖率门禁、单文件/冒烟构建校验和 release verifier，并用 Python 3.6 容器做 QMT 单文件的语法与 GBK 解码检查；打 `v*` tag 时额外产出 release bundle。
- 测试：`python -m pytest`（当前 78 个单元/契约测试）。
- 诊断：`jingni_doctor()` 做启动自检；`jingni_capabilities()` 返回 Phase 1/2 能力矩阵，含 `full/degraded/unsupported` 平台级别。
- 覆盖率门禁：`python -m coverage run -m pytest` + `python -m coverage report`，约束 `core/` 核心契约层 ≥80%；当前 86%，全包约 69%。

# Phase 1 新增函数（股票现货交易闭环）

| 类别 | 函数 | 说明 |
|---|---|---|
| 策略入口 | `jingni_set_strategy` / `jingni_get_strategy` | 注册/读取默认策略函数；`jingni_main(..., strategy=...)` 和 `jingni_handle_data(..., strategy=...)` 可显式绑定 |
| 下单 | `jingni_order_amount` / `jingni_order_value` | 数量/金额下单，默认 `OrderRef`，支持 `dry_run`、`legacy` |
| 目标持仓 | `jingni_order_target_amount` / `jingni_order_target_value` | 当前持仓 + 在途委托差额引擎；QMT 用 `passorder` |
| 市价 | `jingni_order_market` | 市价/保护价；QMT 沪市用 `prType=42` |
| 撤单 | `jingni_cancel_order` / `jingni_cancel_all` / `jingni_close_all` | 单笔撤、全撤、按可用持仓平仓 |
| 查询 | `jingni_get_orders` / `jingni_get_trades` | 统一订单/成交字段，状态映射为 7 个枚举 |
| 账户 | `jingni_get_account` / `jingni_get_positions` | 统一 `total_asset/cash/available/market_value/frozen/pnl` 与持仓可卖量 |
| 风控 | `jingni_set_risk` / `jingni_check_order` / `jingni_calc_max_buy` / `jingni_calc_max_sell` / `jingni_kill_switch` / `jingni_log` | 限额、整手、可卖量、重复窗口、kill switch |
| 行情/日历/调度 | `jingni_history` / `jingni_tick` / `jingni_now` / `jingni_wall_now` / `jingni_offset_trade_date` / `jingni_schedule` | 统一 DataFrame/tick、策略时钟、平台定时任务 |
| 业务 | `jingni_subscribe_new_stock` / `jingni_subscribe_new_bond` / `jingni_participate_reverse_repo` | 打新/新债/逆回购，默认 `dry_run` |

QMT 目标单差额引擎、PTrade `get_orders/get_trades`、QMT 撤单签名等仍需按 `docs/JingniFlow-代码评估与功能扩展规划方案.md` 的 V-01—V-12 在三家终端实机核对；未核对前按“降级/待实测”标注。

# Phase 2 新增函数（交易周边数据、日历与调度）

| 类别 | 函数 | 说明 |
|---|---|---|
| 范围行情 | `jingni_get_history_range(trade_mode, context_data, security_code, frequency, start_time, end_time, fields=None, adjust='pre')` | 按起止时间取历史行情，统一 DataFrame；`start_time` 必填 |
| 数据预热 | `jingni_download_history(trade_mode, context_data, security_codes, frequency, start_time, end_time)` | QMT 逐只 `download_history_data`；GM/PTrade 无操作 |
| 标的元数据 | `jingni_get_instrument(trade_mode, context_data, security_codes, fields=None)` | 返回规范代码为键的 `name/board/lot_size/tick_size/limit_up/limit_down/listed_date/status` |
| 股票状态 | `jingni_get_stock_status(trade_mode, context_data, security_codes, query_type='ST', date=None)` | PTrade 原生；GM/QMT 由标的详情降级推导，未知返回 `None` |
| 交易日历 | `jingni_get_trading_dates(trade_mode, context_data, start_date=None, end_date=None, market='SH')` | 返回 `YYYYMMDD` 列表；GM `get_trading_dates_by_year`、QMT `get_trading_dates`、PTrade `get_trade_days` |
| 交易日判断 | `jingni_is_trading_day(trade_mode=None, context_data=None, date=None)` | 由交易日历推导；平台日历不可用时按工作日降级 |
| 交易时段 | `jingni_is_trading_time(trade_mode=None, context_data=None, now=None, include_auction=False)` | 默认连续竞价 09:30—11:30、13:00—15:00；可含开盘集合竞价 |
| 秒级定时器 | `jingni_run_interval(func, seconds=3, trade_mode=None, context_data=None)` | GM `timer`（毫秒）、QMT `ContextInfo.run_time`（回测无效）、PTrade `run_interval`（最小 3 秒） |

Phase 2 的平台差异与待实测项见 `docs/Phase2-实施记录.md`；三端回测冒烟已完成（掘金 23/0/1、QMT 21/0/3、PTrade 22/0/2），真实报单/柜台/定时器验证见 `docs/live-validation-checklist.md`。能力矩阵/自检与异常契约的加固记录见 `docs/QA-加固记录.md`。

# 三端实机冒烟

三份可粘贴脚本在 `examples/smoke/`，覆盖三端回测的启动、行情/日历、dry-run、
查询和调度检查（实际项数以脚本 `[SMOKE][SUMMARY]` 为准）：

| 平台 | 粘贴文件 | 追加单文件 |
|---|---|---|
| 掘金 | `examples/smoke/goldminer_smoke.py` | `dist/jingniflow_single.py` |
| QMT | `examples/smoke/qmt_smoke.py` | `dist/jingniflow_single_gbk.py` |
| PTrade | `examples/smoke/ptrade_smoke.py` | `dist/jingniflow_single.py` |

默认 `SMOKE_REAL_ORDER=False`，只做 dry-run；真实报单/撤单需要显式打开。完整步骤、日志对照和常见失败见 `docs/smoke-copy-paste.md`；模拟/实盘逐项真机验证见 `docs/live-validation-checklist.md`。

# 诊断与自检

| 函数 | 说明 |
|---|---|
| `jingni_version()` | 打印并返回版本、Python、当前平台 |
| `jingni_capabilities(trade_mode=None)` | 返回能力矩阵；每个能力含 `phase/level/notes/platform_levels` |
| `jingni_doctor(trade_mode=None, context_data=None, config=None, verbose=True)` | 静态检查 Python/平台/适配器/`dry_run`/风控限额/Phase 2 能力，不主动调用柜台接口 |

`jingni_doctor()` 只做启动自检，不替代实机冒烟；`ok=False` 表示存在必须处理的错误，`warnings` 包含实盘开关、kill switch、QMT 账号未配置等提示。

# 项目框架

JingniFlow的核心设计目标是简化跨平台策略开发。通过抽象层将各券商量化交易软件的接口封装成统一函数，使策略只需调用JingniFlow的统一接口，而无需为每个量化交易软件重写适配策略代码。

|**功能模块**|**函数名称**|**使用说明**|
|-------|-------|-------|
|系统控制|main|初始化运行时并立即返回，由平台事件驱动|
|事件驱动|before_trading_start/handle_data/after_trading_end|盘前盘中盘后事件函数；`handle_data` 单次执行|
|交易日期|trading_dates|获取指定日期前后的交易日期|
|交易时间|trading_times|获取指定日期的交易时间|
|账户信息|portfolio|查询账户资产、市值、资金和持仓明细|
|代码转换|map_security_code|转换不同量化交易软件的证券代码格式|
|实时行情|get_current|获取股票的实时行情数据|
|历史行情|get_history|获取股票的历史K线数据，支持多种时间周期|
|单日数据|get_field|提取指定股票在特定交易日的某个字段值|
|多日数据|get_field_n|提取指定股票在多个交易日的字段值序列|
|数量交易|order_amount|按指定数量买卖；默认返回 `OrderRef`，支持 dry-run/legacy|
|金额交易|order_value|按指定金额买卖；默认返回 `OrderRef`，自动按整手计算|
|新股申购|subscribe_new_stock|自动申购新股，自动查询额度并提交订单|
|新债申购|subscribe_new_bond|自动申购新债，自动查询额度并提交订单|
|国债回购|participate_reverse_repo|自动化操作国债逆回购，提高资金利用率|

国内券商采购的第三方量化交易软件主要有掘金量化、QMT及PTrade，研发实力强的券商也推出自研量化交易软件。考虑到个人投资者参与量化交易的门槛，目前JingniFlow优先选择适配下列三款量化交易软件。

**1.掘金量化**

掘金量化（Goldminer）是一款拥有策略编写、数据研究、历史回测、实时仿真、绩效分析等量化投研功能，同时提供量化实盘交易、增值算法等服务。

下载地址：https://www.myquant.cn/terminal

**2.QMT**

QMT是一款专门针对高净值投资者、活跃投资者、非投顾型产品投资者开发设计，是集行情显示，策略编写，交易执行，风控管理于一身的专业交易管理平台。支持股票、期货、融资融券、组合交易等多种交易类型，并且具有算法交易、策略编写、篮子股票交易、自定义交易界面等特色功能。

下载地址：https://xuntou.net/#/download

**3.PTrade**

PTrade是一款面向高净值个人客户及专业机构的一体化智能投资交易系统软件，支持程序化策略交易、日内回转交易、普通交易、策略模型交易等功能场景。

下载地址：https://www.isimu123.com/download.html

上述下载地址的量化交易软件均为**非券商版**，除了不具备实盘能力外，对行情数据的限制也比较多。**非券商版**（建议使用可以长期试用的掘金量化）已经可以满足本项目的部署需要，如果需要解除这些限制，可以联系开户券商开通**券商版**量化交易软件。

# 项目价值

对于普通投资者而言，即使没有深厚的编程背景，也能基于这些封装好的函数，组合实现自己的交易策略，迈出量化交易的第一步。

# 使用指南

**1.JingniFlow**

**函数名称**：无

**学习目标**：理解JingniFlow的设计理念、整体结构以及如何通过配置适应不同券商量化交易软件的策略环境。

**核心内容**：详解券商三款主流量化交易软件(ptrade/qmt/goldminer)的设置，阐述框架如何通过条件判断实现一套代码兼容运行。

**2.系统控制模块**

**函数名称**：jingni_main(trade_mode, context_data, config=None, strategy=None)

**学习目标**：理解如何构建系统初始化入口，把控制权交给平台事件循环。

**核心内容**：`jingni_main` 只解析运行上下文、打印平台/版本并返回，不再按墙钟时间循环调度。掘金用 `on_bar`、QMT 用 `handlebar`、PTrade 用 `handle_data` 调用 `jingni_handle_data`。策略函数签名为 `strategy(trade_mode, context_data)`，推荐在 `jingni_main(..., strategy=my_strategy)` 中绑定；也可以先 `jingni_set_strategy(my_strategy)` 再正常初始化。

**3.事件驱动框架**

**函数名称**：jingni_before_trading_start(trade_mode, context_data)/jingni_handle_data(trade_mode, context_data, ..., strategy=None)/jingni_after_trading_end(trade_mode, context_data)

**学习目标**：理解量化交易系统的事件驱动运行框架，理解不同事件功能模块的执行时机和职责。

**核心内容**：盘前函数用于数据预加载、参数初始化；`handle_data` 每次执行一次策略逻辑，不在内部 `while`/`sleep`，是否在交易时段由平台事件决定；盘后函数用于持久化、绩效分析和清理。

**4.查询交易日期**

**函数名称**：jingni_trading_dates(trade_mode, context_data, trading_dates_count)

**学习目标**：掌握获取交易日期的方法，为所有时间序列运算提供基准。

**核心内容**：详解如何根据偏移量查询过去、当前或未来的交易日期，并处理不同券商量化交易软件的日期差异，返回统一格式的日期，确保策略逻辑基于交易日期而非自然日。

**5.查询交易时间**

**函数名称**：jingni_trading_times(trade_mode, context_data)

**学习目标**：掌握获取交易时间的方法，为所有时间序列运算提供基准。

**核心内容**：详解如何查询当前的交易时间，并处理不同券商量化交易软件的时间差异，返回统一格式的时间，确保策略逻辑基于交易时间而非自然时间。

**6.查询账户信息**

**函数名称**：jingni_portfolio(trade_mode, context_data, security_field)

**学习目标**：掌握查询账户资产、市值、现金及持仓明细，为仓位管理和风险控制提供数据基础。

**核心内容**：详解如何通过指定查询参数，统一查询不同券商账户下的资产净值、持仓市值、可用资金和持仓列表。

**7.证券代码转换**

**函数名称**：jingni_map_security_code(security_code)

**学习目标**：掌握解决不同券商量化交易软件证券代码不一致的问题，实现证券代码的跨平台统一。

**核心内容**：详解如何识别和处理不同券商量化交易软件的证券代码格式（如ptrade的000001.SS与goldminer的SHSE.000001），实现证券代码格式双向自动转换，确保证券代码在不同券商量化交易软件策略环境下都能正确运行。

**8.查询实时行情**

**函数名称**：jingni_get_current(trade_mode, context_data, security_code)

**学习目标**：掌握从不同数据源获取实时行情数据的方法。

**核心内容**：详解如何通过不同券商量化交易软件的实时行情API，获取指定证券标的Tick级或快照数据。

**9.查询历史行情**

**函数名称**：jingni_get_history(trade_mode, context_data, security_code, frequency, fields, count)

**学习目标**：掌握获取指定频率、字段和数量的历史行情数据。

**核心内容**：详解如何调用券商量化交易软件API获取历史行情数据，并处理时间频率（如1d、1m）、字段（如open、high、low、close）和数量等参数。

**10.提取单日行情**

**函数名称**：jingni_get_field(trade_mode, context_data, security_code, date, field)

**学习目标**：掌握从获取的行情数据中提取单日特定行情数据。

**核心内容**：详解如何结合交易日历和行情数据，提取指定证券标的在特定日期的特定字段的单一数值。

**11.提取多日行情**

**函数名称**：jingni_get_field_n(trade_mode, context_data, security_code, date, field, count)

**学习目标**：掌握从获取的行情数据中提取多日特定行情数据。

**核心内容**：详解如何获取指定证券标的在最近N个交易日的特定字段的时间序列数组，为技术指标的计算提供数据基础。

**12.按照数量买卖**

**函数名称**：jingni_order_amount(trade_mode, context_data, security_code, amount, price, dry_run=None, order_type='limit', remark=None, legacy=False, unit='share')

**学习目标**：掌握根据指定证券数量提交买卖委托的基本方法。

**核心内容**：正数买入、负数卖出；默认返回统一 `OrderRef`（含 `platform/order id/status`），旧代码可传 `legacy=True` 取平台 raw；默认先过风控，`dry_run=True` 只打印不报单。

**13.按照金额买卖**

**函数名称**：jingni_order_value(trade_mode, context_data, security_code, value, price, dry_run=None, order_type='limit', remark=None, legacy=False, unit='share')

**学习目标**：掌握根据指定证券金额提交买卖委托的基本方法。

**核心内容**：买入按 `min(目标金额, 可用资金)` 计算 100 股整手；卖出按统一持仓 `available` 计算；默认先过风控并返回 `OrderRef`。

**14.自动申购新股**

**函数名称**：jingni_subscribe_new_stock(context_data, blacklist=None, dry_run=None, trade_mode=None)

**学习目标**：掌握使用自动申购新股的功能。

**核心内容**：自动获取当日新股发行信息，按额度申购；`dry_run=True` 只列出标的，不报单。

**15.自动申购新债**

**函数名称**：jingni_subscribe_new_bond(context_data, blacklist=None, dry_run=None, trade_mode=None)

**学习目标**：掌握使用自动申购新债（可转债）的功能。

**核心内容**：自动获取当日新债发行信息，按额度申购；`dry_run=True` 只列出标的，不报单。

**16.自动国债逆回购**

**函数名称**：jingni_participate_reverse_repo(context_data, cash_ratio=1.0, reverse_repo_days=1, market='SH', min_amount=1000, dry_run=None, trade_mode=None)

**学习目标**：掌握盘中将闲置现金投资于国债逆回购，提升资金利用率。

**核心内容**：按 `int(cash*ratio/1000)*10` 计算张数；不足 1000 元或不足 10 张不报单；默认 dry-run。
