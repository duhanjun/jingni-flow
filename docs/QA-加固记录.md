# QA 加固记录：能力矩阵、自检与异常契约

日期：2026-11-19

## 1. 本轮范围

不依赖掘金、QMT、PTrade 终端的 P0 加固：

1. 补全 `jingni_capabilities()` 的 Phase 2 能力矩阵。
2. 新增 `jingni_doctor()` 启动自检。
3. 补异常路径、空数据、平台 API 缺失、返回形态、日历缓存和核心契约测试。
4. 建立核心契约层覆盖率门禁。

不做三端实机冒烟，不扩展到期货、期权、两融、ETF、L2、财务/板块。

## 2. 能力矩阵

`jingniflow/api/diagnose.py` 现在维护 22 项能力：

- Phase 1：历史行情、tick、数量/金额/目标/市价下单、撤单、查询、账户、风控、打新、新债、逆回购、调度。
- Phase 2：范围行情、数据预热、标的元数据、股票状态、交易日历、交易日判断、交易时段、秒级定时器。

每个能力返回：

```python
{
    "phase": 1,
    "level": "full",          # full / degraded / unsupported
    "notes": "当前平台的说明",
    "platform_levels": {"goldminer": "...", "qmt": "...", "ptrade": "..."},
}
```

`jingni_capabilities("ptrade")` 会返回 PTrade 的平台级别，例如：

- `data.download` 为 `unsupported`（PTrade 无本地下载接口，函数是空操作）；
- `instrument.status` 为 `full`（原生 `get_stock_status`）；
- `calendar.trading_day` 为 `degraded`（平台日历不可用时按工作日降级）。

`jingni_doctor()` 只做静态/配置检查，不主动请求柜台：

- Python 版本、平台名、适配器能否加载；
- `dry_run`、`kill_switch`、单笔数量/金额、每日笔数、重复窗口；
- QMT 账号是否配置；
- Phase 2 能力是否齐全。

`ok=False` 表示存在必须处理的错误；`warnings` 包含实盘开启、kill switch 开启、QMT 账号缺失等提示。QMT 在非 Python 3.6 环境会给出警告，但不会阻断本地开发/回测。

## 3. 新增测试

新增 27 个测试，当时总数 67；后续追加 1 个三端冒烟脚本契约测试，当前总数 68：

| 文件 | 数量 | 覆盖内容 |
|---|---:|---|
| `tests/unit/test_diagnose.py` | 5 | 能力矩阵、未知平台、默认安全配置、危险配置、平台错误 |
| `tests/unit/test_errors_contract.py` | 14 | 空历史、MultiIndex、非法代码/频率、平台 API 缺失、GM 空 `trade_date`、QMT `count>0`、QMT 空标的详情、QMT 回测定时器、PTrade dict 返回、混合标的 payload、日历缓存、空代码列表 |
| `tests/unit/test_core_edges.py` | 8 | 订单状态/方向映射、OrderRef、订单数值容错、标的/日期工具、交易时段边界、配置、异常字符串、风控边界 |

已有测试同步增加了 `jingni_doctor` 导出契约。

## 4. 覆盖率

核心契约层 `jingniflow/core`：

```text
Stmts 666, Miss 90, Cover 86%
```

`pyproject.toml` 增加核心层门禁：

```toml
[tool.coverage.run]
source = ["jingniflow/core"]

[tool.coverage.report]
include = ["jingniflow/core/*"]
fail_under = 80
show_missing = true
```

验证命令：

```powershell
python -m coverage run -m pytest
python -m coverage report
```

当前核心层 86%，门禁 80% 通过。全包覆盖率单独测量约 69%，尚未作为本轮门禁；平台适配器和模板仍有大量未走分支，后续按模块补测。

## 5. 验证结果

```text
python -m pytest -q                        68 passed
python -m pyflakes jingniflow tools tests  无告警
python -m coverage report                  核心层 86%，门禁通过
```

单文件已重建：`dist/jingniflow_single.py`（UTF-8，`__all__` 55 项）、
`dist/jingniflow_single_gbk.py`（GBK）、根目录 `jingniflow.py`；均通过
`ast.parse(feature_version=(3, 6))`，GBK 版本可正常解码，且 `jingni_doctor`
已在单文件导出中。

## 6. 仍未处理

- 三端实机冒烟 V-01—V-20。
- 全包覆盖率 69%，模板和部分平台分支未覆盖；是否提升到全包 80% 需单独立项。
- 单文件构建的 `--check`、版本/构建时间/hash、CI 漂移检查尚未做。
- `docs/api/*.md`、`platform-notes.md`、`migration-v0.1-to-v0.2.md`、`CHANGELOG.md`、CI 配置尚未做。
- `jingni_get_stock_status(ALL)` 仍会调用三次适配器；本轮只补测试，未改批量缓存。
- 平台日历不可用时的工作日降级仍无法识别节假日，后续可增加 `source/degraded` 显式标记。
