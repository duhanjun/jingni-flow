# 三端实机冒烟：可粘贴代码与执行说明

本目录提供三份可直接粘贴到策略软件冒烟脚本，覆盖 `docs/smoke-checklist.md`
中 Phase 1 的 8 项、Phase 2 的 7 项基线，并追加账户/订单/成交、逆回购、
定时器实际触发等检查；三端实际项数以 `[SMOKE][SUMMARY]` 为准（21–23 项）。

- `examples/smoke/goldminer_smoke.py`：掘金量化（UTF-8）
- `examples/smoke/qmt_smoke.py`：QMT（文件本身为纯 ASCII，可被 GBK 读取）
- `examples/smoke/ptrade_smoke.py`：PTrade（UTF-8）

三份脚本默认 `SMOKE_REAL_ORDER = False`，只执行 dry-run，不会向柜台报单。
只有显式改为 `True` 才会用 100 股做一次真实报单并立即撤单；请只在模拟账户
或确认过风险的小额账户上打开。

统一函数内部使用规范代码 `600000.SH`；平台订阅/股票池使用各自格式：
掘金 `SHSE.600000`、PTrade `600000.SS`、QMT `600000.SH`。脚本已分别定义
`SMOKE_CODE` 与 `SMOKE_SYMBOL`，不要只改其中一个。

## 0. 共同前置

在项目根目录重新生成单文件，确保冒烟代码使用的是最新源码：

```powershell
python tools/build_single.py --root
python tools/build_single.py --check --root
python tools/build_smoke.py
python tools/build_smoke.py --check
python tools/verify_release.py
```

回测冒烟只验证代码兼容、行情/日历和 dry-run；真实报单、撤单、成交和实盘
定时器按 `docs/live-validation-checklist.md` 分阶段执行。

然后按平台复制：

| 平台 | 最快方式（已含单文件尾部） | 分开维护时 |
|---|---|---|
| 掘金 | `dist/smoke/goldminer_smoke_full.py` | `examples/smoke/goldminer_smoke.py` + `dist/jingniflow_single.py` |
| QMT | `dist/smoke/qmt_smoke_full.py`（GBK） | `examples/smoke/qmt_smoke.py` + `dist/jingniflow_single_gbk.py` |
| PTrade | `dist/smoke/ptrade_smoke_full.py` | `examples/smoke/ptrade_smoke.py` + `dist/jingniflow_single.py` |

`*_full.py` 已经把对应的单文件尾部拼好，直接把整个文件粘贴到策略软件即可。
如果只想粘贴一次，用 full 版；如果要调整冒烟逻辑，用“分开维护”版，改完
`examples/smoke/*.py` 后重新追加单文件。

追加位置是策略文件的**最末尾**，不要放在 `init/initialize` 函数内部，也
不要只粘贴其中一部分。单文件尾部自带 `__all__` 和全部函数定义，平台在
执行完整个策略文件后才会调用生命周期函数。

## 1. 掘金量化

1. 在掘金终端新建策略，把 `goldminer_smoke.py` 全文粘贴进去。
2. 把 `dist/jingniflow_single.py` 全文粘贴到该策略文件末尾。
3. 确认策略使用模拟账户或仿真环境，运行策略。
4. 脚本会自动 `subscribe("600000.SH", "1d")`，并在第一根 bar 触发一次冒烟。

预期开头：

```text
[JINGNI] ready; platform events drive the strategy
[SMOKE] start platform=goldminer code=600000.SH
[SMOKE][OK] doctor: ...
[SMOKE][OK] history 5 bars: shape=(5, ...)
```

说明：`goldminer_smoke.py` 顶部保留了 `from jingniflow import *` 的
`try/except`。单文件模式下 import 会失败，这是正常的；只要尾部追加了
`dist/jingniflow_single.py`，事件回调执行时函数已经存在。若日志出现
`name 'jingni_main' is not defined`，说明尾部没有粘贴或粘贴不完整。

### 1.1 必须有 `run(...)` 启动块

掘金策略不是“文件里有 `init/on_bar` 就会自动跑”，必须调用 `run(...)` 才会
进入事件循环。`goldminer_smoke_full.py` 为了不暴露策略 ID/token，**故意没有**
内置启动块；粘贴到终端后，请在文件**最末尾**（所有函数和单文件尾部之后）
追加下面这段，并把 `strategy_id`、`token` 换成终端里的值：

```python
if __name__ == '__main__':
    run(strategy_id='你的策略ID',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='你的token',
        backtest_start_time='2024-01-01 09:00:00',
        backtest_end_time='2024-12-31 15:00:00',
        backtest_adjust=ADJUST_NONE,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
```

注意：

- `filename` 必须和实际文件名一致，通常是 `main.py`。
- 这段必须在**最后**；如果放在 `init` 前面，`run()` 会先阻塞，后面的
  `init/on_bar` 还没定义，日志也不会有任何输出。
- 终端右上角的回测参数优先于 `run(...)` 里的回测参数。
- 如果仍然“点击运行回测没反应”，按掘金 FAQ 检查系统 `PATH` 是否包含
  `%SystemRoot%\system32` 和 `%SystemRoot%\system32\cmd.exe`，并确认
  “设置/齿轮 → 解释器路径”指向已安装 `gm` 的 Python。


## 2. QMT

1. 在 QMT 新建策略，把 `qmt_smoke.py` 全文粘贴进去。
2. 把 `dist/jingniflow_single_gbk.py` 全文粘贴到策略文件末尾。
3. 整个策略文件必须以 **GBK** 保存；文件头保留 `# encoding: gbk`。
4. 确认 QMT 使用模拟账户，运行策略。

如果使用 `dist/smoke/qmt_smoke_full.py`，它已经是拼接好的 GBK 文件，直接
整个粘贴即可，不再需要手动追加。

`qmt_smoke.py` 的注释全部是 ASCII，因此即使编辑器先把脚本存成 UTF-8，
GBK 解码也不会坏；但追加的 `jingniflow_single_gbk.py` 必须是 GBK 版本，
不能把 UTF-8 版本粘进 QMT。

预期开头：

```text
[JINGNI] platform=qmt mode=backtest python=3.6...
[SMOKE] start platform=qmt code=600000.SH
[SMOKE][OK] doctor: ...
```

QMT 注意：

- 内置 Python 3.6，不能出现 f-string、`dataclasses`、`pathlib` 等 3.7+ 语法。
- QMT 回测没有资金账号是正常的：`orders` / `trades` / `positions` 会降级为空列表，
  doctor 只给出 `account` 警告，不再记为失败；实盘缺少账号仍会严格报错。
- `run_interval` 和 `schedule` 在回测中不会被脚本执行，而是记为 `[SMOKE][SKIP]`；
  这是平台限制，不是 JingniFlow 失败。请在模拟/实盘环境观察是否触发。
- `ContextInfo.set_universe([...])` 已放在 `init` 中；若券商客户端要求先下载
  历史数据，请先补跑 `jingni_download_history`。
- 若日志出现 `platform=????????` 或 `unsupported platform: ????????`，说明单文件尾部的
  legacy `trade_mode` 覆盖了冒烟脚本的 `trade_mode`。请使用本次重新构建的
  `qmt_smoke_full.py`；其尾部已改为只在该变量未定义时才写入默认值。
- 若日志出现 GBK 解码错误，检查是否误把 UTF-8 单文件粘进了 QMT。

## 3. PTrade

1. 在 PTrade 新建策略，直接粘贴 `dist/smoke/ptrade_smoke_full.py` 全文（已包含
   smoke 脚本 + 单文件，不要再重复粘贴单文件）。
2. 确认股票池包含 `600000.SS`，使用模拟账户运行。
3. `initialize` 中会尝试 `set_universe([...])`；若当前券商版本不支持，异常已被
   捕获，不影响后续冒烟。
4. PTrade 没有“整个回测结束”回调；`after_trading_end` 每个交易日盘后调用一次，
   脚本会在该回调打印 `stage=daily_end` 汇总。回测日志的最后一条 `daily_end`
   才是最终汇总。
5. PTrade 回测环境不支持 `run_interval`，脚本会记为 `[SMOKE][SKIP]`；真实定时器
   请在交易环境验证。`schedule 09:31` 已在 `initialize` 中注册 `run_daily`，
   不会在 `handle_data` 阶段重复调用。
6. 若报 `回测运行失败, 错误码:3 错误信息: sys被禁止使用`，说明用的是旧版单文件；
   旧版顶层有 `import sys`。本次 `ptrade_smoke_full.py` 已移除全部 `sys` 引用，
   重新粘贴即可。可在文件中搜索确认不存在 `import sys` 或 `sys.`。
7. PTrade 实测 Python 为 3.5.1；脚本使用 `.format` 而非 f-string，可直接运行。
   PTrade 的成交额字段是 `money`，JingniFlow 内部仍统一为 `amount`，适配器会自动
   转换并改回列名；`get_trade_days` 返回 numpy 数组时也已兼容。
8. PTrade 的 `get_price` 的 `fields` 必须传 list（不是逗号字符串）；`run_daily`
   回调会带 `context` 参数，冒烟回调已改为 `*args, **kwargs` 兼容。

预期开头：

```text
[JINGNI] platform=ptrade mode=backtest python=...
[SMOKE] start platform=ptrade code=600000.SH
[SMOKE][OK] doctor: ...
```

## 4. 冒烟检查对照（15 项基线 + 本轮新增）

| # | 检查项 | 日志关键字 | 判定 |
|---|---|---|---|
| 1 | 启动、版本、平台、能力矩阵 | `[SMOKE][OK] doctor/version/capabilities` | 有输出且无异常 |
| 2 | `jingni_history` 取 5 条 | `[SMOKE][OK] history 5 bars` | shape 首维为 5 |
| 3 | `jingni_get_field` offset 0/1 | `field close offset=0/1` | 两个 float 与历史最后两根一致 |
| 4 | 下单 dry-run | `[JINGNI_DRY_RUN]`、`order dry-run` | 只打印，不产生委托 |
| 5 | 真实报单 + 撤单 | `real order`、`cancel order` | 仅 `SMOKE_REAL_ORDER=True` 时执行；订单最终 `CANCELED` |
| 6 | 持仓/账户 | `positions`、`account` | 可用数量与柜台一致 |
| 7 | `jingni_schedule("09:31")` | `schedule 09:31` | 注册成功；次日同一时点触发（QMT `repeat_times=-1`） |
| 8 | 打新/新债/逆回购 dry-run | `new stock/new bond/reverse repo dry-run` | 打印标的/额度，不报单 |
| 9 | 区间历史 | `history range 2024` | 返回 DataFrame，首尾在区间内 |
| 10 | 历史下载 | `download history` | QMT 逐只落盘；GM/PTrade 返回 `None` 不报错 |
| 11 | 标的信息 | `instrument` | 含 name/board/lot_size/tick_size 等，不伪造缺失值 |
| 12 | ST/停牌/退市状态 | `stock status ST` | bool 或 `None`，不得把未知当 False |
| 13 | 交易日列表 | `trading dates 2024-01` | `YYYYMMDD` 升序 |
| 14 | 交易日/交易时段 | `is trading day`、`is trading time` | 节假日 False；09:20 默认 False；12:00 False |
| 15 | 秒级定时器 | `run interval 3s`、`interval fired` | GM 3 秒触发；PTrade ≥3 秒；QMT 实盘触发、回测提示不生效 |
| 16 | 账户字段 | `[SMOKE][OK] account` | 7 个统一字段齐全；回测无账号时 QMT 允许空值 |
| 17 | 订单/成交查询 | `[SMOKE][OK] orders`、`trades` | 回测/空账户为 0 条；实盘按柜台返回 |
| 18 | 逆回购 dry-run | `[JINGNI_REPO]`、`reverse repo dry-run` | 打印代码/张数/价格；无现金时 SKIP 不报错 |
| 19 | 定时任务实际触发 | `scheduled task fired` | 模拟/交易环境次一交易日 09:31 触发 |
| 20 | 秒级定时器实际触发 | `interval fired` | 交易环境按配置间隔触发；回测允许 SKIP |
| 21 | QMT 回测无账号降级 | `QMT backtest account unavailable` | positions/account/orders/trades 返回空，不记 FAIL |
| 22 | PTrade 禁 sys | `sys被禁止使用` | 不出现该错误码；full 中无 `import sys` / `sys.` |
| 23 | 历史结果形态 | `history result` | shape 首维为 5，字段为统一列 |

`[SMOKE][FAIL]` 是单项失败，不会中断后续检查。请把完整日志和平台/Python 版本
贴回，便于判断是适配器问题还是终端权限/行情未订阅问题。

## 5. 回测与“真机验证”的边界

先给结论：**直接跑回测不能完成完整的真机验证**，但可以完成“回测冒烟”。
两者要分开看：

| 验证层级 | 能覆盖 | 不能覆盖 | 怎么跑 |
|---|---|---|---|
| 回测冒烟 | 平台 Python 导入/语法、历史行情、字段 offset、交易日历、标的信息、dry-run 下单、部分策略生命周期 | 真实柜台连接、真实资金/持仓、真实报单/撤单、券商权限、实时 tick、柜台回调 | 直接运行本文脚本的回测 |
| 模拟/实盘冒烟 | 账户、持仓、委托、成交、真实报单/撤单、定时器、柜台权限 | 全市场极端行情、长时间稳定性 | 模拟账户运行，并把 `SMOKE_REAL_ORDER = True` |

脚本现在会在检查结束时打印：

```text
[SMOKE][SUMMARY] stage=checks platform=... mode=backtest pass=... fail=... skip=...
[SMOKE][RESULT] checks: ALL CHECKS PASSED; SMOKE VERIFICATION SUCCESS / 验证成功
```

回测结束后还会再打印一次 `stage=backtest_end`（掘金、QMT）；PTrade 没有
“整个回测结束”回调，只在每个交易日 `after_trading_end` 打印 `stage=daily_end`，
**最后一天的这一行才是回测最终汇总**。

判定规则：

- `fail=0`：回测冒烟通过。日志最后出现 `SMOKE VERIFICATION SUCCESS / 验证成功`。
- `fail>0`：至少一项真实失败，按上面的 `[SMOKE][FAIL]` 逐项排查。
- `skip>0`：因平台限制或开关关闭未执行，例如真实报单、QMT 回测定时器、
  PTrade 回测 `run_interval`。`skip` 不等于失败，但也不等于已经验证。
- 只有把 `SMOKE_REAL_ORDER = True` 并在**模拟账户**跑过真实报单/撤单，才建议
  对外称“完成柜台级真机验证”。

## 6. 三端回测结束提示

| 平台 | 回测结束回调 | 最终日志 |
|---|---|---|
| 掘金 | `on_backtest_finished(context, indicator)` | `[SMOKE][RESULT] backtest_end: ... SUCCESS` |
| QMT | `on_backtest_finished(ContextInfo)` | `[SMOKE][RESULT] backtest_end: ... SUCCESS` |
| PTrade | 无整个回测结束回调；`after_trading_end(context, data)` 每交易日盘后调用 | 最后一天的 `[SMOKE][RESULT] daily_end: ... SUCCESS` |

QMT 的 `stop(ContextInfo)` 是实盘停止前回调，且交易连接已断开，不能用于
报单/撤单，也不适合作为回测汇总点；本脚本使用 `on_backtest_finished`。
掘金 `on_backtest_finished` 的参数名按平台常见签名写为
`(context, indicator)`，若终端提示签名不符，只保留 `context` 参数即可。

## 7. 常见失败

- `name 'jingni_main' is not defined`：单文件尾部没粘贴，或粘贴到了函数内部。
- QMT 中文乱码/GBK 报错：把 UTF-8 单文件粘进了 QMT，或策略文件不是 GBK。
- `positions/account` 在回测中失败：部分终端回测不提供账户接口，改用模拟环境。
- `schedule/run_interval` 返回 `None`：QMT 回测限制；GM/PTrade 检查是否在交易
  时段外运行。
- `history` 返回空：先确认代码已加入股票池、行情权限已开通，并调用一次
  `jingni_download_history`（QMT 尤其需要）。
