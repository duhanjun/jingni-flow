# 三种使用方式

JingniFlow 有三种实际用法，不是三套代码，而是同一套源码的三种交付/运行方式。
先按你的环境选，不要同时用。

## 0. 一张表选路径

| 场景 | 单文件粘贴 | 包导入 | 模板 + strategy |
|---|---|---|---|
| 只有券商终端账号 | **首选** | 不适合 | 配合单文件使用 |
| 会 Python，要改源码/跑测试 | 可用 | **首选** | 可用 |
| QMT 内置 Python 3.6 | **必须** GBK 单文件 | 需要手动加包路径，风险高 | 配合 GBK 单文件 |
| PTrade Python 3.5 | **必须** UTF-8 单文件 | 终端通常不能装包 | 配合单文件 |
| 掘金量化 | 可用 | **首选** | 可用 |
| 想把同一策略迁到三端 | 分别构建三份 | 开发期用包，交付期用单文件 | 推荐 |

一句话：**开发/研究用包导入，交付/实盘用单文件，策略入口用 `strategy=`。**

## 1. 单文件粘贴模式

### 适合谁

- 不想在终端里配 `pip install` 的投资者；
- QMT / PTrade 这类只能把代码粘进策略编辑器的环境；
- 需要把策略发给别人、让对方一次粘贴就能跑的场景。

### 怎么做

```powershell
python tools/build_single.py --root
python tools/build_smoke.py
python tools/verify_release.py
```

然后按平台选文件：

| 平台 | 单文件 | 策略模板 |
|---|---|---|
| 掘金 | `dist/jingniflow_single.py` | `jingniflow/templates/goldminer_strategy.py` |
| QMT | `dist/jingniflow_single_gbk.py` | `jingniflow/templates/qmt_strategy.py` |
| PTrade | `dist/jingniflow_single.py` | `jingniflow/templates/ptrade_strategy.py` |

复制顺序：

1. 先复制模板到策略编辑器；
2. 在模板的 `init/initialize` 里绑定 `strategy=my_strategy`；
3. 在文件**最末尾**追加单文件全文；
4. 平台回调里调用 `jingni_handle_data`；
5. 运行回测。

注意：追加单文件的位置是策略文件的**最末尾**，不是 `init` 函数内部。单文件
尾部会定义 `jingni_*` 函数和 `trade_mode` 兼容变量，必须让整个文件先执行完，
平台才会调用生命周期函数。

### 优点 / 代价

- 优点：不需要包管理，终端直接运行；QMT/PTrade 的唯一稳定交付方式。
- 代价：源码改了必须重新构建；单文件很大；QMT 必须 GBK；PTrade 不能有 `sys`。

## 2. 包导入模式

### 适合谁

- 在本地研究环境写策略、跑 pytest、做参数实验；
- 使用掘金这类允许外部 Python 解释器的终端；
- 需要 IDE 调试、类型检查、单元测试的开发者。

### 怎么做

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

`.[dev]` 里的 pytest/coverage 需要 Python 3.8+；QMT 的 3.6、PTrade 的 3.5
环境不要装开发依赖，直接使用单文件。

```python
from jingniflow import (
    RuntimeConfig,
    jingni_handle_data,
    jingni_history,
    jingni_main,
    jingni_order_amount,
    jingni_set_strategy,
)


def my_strategy(trade_mode, context_data):
    history = jingni_history(trade_mode, context_data, "600000.SH", "1d", 5)
    if history is None or len(history) < 2:
        return
    last = float(history["close"].iloc[-1])
    jingni_order_amount(
        trade_mode,
        context_data,
        "600000.SH",
        100,
        last,
        dry_run=True,
        remark="package-mode",
    )


def init(context):
    jingni_main("goldminer", context, strategy=my_strategy)


def on_bar(context, bars):
    jingni_handle_data("goldminer", context)
```

### 平台限制

- **掘金**：终端可以指定已安装 `gm` 的 Python 解释器，包模式最顺。
- **QMT**：内置 Python 3.6，需要把仓库根目录加入 QMT 可访问的 Python 路径；
  交付仍建议用 GBK 单文件。
- **PTrade**：终端通常不能 `pip install`，包模式不作为交付路径；用单文件。

### 优点 / 代价

- 优点：可调试、可测试、可复用；`pytest` 和 CI 都在这个模式上跑。
- 代价：终端环境不一定能装包；三端仍要分别做真机验证。

## 3. 模板 + `strategy` 模式

这不是第三种运行方式，而是单文件和包导入共用的**策略接入方式**。

### 推荐写法

```python
def my_strategy(trade_mode, context_data):
    """每次平台事件触发时执行。"""
    # 1. 读行情
    # 2. 算信号
    # 3. 调 jingni_order_amount / jingni_cancel_order / ...
    pass


def init(context):
    jingni_main("qmt", context, strategy=my_strategy)
```

QMT 里这个上下文参数通常命名为 `C`，写成 `def init(C): jingni_main("qmt", C, ...)` 与
平台代码风格一致；本文示例统一用 `context`，实际以模板为准。

三种绑定方式，优先级从高到低：

```python
# 1. 每次调用显式传，优先级最高
jingni_handle_data("qmt", C, strategy=my_strategy)

# 2. 初始化时绑定，后续 handle_data 自动使用
jingni_main("qmt", C, strategy=my_strategy)

# 3. 全局注册
jingni_set_strategy(my_strategy)
jingni_main("qmt", C)
```

### 旧写法还兼容吗

兼容。未注册时仍然调用 `jingni_trade_strategy` 占位函数；老的单文件策略在
尾部之后覆盖 `jingni_trade_strategy` 也仍然可用。但新代码不建议依赖覆盖位置：

- 单文件模式：覆盖必须发生在单文件尾部之后；
- 包模式：在业务模块里定义同名函数不会替换 `jingniflow.api.lifecycle` 内部
  的全局引用，需要 monkey-patch 或改用 `strategy=`。

## 4. 运行阶段不是使用方式

无论选哪种方式，运行阶段都按同一顺序：

| 阶段 | 目的 | 关键开关 |
|---|---|---|
| 平台回测 | 验证代码能启动、行情/日历/dry-run 可用 | 默认 `dry_run=True` |
| 模拟 dry-run | 验证策略逻辑只打印、不报单 | `dry_run=True` |
| 模拟真实报单 | 验证柜台报单/撤单/成交/持仓 | `dry_run=False`，100 股，模拟账户 |
| 实盘只读 | 验证实盘账户/行情/权限 | 不下单 |
| 实盘 100 股 | 验证真实链路 | 人工旁站，限价单 |

具体步骤见 `docs/config-and-risk.md` 和 `docs/live-validation-checklist.md`。

## 5. 常见选型错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 把 UTF-8 单文件粘进 QMT | GBK 解码错误/乱码 | 用 `dist/jingniflow_single_gbk.py` |
| 把带 `sys` 的旧单文件粘进 PTrade | 错误码 3“sys被禁止使用” | 重新构建并运行 `verify_release.py` |
| 在 `init` 里写 `while True` / `sleep` | 阻塞平台线程 | 由平台事件驱动，逻辑放 `my_strategy` |
| 包模式直接 `from jingniflow import jingni_trade_strategy` 后重定义 | lifecycle 内部仍调旧占位 | 用 `strategy=` 或 `jingni_set_strategy` |
| 回测里打开 `SMOKE_REAL_ORDER=True` | 仍然 skip，误以为验证过 | 到模拟/交易环境再打开 |
| 源码改了不重建单文件 | 根文件/`dist` 与源码不一致 | `build_single --check` 会报 `[STALE]` |
