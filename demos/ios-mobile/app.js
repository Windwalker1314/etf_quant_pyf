const strategies = [
  {
    id: "bigquant_rotation",
    name: "PYF ETF Rotation",
    creator: "PYF Research",
    verified: true,
    subscribed: true,
    price: 59,
    subscribers: 1286,
    trustScore: 92,
    creatorBio: "专注 ETF 轮动和样本外验证，维护本项目核心策略库。",
    verification: ["回测配置已复现", "Walk-forward 样本外通过", "实盘信号跟踪 63 天", "最近审核：2026-05-12"],
    fit: "适合想要积极轮动的 ETF 用户",
    subtitle: "趋势动量 + 波动过滤，覆盖 A 股、黄金、海外指数和债券 ETF。",
    annualReturn: 0.184,
    maxDrawdown: -0.116,
    sharpe: 1.34,
    volatility: 0.138,
    latestSignal: "风险偏积极，黄金和宽基权益占优",
    plainSummary: "用趋势和波动过滤 ETF，每天收盘后给出下一交易日目标仓位。",
    principle:
      "这套策略会先观察每个 ETF 最近一段时间是否上涨，再检查上涨过程是否足够稳定。它倾向于买入趋势更强、波动更可控的资产；如果市场变差，会提高债券或现金类资产权重。",
    deliverables: ["每日 09:20 调仓提醒", "目标权重和买卖方向", "历史回测曲线", "策略失效场景说明"],
    risks: ["震荡市可能频繁换仓", "短期可能跑输单一强势指数", "QDII ETF 可能受汇率和额度影响"],
    allocation: [
      ["518880.SH", "Gold ETF", 0.35],
      ["510300.SH", "CSI 300 ETF", 0.3],
      ["513100.SH", "Nasdaq ETF", 0.2],
      ["511010.SH", "Treasury ETF", 0.15],
    ],
    orders: [
      ["BUY", "518880.SH", "Gold ETF", 10480, 0.35],
      ["SELL", "513100.SH", "Nasdaq ETF", 7264, 0.2],
      ["HOLD", "511010.SH", "Treasury ETF", 0, 0.15],
    ],
    curveSeed: [0.18, 0.08],
  },
  {
    id: "global_macro_risk",
    name: "Global Macro Risk",
    creator: "Northstar Macro",
    verified: true,
    subscribed: false,
    price: 79,
    subscribers: 842,
    trustScore: 88,
    creatorBio: "宏观资产配置研究团队，偏重回撤控制和防守型组合。",
    verification: ["数据源已审查", "样本外曲线已提交", "实盘信号跟踪 41 天", "最近审核：2026-05-10"],
    fit: "适合重视回撤控制的长期用户",
    subtitle: "根据宏观风险状态，在权益、黄金和债券之间做防守切换。",
    annualReturn: 0.128,
    maxDrawdown: -0.082,
    sharpe: 1.18,
    volatility: 0.095,
    latestSignal: "风险中性，维持均衡防守组合",
    plainSummary: "市场风险升高时减少权益暴露，优先保住回撤体验。",
    principle:
      "这套策略把市场分成风险偏好、风险中性和风险规避三种状态。它不会追求每天最高收益，而是希望在危险阶段减少亏损，在环境改善后再逐步恢复权益仓位。",
    deliverables: ["每日风险状态更新", "防守/进攻仓位建议", "宏观指标解释", "月度策略复盘"],
    risks: ["强牛市中可能涨得较慢", "宏观信号可能滞后", "防守资产也可能短期下跌"],
    allocation: [
      ["511010.SH", "Treasury ETF", 0.4],
      ["518880.SH", "Gold ETF", 0.25],
      ["510300.SH", "CSI 300 ETF", 0.2],
      ["513100.SH", "Nasdaq ETF", 0.15],
    ],
    orders: [
      ["BUY", "511010.SH", "Treasury ETF", 12600, 0.4],
      ["HOLD", "510300.SH", "CSI 300 ETF", 0, 0.2],
    ],
    curveSeed: [0.12, 0.05],
  },
  {
    id: "income_balance",
    name: "Income Balance ETF",
    creator: "Harbor Quant Lab",
    verified: false,
    subscribed: false,
    price: 39,
    subscribers: 312,
    trustScore: 71,
    creatorBio: "新入驻策略团队，主打低波动 ETF 配置。",
    verification: ["回测已提交", "等待完整样本外复核", "实盘信号跟踪 12 天", "最近审核：2026-05-08"],
    fit: "适合新手的小波动入门组合",
    subtitle: "低换手配置型策略，以债券和黄金为核心，少量参与权益机会。",
    annualReturn: 0.092,
    maxDrawdown: -0.071,
    sharpe: 0.91,
    volatility: 0.082,
    latestSignal: "维持防守，等待权益趋势确认",
    plainSummary: "更像自动化资产配置，目标是少犯错、少折腾。",
    principle:
      "这套策略大部分时间持有债券和黄金，只有当权益 ETF 趋势改善时才逐步加仓。它牺牲一部分上涨弹性，换取更平滑的持有体验。",
    deliverables: ["每周配置检查", "低频调仓提醒", "新手解释版信号", "组合风险温度计"],
    risks: ["收益弹性有限", "低波动不等于无亏损", "不适合追求短期暴利的用户"],
    allocation: [
      ["511010.SH", "Treasury ETF", 0.5],
      ["518880.SH", "Gold ETF", 0.25],
      ["510300.SH", "CSI 300 ETF", 0.15],
      ["159915.SZ", "ChiNext ETF", 0.1],
    ],
    orders: [["HOLD", "511010.SH", "Treasury ETF", 0, 0.5]],
    curveSeed: [0.08, 0.04],
  },
];

const state = {
  selectedId: "bigquant_rotation",
  reminder: "09:20",
  capital: 100000,
  risk: "balanced",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function selectedStrategy() {
  return strategies.find((strategy) => strategy.id === state.selectedId) || strategies[0];
}

function pct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function money(value) {
  if (!value) return "0";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function recommendedStrategyId() {
  if (state.risk === "conservative") return "income_balance";
  if (state.risk === "growth") return "bigquant_rotation";
  return "global_macro_risk";
}

function riskLabel() {
  return {
    conservative: "稳健型",
    balanced: "均衡型",
    growth: "成长型",
  }[state.risk];
}

function recommendationReason(strategy = strategies.find((item) => item.id === recommendedStrategyId())) {
  if (!strategy) return "";
  if (state.risk === "conservative") return `你选择了稳健型，${strategy.name} 的回撤更低、换手更少，适合作为第一套订阅策略。`;
  if (state.risk === "growth") return `你选择了成长型，${strategy.name} 的收益弹性更强，但需要接受更明显的波动。`;
  return `你选择了均衡型，${strategy.name} 在回撤控制和收益之间更平衡，适合作为默认推荐。`;
}

function curvePoints(strategy) {
  const [seed, drawdown] = strategy.curveSeed;
  return Array.from({ length: 24 }, (_, month) => {
    const wave = Math.sin(month / 2.4) * drawdown;
    const strategyValue = 1 + (seed * month) / 12 + wave;
    const baselineValue = 1 + (0.075 * month) / 12 + Math.sin(month / 2.1) * 0.045;
    return { month, strategyValue, baselineValue };
  });
}

function render() {
  const strategy = selectedStrategy();
  $("#strategyName").textContent = strategy.name;
  $("#latestSignal").textContent = strategy.latestSignal;
  $("#plainSummary").textContent = strategy.plainSummary;
  $("#annualReturn").textContent = pct(strategy.annualReturn);
  $("#maxDrawdown").textContent = pct(strategy.maxDrawdown);
  $("#sharpe").textContent = strategy.sharpe.toFixed(2);
  $("#capitalAmount").textContent = `¥${money(state.capital)}`;
  $("#notifyButton").textContent = state.reminder;
  $("#recommendationText").textContent = recommendationReason();
  $("#riskProfileLabel").textContent = riskLabel();
  $("#exploreRecommendation").textContent = recommendationReason();
  $("#capitalInput").value = state.capital;
  $("#riskSelect").value = state.risk;
  $("#subscriptionBadge").textContent = strategy.subscribed ? "已订阅" : "未订阅";
  $("#subscriptionBadge").className = `pill ${strategy.subscribed ? "success" : ""}`;
  $("#accountSummary").textContent = `已订阅 ${strategies.filter((item) => item.subscribed).length} 个策略，调仓提醒 ${state.reminder}。`;

  renderMarketplace();
  renderDetail(strategy);
  renderOrders(strategy);
  renderAllocation(strategy);
  drawCurve(strategy);
}

function renderMarketplace() {
  $("#marketplaceList").innerHTML = strategies
    .map((strategy) => {
      const active = strategy.id === state.selectedId ? "active" : "";
      const verified = strategy.verified ? "已验证" : "待验证";
      return `
        <button class="strategy-button ${active}" data-strategy="${strategy.id}">
          <span class="card-topline">
            <span class="pill ${strategy.verified ? "success" : ""}">${verified}</span>
            <span>¥${strategy.price}/月</span>
          </span>
          <strong>${strategy.name}</strong>
          <span class="subtext">${strategy.fit}</span>
          <span class="strategy-meta">
            <span>年化 ${pct(strategy.annualReturn)}</span>
            <span>回撤 ${pct(strategy.maxDrawdown)}</span>
            <span>${strategy.subscribers} 人订阅</span>
          </span>
        </button>
      `;
    })
    .join("");

  $$(".strategy-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.strategy;
      render();
      setView("detail");
      showToast("已打开策略详情");
    });
  });
}

function renderDetail(strategy) {
  $("#detailName").textContent = strategy.name;
  $("#detailCreator").textContent = strategy.creator;
  $("#detailFit").textContent = strategy.fit;
  $("#detailSubtitle").textContent = strategy.subtitle;
  $("#trustScore").textContent = `${strategy.trustScore}`;
  $("#creatorBio").textContent = strategy.creatorBio;
  $("#principleText").textContent = strategy.principle;
  $("#allocationName").textContent = strategy.name;
  $("#subscribeButton").textContent = strategy.subscribed ? "已订阅，查看今日计划" : `7 天试用，然后 ¥${strategy.price}/月`;
  $("#deliverablesList").innerHTML = strategy.deliverables.map((item) => `<li>${item}</li>`).join("");
  $("#riskList").innerHTML = strategy.risks.map((item) => `<li>${item}</li>`).join("");
  $("#verificationList").innerHTML = strategy.verification.map((item) => `<li>${item}</li>`).join("");
}

function renderOrders(strategy) {
  const activeOrders = strategy.orders.filter((order) => order[0] !== "HOLD");
  $("#orderSummary").textContent = activeOrders.length ? `${activeOrders.length} 笔需处理` : "无需交易";
  $("#ordersList").innerHTML = strategy.orders
    .map(([side, symbol, name, value, weight]) => {
      const sideClass = side.toLowerCase();
      const targetValue = state.capital * weight;
      return `
        <article class="order-row">
          <span class="side ${sideClass}">${side}</span>
          <div>
            <div class="symbol">${symbol}</div>
            <div class="name">${name}</div>
          </div>
          <div class="amount">
            <div>${pct(weight)}</div>
            <div class="name">目标 ¥${money(targetValue)}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderAllocation(strategy) {
  $("#allocationList").innerHTML = strategy.allocation
    .map(
      ([symbol, name, weight]) => `
        <article class="allocation-row">
          <header>
            <div>
              <div class="symbol">${symbol}</div>
              <div class="name">${name}</div>
            </div>
            <strong>${pct(weight)}</strong>
          </header>
          <div class="bar" style="--w: ${weight * 100}%"><span></span></div>
        </article>
      `
    )
    .join("");
}

function drawCurve(strategy) {
  const canvas = $("#equityCanvas");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);

  const points = curvePoints(strategy);
  const values = points.flatMap((point) => [point.strategyValue, point.baselineValue]);
  const min = Math.min(...values) - 0.03;
  const max = Math.max(...values) + 0.03;
  const left = 34;
  const right = 12;
  const top = 16;
  const bottom = 28;
  const width = rect.width - left - right;
  const height = rect.height - top - bottom;

  ctx.strokeStyle = "#dde3ea";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = top + (height * i) / 3;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(left + width, y);
    ctx.stroke();
  }

  function toXY(point, key) {
    const x = left + (point.month / (points.length - 1)) * width;
    const y = top + (1 - (point[key] - min) / (max - min)) * height;
    return [x, y];
  }

  function line(key, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    points.forEach((point, index) => {
      const [x, y] = toXY(point, key);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  line("baselineValue", "#d17a22");
  line("strategyValue", "#087f8c");

  ctx.fillStyle = "#667085";
  ctx.font = "12px system-ui";
  ctx.fillText("2023", left, rect.height - 8);
  ctx.fillText("2024", left + width - 34, rect.height - 8);
  ctx.fillStyle = "#087f8c";
  ctx.fillText("Strategy", left, 14);
  ctx.fillStyle = "#d17a22";
  ctx.fillText("Baseline", left + 78, 14);
}

function setView(name) {
  $$(".screen").forEach((screen) => screen.classList.toggle("hidden", screen.dataset.view !== name));
  $$(".tabbar button").forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  if (name === "today") drawCurve(selectedStrategy());
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

$$(".tabbar button").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.tab));
});

$("#notifyButton").addEventListener("click", () => {
  setView("settings");
});

$("#copyPlanButton").addEventListener("click", () => {
  const strategy = selectedStrategy();
  const lines = strategy.orders.map(([side, symbol, name, value, weight]) => `${side} ${symbol} ${name} -> ${pct(weight)} ¥${money(value)}`);
  navigator.clipboard?.writeText(lines.join("\n")).catch(() => {});
  showToast("今日调仓计划已复制");
});

$("#subscribeButton").addEventListener("click", () => {
  const strategy = selectedStrategy();
  if (!strategy.subscribed) {
    strategy.subscribed = true;
    render();
    showToast("订阅成功，已加入每日提醒");
    return;
  }
  setView("today");
});

$("#applyRecommendationButton").addEventListener("click", () => {
  state.selectedId = recommendedStrategyId();
  render();
  setView("detail");
  showToast("已应用推荐策略");
});

$("#saveProfileButton").addEventListener("click", () => {
  state.reminder = $("#timeInput").value || "09:20";
  state.capital = Number($("#capitalInput").value || 100000);
  state.risk = $("#riskSelect").value;
  $("#permissionText").textContent = `已保存 ${riskLabel()}、¥${money(state.capital)} 和每日 ${state.reminder} 的提醒。`;
  render();
  showToast("画像已保存，推荐已更新");
});

window.addEventListener("resize", () => drawCurve(selectedStrategy()));
render();
