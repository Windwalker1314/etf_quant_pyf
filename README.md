# ETF Quant

日频 ETF 大类资产与指数策略研究框架，目标是高扩展、低耦合、可落地到每日调仓计划。

当前版本提供一个可运行的最小系统：

- 数据层：CSV、本地模拟数据源，统一为 OHLCV 长表与价格宽表。
- 因子层：动量、波动率、均线距离等可插拔因子。
- 策略层：统一 `Strategy` 协议，示例实现多因子规则策略。
- 回测层：日频、下一交易日调仓生效、交易成本、净值曲线、夏普、最大回撤、年化收益、波动率。
- 验证层：滚动窗口和扩展窗口 Walk-forward，拼接样本外资金曲线。
- 实盘预演：每天跑脚本，读取最新数据，输出目标权重和调仓计划。

## 快速开始

```bash
PYTHONPATH=src python3 -m etf_quant.cli init-sample-data --config configs/universe.yaml
PYTHONPATH=src python3 -m etf_quant.cli backtest --config configs/backtest.yaml
PYTHONPATH=src python3 -m etf_quant.cli walk-forward --config configs/walk_forward.yaml
PYTHONPATH=src python3 -m etf_quant.cli rebalance --config configs/rebalance.yaml
```

输出会写入 `outputs/`：

- `equity_curve.csv`
- `metrics.yaml`
- `equity_curve.png`
- `rebalance_plan.csv`

## 扩展策略

新增策略只需实现 `Strategy` 协议，并注册到 `STRATEGY_REGISTRY`：

```python
class MyStrategy:
    name = "my_strategy"

    def fit(self, train_data, validation_data=None):
        return self

    def generate_weights(self, as_of_date, market_data, factor_data):
        ...
```

规则策略、机器学习、小模型、大模型、强化学习、多智能体都走同一个接口。回测器与验证器不关心策略内部实现。

## 数据防过拟合约定

Walk-forward 的每一折都严格分成：

- Train：训练策略参数或模型。
- Validation：调参、早停、模型选择。
- Test：只做样本外预测和收益拼接。

最终可信资金曲线来自所有 Test 段拼接，而不是单次全样本回测。

## 目录

```text
src/etf_quant/
  backtest/       回测、绩效、图表
  config/         配置读取与 schema
  data/           数据源、数据集、模拟样本
  factors/        因子协议与示例因子
  live/           每日调仓计划
  strategies/     策略协议与注册表
  validation/     滚动/扩展窗口验证
configs/          示例配置
tests/            轻量测试
```
