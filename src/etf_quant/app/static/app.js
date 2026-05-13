const state = {
  strategies: [],
  selectedConfig: null,
  positions: { cash: 0, holdings: [] },
  plan: null,
  busy: false,
};

const els = {
  strategySelect: document.querySelector("#strategySelect"),
  strategyMeta: document.querySelector("#strategyMeta"),
  lotSizeInput: document.querySelector("#lotSizeInput"),
  minTradeInput: document.querySelector("#minTradeInput"),
  refreshInput: document.querySelector("#refreshInput"),
  savePositionsButton: document.querySelector("#savePositionsButton"),
  generateButton: document.querySelector("#generateButton"),
  pageTitle: document.querySelector("#pageTitle"),
  holdingsBody: document.querySelector("#holdingsBody"),
  cashInput: document.querySelector("#cashInput"),
  positionsPath: document.querySelector("#positionsPath"),
  asOfDate: document.querySelector("#asOfDate"),
  portfolioValue: document.querySelector("#portfolioValue"),
  cashValue: document.querySelector("#cashValue"),
  tradeCount: document.querySelector("#tradeCount"),
  chartHint: document.querySelector("#chartHint"),
  weightChart: document.querySelector("#weightChart"),
  ordersBody: document.querySelector("#ordersBody"),
  orderHint: document.querySelector("#orderHint"),
  toast: document.querySelector("#toast"),
};

const palette = ["#087f8c", "#d17a22", "#4d6baf", "#8a5a9e", "#26845b", "#b64b49", "#6b7280"];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.background = isError ? "#8f2f2a" : "#15212d";
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 3600);
}

function setBusy(value) {
  state.busy = value;
  els.generateButton.disabled = value;
  els.savePositionsButton.disabled = value;
  els.generateButton.textContent = value ? "生成中..." : "生成计划";
}

function renderStrategies() {
  els.strategySelect.innerHTML = "";
  state.strategies.forEach((strategy) => {
    const option = document.createElement("option");
    option.value = strategy.path;
    option.textContent = strategy.label;
    els.strategySelect.appendChild(option);
  });
  if (state.selectedConfig) {
    els.strategySelect.value = state.selectedConfig;
  }
  renderStrategyMeta();
}

function selectedStrategy() {
  return state.strategies.find((item) => item.path === state.selectedConfig) || state.strategies[0];
}

function renderStrategyMeta() {
  const strategy = selectedStrategy();
  if (!strategy) {
    els.strategyMeta.innerHTML = '<div class="meta-row"><span>状态</span><strong>未找到配置</strong></div>';
    els.pageTitle.textContent = "策略调仓计划";
    return;
  }
  els.pageTitle.textContent = strategy.label;
  els.strategyMeta.innerHTML = [
    ["策略", strategy.strategy_name],
    ["数据源", strategy.data_source],
    ["资产数", strategy.universe_size],
    ["配置", strategy.path],
  ]
    .map(([label, value]) => `<div class="meta-row"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderPositions() {
  els.cashInput.value = state.positions.cash ?? 0;
  els.positionsPath.textContent = state.positions.path || "-";
  els.holdingsBody.innerHTML = "";
  state.positions.holdings.forEach((holding) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${holding.symbol}</td>
      <td>${holding.name || "-"}</td>
      <td class="num"><input type="number" step="1" data-symbol="${holding.symbol}" value="${holding.shares || 0}" /></td>
    `;
    els.holdingsBody.appendChild(row);
  });
  if (state.positions.holdings.length === 0) {
    els.holdingsBody.innerHTML = '<tr><td class="empty-row" colspan="3">暂无持仓资产</td></tr>';
  }
}

function collectPositions() {
  const inputs = [...els.holdingsBody.querySelectorAll("input[data-symbol]")];
  return {
    config_path: state.selectedConfig,
    cash: Number(els.cashInput.value || 0),
    holdings: inputs.map((input) => ({
      symbol: input.dataset.symbol,
      shares: Number(input.value || 0),
    })),
  };
}

function renderPlan(plan) {
  els.asOfDate.textContent = plan?.as_of_date || "-";
  els.portfolioValue.textContent = money(plan?.portfolio_value);
  els.cashValue.textContent = money(plan?.cash);
  els.tradeCount.textContent = plan ? String(plan.trade_count) : "-";
  renderOrders(plan?.orders || []);
  drawWeights(plan?.targets || []);
}

function renderOrders(orders) {
  els.ordersBody.innerHTML = "";
  els.orderHint.textContent = orders.length ? `${orders.length} 笔需要处理` : "无需交易";
  if (!orders.length) {
    els.ordersBody.innerHTML = '<tr><td class="empty-row" colspan="6">当前持仓可保持不动</td></tr>';
    return;
  }
  orders
    .sort((a, b) => Math.abs(b.trade_value || 0) - Math.abs(a.trade_value || 0))
    .forEach((order) => {
      const side = String(order.side || "HOLD").toLowerCase();
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${order.symbol}</td>
        <td><span class="badge ${side}">${order.side}</span></td>
        <td class="num">${money(order.trade_shares)}</td>
        <td class="num">${money(order.price)}</td>
        <td class="num">${money(order.trade_value)}</td>
        <td class="num">${pct(order.target_weight)}</td>
      `;
      els.ordersBody.appendChild(row);
    });
}

function drawWeights(targets) {
  const canvas = els.weightChart;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);

  const data = targets.filter((item) => Number(item.target_weight) > 0).slice(0, 8);
  els.chartHint.textContent = data.length ? "按目标权重排序" : "等待生成计划";
  if (!data.length) {
    ctx.fillStyle = "#637083";
    ctx.font = "14px sans-serif";
    ctx.fillText("暂无目标权重", 24, 42);
    return;
  }

  const left = 118;
  const right = 28;
  const top = 24;
  const barHeight = 24;
  const gap = 14;
  const maxWeight = Math.max(...data.map((item) => Number(item.target_weight)));
  ctx.font = "13px sans-serif";
  data.forEach((item, index) => {
    const y = top + index * (barHeight + gap);
    const width = ((rect.width - left - right) * Number(item.target_weight)) / maxWeight;
    ctx.fillStyle = "#2f3a45";
    ctx.fillText(item.symbol, 18, y + 17);
    ctx.fillStyle = "#e5e9ef";
    ctx.fillRect(left, y, rect.width - left - right, barHeight);
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(left, y, width, barHeight);
    ctx.fillStyle = "#17202a";
    ctx.fillText(pct(item.target_weight), left + Math.min(width + 8, rect.width - left - right - 48), y + 17);
  });
}

async function loadPositionsForSelected() {
  const data = await api(`/api/positions?config=${encodeURIComponent(state.selectedConfig || "")}`);
  state.positions = data;
  renderPositions();
}

async function savePositions() {
  setBusy(true);
  try {
    state.positions = await api("/api/positions", {
      method: "POST",
      body: JSON.stringify(collectPositions()),
    });
    renderPositions();
    showToast("持仓已保存");
  } finally {
    setBusy(false);
  }
}

async function generatePlan() {
  setBusy(true);
  try {
    const payload = {
      ...collectPositions(),
      lot_size: Number(els.lotSizeInput.value || 100),
      min_trade_value: Number(els.minTradeInput.value || 0),
      refresh_data: els.refreshInput.checked,
    };
    state.plan = await api("/api/plan", { method: "POST", body: JSON.stringify(payload) });
    renderPlan(state.plan);
    showToast(`计划已生成：${state.plan.as_of_date}`);
  } finally {
    setBusy(false);
  }
}

async function persistStatePatch(patch) {
  await api("/api/state", { method: "POST", body: JSON.stringify(patch) });
}

async function init() {
  try {
    const data = await api("/api/bootstrap");
    state.strategies = data.strategies || [];
    state.selectedConfig = data.selected_config;
    state.positions = data.positions || state.positions;
    els.lotSizeInput.value = data.settings?.lot_size ?? 100;
    els.minTradeInput.value = data.settings?.min_trade_value ?? 0;
    els.refreshInput.checked = Boolean(data.settings?.refresh_data);
    renderStrategies();
    renderPositions();
    renderPlan(null);
  } catch (error) {
    showToast(error.message, true);
  }
}

els.strategySelect.addEventListener("change", async () => {
  state.selectedConfig = els.strategySelect.value;
  renderStrategyMeta();
  await persistStatePatch({ selected_config: state.selectedConfig });
  await loadPositionsForSelected();
});

els.savePositionsButton.addEventListener("click", async () => {
  try {
    await savePositions();
  } catch (error) {
    showToast(error.message, true);
    setBusy(false);
  }
});

els.generateButton.addEventListener("click", async () => {
  try {
    await generatePlan();
  } catch (error) {
    showToast(error.message, true);
    setBusy(false);
  }
});

[els.lotSizeInput, els.minTradeInput, els.refreshInput].forEach((el) => {
  el.addEventListener("change", () => {
    persistStatePatch({
      lot_size: Number(els.lotSizeInput.value || 100),
      min_trade_value: Number(els.minTradeInput.value || 0),
      refresh_data: els.refreshInput.checked,
    }).catch((error) => showToast(error.message, true));
  });
});

window.addEventListener("resize", () => drawWeights(state.plan?.targets || []));
init();

