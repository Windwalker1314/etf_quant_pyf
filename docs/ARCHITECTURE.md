# Architecture

这个项目按“数据、因子、策略、执行/回测、验证、实盘预演”分层。每一层只依赖稳定协议，不依赖具体实现。

## 数据层

核心对象是 `MarketData`，内部使用标准 OHLCV 长表：

```text
date, symbol, open, high, low, close, volume
```

新增数据源时，实现 `DataSource.load(config) -> MarketData`，并注册到 `DATA_SOURCE_REGISTRY`。例如 AkShare、Tushare、Yahoo、Wind、本地数据库都应该只影响数据层。

## 因子层

因子实现 `compute(market_data) -> DataFrame`，输出为：

```text
index = date
columns = symbol
values = factor value
```

因子只负责加工历史可观测数据，不做策略决策。

## 策略层

策略实现统一协议：

```python
fit(train_data, validation_data=None)
generate_weights(as_of_date, market_data, factor_data)
```

`generate_weights` 返回目标权重。规则策略、机器学习模型、小模型、大模型、强化学习、多智能体策略都可以接进来。回测器只认“目标权重”，不关心策略内部形态。

## 回测层

回测引擎负责：

- 按调仓频率调用策略。
- 只把截至 `as_of_date` 的数据传给策略。
- 默认下一交易日权重生效，减少前视偏差。
- 计算交易成本、净值曲线、换手率和绩效指标。

## Walk-forward 验证

验证器将历史数据拆成 Train、Validation、Test 三段，并滚动或扩展窗口：

- Train：拟合模型或策略参数。
- Validation：调参、早停、选择模型。
- Test：只产出样本外收益。

最终资金曲线只拼接每折 Test 段收益。

## 实盘预演

`rebalance` 命令读取最新本地数据，输出目标权重和需要交易的权重差。后续接交易账户时，应新增执行层适配器，不改策略和回测模块。
