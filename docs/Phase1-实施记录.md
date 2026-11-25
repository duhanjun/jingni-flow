# Phase 1 实施记录：契约层与订单闭环

**版本**：v0.2.0.dev0  
**范围**：股票现货 + 打新/逆回购；只覆盖交易相关能力，不扩展期货、期权、两融、ETF、L2。  
**依据**：`docs/JingniFlow-代码评估与功能扩展规划方案.md` v1.1（D1—D7 全部选 A）。

## 1. 本阶段交付

### 1.1 统一订单模型

新增 `jingniflow/core/order.py`：

- 统一状态：`PENDING/PARTIAL/FILLED/CANCELED/REJECTED/EXPIRED/UNKNOWN`。
- 统一方向：`BUY/SELL`；兼容 `1/2`、`23/24`、中文方向、平台常量名。
- 统一订单字段：`order_ref`、`platform_order_id`、`code`、`side`、`price`、`amount`、`filled`、`status`、`status_code`、`created_at`、`updated_at`、`remark`、`raw`。
- 平台状态码映射：掘金 0—5、QMT 48—57、PTrade 0—8；未知码返回 `UNKNOWN`，不猜测。
- `coerce_order_ref` 支持 `OrderRef`、dict、字符串，便于旧策略把平台订单号直接传给撤单接口。

### 1.2 风控

新增 `jingniflow/core/risk.py`：

- `check_order(context, code, side, amount, price, account, positions, now, record, check_sell_available)`。
- 检查项：kill switch、方向、正数、正价、买入 100 股整手、单笔数量/金额、每日笔数、重复窗口、现金、可卖量。
- `record=False` 用于 `dry_run`：只检查，不消耗每日计数/重复窗口。
- 卖出默认按统一 `available` 校验；逆回购通过 `check_sell_available=False` 跳过股票持仓校验。
- `calc_max_buy` 按可用资金与价格向下取整到 100 股；`calc_max_sell` 按 `available`。
- `set_kill_switch` 同时写入运行上下文与模块级状态；不依赖 QMT `ContextInfo`。

`RuntimeConfig` 默认值按 D7 调整：

| 配置 | 默认 |
|---|---|
| `dry_run` | `True` |
| `max_order_amount` | `100000` |
| `max_order_value` | `1000000.0`（仅买入检查） |
| `max_daily_orders` | `100` |
| `repeat_window_seconds` | `3` |
| `kill_switch` | `False` |

> 这些默认值是安全护栏，不代表策略参数。实盘前应按账户规模调整；卖出不受 `max_order_value` 限制，避免无法平仓。

### 1.3 适配器交易接口

`adapters/base.py` 增加默认接口：`order`、`cancel`、`cancel_all`、`get_orders`、`get_trades`、`get_positions`、`get_account`。

#### 掘金 `adapters/goldminer.py`

- 下单：`order_volume`；方向用 `OrderSide_Buy/Sell`，价格类型用 `OrderType_Limit/Market`，仓位效果 `PositionEffect_Open/Close`。
- 撤单：`order_cancel`；全撤：`order_cancel_all`。
- 查询：`get_orders` / `get_unfinished_orders`；成交：`get_execution_reports`。
- 统一持仓：`volume` 为总量，`available = volume - volume_today`。
- 统一账户：`nav`、`balance`、`available`、`market_value`、`frozen`、`pnl`。

#### QMT `adapters/qmt.py`

- 下单：`passorder(opType, 1101, account, code, prType, price, volume, "", 2, remark, context.raw)`。
  - 买入 `opType=23`，卖出 `24`；限价 `prType=11`；市价沪市 `42`、深市 `5`。
- 撤单：`cancel(order_id, account, account_type, context.raw)`；全撤遍历未完成委托。
- 查询：`get_trade_detail_data(account, account_type, "order"/"deal"/"position"/"account")`。
- 订单字段：`m_strOrderSysID`、`m_strInstrumentID`、`m_strExchangeID`、`m_nDirection`、`m_dLimitPrice`、`m_nVolumeTotalOriginal`、`m_nVolumeTraded`、`m_nOrderStatus`、`m_strRemark`。
- 持仓字段：`m_nVolume`、`m_nCanUseVolume`、`m_dOpenPrice`、`m_dMarketValue`、`m_dFloatProfit`。
- 账户字段：`m_dBalance`、`m_dAvailable`、`m_dInstrumentValue`、`m_dFrozen`。
- 账户解析：优先 `config.account_id`，其次策略全局 `account`，再次 `context.raw.account`。

#### PTrade `adapters/ptrade.py`

- 下单：限价 `order(code, signed_amount, limit_price=price)`；市价优先 `order_market`，失败回退 `order`。
- 撤单：`cancel_order(order_id)`；全撤遍历 `get_orders`。
- 查询：`get_orders` / `get_open_orders`、`get_trades`；兼容 dict/list 返回。
- 持仓：`context.portfolio.positions`；字段兼容 `security/code`、`amount/total_amount`、`enable_amount/available`。
- 账户：`context.portfolio` 的 `portfolio_value/cash/positions_value`。

### 1.4 交易 API

`api/trade.py` 已重写：

| 函数 | 行为 |
|---|---|
| `jingni_order_amount(..., dry_run=None, order_type='limit', remark=None, legacy=False, unit='share')` | 数量下单；默认返回 `OrderRef`；`legacy=True` 返回平台 raw；`unit` 首批只接受 `share` |
| `jingni_order_value(...)` | 金额下单；买入按 `min(金额, 可用资金)` 计算 100 股整手；卖出按可用持仓 |
| `jingni_order_target_amount(...)` | 目标持仓差额 = target - current - 在途买 + 在途卖；买入差额向下取整 100 股 |
| `jingni_order_target_value(...)` | 目标市值按价格换算目标股数后走差额引擎 |
| `jingni_order_market(...)` | 市价单；QMT 走 `passorder` 市价类型 |
| `jingni_cancel_order(...)` | 单笔撤单，返回 bool |
| `jingni_cancel_all(...)` | 全撤，返回平台计数/实际撤单数 |
| `jingni_close_all(...)` | 按统一持仓 `available` 逐只卖出，返回成功提交数 |
| `jingni_get_orders(...)` | 统一订单列表；`status` 过滤、`include_finished` 控制 |
| `jingni_get_trades(...)` | 统一成交列表；可按 `OrderRef` 过滤 |

### 1.5 账户、风控、运行、行情 API

- `api/account.py`：`jingni_get_account`、`jingni_get_positions` 改走适配器统一字段；旧 `jingni_portfolio` 保留。
- `api/risk.py`：`jingni_set_risk`、`jingni_check_order`、`jingni_calc_max_buy`、`jingni_calc_max_sell`、`jingni_kill_switch`、`jingni_log`。
- `api/runtime.py`：`jingni_now`、`jingni_wall_now`、`jingni_offset_trade_date`、`jingni_schedule`。
- `api/market.py`：`jingni_history`（统一 DataFrame）、`jingni_tick`（统一 tick 别名）。
- `api/__init__.py`：导出 59 个函数/入口；`compat/legacy.py` 同步导出。
- `api/lifecycle.py`：`jingni_handle_data` 修复为把原始 `trade_mode/context_data` 传给 `jingni_trade_strategy`，不破坏旧策略覆盖。后续新增 `jingni_set_strategy` / `jingni_get_strategy` 与 `jingni_main(..., strategy=...)`，作为面向策略作者的显式注册入口；旧占位实现保留。

### 1.6 构建

`tools/build_single.py` 的 `MODULES` 已加入 `core/order.py`、`core/risk.py`、`api/risk.py`。

已重建：

- `dist/jingniflow_single.py`（UTF-8，约 104 KB）
- `dist/jingniflow_single_gbk.py`（GBK，约 104 KB）
- 根 `jingniflow.py`（UTF-8 单文件）

构建后验证：

- UTF-8/GBK 均通过 `ast.parse(feature_version=(3, 6))`。
- 单文件直接 `exec` 可导入，`__all__` 45 项，`jingni_version()` 正常。
- `jingni_order_amount` 等新函数在单文件中可访问。

## 2. 测试

当前 33 个测试：

- Phase 0：24 个（契约、行情、交易、业务、单文件、legacy）。
- Phase 1：9 个（`tests/unit/test_order_lifecycle.py` 6 个 + `test_business.py` 逆回购实单 1 个 + `test_runtime.py` 2 个）。

覆盖：

- 掘金下单/撤单/查询/成交/统一持仓/账户。
- QMT 查询/持仓、`passorder` 参数、沪市市价 `prType=42`。
- PTrade 下单代码转换、统一账户。
- 风控：整手、单笔金额、每日笔数、重复窗口、kill switch。
- 目标持仓差额引擎：在途委托抵扣后只补 100 股。
- 逆回购：`dry_run` 不报单；实单跳过股票可卖量校验。

运行：

```powershell
python -m pytest
```

## 3. 尚未实机确认（V 清单）

以下代码路径已按官方文档/旧实现“尽力映射”，但未在三家终端实机核对，仍按规划 V-01—V-12 处理：

- V-01 QMT `get_market_data_ex` 边界/bar 时间。
- V-02 QMT `cancel` 签名、委托号字段、`m_nOrderStatus` 全量码表。
- V-03 QMT 打新 `opType`、逆回购参数。
- V-04 QMT 市价 `prType`（沪市 42 / 深市 5）与保护价。
- V-05 PTrade `order_market` 参数类型、`get_orders/get_trades` 返回结构。
- V-06 PTrade `get_snapshot` 字段、`get_price`。
- V-07 PTrade `ipo_stocks_order` 返回结构。
- V-08 掘金 `history_n` 分钟线边界。
- V-09 掘金 `volume_today` 口径。
- V-10 掘金 `get_instruments` 字段。
- V-11 三平台 Python/pandas 版本。
- V-12 QMT 单文件 GBK 粘贴后 `account` 全局可见性。

## 4. 本阶段未做

- 期货、期权、两融、ETF 申赎、L2、财务、板块、分红等非交易/延后项。
- `jingni_get_history_range`、`jingni_run_interval`、`jingni_is_trading_time`、`jingni_get_instrument` 等 P1 周边函数（保留在 Phase 2）。
- 订单状态回调/事件注册（E-01/E-02，P2）。
- 订单 JSON 持久化；当前状态在模块级内存中，进程重启丢失。
- QMT `ContextInfo` 属性隔离已做（风控状态挂 `RuntimeContext`，不写 `ContextInfo`），但跨进程恢复未实现。

## 5. 下一阶段建议

1. 用三家模拟/仿真终端跑 `docs/smoke-checklist.md` 的 8 项，优先关闭 V-02、V-05、V-09。
2. 补 `jingni_get_history_range`、`jingni_is_trading_time`、`jingni_run_interval`、`jingni_get_instrument`，完成 Phase 2 交易相关取数/调度。
3. 增加 Golden 夹具：录制三平台订单/成交/持仓返回，锁定字段映射。
4. 增加订单状态回调适配（P2），但保持“轮询可用、回调可选”。
