# Handoff Notes

这份文件给后续接手项目的人快速定位入口。

## 环境

推荐使用项目内 conda 环境：

```bash
conda create -y -p ./.conda/etf-quant python=3.11 pip pandas numpy matplotlib pyyaml
.conda/etf-quant/bin/python -m pip install akshare tushare
```

后续统一用：

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli ...
```

## 推荐主流程

优先跑 hybrid 口径：

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli validate-data --config configs/bigquant_rotation_hybrid.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli backtest --config configs/bigquant_rotation_hybrid.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli rebalance --config configs/bigquant_rotation_hybrid.yaml
```

输出：

- `outputs/strategies/bigquant_rotation/hybrid/equity_curve.png`
- `outputs/strategies/bigquant_rotation/hybrid/metrics.yaml`
- `outputs/strategies/bigquant_rotation/hybrid/weights.csv`
- `outputs/strategies/bigquant_rotation/hybrid/rebalance_plan.csv`

## 数据源状态

- AkShare：当前网络可下载，建议每次下载后跑 `validate-data`。
- Yahoo：当前网络现网下载返回 `403 Forbidden`，但已有缓存可用于实验。
- Tushare：代码已接入，需要 `TUSHARE_TOKEN`，尚未实测。

## BigQuant 策略迁移口径

已迁移内容：

- `trend_score`
- `mom_20`
- `mom_60`
- `ma_5_10`
- `ma_10_20`
- `don_pos_20`
- `dev_atr_20`
- `turn_accel_20`
- `amt_accel_20`
- `obv_balance_20`
- `mfi_14`
- `vol_ratio_10_60`
- `downvar_60`
- `ulcer_60`
- `gap_open`
- `candle_pos`
- `intraday_range`
- `premium_iopv`
- 动态 gap
- 交易缓冲区
- 逆波动配仓
- 簇权重上限
- 止盈止损与冷却期

注意：

- 原始 BigQuant 代码虽然定义了 `REBALANCE_WEEKDAY = 4`，但 `handle_data` 中没有调用 `_is_rebalance_day`，因此实际是每日重算目标池。
- 本项目配置中 `rebalance: D`，策略参数 `rebalance_weekday: null`，以贴近原始代码行为。
- 原始 BigQuant 用开盘成交，本项目使用 `execution: next_open` 近似。

## 已知风险

- AkShare fallback 到 Sina 时可能出现未复权跳变，尤其是 QDII ETF 拆分/折算日。
- `turn` / `iopv` 字段并非所有数据源都有。缺失时因子会使用近似或按 0 处理。
- 当前回测器仍是轻量级权重回测，不完全等同 BigTrader 的撮合、滑点、账户对象与开盘成交细节。

## 下一步建议

1. 用 Tushare token 或 Wind 数据源补齐稳定前复权日线。
2. 把 `iopv` 和 `turn` 做成可选字段质量报告。
3. 增加回测事件日志，记录每次止损、止盈、冷却和调仓原因。
4. 做 walk-forward 版本的 BigQuant 策略样本外回测。
