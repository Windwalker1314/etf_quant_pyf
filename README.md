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

## Conda 环境

推荐使用项目内 conda 环境，避免污染系统 Python：

```bash
conda create -y -p ./.conda/etf-quant python=3.11 pip pandas numpy matplotlib pyyaml
.conda/etf-quant/bin/python -m pip install akshare tushare
```

之后运行命令时使用：

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli backtest --config configs/backtest.yaml
```

## 真实数据源

项目已接入三个数据源：

- `yahoo`：无需额外依赖，适合海外 ETF 和部分 A 股/H 股 ETF。
- `akshare`：适合国内 ETF/LOF，无需 token；当前配置会优先用东方财富线路，失败后 fallback 到新浪 ETF 日线。
- `tushare`：适合更稳定的数据生产环境；需要 Tushare token。

下载 AkShare 数据并回测：

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli download-data --config configs/bigquant_rotation_akshare.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli validate-data --config configs/bigquant_rotation_akshare.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli backtest --config configs/bigquant_rotation_akshare.yaml
```

注意：AkShare 东方财富线路在网络不可用时会 fallback 到新浪 ETF 日线。新浪数据可能是未复权口径，QDII ETF 在拆分/折算日会出现异常跳变；正式回测前请先运行 `validate-data`。

下载 Tushare 数据并回测：

```bash
export TUSHARE_TOKEN=你的token
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli download-data --config configs/bigquant_rotation_tushare.yaml
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli backtest --config configs/bigquant_rotation_tushare.yaml
```

输出会写入 `outputs/`，并按用途归类：

- `outputs/strategies/`：正式策略输出。
- `outputs/baselines/`：基准策略输出。
- `outputs/experiments/`：候选参数、sweep 搜索等实验输出。
- `outputs/global/`：全球 ETF 长历史实验输出。
- `outputs/archive/`：早期通用样例输出。

常见文件包括 `equity_curve.csv`、`metrics.yaml`、`equity_curve.png`、`weights.csv` 和 `rebalance_plan.csv`。具体目录约定见 `outputs/README.md`。

## 每日实盘预演

如果想用本地小程序操作，启动：

```bash
scripts/app.sh
```

然后打开 <http://127.0.0.1:8765>。界面会自动读取 `configs/*hybrid*.yaml` 作为可选策略，默认使用 `configs/bigquant_rotation_hybrid_candidate_turnover.yaml`。持仓和现金保存到 `data/live/positions.csv`，每天早上点“生成计划”即可生成调仓动作。设置会记在 `data/live/app_state.json`。

## iOS App Demo

当前分支包含一个 ETF Quant iOS 产品 demo：

- 产品设计：`docs/product/ios_quant_app_demo.md`
- 原生 SwiftUI 工程：`ios/ETFQuantApp/ETFQuantApp.xcodeproj`
- 无需 Xcode 的移动端预览：`demos/ios-mobile/index.html`

本机如果还没有完整 Xcode，可以先启动浏览器预览：

```bash
python3 -m http.server 8877 --directory demos/ios-mobile
```

然后打开 <http://127.0.0.1:8877>。原生工程内置了策略选择、每日调仓提醒、回测曲线和调仓计划预览，后续可以把 demo 数据仓库替换为现有 Python 服务 API。

开盘前生成交易计划：

```bash
cp data/live/positions_example.csv data/live/positions.csv
# 编辑 data/live/positions.csv，填入当前持仓份额和现金。
scripts/live_plan.sh
```

脚本默认会：

- 用 `configs/bigquant_rotation_hybrid_candidate_turnover.yaml` 读取 hybrid 口径行情。
- 读取 `data/live/positions.csv`。
- 按 100 份整手取整。
- 输出到 `outputs/live/bigquant_rotation_hybrid_candidate_turnover/`。

输出文件：

- `live_rebalance_plan.md`：适合开盘前阅读的交易计划。
- `live_rebalance_plan.csv`：适合复制、检查或后续接券商接口的结构化计划。

也可以直接跑 CLI：

```bash
PYTHONPATH=src .conda/etf-quant/bin/python -m etf_quant.cli live-plan \
  --config configs/bigquant_rotation_hybrid_candidate_turnover.yaml \
  --positions data/live/positions.csv \
  --lot-size 100 \
  --min-trade-value 0
```

`positions.csv` 格式：

```csv
symbol,shares,cash
513600.SH,10000,
518880.SH,2000,
CASH,0,150000
```

其中 `shares` 是当前持仓份额，`CASH` 行的 `cash` 是可用现金。报告中的交易价格默认使用最新一根日线收盘价估算，实际下单仍需按开盘价/盘口手动确认。

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
