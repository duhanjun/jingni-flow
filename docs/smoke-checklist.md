# 三平台冒烟清单（Phase 1）

可粘贴脚本与逐步说明见 `docs/smoke-copy-paste.md`；三份脚本位于 `examples/smoke/`。
回测阶段实际检查项以脚本 `[SMOKE][SUMMARY]` 为准（三端各 21–23 项）。真机
报单/撤单/成交/定时器验证见 `docs/live-validation-checklist.md`。

1. 启动：打印 `[JINGNI] version/python/platform/capabilities`，无异常退出。
2. `jingni_get_history(code, '1d', 5)`：返回 5 条，最后一条为当前/指定 bar。
3. `jingni_get_field(code, '1d', 'close', offset=0)` 与 `offset=1`：返回 float，且与历史最后两条一致。
4. `jingni_order_amount(..., dry_run=True)`：只打印 `[JINGNI_DRY_RUN]`，无委托；`dry_run=False` 返回 `OrderRef`，`jingni_get_orders` 可见。
5. `jingni_cancel_order(ref)`：返回 True，订单状态最终为 `CANCELED`。
6. `jingni_get_positions()`：`available` 与柜台“可用”一致；当日买入后卖出不被风控误拒。
7. `jingni_schedule(func, '09:31')`：次一交易日同一时点再次触发；QMT 使用 `repeat_times=-1`。
8. `jingni_subscribe_new_stock(dry_run=True)`：列出标的/额度，不报单；`jingni_participate_reverse_repo(dry_run=True)` 打印代码、张数、价格。

## 重点回归

- QMT：内置 Python 3.6 + GBK；`passorder` 的 `prType`、`cancel` 签名、订单状态码。
- PTrade：`order_market` 参数、`get_orders/get_trades` 返回结构、`get_snapshot` 字段。
- 掘金：`history_n` 分钟线边界、`volume_today` 可卖量口径、`order_volume` 返回对象。
- 风控：kill switch 撤单后仍禁止下单；重复窗口内同方向同数量同价格被拒。

# Phase 2 追加冒烟项

在 Phase 1 的 8 项之外，每个平台追加以下 7 项：

1. `jingni_get_history_range(code, '1d', '2024-01-01', '2024-01-31')`：返回 DataFrame，首尾日期在区间内，字段与 `jingni_history` 一致；PTrade 确认 `get_price` 单股票返回结构。
2. `jingni_download_history([code], '1d', '2024-01-01', '2024-12-31')`：QMT 逐只调用并落盘；GM/PTrade 返回 None 且不报错。
3. `jingni_get_instrument(code)`：返回 `name/board/lot_size/tick_size/limit_up/limit_down/listed_date/status`；缺失字段为 None 或默认 100 股，不出现伪造值。
4. `jingni_get_stock_status(code, 'ST')` / `'HALT'` / `'DELISTING'`：PTrade 返回 bool；GM/QMT 可判断时返回 bool，不可判断时返回 None。
5. `jingni_get_trading_dates('2024-01-01', '2024-01-31')`：返回 `YYYYMMDD` 升序列表；与终端交易日历对照；QMT 确认 `count>0` 不再报错。
6. `jingni_is_trading_day(date)` / `jingni_is_trading_time(now)`：节假日返回 False；`09:20` 默认 False、`include_auction=True` 为 True；`12:00` 为 False。
7. `jingni_run_interval(func, 3)`：GM 每 3 秒触发；PTrade 交易环境不小于 3 秒，回测为 `[SMOKE][SKIP]`；QMT 实盘触发，回测为 `[SMOKE][SKIP]`。

## 结果汇总

- 三项均为零失败时，日志出现 `[SMOKE][RESULT] ... ALL CHECKS PASSED; SMOKE VERIFICATION SUCCESS`。
- 回测结束：掘金、QMT 由 `on_backtest_finished` 打印 `stage=backtest_end`；
  PTrade 无整个回测结束回调，由每交易日 `after_trading_end` 打印 `stage=daily_end`，
  最后一天那一行才是最终汇总。
- `fail>0` 必须排查；`skip>0` 表示平台限制或开关未开，不等于通过。
- 回测只能完成“代码兼容 + 行情/日历 + dry-run”冒烟；真实报单、账户、柜台权限
  必须在模拟/实盘环境把 `SMOKE_REAL_ORDER = True` 再跑一次。

## Phase 2 重点回归

- QMT：`run_time` 回调函数必须位于策略全局命名空间；`download_history_data` 的起止时间空值与分钟周期降级。
- PTrade：`get_price` 多股票/多字段可能返回 Panel；`get_stock_status` 的 dict 键和值形态。
- 掘金：`get_trading_dates_by_year` 的 `trade_date` 空字符串过滤；`get_symbol_infos` 字段完整性。
- 日历：无平台上下文时仅按工作日降级，不能把“日历接口不可用”误报为“节假日”。

