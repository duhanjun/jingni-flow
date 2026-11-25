# 文档导航

先看这里，再按路径往下读。JingniFlow 不是独立运行的量化平台，而是嵌在掘金 /
QMT / PTrade 策略环境里的统一适配层。

## 1. 新用户

| 顺序 | 文档 | 解决什么问题 |
|---|---|---|
| 1 | `getting-started.md` | 15 分钟跑通第一个回测：构建、粘贴、启动、看日志 |
| 2 | `usage-modes.md` | 单文件 / 包导入 / 模板三种方式怎么选 |
| 3 | `first-strategy.md` | 策略逻辑写在哪，`strategy=` 怎么绑定，dry-run 怎么看 |
| 4 | `config-and-risk.md` | dry-run、限额、kill switch、模拟到实盘的开关 |

## 2. 部署与验证

| 文档 | 用途 |
|---|---|
| `smoke-copy-paste.md` | 三端可粘贴冒烟脚本、逐平台步骤、常见失败 |
| `smoke-checklist.md` | 回测冒烟的检查项与 skip 解释 |
| `live-validation-checklist.md` | 模拟/实盘真机验证、100 股报单、GO/NO-GO |
| `../dist/validation/README.md` | 三端可直接粘贴的仿真验证策略与操作步骤 |
| `build-governance-ci.md` | 单文件构建、hash、CI、发布产物治理 |

## 3. 开发与设计

| 文档 | 用途 |
|---|---|
| `Phase0-实施记录.md` | 运行模型纠偏 |
| `Phase1-实施记录.md` | 订单/账户/风控闭环 |
| `Phase2-实施记录.md` | 行情范围、日历、标的、调度 |
| `QA-加固记录.md` | 异常、契约、覆盖率加固 |
| `JingniFlow-代码评估与功能扩展规划方案.md` | 早期评估与 D1–D7 决策、扩展路线 |

## 4. 最短路径

### 只想在券商终端跑

```text
getting-started.md
  → 选择平台模板
  → 追加对应单文件
  → 回测看到 SMOKE VERIFICATION SUCCESS
  → config-and-risk.md
```

### 想写自己的策略

```text
getting-started.md
  → usage-modes.md
  → first-strategy.md
  → config-and-risk.md
  → live-validation-checklist.md
```

### 想改源码/贡献代码

```text
README.md
  → docs/build-governance-ci.md
  → tests/
  → tools/build_single.py / tools/build_smoke.py / tools/verify_release.py
```

## 5. 约定

- 规范代码统一用 `600000.SH`；平台订阅格式由模板/适配器转换。
- 默认 `dry_run=True`；真实报单必须显式 `dry_run=False` 并压小限额。
- QMT 单文件必须是 GBK、Python 3.6；PTrade 单文件必须是 UTF-8、Python 3.5、
  不得出现 `sys`。
- 源码改动后必须重新构建；`build_single --check` / `build_smoke --check` /
  `verify_release.py` 是三道门禁。
