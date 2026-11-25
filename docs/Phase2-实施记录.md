# Phase 2 实施记录：交易周边数据、日历与调度

- 版本：`0.2.0.dev0`
- 范围：股票现货交易周边能力（D-02、D-08、R-04、R-08、I-01、I-02、I-04、I-07）
- 状态：代码与 Mock 测试已完成；掘金 / QMT / PTrade 回测冒烟已通过；模拟/实盘真机待按 `docs/live-validation-checklist.md` 执行
- 依赖：仅 pandas / numpy，无新增第三方依赖

## 1. 本轮新增内容

### 1.1 新增模块

| 文件 | 作用 |
|---|---|
| `jingniflow/core/calendar.py` | 日期归一化、A 股连续竞价/集合竞价时段判断 |
| `jingniflow/core/instrument.py` | 板块推断、标的元数据构造、平台字段归一化 |
| `jingniflow/api/instrument.py` | `jingni_get_instrument` / `jingni_get_stock_status` |
| `jingniflow/api/calendar.py` | `jingni_get_trading_dates` / `jingni_is_trading_day` / `jingni_is_trading_time` |
| `tests/unit/test_phase2.py` | 6 个 Phase 2 Mock 测试 |

### 1.2 扩展模块

- `adapters/base.py`：新增 `get_history_range`、`download_history`、`get_instruments`、`get_stock_status`、`get_trading_dates` 默认接口。
- `adapters/goldminer.py`：范围行情、标的元数据、交易日历、数据预热空操作。
- `adapters/qmt.py`：范围行情、逐只下载、标的详情、股票状态降级、交易日历；范围行情 `count=-1`，下载按最小可用周期。
- `adapters/ptrade.py`：`get_price` 范围行情、`get_stock_info` 标的元数据、`get_stock_status`、`get_trade_days`、下载空操作。
- `api/market.py`：新增 `jingni_get_history_range` / `jingni_download_history`。
- `api/runtime.py`：新增 `jingni_run_interval`；修正 QMT 交易日历 `count=-1` 的旧实现。
- `api/__init__.py`、`compat/legacy.py`：导出全部 Phase 2 函数。
- `tools/build_single.py`：加入 `core/calendar.py`、`core/instrument.py`、`api/instrument.py`、`api/calendar.py`。

## 2. API 契约

### 2.1 范围行情

```python
jingni_get_history_range(
    trade_mode, context_data, security_code,
    security_frequency="1d",
    start_time=None, end_time=None,
    fields=None, adjust="pre",
)
```

- `start_time` 必填；`end_time` 为空时由平台取到最新。
- 返回统一 DataFrame，字段仍为 `open/high/low/close/volume/amount` 等。
- 平台映射：
  - 掘金：`history(symbol, frequency, start_time, end_time, fields, adjust, df=True)`；
  - QMT：`get_market_data_ex(count=-1, subscribe=False, start_time, end_time)`；
  - PTrade：`get_price(security, start_date, end_date, frequency, fields, fq)`。
- PTrade `get_price` 的 `start_date` 与 `count` 互斥，因此统一 API 强制 `start_time`，避免传入 `count`。

### 2.2 历史数据预热

```python
jingni_download_history(
    trade_mode, context_data, security_codes,
    security_frequency="1d", start_time=None, end_time=None,
)
```

- 掘金 / PTrade：服务端行情，直接返回 `None`。
- QMT：逐只调用 `download_history_data(stockcode, period, startTime, endTime)`。
- QMT 下载周期按最小可用周期降级：`15m/30m/60m -> 5m`，`1w/1M -> 1d`。

### 2.3 标的元数据

```python
jingni_get_instrument(trade_mode, context_data, security_codes, fields=None)
```

返回：

```python
{
    "600000.SH": {
        "code": "600000.SH",
        "name": "浦发银行",
        "board": "主板",
        "lot_size": 100,
        "tick_size": 0.01,
        "limit_up": 12.0,
        "limit_down": 8.0,
        "listed_date": "1999-11-10",
        "status": {"st": False, "suspend": False, "delisted": False},
    }
}
```

- 掘金：优先 `get_instruments`，失败或不可用时降级 `get_symbol_infos(sec_type1=1010)`；
- QMT：逐只 `get_instrument_detail(stockcode, iscomplete=True)`；
- PTrade：`get_stock_info`，仅原生提供 `stock_name/listed_date/de_listed_date`，其余字段为 `None` 或默认 100 股。
- 缺失字段不猜测；`lot_size` 默认 100 仅作为股票现货兜底值。

### 2.4 股票状态

```python
jingni_get_stock_status(
    trade_mode, context_data, security_codes,
    query_type="ST", date=None,
)
```

- 返回 `{canonical_code: True/False/None}`。
- `query_type=None` 或 `'ALL'` 时合并为 `{code: {'st': ..., 'suspend': ..., 'delisted': ...}}`。
- PTrade：原生 `get_stock_status(stocks, query_type='ST', query_date=None)`，支持 `ST/HALT/DELISTING`。
- QMT：从 `get_instrument_detail` 的 `IsST`、`IsTrading`、`ExpireDate` 降级推导；无法判断返回 `None`。
- 掘金：从 `get_instruments/get_symbol_infos` 的 `is_st/is_suspended/delisted_date` 降级推导；无法判断返回 `None`。

### 2.5 交易日历

```python
jingni_get_trading_dates(
    trade_mode, context_data,
    start_date=None, end_date=None, market="SH",
)
```

- 返回 `YYYYMMDD` 字符串列表，按日期升序。
- 掘金：`get_trading_dates_by_year(exchange, start_year, end_year)`，取 `trade_date` 非空行；失败时降级旧 `get_trading_dates`。
- QMT：`get_trading_dates("", start, end, 10000, "1d")`；官方要求 `count > 0`，不能使用 `-1`。
- PTrade：`get_trade_days(start_date, end_date)`，返回 numpy.ndarray 后统一格式。
- `market` 仅影响掘金交易所映射：`SH->SHSE`、`SZ->SZSE`、`BJ->BJSE`。
- 显式 `(平台, context, 起, 止, 市场)` 的查询结果做进程内缓存，避免 `handle_data` 每轮重复请求柜台日历；缓存上限 256 条。

### 2.6 交易日与交易时段

```python
jingni_is_trading_day(trade_mode=None, context_data=None, date=None)
jingni_is_trading_time(
    trade_mode=None, context_data=None,
    now=None, include_auction=False,
)
```

- `jingni_is_trading_day` 由 `jingni_get_trading_dates` 当日查询推导；平台日历不可用时按工作日降级。
- `jingni_is_trading_time` 默认仅连续竞价 `09:30—11:30`、`13:00—15:00`；`include_auction=True` 额外包含 `09:15—09:25`。
- 不把午休、收盘后集合竞价误判为可连续交易时段。

### 2.7 秒级定时器

```python
jingni_run_interval(func, seconds=3, trade_mode=None, context_data=None)
```

- 掘金：`timer(timer_func=func, period=seconds*1000, start_delay=0)`，平台单位是毫秒。
- QMT：`ContextInfo.run_time(func.__name__, "{seconds}nSecond", "1970-01-01 00:00:00")`；只接受函数名字符串，回测模式无效，本函数在回测直接返回 `None`。
- PTrade：`run_interval(context, func, seconds=max(3, seconds))`，平台最小 3 秒。
- 不使用本地线程，不绕过平台事件循环。

## 3. 同步修复的旧问题

### 3.1 QMT 交易日历 `count=-1`

Phase 1 的 `jingni_trading_dates` 与 `jingni_offset_trade_date` 在 QMT 分支调用：

```python
raw.get_trading_dates("", "", "", -1, "1d")
```

QMT 官方文档要求 `count` 必须大于 0。本轮改为正数请求：

- `jingni_trading_dates`：`abs(count) + 1`；
- `jingni_offset_trade_date`：`10000`（覆盖常用历史区间）。

这属于 Phase 1 遗留的实际 bug，已在本轮一并修正；QMT 相对未来交易日（正偏移）仍受平台历史日历接口限制，待 V-13 实机确认。

### 3.2 QMT 频率别名

QMT 适配器内部统一把：

- `60m -> 1h`
- `1M -> 1mon`

避免把统一频率直接传给 QMT 导致周期非法。

### 3.3 QMT 状态数值

`IsTrading` 可能是 `1/0` 而非 bool；本轮先用 `bool_or_none` 归一化，再推导 `suspend`，避免 `1 is True` 恒假。

## 4. 测试结果

执行命令：

```powershell
cd D:\codebuddy\jingni-flow
python -m pytest -q
python -m pyflakes jingniflow tools tests
python tools/build_single.py --root
```

结果：

- `python -m pytest`：**40 个测试通过**（Phase 2 新增 6 个 Mock 测试 + 1 个导出契约测试）。后续 QA 加固新增 27 个测试，当前总数 67，见 `docs/QA-加固记录.md`。
- `python -m pyflakes jingniflow tools tests`：无告警。
- 单文件构建成功：
  - `dist/jingniflow_single.py`（UTF-8）
  - `dist/jingniflow_single_gbk.py`（GBK）
  - 根 `jingniflow.py`（UTF-8）
- 单文件继续通过 Python 3.6 语法检查（`ast.parse(feature_version=(3, 6))`）和 GBK 解码检查。

Phase 2 Mock 覆盖：

| 测试 | 覆盖 |
|---|---|
| `test_goldminer_range_instrument_and_calendar` | GM 范围行情、标的、状态、日历、下载空操作 |
| `test_qmt_range_download_instrument_and_calendar` | QMT 范围行情、逐只下载、标的、日历 `count>0`、时段 |
| `test_ptrade_range_instrument_status_and_calendar` | PTrade `get_price`、`get_stock_info`、`get_stock_status`、`get_trade_days` |
| `test_run_interval_three_platforms` | GM 毫秒、QMT `nSecond`、PTrade 最小 3 秒 |
| `test_calendar_fallback_without_context` | 无平台上下文的工作日/时段降级 |
| `test_history_range_requires_start` | 范围行情缺 `start_time` 的校验 |

## 5. 未完成 / 待实测

本轮只做 Mock，不把以下项目当作已验证：

- **V-13 QMT 交易日历边界**：`get_trading_dates` 单次 `count=10000` 是否足够覆盖长区间；正偏移（未来交易日）是否可用其他接口。
- **V-14 QMT `run_time`**：回调函数必须是策略全局命名空间中的函数名；回测无效；首次触发时点是否符合预期。
- **V-15 QMT `download_history_data`**：`startTime/endTime` 空值、分钟周期与 `5m` 降级后的实际落盘范围。
- **V-16 GM `get_symbol_infos` 字段**：`lot_size`、`price_tick`、`listed_date`、`is_st` 在券商版是否齐全；`get_instruments` 下线后的实际可用性。
- **V-17 PTrade `get_price` 返回结构**：单股票/多股票、单字段/多字段是否返回 DataFrame/Panel；本实现只取单股票路径。
- **V-18 PTrade `get_stock_status` 返回形态**：dict 键是 `600000.SS` 还是 `600000`，值是 bool 还是状态码。
- **V-19 GM `history` 范围边界**：`start_time/end_time` 为日期或分钟字符串时的闭开区间、分钟线起点限制。
- **V-20 三平台 Python/pandas 版本**：QMT 内置 Python 3.6 + GBK 已做语法/编码检查，但仍需在真实 QMT 进程内导入验证。

## 6. 下一阶段建议

1. 按 `docs/smoke-checklist.md` 追加 Phase 2 冒烟项，优先 QMT（3.6 + GBK）和 PTrade。
2. 实机确认后再决定是否补充：`jingni_get_trading_session`、`jingni_get_stock_status` 的更细粒度状态、GM/PTrade 的交易日历缓存。
3. 不扩展期货、期权、两融、ETF、L2、财务/板块等非首批能力；这些仍按 D2 延后。
