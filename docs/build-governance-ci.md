# 构建治理与 CI

本轮把单文件构建从“手工执行脚本”提升为可校验、可追溯、可被 CI 拦截的发布流程。

## 1. 产物与元数据

`python tools/build_single.py --root` 会生成：

| 文件 | 编码 | 用途 |
|---|---|---|
| `dist/jingniflow_single.py` | UTF-8 | 掘金 / PTrade 单文件 |
| `dist/jingniflow_single_gbk.py` | GBK | QMT（Python 3.6）单文件 |
| `dist/build-manifest.json` | UTF-8 | 版本、源码 hash、构建时间、产物 hash |
| `jingniflow.py` | UTF-8 | 仓库根目录兼容单文件 |

`python tools/build_smoke.py` 再生成三份“冒烟脚本 + 单文件尾部”的完整粘贴版：

| 文件 | 用途 |
|---|---|
| `dist/smoke/goldminer_smoke_full.py` | 掘金一次粘贴完整版 |
| `dist/smoke/qmt_smoke_full.py` | QMT 一次粘贴完整版（GBK） |
| `dist/smoke/ptrade_smoke_full.py` | PTrade 一次粘贴完整版 |

`python tools/build_smoke.py --check` 逐字节校验这三份 full 文件；CI 会在单文件
构建后执行生成与校验，避免 `examples/smoke/*.py` 和 `dist/smoke/*_full.py` 脱节。

`python tools/verify_release.py` 是构建之后的发布契约校验：它不写文件，检查
QMT full 的 GBK 解码与 Python 3.6 语法、PTrade full 的 Python 3.5 语法和
`sys` 禁用约束、三份 full 的 `trade_mode`，以及根 `jingniflow.py` 与 dist
UTF-8 单文件的字节一致性。`--check` 管“产物是否由当前源码生成”，verifier
管“产物是否符合平台硬约束”，两者互补。

单文件头部现在包含：

```text
# JingniFlow single-file distribution, version: 0.2.0.dev0
# Source-SHA256: <所有打包模块的源码摘要>
# Build-UTC: 2026-11-19T06:45:34Z
```

`Source-SHA256` 覆盖 `MODULES` 中列出的全部源文件内容，不是只对
`version.py` 做 hash。`build-manifest.json` 再记录每个产物的文件大小与
SHA256，因此可以区分“源码没变但产物被手改”和“源码变了但产物没重建”。

## 2. `--check` 的语义

```powershell
python tools/build_single.py --check --root
```

- 不写任何文件。
- 检查 UTF-8 单文件、GBK 单文件和根目录单文件是否存在。
- 读取每个文件已有的 `Build-UTC`，用它重建期望内容；因此不会因为每次
  校验都生成新时间而误报。
- 逐字节比较产物；再校验 manifest 的版本、源码 hash、产物 hash 和大小。
- 任一项不一致打印 `[STALE]` 并返回 1；全部通过返回 0。

用于“源码改了但忘记重建”的本地门禁：

```powershell
python tools/build_single.py --root
python tools/build_single.py --check --root
python tools/build_smoke.py
python tools/build_smoke.py --check
python tools/build_validation.py
python tools/build_validation.py --check
python tools/verify_release.py
```

如果只想在干净检出（`dist/` 不存在）时检查已提交的根单文件：

```powershell
python tools/build_single.py --check --root --allow-missing
```

`--allow-missing` 会跳过缺失的 dist 文件和 manifest，但仍会逐字节校验存在的
根 `jingniflow.py`；如果源码已经改了而根文件没重建，会报 `[STALE]`。

### 可复现构建

构建时间默认取当前 UTC。需要可复现构建时设置 `SOURCE_DATE_EPOCH`：

```powershell
$env:SOURCE_DATE_EPOCH = "1760000000"
python tools/build_single.py --root
```

相同源码、相同 `SOURCE_DATE_EPOCH` 会得到相同的头部和产物 hash。

## 3. 为什么 `dist/` 不入库

`.gitignore` 仍忽略 `dist/`。这是有意的：

- `dist/` 是构建产物，体积较大，且每次构建时间变化都会产生无意义 diff；
- 仓库跟踪根 `jingniflow.py`，CI 用它做“源码-根单文件”漂移门禁；
- 发布时由 CI 重新构建 `dist/`，把两个单文件、manifest、三份 full 和根
  `jingniflow.py` 作为 workflow artifact 上传，而不是把二进制产物提交进源码历史。

如果团队后续决定把发布单文件直接跟踪进仓库，需要同时把
`.gitignore` 中的 `dist/` 改为只忽略临时文件，并让 CI 的 `--check` 在构建前
执行；否则 CI 的“先构建再校验”只能证明构建可重复，不能证明仓库里的产物
没有过期。

## 4. CI 工作流

`.github/workflows/ci.yml` 包含三个 job：

### `quality`（Python 3.13）

1. `python -m pytest -q`：78 个单元/契约测试。
2. `python -m pyflakes jingniflow tools tests`：静态检查。
3. `python -m coverage run -m pytest -q` + `python -m coverage report`：
   `jingniflow/core` 覆盖率门禁 80%。
4. `python tools/build_single.py --check --root --allow-missing`：在干净检出
   上检查已提交的根单文件是否与源码一致。
5. `python tools/build_single.py --root`：生成 dist 和根文件。
6. `python tools/build_single.py --check --root`：校验构建结果、hash 和 manifest。
7. `python tools/build_smoke.py` + `--check`：生成并逐字节校验三份 full 冒烟文件。
8. `python tools/build_validation.py` + `--check`：生成并校验三端仿真验证 full 文件。
9. `python tools/verify_release.py`：校验三端编码/语法/`trade_mode`、PTrade
   禁 `sys` 约束，以及验证文件的默认 `dry_run`。

### `legacy-py36-static`（Python 3.6 容器）

1. 在宿主机构建单文件和三份 full。
2. 用 `python:3.6.15-slim` 容器执行：
   - UTF-8 单文件 `compile` + `ast.parse`；
   - GBK 单文件按 GBK 解码，确认 `# coding: gbk`，再 `compile` + `ast.parse`；
   - QMT full 按 GBK 解码后 `compile` + `ast.parse`；
   - PTrade full `compile`，并断言无 `import sys` / `sys.` 引用。

PTrade 真实运行环境是 Python 3.5.1，Python 3.6 容器只能兜住 3.7+ 语法；
Python 3.5 特有的限制由 `tools/verify_release.py` 的
`ast.parse(feature_version=(3, 5))`、`ast.JoinedStr` / `ast.AnnAssign` /
async comprehension 扫描补足。当前 `ptrade_smoke_full.py` 已在真实 PTrade
3.5.1 回测中运行通过，CI 做的是回归门禁，不替代真机验证。

### `release-artifacts`（`v*` tag）

只有打 `v*` tag 时触发，依赖前两个 job 通过。重新构建并校验后，把两个单文件、
manifest、三份 full 和根 `jingniflow.py` 作为 workflow artifact 上传，供发布
时下载；不把 `dist/` 提交进源码历史。

## 5. 提交前检查清单

```powershell
python -m pytest -q
python -m pyflakes jingniflow tools tests
python -m coverage run -m pytest -q
python -m coverage report
python tools/build_single.py --root
python tools/build_single.py --check --root
python tools/build_smoke.py
python tools/build_smoke.py --check
python tools/build_validation.py
python tools/build_validation.py --check
python tools/verify_release.py
```

若修改了 `jingniflow/` 下任一被打包模块，必须重新执行
`python tools/build_single.py --root`，否则根单文件和 dist 会保留旧
`Source-SHA256`，`--check` 会失败。

## 6. 已知边界

- `--check` 只验证“当前文件是否与当前源码一致”，不验证平台 API 行为；
  平台差异仍按 `docs/smoke-checklist.md` 和 `docs/smoke-copy-paste.md` 实机核对。
- `verify_release.py` 会执行三份 full 以读取尾部 `trade_mode`，因此需要 pandas；
  纯语法/编码检查的 3.6 容器 job 不安装 pandas，也不执行策略。
- Python 3.5 没有 f-string；`ast.parse(feature_version=(3,5))` 在当前 CPython
  上不会拒绝 f-string，所以 verifier 额外扫描 `ast.JoinedStr`、`ast.AnnAssign`
  和 async comprehension。真正的 3.5 运行仍以 PTrade 3.5.1 真机回测为准。
- `pyflakes` 不检查 `examples/smoke/` 中的通配符导入；那三份脚本依赖
  `from jingniflow import *` 或单文件尾部定义，属于运行期契约，不纳入静态
  检查，避免把平台全局函数误报为未定义。
- CI 的 Python 3.6 job 不执行 `import pandas`；QMT 终端自带的 pandas/numpy
  版本仍属于实机待核对项。
