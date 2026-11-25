# JingniFlow 代码问题评估与功能扩展规划方案

- 评估日期：2026-11-19
- 评估对象：`D:\codebuddy\jingni-flow`（jingniflow.py v0.1.16、`__init__.py`、pyproject.toml、examples 三个平台示例）
- 评估方式：静态代码审查 + 三家平台官方文档逐项核对（本轮未运行实盘/回测验证）
- 文档依据：
  - 掘金量化：https://www.myquant.cn/docs2/sdk/python/快速开始.html 、基本函数、行情数据查询函数（免费）、交易函数、新股新债交易函数等页面；交易日历函数另参照东财掘金同源文档 https://emt.18.cn/api/quant-help/python/python_subscribe.html
  - QMT：https://dict.thinktrader.net/innerApi/start_now.html 、system_function.html 、data_function.html 、code_examples.html
  - PTrade：<INTERNAL_HOST>/hub/help/api （已完整抓取核对）
- 结论性质说明：标注「已证实」的问题有官方文档或代码逻辑直接支撑；标注「待验证」的需在三平台仿真环境实测确认。本文只做规划，不含代码实施。

---

## 第一部分 现状概览

项目为单文件适配层（jingniflow.py，约 760 行、15 个函数），通过全局变量 `trade_mode` 与每个函数的 `trade_mode` 参数双轨选择平台，用 if/elif 分发到掘金（gm.api）、QMT（ContextInfo/内置函数）、PTrade（内置函数）的原生 API。README 采用"把 jingniflow.py 复制到策略文件尾部"的使用方式。

总体判断：**框架方向正确，但当前代码存在多处必然崩溃的缺陷和与官方文档相悖的用法，尚不具备可靠的实盘/回测运行能力；功能覆盖面约为三家平台可用 API 的一小部分，扩展空间大。** 建议先修复 P0/P1 问题并补齐测试，再按第三部分的路线图扩展功能。

---

## 第二部分 问题评估清单

### A 级：必然出错（崩溃、未定义变量、逻辑恒错）

| # | 位置 | 问题 | 影响与依据 |
|---|------|------|-----------|
| A1 | jingniflow.py:372、492 | 空值判断写成 `if x is None and x.shape[0] == 0`：x 为 None 时访问 `.shape` 抛 AttributeError；x 非 None 时整个条件恒为 False，缺省值分支永远不生效。应为 `or` 且先判 None | `jingni_get_field` / `jingni_get_field_n` 在行情取空时必崩，"缺省值 0"设计完全失效（已证实，纯逻辑错误） |
| A2 | jingniflow.py:177-181 | ptrade 代码转换分支使用未定义变量 `securities_code_char_market`（多了 s），实际变量名为 `security_code_char_market` | 输入 `.XSHG`/`.XSHE` 代码时抛 NameError，被外层 try 吞掉后原样返回未转换代码（已证实） |
| A3 | jingniflow.py:237、242、253 | 历史行情数量传成负数：`count=int(-security_count)`，而 security_count 约定 ≤0，负负得正后传给底层的是负值或 0。gm `history_n` 官方要求 count 为正整数；PTrade `get_history` 官方要求 count>0；QMT `get_market_data_ex` count=-1 语义是"取全部"而非 N 条 | 三平台历史行情查询全部不符合预期：掘金/PTrade 报错或空数据，QMT 返回全量数据（已证实，官方文档明确 count 语义） |
| A4 | jingniflow.py:286/290、320/324、358/362 | 回测"当天"分支用 `security_count-1`（即 -1）取数，却用 `iloc[security_count-1]`（即 iloc[-1] 之外的越界索引）或 `[security_count-1]` 提取：只取 1 条数据却按第 -1 位之外的索引访问 | 掘金 iloc[-1] 恰好可用但取数窗口语义错误；PTrade/QMT 按标签/位置访问越界，IndexError 或 KeyError（已证实逻辑矛盾；PTrade 旧版 pandas 负标签行为待验证） |
| A5 | jingniflow.py:614、656 | QMT 新股/新债申购把 `ContextInfo` 当变量传给 passorder，但函数入参名是 `context_data`，模块内不存在 ContextInfo 变量 | QMT 打新必抛 NameError，被打印吞掉，申购静默失败（已证实） |
| A6 | jingniflow.py:731-756 | `jingni_main` 外层 while True 没有任何 break：收盘后内层循环退出、执行盘后函数，随后外层继续循环，`app_now_time > 15:00` 两个分支都不命中，进入每 3 秒打印"程序等待运行"的死循环，进程永不退出、也不跨日重置 | 主控制循环设计失效（已证实） |
| A7 | jingniflow.py:701-715 | `jingni_handle_data` 用 `datetime.datetime.now()`（真实墙钟）判断交易窗口并 `while True + sleep` 阻塞：① 回测模式下真实时间不在 9:30-15:00 时策略一次都不执行，在窗口内则阻塞回测引擎直到真实收盘；② 与三家平台的事件驱动机制（on_bar/handlebar/handle_data）冲突 | 回测不可用；实盘阻塞事件线程（已证实机制冲突；PTrade 官方明确 tick 处理超 3 秒会丢数据） |
| A8 | examples/demo_qmt.py:6-10 | 使用 `datetime`、`datetime.timedelta` 但文件没有 `import datetime`（jingniflow.py 的 import 在"复制到尾部"之后才生效，init 定义时不报错、运行时 NameError） | QMT 示例一运行即崩（已证实） |
| A9 | examples 三个文件 | 示例调用 `jingni_subscribe_new_stock` 等函数与 `trade_mode`，但示例自身未定义/导入；QMT 内置 Python 3.6 环境无法 pip 安装本包，"复制到尾部"是唯一途径，而复制说明只写在注释里且未说明要设置 trade_mode | 三个示例按现状都无法直接运行（已证实） |

### B 级：与官方文档不符 / 语义错误（结果错但不一定崩溃）

| # | 位置 | 问题 | 官方依据 |
|---|------|------|---------|
| B1 | jingniflow.py:237 | 掘金历史行情 end_time 只传日期（当天 00:00:00）。官方：history/history_n 按 eob **前开后闭**区间返回，日线 eob 为当日 15:00 → 当天日线永远取不到；分钟线同理丢失当天全部数据 | gm 行情查询函数文档"前开后闭"注意事项 |
| B2 | jingniflow.py:253 | QMT 历史行情未显式传 `subscribe=False`（默认 True）。官方回测指引明确：回测取本地数据应指定 subscribe=False，否则走订阅通道（有 500 标的上限、依赖实时行情） | QMT 快速开始"回测模型"第 2 条 |
| B3 | jingniflow.py:253 | QMT end_time 传当天日期（00:00 边界），当天日线是否包含取决于版本对边界时间的处理 | 待验证：官方示例统一用 `timetag_to_datetime(C.get_bar_timetag(C.barpos),'%Y%m%d%H%M%S')` 作为 end_time，建议对齐 |
| B4 | jingniflow.py:504-507 | 掘金卖出固定 `PositionEffect_Close`，官方说明平仓默认**平昨仓**；可卖数量却按 `data.volume`（总持仓）计算 | 当日买入的股票（T+1 不可卖）会被计入可卖量导致废单；应使用可用量字段（字段名待验证，gm position 对象有 available 类字段） |
| B5 | jingniflow.py:530-541 | `jingni_order_value`：cash 查询失败返回 None 时 `security_value <= cash` 抛 TypeError；price=0（get_field 缺省值）时除零；未处理科创板 688 最小 200 股、北交所 100 股起 1 股递增等特殊整手规则 | gm/PTrade/QMT 文档均有各板块数量规则；PTrade order 文档明确可转债 10 张取整 |
| B6 | jingniflow.py:664-686 | 国债逆回购：① 硬编码沪市 204001（1 天期），README 承诺的 `cash_ratio`、`reverse_repo_days` 参数未实现（签名只有 context_data）；② 数量 `int(cash/1000)*10` 未扣除下单后资金占用与费用余量；③ 用日线 close 作为委托价，盘中与实时利率偏差大；④ 未校验最小 1000 元/10 张门槛（PTrade 文档明确） | PTrade order 接口说明"逆回购最小申购金额 1000 元(10 张)" |
| B7 | jingniflow.py:579、627 | 掘金 `ipo_get_instruments(df=True)` 返回 DataFrame，`if ipo_stock:` 对 DataFrame 抛 ValueError（truth value ambiguous）；后续按 list[dict] 方式遍历也不匹配 | gm 新股新债交易函数文档：df=True 返回 DataFrame |
| B8 | jingniflow.py:573-661 | 打新函数无运行模式守卫：gm ipo 系列官方明确**仅实盘可用**，PTrade `ipo_stocks_order` 仅交易模块可用；回测中定时任务触发即报错 | gm/PTrade 官方使用场景标注 |
| B9 | jingniflow.py:591-597 | PTrade 四个市场的新股申购连续调用无间隔；官方示例每次调用间 `time.sleep(5)` | PTrade ipo_stocks_order 示例 |
| B10 | jingniflow.py:69-72 | `jingni_trading_times` 注释称"实时模式返回当前本地时间"，实际三平台都返回 bar/回测时间（QMT 实时分笔驱动下为最新 bar 时间，非墙钟） | 与注释语义不符，策略若据此做时间判断会出错 |
| B11 | jingniflow.py:50-55 | QMT 交易日偏移（±n）直接返回 None，未实现也未声明不支持；官方提供 `ContextInfo.get_trading_dates` 可取个股交易日列表（注意 init 内不可用，需 after_init 之后） | QMT system_function 文档 |
| B12 | jingniflow.py:32-35 | 掘金 `get_next_n_trading_dates / get_previous_n_trading_dates` 取返回列表 `[0]` 作为"第 n 个交易日"。函数存在于 gm 生态（东财掘金同源文档可查），但返回列表中 [0] 是否恰为第 n 日**待验证**（myquant 主站对应页面本轮未直接核到） | 建议实测或改用 get_trading_dates 区间切片实现 |
| B13 | jingniflow.py:128-207 | 代码转换只覆盖沪深 A 股格式：不支持北交所（.BJ/BSE）、可转债/ETF 特殊后缀、指数代码；无输入校验（无 '.' 的代码 find('.')-1=-1 会取末位字符误判）；异常时原样返回输入，调用方无法感知失败 | 三平台代码规范（QMT 支持 430047.BJ 等，官方示例可查） |
| B14 | jingniflow.py:210-229 | `jingni_get_current` 的 security_field 参数在 PTrade/QMT 分支被忽略，三平台返回结构完全不同（gm list[dict] / PTrade dict / QMT dict），未做统一化 | 跨平台"统一接口"目标未达成 |
| B15 | jingniflow.py:379-496 | `jingni_get_field_n` 各分支取数窗口不一致：掘金 count<0 用 count-1，PTrade 用 count，QMT 用 count-1；实时分支只返回单标量而非序列 | 同一策略换平台结果不同（已证实代码不一致） |
| B16 | jingniflow.py:401 | 掘金实时分支 `data[security_field].values`：current() 返回 list[dict]，不能用字符串键索引 | 实时取数必抛 TypeError（待验证 current 返回结构，官方为 list[dict]，基本可证实） |
| B17 | examples/demo_qmt.py | ① 首行 `# encoding: gbk`，官方强制要求 `#coding:gbk` 且文件实际需以 GBK 保存（当前文件为 UTF-8 含中文注释，QMT 内解析会乱码/报错）；② handlebar 未加 `if not C.is_last_bar(): return`，实盘启动时会对全部历史 K 线逐根执行策略 | QMT 快速开始"警告"与实盘示例 |
| B18 | examples/demo_qmt.py:6-10 | `schedule_run(..., repeat_times=1, interval=1天)`：官方语义为"首次触发后**再**重复 1 次"，即只执行 2 次，并非每日循环；每日任务应 repeat_times=-1；且官方提示首次时间已过会立即触发 | QMT schedule_run 参数说明 |
| B19 | examples/demo_goldminer.py:9 | 只订阅 '1d' 频率却定义 on_tick 期望触发；日线订阅不会产生 tick 事件 | gm 数据订阅文档 |
| B20 | examples/demo_ptrade.py | PTrade 回测分钟周期下 run_daily 的 time 限定 09:31~11:30/13:00~15:00，日周期回测一律 15:00 执行；示例 10:00/10:10/14:50 在日线回测中全部挤到 15:00，打新/逆回购时序失真 | PTrade run_daily 注意事项第 3 条 |

### C 级：架构与工程化问题

| # | 位置 | 问题 |
|---|------|------|
| C1 | `__init__.py`:3 | `from JingniFlow.jingniflow import *` 假定包名为大写 JingniFlow，而 pyproject 声明 `py-modules=["jingniflow"]` 的扁平模块安装，安装后 `import jingniflow` 不会执行该 `__init__`，直接运行则 ModuleNotFoundError。包布局与导入路径自相矛盾 |
| C2 | pyproject.toml | `dynamic=["version"]` 但未配置 `[tool.setuptools.dynamic]` 版本来源，构建会失败；pytest 配置 testpaths=["tests"] 但仓库无 tests 目录；dependencies 为空但未声明 gm 等可选依赖 |
| C3 | jingniflow.py:20-21 | 模块级 `global trade_mode`（模块作用域无意义）+ 默认值 '软件名称'；部分函数读全局、部分读参数，双轨制极易错配；直接运行本文件时 jingni_main 以空字符串 context 启动并死循环 |
| C4 | 全文件 | 所有异常被 `except Exception: print(...)` 吞掉并返回 None/原值：NameError 这类编程错误与网络异常无法区分，调用方拿到 None 后继续运算引发二次错误；无 logging、无错误码 |
| C5 | jingniflow.py:111-120、518-521 | QMT 分支依赖策略环境注入的全局 `account`，且账户类型硬编码 'stock'，两融账号（官方示例 buy_code 33/34）不可用；未提供账号配置入口 |
| C6 | 全文件 | 下单函数不返回委托 ID/状态，无撤单、无委托查询、无成交回报处理，策略无法做订单生命周期管理（三家平台均有对应 API，见第三部分） |
| C7 | 全文件 | 无类型注解、无 docstring 参数契约（count 正负约定、field 命名约定全靠猜）、README 函数签名与实现不一致（如 order_amount 文档写有 direction 参数、逆回购文档写有 cash_ratio 参数，实现均无） |
| C8 | 使用方式 | "复制源码到策略尾部"导致版本碎片化，无法随包升级；QMT Python 3.6 约束（pyproject 宣称 >=3.8）未在文档中说明兼容策略 |
| C9 | 全文件 | 大量重复代码：字段映射（open/high/low/close→各平台字段）在 get_field/get_field_n 中重复 6 处；代码转换分支重复且含死分支（.SZ→.SZ 写了两次） |
| C10 | 安全 | 无风控层：无单笔/单日限额、无涨跌停与停牌校验、无重复下单防护（PTrade 官方明确 order_target 类接口在持仓同步时滞下会重复下单，自研循环同样存在此风险） |

### 修复优先级建议

- **P0（先修，否则任何平台都跑不通）**：A1-A9、C1、C2、B17
- **P1（语义正确性）**：B1-B16、B18-B20、C3-C5
- **P2（工程质量）**：C6-C10 及测试体系建设

---

## 第三部分 功能扩展规划

### 3.1 扩展总体思路

1. **先重构骨架，再堆函数**：把 if/elif 单文件分发改为「统一接口层 + 三个平台适配器」结构（策略只依赖统一接口；适配器内部调用原生 API）。保留现有 `jingni_*` 函数名作为兼容入口，避免破坏已有用户策略。
2. **统一数据契约**：定义跨平台的标的代码规范（内部统一 `600000.SH` 风格，出入口自动转换）、K 线周期映射表（1m/5m/15m/30m/60m/1d/1w/1mon…，注意 QMT 月线是 '1mon'、PTrade 是 'mo'、gm 无月线需合成）、字段映射表（open/high/low/close/volume/amount/preclose/涨跌停价等）、统一返回结构（建议 DataFrame/dict 二选一并写进文档）。
3. **统一时间语义**：所有"当前时间/当前 bar"取平台回测时钟而非墙钟；count 统一为正整数"最近 N 条"，偏移统一为负数"前第 n 条"，在适配层翻译。
4. **能力分级声明**：每个统一函数标注三平台支持度（完整支持/降级支持/不支持+原因），不支持时显式抛 `UnsupportedOperation` 而不是静默返回 None。
5. **兼容 QMT Python 3.6**：适配层代码避免 3.7+ 语法（dataclasses 可用 typing.NamedTuple 替代），或提供 3.6 兼容分支；这是"复制到策略尾部"场景的硬约束。

### 3.2 三家平台可封装 API 盘点（均来自本轮官方文档核对）

#### 掘金量化（gm.api）

| 能力域 | 可封装函数 | 现状 |
|--------|-----------|------|
| 行情查询 | history（区间）、history_n（最新N条）、current、current_price、last_tick、context.data 滑窗 | 仅粗糙封装 history_n/current |
| 数据订阅 | subscribe（多标的/多频率/count/fields/format）、unsubscribe、on_tick/on_bar/on_l2order/on_l2transaction 事件 | 未封装 |
| L2 数据 | get_history_l2ticks/l2bars/l2transactions/l2orders/l2orders_queue（券商付费） | 未封装 |
| 通用数据 | get_trading_dates、get_previous/next_n_trading_dates、get_trading_dates_by_year、get_symbol_infos、get_symbols、get_history_symbol、分红送股/配股/复权因子/股东/龙虎榜/沪深港通等（3.17+ 新增 30+ 接口） | 仅交易日部分封装 |
| 交易下单 | order_volume、order_value、order_percent、order_target_volume、order_target_value、order_target_percent、order_batch | 仅 order_volume |
| 订单管理 | order_cancel、order_cancel_all、order_close_all、get_orders、get_unfinished_orders、get_execution_reports | 完全缺失 |
| 事件回报 | on_order_status、on_execution_report、on_trade_data_connected、on_account_status、on_parameter（动态参数）、on_backtest_finished | 完全缺失 |
| 定时/控制 | schedule、timer/timer_stop（毫秒级，仅仿真/实盘）、stop、set_token、log、add_parameter | 仅示例用 schedule |
| 打新 | ipo_get_instruments、ipo_get_quota、ipo_buy、ipo_get_match_number（配号）、ipo_get_lot_info（中签） | 仅清单+申购，缺额度/配号/中签 |
| 可转债 | bond_convertible_call/put/put_cancel（转股/回售/撤销，券商实盘） | 未封装 |
| 账户 | context.account()（cash/positions）、多账户 account 参数 | 部分封装 |

#### QMT（ContextInfo / 内置函数）

| 能力域 | 可封装函数 | 现状 |
|--------|-----------|------|
| 行情获取 | get_market_data_ex（K线/tick/L2/特色数据）、get_full_tick（全推，仅实盘）、get_local_data | 仅 get_market_data_ex/get_full_tick 粗糙封装 |
| 数据下载 | download_history_data（基础周期 tick/1m/5m/1d，合成周期规则） | 未封装（回测前置条件，急需） |
| 订阅 | subscribe_quote（含 L2 六类周期）、subscribe_whole_quote（市场级全推）、unsubscribe_quote、subscribe_formula/call_formula（VBA 模型） | 未封装 |
| 合约信息 | get_instrument_detail（涨跌停价/股本/停牌状态/上市日）、get_stock_name、get_open_date、get_last_volume、get_total_share、get_st_status/get_his_st_data | 未封装 |
| 板块 | get_stock_list_in_sector、create_sector、reset_sector_stock_list、add/remove_stock_from_sector、get_sector_list | 未封装 |
| 交易下单 | passorder（股票23/24、两融33/34/27/32、期货0/3/6、期权50/51、基金60/61、篮子35）、algo_passorder/smart_algo_passorder（算法单）、cancel（撤单）、set_basket（篮子） | 仅 passorder 股票限价 |
| 订单管理 | get_trade_detail_data（account/position/order/deal 四类）、order_callback/deal_callback 回报、投资备注 userOrderId 追踪、quickTrade=2 立即下单模式 | 仅账户/持仓查询 |
| 定时/事件 | schedule_run/cancel_schedule_run（任务组）、run_time、init/after_init/handlebar/stop、is_last_bar/is_new_bar | 仅示例用 schedule_run（且用法错误） |
| 特色数据 | get_financial_data/get_raw_financial_data（财务）、get_turnover_rate、get_longhubang（龙虎榜）、get_north_finance_change/get_hkt_details/get_hkt_statistics（北向）、get_etf_info/get_etf_iopv、get_svol/get_bvol（内外盘）、扩展数据写入 create_extend_data/set_extend_data_value | 未封装 |
| 打新 | get_ipo_data("STOCK"/"BOND") + passorder | 已封装但有 A5 缺陷 |
| 两融 | get_assure_contract（担保明细）、query_credit_account | 未封装 |

#### PTrade（内置函数）

| 能力域 | 可封装函数 | 现状 |
|--------|-----------|------|
| 行情 | get_history（回测/交易）、get_price（研究/回测/交易，支持区间）、get_snapshot（仅交易）、get_gear_price（档位价）、get_tick_direction（分时成交）、get_individual_entrust/transcation（逐笔，需L2）、get_sort_msg（板块涨幅排名） | 仅 get_history/get_snapshot 粗糙封装 |
| 交易日历 | get_trading_day、get_all_trades_days、get_trade_days | 仅 get_trading_day |
| 股票信息 | get_stock_name、get_stock_info、get_stock_status（ST/停牌/退市）、get_stock_exrights（除权除息）、get_stock_blocks、get_index_stocks、get_industry_stocks、get_Ashares、get_market_value（市值/PE/PB）、get_fundamentals（财务） | 未封装 |
| ETF | get_etf_list、get_etf_info、get_etf_stock_info、get_etf_stock_list、etf_basket_order（篮子下单）、etf_purchase_redemption（申赎） | 未封装 |
| 下单 | order、order_target、order_value、order_target_value、order_market（6 种市价类型+沪市保护限价）、after_trading_order/after_trading_cancel_order（盘后固定价）、order_tick（tick 触发）、debt_to_stock_order（债转股） | 仅 order |
| 订单管理 | cancel_order、cancel_order_ex、get_order、get_orders、get_all_orders、get_open_orders、get_trades、get_position、get_positions | 完全缺失 |
| 定时/事件 | run_daily、run_interval（≥3秒，多线程）、initialize/before_trading_start/handle_data/tick_data/after_trading_end、set_universe、g 全局对象持久化（pickle，'__'前缀不保存） | 仅示例用 run_daily |
| 风控辅助 | check_limit（涨跌停状态 2/1/0/-1/-2）、is_trade、permission_test | 仅 is_trade |
| 两融 | margin_trade、margincash_open/close/direct_refund、marginsec_open/close/direct_refund、get_margincash_stocks、get_marginsec_stocks、get_margin_contract(real)、get_margin_assert、get_assure_security_list、四类最大可买可卖数量查询 | 未封装 |
| 期货/期权 | buy_open/sell_close 等期货四键、get_instruments、get_opt_contracts/get_opt_objects/get_contract_info、set_future_commission/set_margin_rate | 未封装 |
| 技术指标 | get_MACD、get_KDJ、get_RSI、get_CCI（平台内置） | 未封装 |
| 通知 | send_email、send_qywx（企业微信，券商配置决定） | 未封装 |
| 账务 | get_deliver（交割单）、get_fundjour（资金流水）、get_trades_file（对账文件）、get_user_name | 未封装 |
| 打新 | ipo_stocks_order（0-4 市场类型+黑名单） | 已封装，缺黑名单与间隔 |

### 3.3 新增统一函数设计（建议命名沿用 jingni_ 前缀）

按能力域分组，每个函数给出三平台映射与优先级（P1=第一批，P2=第二批，P3=远期）：

**① 订单生命周期（最高优先，当前完全缺失）**
- `jingni_cancel_order(order_id)`：gm order_cancel / QMT cancel(m_strOrderSysID) / PTrade cancel_order —— P1
- `jingni_cancel_all()`：gm order_cancel_all / QMT 遍历可撤状态(48,49,50,51,52,55,86,255)逐笔 cancel / PTrade 遍历 get_open_orders 撤单 —— P1
- `jingni_get_orders(status_filter)`：gm get_orders/get_unfinished_orders / QMT get_trade_detail_data(...,'order') / PTrade get_orders/get_open_orders —— P1
- `jingni_get_trades()`：gm get_execution_reports / QMT 'deal' / PTrade get_trades —— P1
- `jingni_order_amount/value` 改造：返回统一委托回执（委托号、状态），QMT 用投资备注 userOrderId 关联，gm 用 cl_ord_id，PTrade 用 order id —— P1
- 委托状态统一枚举（已报/部成/已成/已撤/废单），QMT 状态码 56/53/54/57 等做映射 —— P1

**② 下单方式补全**
- `jingni_order_market(code, amount, market_type, protect_price)`：gm OrderType_Market+沪市保护限价 / QMT prType 42 等 / PTrade order_market(0-5) —— P1
- `jingni_order_target_volume / target_value / target_percent`：gm 原生同名 / PTrade order_target 系列（需内置防重复下单：在途委托计入）/ QMT 自研"目标持仓差额下单"（参照官方调仓 Demo，含等待字典与超时撤单）—— P2
- `jingni_order_batch(orders)`：gm order_batch / QMT set_basket+passorder(35) / PTrade etf_basket_order 或循环下单 —— P2
- 整手规则引擎：主板 100、科创板 200 起、北交所 100 起 1 股递增、可转债 10 张、逆回购 10 张，卖出零股一次性放行 —— P1（并入 order_amount/value 修复）

**③ 行情与订阅**
- `jingni_subscribe(codes, frequency, count, callback)` / `jingni_unsubscribe()`：gm subscribe/unsubscribe / QMT subscribe_quote+unsubscribe_quote（记录订阅号）/ PTrade set_universe+tick_data/handle_data 或 run_interval —— P1
- `jingni_get_history` 修复版：统一正数 count、统一 end_time 语义（含当天）、QMT 回测 subscribe=False、复权方式参数化（none/pre/post/等比）—— P0（属修复）
- `jingni_get_history_range(code, freq, start, end)`：gm history / QMT get_market_data_ex(start_time,end_time) / PTrade get_price —— P1
- `jingni_get_tick(codes)`：gm current/last_tick / QMT get_full_tick / PTrade get_snapshot，返回统一字段（最新价/五档/涨跌停价/停牌状态）—— P1
- `jingni_download_history(codes, period, start, end)`：仅 QMT 需要（download_history_data，含合成周期→基础周期换算），其余平台空实现 —— P1
- L2 统一接口（逐笔成交/逐笔委托/十档）：gm get_history_l2* / QMT l2* 周期 / PTrade get_individual_*，标注权限依赖 —— P3

**④ 标的与基础数据**
- `jingni_get_stock_info(codes)`：名称/上市日/涨跌停价/股本/停牌：gm get_symbol_infos+get_instruments / QMT get_instrument_detail / PTrade get_stock_info+get_stock_status —— P1
- `jingni_get_stock_status(codes, 'ST'/'HALT'/'DELISTING')`：PTrade 原生 / QMT get_st_status+InstrumentStatus / gm get_symbols —— P1（风控前置）
- `jingni_check_limit(codes)`：涨跌停状态：PTrade check_limit / QMT 用 UpStopPrice+lastPrice 计算 / gm 用涨跌停价字段计算 —— P1
- `jingni_get_sector_stocks(sector)` / `jingni_get_index_stocks(index)`：QMT get_stock_list_in_sector / PTrade get_index_stocks、get_industry_stocks / gm 对应板块接口 —— P2
- `jingni_get_trading_dates(start,end)` / `jingni_is_trading_day(date)`：gm get_trading_dates / PTrade get_trade_days / QMT get_trading_dates（after_init 后可用）—— P1（替换现有 None 实现）
- `jingni_get_fundamentals(codes, table, fields)`：gm get_fundamentals / QMT get_financial_data（默认 announce_time 防未来数据）/ PTrade get_fundamentals —— P2
- 除权除息/分红：PTrade get_stock_exrights / gm 分红送股接口 / QMT dividend_type 处理 —— P3

**⑤ 事件与调度框架（替换 jingni_main 死循环）**
- `jingni_schedule(func, time_rule, date_rule)`：gm schedule / QMT schedule_run(repeat_times=-1) / PTrade run_daily —— P0（修复示例即依赖）
- `jingni_run_interval(func, seconds)`：gm timer / QMT run_time / PTrade run_interval —— P1
- 统一事件模板：提供三平台策略骨架（init/盘前/盘中/盘后/stop），盘中逻辑由平台事件驱动，框架只做"交易时段过滤+策略分发"，不再自建 while 循环；QMT 骨架强制 is_last_bar 守卫与 #coding:gbk —— P0
- 订单/成交回报事件：gm on_order_status/on_execution_report / QMT order_callback/deal_callback / PTrade 轮询 get_orders 兜底 —— P2

**⑥ 业务功能增强（现有三件套升级）**
- 打新：增加额度查询（gm ipo_get_quota）、中签查询（gm ipo_get_lot_info）、黑名单（PTrade black_stocks）、申购间隔、模式守卫、统一回执 —— P1
- 逆回购：参数化（天数 1/2/3/4/7/14/28…对应 204001-204018 与深市 1318xx 代码表、资金比例、最低门槛校验、实时价委托）—— P1
- 可转债转股/回售：gm bond_convertible_* / PTrade debt_to_stock_order / QMT 对应 opType —— P3
- ETF 申赎与篮子：PTrade etf_purchase_redemption/etf_basket_order / QMT passorder 60/61+get_etf_info / gm 基金交易函数 —— P3
- 两融：PTrade margin 系列 / QMT 33/34/27/32+get_assure_contract / gm 信用账户支持度待验证 —— P3
- 通知：`jingni_notify(msg)`：PTrade send_email/send_qywx / gm log+本地文件 / QMT 本地文件+可选第三方 —— P3（涉及外发，默认关闭，用户显式配置才启用）

**⑦ 风控与工程层（新增模块）**
- 下单前校验链：资金/可用持仓/涨跌停/停牌/整手/单笔限额/单日累计限额/在途委托去重 —— P1
- 统一日志（logging，分级、落盘）与错误类型体系（参数错误/平台不支持/网络异常/柜台拒绝）—— P1
- 状态持久化：PTrade 用 g+pickle 机制；QMT 用全局类实例（官方明确 ContextInfo 属性随 bar 回退，不可存委托状态）；gm 用 context 属性+本地文件 —— P2
- 测试体系：tests/ 目录 + 三平台 API mock（桩对象模拟 ContextInfo/gm.api/PTrade 内置函数），覆盖代码转换、count 语义、字段映射、整手计算、空值路径；QMT 3.6 语法兼容检查 —— P0（与修复同步）

### 3.4 实施路线图（建议）

**阶段 0：止血修复（P0）**
1. 修复 A1-A9 全部必然错误；修复包布局 C1/C2（确定"扁平模块"或"包"二选一，推荐改为规范包结构 jingniflow/，同时保留单文件合并导出以兼容 QMT 复制场景）。
2. 重写 jingni_main/handle_data 为平台事件驱动骨架；三个示例改为可直接运行的完整模板（含 import、trade_mode 设置、QMT GBK 编码与 is_last_bar 守卫）。
3. 建立 mock 测试骨架，为每个修复写回归用例。
   验收：三平台示例在仿真/回测环境可启动、定时任务按日重复、历史行情取数数量与时间窗口正确。

**阶段 1：语义对齐 + 订单闭环（P1 核心）**
1. 统一代码转换（含北交所/可转债/ETF）、周期映射、字段映射、count/时间语义；修复 B1-B16。
2. 新增订单生命周期四件套（撤单/查委托/查成交/回执）与市价单、整手规则引擎、下单前风控校验链。
3. 升级打新/逆回购为参数化完整实现；补 QMT 数据下载与交易日历。
   验收：同一策略脚本在三平台仿真环境下单→查询→撤单全链路一致；mock 测试覆盖率核心路径 ≥80%。

**阶段 2：数据与调度扩展（P1 其余 + P2）**
1. 订阅统一接口、区间行情、标的信息/状态/涨跌停、股票池与指数成分、财务数据。
2. 目标持仓调仓（含 QMT 官方调仓 Demo 的防超单机制）、批量下单、回报事件、状态持久化。
   验收：双均线+打新+逆回购+调仓的组合示例策略三平台回测结果口径一致（允许撮合规则差异，需文档列明）。

**阶段 3：高级品种与生态（P3）**
L2 数据、可转债转股回售、ETF 申赎、两融、期货/期权（QMT/PTrade）、通知、绩效分析辅助。按用户需求逐项立项，每项先做平台能力验证再封装。

### 3.5 风险与待验证清单（实施前必须确认）

| 事项 | 验证方式 |
|------|---------|
| gm get_next/previous_n_trading_dates 返回 [0] 的语义 | 掘金仿真环境实测，或改用 get_trading_dates 切片 |
| gm position 可用数量字段名（available 类） | 查 gm 数据结构文档 position 对象并实测 |
| QMT get_market_data_ex 当天日线边界、count 与 end_time 组合行为 | QMT 回测实测（不同客户端版本可能有差异） |
| PTrade 旧版 pandas 对 Series[-1] 标签索引的行为 | PTrade 回测实测 |
| QMT 内置 Python 3.6 对适配层语法的限制 | 在 QMT 策略编辑器实际加载验证 |
| gm ipo 系列、PTrade ipo_stocks_order 在仿真环境可用性 | 官方标注仅实盘/交易模块，仿真可能不可用，需降级提示 |
| 两融/期货/期权各平台权限差异 | 逐项权限测试后再封装 |
| PTrade 文档来源为用户提供的 IP 站点，版本可能与券商部署版本不一致 | 以目标券商实际 PTrade 版本复核接口签名 |

### 3.6 交付与协作约定

- 本方案经确认后，按阶段 0 → 1 → 2 → 3 顺序实施，每阶段独立提交并附测试与变更说明。
- 修改默认在原文件上进行；`jingni_*` 既有函数签名变更（如逆回购加参数）采用"新增可选参数+默认值"方式保持向后兼容。
- 所有新增函数同步更新 README 功能表与参数契约，标注三平台支持度。
- 实盘相关功能一律先在仿真环境验证；涉及真实资金的操作默认关闭，需用户显式开启。

---

## 附：本轮已核对的官方文档页面

1. 掘金快速开始（策略结构/运行模式/数据研究示例）
2. 掘金基本函数（init/schedule/run/stop/timer，MODE_LIVE=1/MODE_BACKTEST=2）
3. 掘金行情数据查询函数（last_tick/current_price/history/history_n/context.data/L2 系列，前开后闭区间、count 正整数、单次 33000 条上限）
4. 掘金交易函数（order_volume/value/percent/target 系列/batch/cancel/close_all/get_orders/get_unfinished_orders/get_execution_reports，沪市市价保护限价、平昨仓规则）
5. 掘金新股新债交易函数（ipo_buy/ipo_get_quota/ipo_get_instruments/ipo_get_match_number/ipo_get_lot_info，仅实盘）
6. 东财掘金数据订阅（subscribe/unsubscribe 完整签名；get_previous/next_n_trading_dates 存在性佐证）
7. QMT 快速开始（回测/实盘模型、handlebar/subscribe/run_time 三机制、#coding:gbk、quickTrade、GBK 编码）
8. QMT 系统函数（ContextInfo 属性随 bar 回退、init/after_init/handlebar/stop、schedule_run/cancel_schedule_run/run_time、is_last_bar/is_new_bar、板块管理）
9. QMT 行情函数（download_history_data 合成周期规则、get_market_data_ex 全参数、get_full_tick 仅实盘、subscribe_quote/whole_quote、财务/龙虎榜/北向/ETF/合约信息）
10. QMT 完整示例（passorder 各品种 opType、新股申购、投资备注、调仓防超单 Demo、两融、算法单、篮子交易）
11. PTrade API 全文（run_daily/run_interval、get_trading_day/get_trade_days、get_history/get_price/get_snapshot、order 系列/order_market/ipo_stocks_order/after_trading_order、两融/期货/期权函数目录、is_trade/check_limit、g 持久化机制）
