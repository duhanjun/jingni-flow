# JingniFlow Phase 0 实施记录

日期：2026-11-19  
对应规划：`docs/JingniFlow-代码评估与功能扩展规划方案.md` v1.1（决策 D1—D7 全部 A）

## 1. 本次完成范围

Phase 0 的目标是“止血 + 建立可测试的包骨架”，不新增 50 个首批业务函数。已完成：

| 编号 | 内容 | 落点 |
|---|---|---|
| 0-1 | 包结构、版本号、运行上下文 | `jingniflow/__init__.py`、`core/runtime.py`、`version.py` |
| 0-2 | 空值/切片/字段偏移修复 | `api/market.py` |
| 0-3 | 三平台证券代码统一 | `core/contract.py` |
| 0-4 | QMT 取数与 `subscribe=False` | `adapters/qmt.py` |
| 0-5 | tick 统一结构 | `adapters/base.py`、`api/market.py` |
| 0-6 | 生命周期去循环化 + 三平台模板 | `api/lifecycle.py`、`templates/` |
| 0-7 | QMT 打新/新债 `context.raw` + `quickTrade=2` | `api/ipo.py` |
| 0-8 | 单文件构建（UTF-8/GBK） | `tools/build_single.py`、`dist/`、根 `jingniflow.py` |
| 0-9 | 单元/契约测试 | `tests/unit/`、`tests/contract/` |
| 0-10 | 旧接口兼容层 | `compat/legacy.py` |

## 2. P0 问题与修复对照

1. `jingni_main` 墙钟 `while True` → 只初始化并返回；`jingni_handle_data` 不再 `sleep/循环`。
2. `get_field` 的 `x is None and x.shape[0]==0` → 空值/空 DataFrame 分离处理。
3. `jingni_portfolio` 未知字段 `UnboundLocalError` → 显式校验，默认返回 `None`，`strict=True` 抛异常。
4. PTrade 代码转换变量未定义 → 统一 `normalize_code`。
5. QMT 打新/新债 `ContextInfo` 未定义 → `context.raw`，并统一 `quickTrade=2`。
6. QMT 负偏移 `[security_count-1]` 越界 → 条数取绝对值，正数 count。
7. 实时行情对 `list/float` 取 `.values` → 适配器先归一化为 `{code: {field: value}}`。
8. QMT `schedule_run(repeat_times=1)` 只触发一次 → 模板/示例改用持续规则并注明。
9. 掘金 `get_next_n_trading_dates(...)[0]` 恒为 T+1 → 正偏移取 `[-1]`。
10. `demo_qmt.py` 缺 `import datetime` → 补齐。
11. 根 `__init__.py` 指向不存在的 `JingniFlow`、`pyproject` `py-modules` 错误 → 根文件改为占位，`pyproject` 改为包发现。
12. `trade_mode` 全局/参数双轨 → `resolve_context` 统一解析，旧全局仍可读。
13. 旧单文件与包同名冲突 → 旧文件归档到 `legacy/jingniflow_v0.1.16.py`，根 `jingniflow.py` 由包构建生成。

## 3. 安全默认（D7）

- `RuntimeConfig.dry_run=True`。
- `jingni_order_amount` / `jingni_order_value` 默认只打印 `[JINGNI_DRY_RUN]`，不调用平台下单。
- `jingni_subscribe_new_stock` / `jingni_subscribe_new_bond` / `jingni_participate_reverse_repo` 同样默认 dry-run。
- 可传 `dry_run=False`，或在 `jingni_setup(..., RuntimeConfig(dry_run=False, max_order_amount=..., max_order_value=..., max_daily_orders=...))` 显式开启。
- 单笔数量、单笔金额、每日委托笔数限额已接入 `order_amount`。

## 4. 构建与测试

```powershell
python tools/build_single.py          # dist UTF-8 + GBK
python tools/build_single.py --root   # 同时刷新根 jingniflow.py
python -m pytest                      # 23 个测试
python -m py_compile dist/jingniflow_single.py dist/jingniflow_single_gbk.py
```

已验证：

- 包导入：`jingniflow.__version__ == 0.2.0.dev0`。
- 单文件导出全部存在（旧 18 个接口 + 新增诊断/账户/tick 接口）。
- UTF-8 与 GBK 产物均可编译。
- 单文件通过 Python 3.6 语法检查（`ast.parse(feature_version=(3,6))`）。
- QMT 模板/示例为 GBK。

## 5. 明确未完成 / 待实测

- QMT/PTrade/掘金终端未实机运行，柜台行为仍以规划文档 V-01—V-12 为准。
- Phase 1 的订单回执、撤单、查单、成交回报、统一持仓字段、风控去重/`kill_switch` 尚未实现。
- 50 个首批函数中的 `jingni_history`、`jingni_tick`、`jingni_buy/sell`、`jingni_cancel`、`jingni_orders` 等新名字尚未批量落地；当前只提供 Phase 0 的最小新接口（`jingni_get_tick`、`jingni_get_account`、`jingni_get_positions`、`jingni_setup`、`jingni_version`、`jingni_capabilities`）。
- `get_field` / `get_field_n` 的 `legacy` 语义已由测试覆盖“新默认”，但旧策略若依赖 `-1=当前` 需显式传 `legacy=True`。
- `pyproject` 已去掉 `pytest-cov` 强制参数；如需覆盖率需自行安装 `pytest-cov`。
