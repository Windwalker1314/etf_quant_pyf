const strategies = [
  {
    id: "bigquant_rotation",
    name: "PYF ETF Rotation",
    subtitle: "Momentum plus volatility rotation across A-share and commodity ETFs",
    annualReturn: 0.184,
    maxDrawdown: -0.116,
    sharpe: 1.34,
    volatility: 0.138,
    latestSignal: "Risk-on, rotate to gold and broad-market beta",
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
    subtitle: "Risk regime allocation with defensive bond and gold sleeves",
    annualReturn: 0.128,
    maxDrawdown: -0.082,
    sharpe: 1.18,
    volatility: 0.095,
    latestSignal: "Neutral risk, keep a balanced defensive mix",
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
    id: "equal_weight",
    name: "Equal Weight Baseline",
    subtitle: "Simple benchmark allocation for sanity checks",
    annualReturn: 0.092,
    maxDrawdown: -0.151,
    sharpe: 0.74,
    volatility: 0.126,
    latestSignal: "No signal. Maintain equal weights.",
    allocation: [
      ["518880.SH", "Gold ETF", 0.25],
      ["510300.SH", "CSI 300 ETF", 0.25],
      ["513100.SH", "Nasdaq ETF", 0.25],
      ["511010.SH", "Treasury ETF", 0.25],
    ],
    orders: [["HOLD", "518880.SH", "Gold ETF", 0, 0.25]],
    curveSeed: [0.08, 0.12],
  },
];

const state = {
  selectedId: "bigquant_rotation",
  reminder: "09:20",
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
  $("#annualReturn").textContent = pct(strategy.annualReturn);
  $("#maxDrawdown").textContent = pct(strategy.maxDrawdown);
  $("#sharpe").textContent = strategy.sharpe.toFixed(2);
  $("#volatility").textContent = pct(strategy.volatility);
  $("#reminderTime").textContent = state.reminder;
  $("#allocationName").textContent = strategy.name;

  renderStrategies();
  renderOrders(strategy);
  renderAllocation(strategy);
  drawCurve(strategy);
}

function renderStrategies() {
  $("#strategyList").innerHTML = strategies
    .map(
      (strategy) => `
        <button class="strategy-button ${strategy.id === state.selectedId ? "active" : ""}" data-strategy="${strategy.id}">
          <strong>${strategy.name}</strong>
          <span class="subtext">${strategy.subtitle}</span>
          <span class="strategy-meta">
            <span>年化 ${pct(strategy.annualReturn)}</span>
            <span>回撤 ${pct(strategy.maxDrawdown)}</span>
            <span>Sharpe ${strategy.sharpe.toFixed(2)}</span>
          </span>
        </button>
      `
    )
    .join("");

  $$(".strategy-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.strategy;
      render();
      showToast("策略已切换");
    });
  });
}

function renderOrders(strategy) {
  const activeOrders = strategy.orders.filter((order) => order[0] !== "HOLD");
  $("#orderSummary").textContent = activeOrders.length ? `${activeOrders.length} 笔需处理` : "无需交易";
  $("#ordersList").innerHTML = strategy.orders
    .map(([side, symbol, name, value, weight]) => {
      const sideClass = side.toLowerCase();
      return `
        <article class="order-row">
          <span class="side ${sideClass}">${side}</span>
          <div>
            <div class="symbol">${symbol}</div>
            <div class="name">${name}</div>
          </div>
          <div class="amount">
            <div>${pct(weight)}</div>
            <div class="name">¥${money(value)}</div>
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

$("#saveReminderButton").addEventListener("click", () => {
  state.reminder = $("#timeInput").value || "09:20";
  $("#permissionText").textContent = `已保存每日 ${state.reminder} 的调仓提醒。`;
  render();
  showToast("提醒已保存");
});

window.addEventListener("resize", () => drawCurve(selectedStrategy()));
render();
