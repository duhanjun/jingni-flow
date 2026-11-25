# 三平台模板说明

| 文件 | 平台 | 入口 | 编码 |
|---|---|---|---|
| `goldminer_strategy.py` | 掘金 | `init` / `on_bar` | UTF-8 |
| `qmt_strategy.py` | QMT | `init(C)` / `handlebar(C)` | GBK（必须另存） |
| `ptrade_strategy.py` | PTrade | `initialize` / `handle_data` | UTF-8 |

## 两种接入方式

1. **单文件**：把 `dist/jingniflow_single.py`（QMT 用 `_gbk` 版）全文粘贴到模板末尾。
2. **包**：将仓库根目录加入 `PYTHONPATH`，或 `pip install -e .`，模板直接用 `from jingniflow import ...`。

## 注意

- 单文件生成命令：`python tools/build_single.py`
- QMT 的 `get_market_data_ex` 已显式传 `subscribe=False`，避免订阅泄漏。
- 打新/新债在 QMT 使用 `quickTrade=2`，委托后立即撮合。
- 旧的 `jingni_main` 不再阻塞；平台事件负责调用 `jingni_handle_data`。
