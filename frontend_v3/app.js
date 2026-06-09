/**
 * 工银牧融 V3 - 前端应用
 * ============================================================================
 * 5 页功能闭环: 总览 / 数据资产 / 风险评估 / 智能放贷 / 贷后监控
 * 设计: Modern SaaS Dashboard + ECharts
 *
 * 关键设计: 每个 pageInit() 独立 try/catch, 单页失败不影响整体
 */

const { createApp, ref, reactive, onMounted, watch, nextTick } = Vue;

// ============================================================================
// API 封装
// ============================================================================

async function safeFetch(url, options = {}) {
  try {
    const res = await fetch(url, { cache: "no-store", ...options });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`[fetch] ${url} 失败:`, e.message);
    throw e;
  }
}

const api = {
  platform: () => safeFetch("/api/platform"),
  regions: () => safeFetch("/api/regions"),
  subjects: () => safeFetch("/api/subjects"),
  finance: () => safeFetch("/api/finance"),
  dataSources: () => safeFetch("/api/data-sources"),
  dataQuality: () => safeFetch("/api/data-quality"),
  dataConnections: () => safeFetch("/api/data-connections"),
  publicDataSamples: () => safeFetch("/api/public-data/samples"),
  publicDataProcessed: () => safeFetch("/api/public-data/processed"),
  forageSummary: () => safeFetch("/api/forage-supply-demand/summary"),
  closedLoop: () => safeFetch("/api/closed-loop"),
  modelStatus: () => safeFetch("/api/model/status"),
  modelImportance: () => safeFetch("/api/model/importance"),
  riskAssessment: (regionId) => safeFetch(`/api/risk-assessment/${encodeURIComponent(regionId)}`),
  cooperativeRanking: (regionId, topN = 10) =>
    safeFetch(`/api/cooperative-ranking/${encodeURIComponent(regionId)}?top_n=${topN}`),
  warningComprehensive: (regionId, year = 2025) =>
    safeFetch(`/api/warning/comprehensive/${encodeURIComponent(regionId)}?year=${year}`),
  warningComprehensiveAll: (year = 2025) =>
    safeFetch(`/api/warning/comprehensive-all?year=${year}`),
  warningGdi: () => safeFetch("/api/warning/gdi"),
  warningNdvi: (regionId) =>
    regionId
      ? safeFetch(`/api/warning/ndvi?region_id=${encodeURIComponent(regionId)}`)
      : safeFetch("/api/warning/ndvi"),
  carryingCapacityDaily: (regionId, days = 30) =>
    safeFetch(`/api/carrying-capacity/daily?region_id=${encodeURIComponent(regionId)}&days=${days}`),
};

// ============================================================================
// 工具函数
// ============================================================================

const fmt = {
  num: (n) => (n === null || n === undefined ? "--" : Number(n).toLocaleString("zh-CN")),
  pct: (n) => (n === null || n === undefined ? "--" : `${(Number(n) * 100).toFixed(1)}%`),
  round: (n, d = 1) => (n === null || n === undefined ? "--" : Number(n).toFixed(d)),
};

function el(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  // 支持 #id / .class / [attr=val] / tag 三类选择器
  let node;
  if (id.startsWith("#")) {
    node = document.getElementById(id.slice(1));
  } else if (id.startsWith("[") || id.startsWith(".") || /^[a-z]/i.test(id)) {
    try {
      node = document.querySelector(id);
    } catch (e) {
      node = null;
    }
  } else {
    node = document.getElementById(id);
  }
  if (node) node.textContent = value;
}

function clearChildren(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function showEmpty(containerId, title = "暂无数据", desc = "") {
  const node = el(containerId);
  if (!node) return;
  clearChildren(node);
  const div = document.createElement("div");
  div.className = "empty-state";
  div.innerHTML = `
    <div class="empty-state-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
      </svg>
    </div>
    <p class="empty-state-title">${title}</p>
    <p class="empty-state-desc">${desc}</p>
  `;
  node.appendChild(div);
}

function getRiskClass(level) {
  if (!level) return "risk-badge-low";
  if (level.includes("高")) return "risk-badge-high";
  if (level.includes("中")) return "risk-badge-mid";
  return "risk-badge-low";
}

function ensureChart(id) {
  const node = el(id);
  if (!node) return null;
  if (!node._echart) {
    try {
      node._echart = echarts.init(node, null, { renderer: "canvas" });
    } catch (e) {
      console.warn("[echarts.init]", id, e);
      return null;
    }
  }
  return node._echart;
}

const chartBaseOption = {
  textStyle: { fontFamily: "inherit", fontSize: 12, color: "#475569" },
  grid: { left: 50, right: 24, top: 32, bottom: 40, containLabel: true },
  tooltip: {
    backgroundColor: "rgba(15, 23, 42, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fff", fontSize: 12 },
    extraCssText: "box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-radius: 8px;",
  },
  legend: { textStyle: { color: "#475569" }, top: 0, right: 0, icon: "circle" },
};

window.addEventListener("resize", () => {
  document.querySelectorAll("[id$='-chart']").forEach((node) => {
    if (node._echart) node._echart.resize();
  });
});

// ============================================================================
// 全局状态
// ============================================================================

const state = reactive({
  currentPage: "overview",
  data: null,        // /api/platform 缓存
  regions: [],       // /api/regions
  initialized: false,
});

const PAGE_TITLES = {
  overview: "总览",
  data: "数据资产",
  risk: "风险评估",
  loan: "智能放贷",
  monitor: "贷后监控",
};

// ============================================================================
// 路由
// ============================================================================

function navigate(page) {
  if (!PAGE_TITLES[page]) return;
  state.currentPage = page;

  document.querySelectorAll(".sidebar-nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === page);
  });

  document.querySelectorAll(".page-section").forEach((sec) => {
    sec.classList.toggle("active", sec.id === `page-${page}`);
  });

  el("topbar-title").textContent = PAGE_TITLES[page];

  // 触发对应页 init
  const fn = pageInits[page];
  if (fn && !fn._called) {
    fn._called = true;
    fn();
  } else if (fn) {
    fn();
  }
}

// ============================================================================
// Page 1: 总览
// ============================================================================

async function initOverview() {
  try {
    // 并行抓取所有独立数据 (5 个数字 + 4 能力卡)
    const [platform, dq, ms, conns, w, cl, subjects, finance] = await Promise.all([
      api.platform().catch(() => ({})),
      api.dataQuality().catch(() => null),
      api.modelStatus().catch(() => null),
      api.dataConnections().catch(() => []),
      api.warningComprehensiveAll(2025).catch(() => null),
      api.closedLoop().catch(() => ({})),
      api.subjects().catch(() => []),
      api.finance().catch(() => []),
    ]);
    state.data = platform;

    // Hero 5 个数字
    const regions = platform.regions || [];
    setText("[data-metric='regions']", fmt.num(regions.length));

    setText("[data-metric='subjects']", fmt.num(subjects.length || (platform.subjects || []).length));

    // finance 同时支持 credit_value(数字) / credit_line(数字) / credit_value(字符串"230 万元")
    const totalCredit = (finance.length ? finance : (platform.finance || [])).reduce((s, f) => {
      const v = Number(f.credit_value) || Number(f.credit_line) || 0;
      return s + v;
    }, 0);
    setText("[data-metric='credit']", fmt.num(Math.round(totalCredit)));

    // 数据资产行数
    if (dq) {
      setText("[data-metric='rows']", fmt.num(dq?.total?.total_rows || 0));
    } else {
      setText("[data-metric='rows']", "--");
    }

    // 模型准确率
    if (ms) {
      const acc = ms?.metrics?.accuracy ?? ms?.accuracy;
      setText("[data-metric='accuracy']", acc ? fmt.pct(acc) : "--");
      setText("ov-model-status", ms?.trained ? "已训练" : "未训练");
      const features = (ms?.metrics?.n_features || ms?.n_features || 0);
      setText("ov-model-meta", features ? `${features} 个特征 · XGBoost` : "XGBoost 风险模型");
    } else {
      setText("ov-model-status", "未训练");
      setText("ov-model-meta", "XGBoost 风险模型");
    }

    // 4 能力卡
    setText("ov-data-sources", fmt.num((conns || []).length));

    if (w) {
      setText("ov-warning-count", fmt.num((w?.high_risk_count || 0) + (w?.mid_risk_count || 0)));
      const total = w?.total_regions || 0;
      setText("ov-warning-meta", `${w?.high_risk_count || 0} 高 · ${w?.mid_risk_count || 0} 中 / ${total} 县`);
    } else {
      setText("ov-warning-count", "--");
      setText("ov-warning-meta", "--");
    }

    const loopTotal = Object.values(cl || {}).reduce((s, arr) => s + (arr?.length || 0), 0);
    setText("ov-loop", fmt.num(loopTotal));

    // 价值流 4 卡
    renderFlow();
  } catch (e) {
    console.error("[overview] init 失败:", e);
  }
}

function renderFlow() {
  const container = el("ov-flow");
  if (!container) return;
  clearChildren(container);

  const items = [
    { title: "数据采集", desc: "气象 · 遥感 · 工商 · 金融", icon: "M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7C5 4 4 5 4 7z" },
    { title: "风险建模", desc: "XGBoost 25 县评估", icon: "M3 3v18h18M7 14l4-4 4 4 5-5" },
    { title: "智能放贷", desc: "多维度合作社排序", icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2" },
    { title: "贷后闭环", desc: "订单 · 支付 · 理赔 · 绩效", icon: "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3" },
  ];

  items.forEach((it) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.cssText = "display: flex; align-items: center; gap: 16px;";
    card.innerHTML = `
      <div class="card-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="${it.icon}"/></svg>
      </div>
      <div>
        <h4 class="card-title" style="margin: 0 0 4px 0;">${it.title}</h4>
        <p class="card-subtitle" style="margin: 0;">${it.desc}</p>
      </div>
    `;
    container.appendChild(card);
  });
}

// ============================================================================
// Page 2: 数据资产
// ============================================================================

async function initData() {
  try {
    // 县域 select - 不依赖 overview
    if (!state.regions.length) {
      try { state.regions = await api.regions(); } catch {}
    }
    const regions = state.regions;

    const sel1 = el("data-region-select");
    const sel3 = el("risk-region-select");
    const sel4 = el("loan-region-select");
    const sel5a = el("monitor-ndvi-region");
    const sel5b = el("monitor-cap-region");
    [sel1, sel3, sel4, sel5a, sel5b].forEach((s) => {
      if (!s) return;
      if (s.children.length === 0) {
        regions.forEach((r) => {
          const opt = document.createElement("option");
          opt.value = r.id;
          opt.textContent = r.name;
          s.appendChild(opt);
        });
      }
    });

    // 4 类数据源
    const sources = await api.dataSources();
    renderDataSources(sources || []);

    // 数据质量
    const dq = await api.dataQuality();
    renderDataQuality(dq);

    // 县域图
    const subjects = await api.subjects();
    renderRegionChart(regions, subjects);

    // 公开数据
    try {
      const [samples, processed] = await Promise.all([
        api.publicDataSamples(),
        api.publicDataProcessed(),
      ]);
      renderPublicData(samples, processed);
    } catch (e) {
      showEmpty("data-public-list", "公开数据加载失败", e.message);
    }
  } catch (e) {
    console.error("[data] init 失败:", e);
  }
}

function renderDataSources(sources) {
  const grid = el("data-sources-grid");
  if (!grid) return;
  clearChildren(grid);
  if (!sources.length) {
    showEmpty("data-sources-grid", "暂无数据源");
    return;
  }
  const iconMap = {
    气象数据: "M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83",
    遥感数据: "M3 3v18h18M7 14l4-4 4 4 5-5",
    产业经营数据: "M3 7h18M3 12h18M3 17h18",
    金融保险数据: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2",
  };
  sources.forEach((s) => {
    const card = document.createElement("div");
    card.className = "card";
    const path = iconMap[s.name] || "M12 2l3 7h7l-5.5 4 2 7L12 16l-6.5 4 2-7L2 9h7z";
    card.innerHTML = `
      <div class="card-header">
        <div class="card-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="${path}"/></svg>
        </div>
      </div>
      <h4 class="card-title">${s.name}</h4>
      <p class="card-subtitle" style="min-height: 36px;">${s.source || "未配置"}</p>
      <div class="metric-trend">
        <span class="risk-badge ${s.status === "已接入" ? "risk-badge-low" : s.status === "部分接入" ? "risk-badge-mid" : "risk-badge-high"}">${s.status || "待接入"}</span>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderDataQuality(dq) {
  const container = el("data-quality-list");
  if (!container) return;
  clearChildren(container);
  const tables = Object.entries(dq?.tables || {});
  if (!tables.length) {
    showEmpty("data-quality-list", "暂无数据");
    return;
  }
  const total = dq?.total?.total_rows || 1;
  tables.slice(0, 8).forEach(([name, t]) => {
    const ratio = (t.real_rows || 0) / Math.max(1, total);
    const realPct = (ratio * 100).toFixed(1);
    const row = document.createElement("div");
    row.className = "list-item";
    row.innerHTML = `
      <div class="list-item-content">
        <p class="list-item-title">${t.label || name}</p>
        <p class="list-item-meta">${fmt.num(t.row_count)} 行 · 真实 ${fmt.num(t.real_rows)} (${realPct}%)</p>
        <div class="progress" style="margin-top: 6px;">
          <div class="progress-bar progress-bar-low" style="width: ${Math.min(100, ratio * 100 * 5)}%;"></div>
        </div>
      </div>
    `;
    container.appendChild(row);
  });
}

function renderRegionChart(regions, subjects) {
  const chart = ensureChart("data-region-chart");
  if (!chart) return;
  const counts = regions.map((r) => ({
    name: r.name,
    value: subjects.filter((s) => s.region_id === r.id).length,
  }));
  counts.sort((a, b) => a.value - b.value);
  chart.setOption({
    ...chartBaseOption,
    grid: { left: 100, right: 24, top: 16, bottom: 24, containLabel: true },
    tooltip: { ...chartBaseOption.tooltip, trigger: "axis" },
    xAxis: { type: "value", axisLine: { lineStyle: { color: "#E2E8F0" } }, splitLine: { lineStyle: { color: "#F1F5F9" } } },
    yAxis: {
      type: "category",
      data: counts.map((c) => c.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#475569", fontSize: 11 },
    },
    series: [{
      type: "bar",
      data: counts.map((c) => c.value),
      itemStyle: { color: "#6366F1", borderRadius: [0, 4, 4, 0] },
      barWidth: 12,
      label: { show: true, position: "right", color: "#475569", fontSize: 11 },
    }],
  });
}

function renderPublicData(samples, processed) {
  const container = el("data-public-list");
  if (!container) return;
  clearChildren(container);
  const all = [...(samples || []).map((s) => ({ ...s, type: "样例" })), ...(processed || []).map((p) => ({ ...p, type: "已处理" }))];
  if (!all.length) {
    showEmpty("data-public-list", "暂无公开数据");
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr><th>文件名</th><th>类型</th><th>数据表</th><th class="num">大小</th></tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  all.slice(0, 20).forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.filename}</td>
      <td><span class="risk-badge ${row.type === "样例" ? "risk-badge-low" : "risk-badge-mid"}">${row.type}</span></td>
      <td>${row.table || "--"}</td>
      <td class="num">${(row.size_bytes / 1024).toFixed(1)} KB</td>
    `;
    tbody.appendChild(tr);
  });
  container.appendChild(table);
}

// ============================================================================
// Page 3: 风险评估
// ============================================================================

async function initRisk() {
  try {
    // 年份
    const sel = el("risk-year-select");
    if (sel && sel.children.length === 0) {
      [2023, 2024, 2025].forEach((y) => {
        const opt = document.createElement("option");
        opt.value = y;
        opt.textContent = `${y} 年`;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", () => loadRiskHeatmap());
    }
    await loadRiskHeatmap();
    await loadRiskImportance();
    // 单县详情
    const sel3 = el("risk-region-select");
    if (sel3 && !sel3._bound) {
      sel3._bound = true;
      sel3.addEventListener("change", () => loadRegionDetail(sel3.value));
    }
    if (state.regions.length) loadRegionDetail(state.regions[0].id);
  } catch (e) {
    console.error("[risk] init 失败:", e);
  }
}

async function loadRiskHeatmap() {
  const year = Number(el("risk-year-select")?.value || 2025);
  try {
    const all = await api.warningComprehensiveAll(year);
    const details = all?.details || {};
    const container = el("risk-heatmap");
    if (!container) return;
    clearChildren(container);
    const entries = Object.entries(details);
    if (!entries.length) {
      showEmpty("risk-heatmap", "暂无风险数据");
      return;
    }
    // 确保 regions 已加载
    if (!state.regions.length) {
      try { state.regions = await api.regions(); } catch {}
    }
    const regionMap = new Map(state.regions.map((r) => [r.id, r.name]));
    entries.forEach(([rid, r]) => {
      const level = r.overall_risk || "低风险";
      const css = level.includes("高") ? "risk-high" : level.includes("中") ? "risk-mid" : "risk-low";
      const name = regionMap.get(rid) || rid;
      const cell = document.createElement("div");
      cell.className = `heatmap-cell heatmap-cell-${css}`;
      cell.innerHTML = `
        <div class="heatmap-cell-name">${name}</div>
        <div class="heatmap-cell-meta">
          <span class="risk-badge ${getRiskClass(level)}">${level}</span>
        </div>
      `;
      cell.title = `${name} · ${level}`;
      cell.addEventListener("click", () => {
        const sel3 = el("risk-region-select");
        if (sel3) {
          sel3.value = rid;
          loadRegionDetail(rid);
        }
      });
      container.appendChild(cell);
    });
  } catch (e) {
    showEmpty("risk-heatmap", "风险数据加载失败", e.message);
  }
}

async function loadRiskImportance() {
  try {
    const list = await api.modelImportance();
    const chart = ensureChart("risk-importance-chart");
    if (!chart || !list || !list.length) return;
    const items = list.slice(0, 10).reverse();
    chart.setOption({
      ...chartBaseOption,
      grid: { left: 120, right: 24, top: 16, bottom: 24, containLabel: true },
      tooltip: { ...chartBaseOption.tooltip, trigger: "axis" },
      xAxis: { type: "value", axisLine: { lineStyle: { color: "#E2E8F0" } }, splitLine: { lineStyle: { color: "#F1F5F9" } } },
      yAxis: {
        type: "category",
        data: items.map((i) => i.feature || i.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#475569", fontSize: 11 },
      },
      series: [{
        type: "bar",
        data: items.map((i) => Number(i.importance || 0)),
        itemStyle: { color: "#10B981", borderRadius: [0, 4, 4, 0] },
        barWidth: 10,
      }],
    });
  } catch (e) {
    console.warn("[risk] importance 加载失败:", e);
  }
}

async function loadRegionDetail(regionId) {
  if (!regionId) return;
  const container = el("risk-region-detail");
  if (!container) return;
  clearChildren(container);
  container.innerHTML = '<div class="empty-state"><p class="empty-state-desc">加载中…</p></div>';

  try {
    const [comp, daily] = await Promise.all([
      api.warningComprehensive(regionId, 2025),
      api.carryingCapacityDaily(regionId, 30),
    ]);
    clearChildren(container);

    const level = comp?.overall_risk || "低风险";
    const gdi = comp?.gdi || {};
    const drought = comp?.drought || {};
    const snow = comp?.snow || {};
    const dailyItems = daily?.daily || [];

    const regionName = state.regions.find((r) => r.id === regionId)?.name || regionId;

    const card = document.createElement("div");
    card.style.cssText = "display: flex; flex-direction: column; gap: 12px;";
    card.innerHTML = `
      <div class="list-item" style="border: none; padding: 0;">
        <div class="alert-icon alert-icon-info" style="width:40px;height:40px;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83"/></svg>
        </div>
        <div class="list-item-content">
          <p class="list-item-title">${regionName}</p>
          <p class="list-item-meta">综合风险: <span class="risk-badge ${getRiskClass(level)}">${level}</span></p>
        </div>
      </div>
      <div class="bento" style="grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="list-item" style="border: 1px solid var(--color-border); border-radius: 8px; padding: 10px;">
          <div class="list-item-content">
            <p class="list-item-meta">GDI 风险</p>
            <p class="list-item-title">${gdi.risk_level || "--"}</p>
          </div>
        </div>
        <div class="list-item" style="border: 1px solid var(--color-border); border-radius: 8px; padding: 10px;">
          <div class="list-item-content">
            <p class="list-item-meta">SPI 干旱</p>
            <p class="list-item-title">${fmt.round(drought.spi, 2)}</p>
          </div>
        </div>
        <div class="list-item" style="border: 1px solid var(--color-border); border-radius: 8px; padding: 10px;">
          <div class="list-item-content">
            <p class="list-item-meta">雪灾等级</p>
            <p class="list-item-title">${snow.level || "--"}</p>
          </div>
        </div>
        <div class="list-item" style="border: 1px solid var(--color-border); border-radius: 8px; padding: 10px;">
          <div class="list-item-content">
            <p class="list-item-meta">日均载畜</p>
            <p class="list-item-title">${dailyItems.length ? fmt.round(dailyItems.reduce((s, d) => s + (d.capacity || 0), 0) / dailyItems.length, 0) : "--"}</p>
          </div>
        </div>
      </div>
    `;
    container.appendChild(card);
  } catch (e) {
    showEmpty("risk-region-detail", "加载失败", e.message);
  }
}

// ============================================================================
// Page 4: 智能放贷
// ============================================================================

async function initLoan() {
  try {
    // 先确保 regions 已加载 (不依赖 overview)
    if (!state.regions.length) {
      try { state.regions = await api.regions(); } catch {}
    }
    const sel = el("loan-region-select");
    if (sel && sel.children.length === 0) {
      state.regions.forEach((r) => {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = r.name;
        sel.appendChild(opt);
      });
    }
    if (sel && !sel._bound) {
      sel._bound = true;
      sel.addEventListener("change", () => loadLoanRanking(sel.value));
    }
    if (state.regions.length) await loadLoanRanking(state.regions[0].id);
  } catch (e) {
    console.error("[loan] init 失败:", e);
  }
}

async function loadLoanRanking(regionId) {
  if (!regionId) return;
  try {
    const data = await api.cooperativeRanking(regionId, 10);
    renderLoanSummary(data);
    renderLoanTable(data);
    renderLoanRecommend(data);
  } catch (e) {
    showEmpty("loan-ranking-table", "排序数据加载失败", e.message);
  }
}

function renderLoanSummary(data) {
  const container = el("loan-summary");
  if (!container) return;
  clearChildren(container);
  const summary = data.summary || {};
  const list = data.ranking || [];
  const totalCredit = list.reduce((s, r) => s + (Number(r.ops_credit_limit_wan) || Number(r.recommend_credit) || 0), 0);
  const avgScore = list.length
    ? (list.reduce((s, r) => s + (Number(r.score_total) || Number(r.score) || 0), 0) / list.length).toFixed(1)
    : "--";
  const items = [
    { label: "县域合作社数", value: fmt.num(list.length), trend: summary.region_name || "" },
    { label: "授信总额(万元)", value: fmt.num(Math.round(totalCredit)), trend: "基于信用等级" },
    { label: "平均综合得分", value: avgScore, trend: "满分 100" },
    { label: "数据来源", value: summary.data_source || "多源融合", trend: "工商/生态/气象/经营" },
  ];
  items.forEach((it) => {
    const card = document.createElement("div");
    card.className = "card metric-card";
    card.innerHTML = `
      <div class="metric-label">${it.label}</div>
      <div class="metric-value">${it.value}</div>
      <div class="metric-trend">${it.trend}</div>
    `;
    container.appendChild(card);
  });
}

function renderLoanTable(data) {
  const container = el("loan-ranking-table");
  if (!container) return;
  clearChildren(container);
  const list = data.ranking || [];
  if (!list.length) {
    showEmpty("loan-ranking-table", "暂无合作社数据");
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>#</th><th>合作社</th><th>综合得分</th>
        <th>工商</th><th>生态</th><th>气象</th><th>经营</th>
        <th class="num">授信额度(万)</th><th>建议</th><th>验证</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  list.forEach((r, i) => {
    const tr = document.createElement("tr");
    const score = Number(r.score_total ?? r.score ?? 0);
    const rec = score >= 80 ? "重点推荐" : score >= 65 ? "可放贷" : score >= 50 ? "审慎" : "不建议";
    const badge = score >= 80 ? "risk-badge-low" : score >= 65 ? "risk-badge-low" : score >= 50 ? "risk-badge-mid" : "risk-badge-high";
    const credit = Number(r.ops_credit_limit_wan ?? r.recommend_credit ?? r.credit_value ?? 0);
    const vLevel = r.verification?.label || r.verification?.level || "未验证";
    const vBadge = vLevel.includes("双源") || vLevel.includes("★★★") ? "risk-badge-low" : vLevel.includes("单源") || vLevel.includes("★★") ? "risk-badge-mid" : "risk-badge-high";
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${r.name || r.coop_name || "--"}</strong></td>
      <td><strong>${fmt.round(score, 1)}</strong></td>
      <td>${fmt.round(r.score_biz ?? r.biz_score, 1)}</td>
      <td>${fmt.round(r.score_eco ?? r.eco_score, 1)}</td>
      <td>${fmt.round(r.score_weather ?? r.weather_score, 1)}</td>
      <td>${fmt.round(r.score_ops ?? r.ops_score, 1)}</td>
      <td class="num">${fmt.num(Math.round(credit))}</td>
      <td><span class="risk-badge ${badge}">${rec}</span></td>
      <td><span class="risk-badge ${vBadge}">${vLevel}</span></td>
    `;
    tbody.appendChild(tr);
  });
  container.appendChild(table);
}

function renderLoanRecommend(data) {
  const container = el("loan-recommend-list");
  if (!container) return;
  clearChildren(container);
  const list = (data.ranking || []).slice(0, 5);
  if (!list.length) {
    showEmpty("loan-recommend-list", "暂无建议");
    return;
  }
  list.forEach((r) => {
    const score = Number(r.score_total ?? r.score ?? 0);
    const credit = Number(r.ops_credit_limit_wan ?? r.recommend_credit ?? r.credit_value ?? 0);
    const item = document.createElement("div");
    item.className = "list-item";
    item.innerHTML = `
      <div class="alert-icon ${score >= 65 ? "alert-icon-low" : "alert-icon-mid"}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2"/></svg>
      </div>
      <div class="list-item-content">
        <p class="list-item-title">${r.name || "--"}</p>
        <p class="list-item-meta">综合 ${fmt.round(score, 1)} 分 · 授信 ${fmt.num(Math.round(credit))} 万元</p>
      </div>
    `;
    container.appendChild(item);
  });
}

// ============================================================================
// Page 5: 贷后监控
// ============================================================================

async function initMonitor() {
  try {
    // 不依赖其他页, 先确保 regions 已加载 + select 已填
    if (!state.regions.length) {
      try { state.regions = await api.regions(); } catch {}
    }
    const selNdvi = el("monitor-ndvi-region");
    const selCap = el("monitor-cap-region");
    [selNdvi, selCap].forEach((s) => {
      if (s && s.children.length === 0) {
        state.regions.forEach((r) => {
          const opt = document.createElement("option");
          opt.value = r.id;
          opt.textContent = r.name;
          s.appendChild(opt);
        });
      }
    });

    // 并行加载
    await Promise.all([
      loadMonitorSummary(),
      selNdvi && !selNdvi._bound ? Promise.resolve().then(() => {
        selNdvi._bound = true;
        selNdvi.addEventListener("change", () => loadNdviChart(selNdvi.value));
      }) : null,
      state.regions.length ? loadNdviChart(state.regions[0].id) : null,
      selCap && !selCap._bound ? Promise.resolve().then(() => {
        selCap._bound = true;
        selCap.addEventListener("change", () => loadCapacityChart(selCap.value));
      }) : null,
      state.regions.length ? loadCapacityChart(state.regions[0].id) : null,
      loadMonitorAlerts(),
    ]);
  } catch (e) {
    console.error("[monitor] init 失败:", e);
  }
}

async function loadMonitorSummary() {
  try {
    const all = await api.warningComprehensiveAll(2025);
    const container = el("monitor-summary");
    if (!container) return;
    clearChildren(container);
    const highRisk = all?.high_risk_count || 0;
    const midRisk = all?.mid_risk_count || 0;
    const lowRisk = (all?.total_regions || 0) - highRisk - midRisk;
    const items = [
      { label: "高风险县", value: fmt.num(highRisk), trend: "需重点关注", css: "risk-badge-high" },
      { label: "中风险县", value: fmt.num(midRisk), trend: "加强监测", css: "risk-badge-mid" },
      { label: "低风险县", value: fmt.num(lowRisk), trend: "正常运行", css: "risk-badge-low" },
      { label: "覆盖县域", value: fmt.num(all?.total_regions || 0), trend: "实时监控中", css: "risk-badge-low" },
    ];
    items.forEach((it) => {
      const card = document.createElement("div");
      card.className = "card metric-card";
      card.innerHTML = `
        <div class="metric-label">${it.label}</div>
        <div class="metric-value"><span class="risk-badge ${it.css}">${it.value}</span></div>
        <div class="metric-trend">${it.trend}</div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    showEmpty("monitor-summary", "预警数据加载失败", e.message);
  }
}

async function loadNdviChart(regionId) {
  if (!regionId) return;
  const chart = ensureChart("monitor-ndvi-chart");
  if (!chart) return;
  try {
    const data = await api.warningNdvi(regionId);
    const item = Array.isArray(data) ? data[0] : data;
    if (!item || !item.available) {
      chart.clear();
      return;
    }
    const latest = Number(item.latest_ndvi);
    const histMean = Number(item.historical_mean);
    const z = Number(item.z_score);
    const status = item.status || "";
    const zColor = z < -1 ? "#EF4444" : z < -0.5 ? "#F59E0B" : "#10B981";
    chart.setOption({
      ...chartBaseOption,
      tooltip: { ...chartBaseOption.tooltip },
      grid: { left: 16, right: 16, top: 24, bottom: 24, containLabel: true },
      title: {
        text: `本季 NDVI vs 5 年同期`,
        left: 0, top: 0,
        textStyle: { fontSize: 13, color: "#475569", fontWeight: 600 },
      },
      xAxis: { type: "value", min: 0, max: 1, show: false },
      yAxis: { type: "category", data: [""], show: false },
      series: [
        {
          // 历史均值背景
          type: "bar",
          data: [histMean],
          barWidth: 36,
          itemStyle: { color: "#E2E8F0", borderRadius: [4, 4, 0, 0] },
          label: {
            show: true, position: "top", color: "#94A3B8", fontSize: 10,
            formatter: `5年均值 ${histMean.toFixed(3)}`,
          },
        },
        {
          // 当前 NDVI
          type: "bar",
          data: [latest],
          barWidth: 36,
          itemStyle: { color: zColor, borderRadius: [4, 4, 0, 0] },
          label: {
            show: true, position: "inside", color: "#fff", fontSize: 13, fontWeight: 700,
            formatter: () => `${latest.toFixed(4)}`,
          },
        },
        {
          // 异常指示
          type: "bar",
          data: [Math.abs(z) > 0.5 ? Math.abs(z) * 0.1 : 0],
          barWidth: 0,
          label: {
            show: true, position: "right", color: zColor, fontSize: 11, fontWeight: 600,
            formatter: () => `Z = ${z.toFixed(2)} · ${status}`,
          },
        },
      ],
    });
  } catch (e) {
    console.warn("[ndvi chart] 失败:", e);
    chart.clear();
  }
}

async function loadCapacityChart(regionId) {
  if (!regionId) return;
  const chart = ensureChart("monitor-cap-chart");
  if (!chart) return;
  try {
    const data = await api.carryingCapacityDaily(regionId, 30);
    const items = data?.daily || [];
    if (!items.length) {
      chart.clear();
      return;
    }
    chart.setOption({
      ...chartBaseOption,
      tooltip: { ...chartBaseOption.tooltip, trigger: "axis" },
      xAxis: {
        type: "category",
        data: items.map((d) => d.date?.slice(5) || ""),
        axisLine: { lineStyle: { color: "#E2E8F0" } },
        axisLabel: { color: "#94A3B8", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#F1F5F9" } },
        axisLabel: { color: "#94A3B8", fontSize: 11 },
      },
      series: [{
        type: "line",
        data: items.map((d) => Math.round(d.capacity || 0)),
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { color: "#10B981", width: 2.5 },
        itemStyle: { color: "#10B981" },
        areaStyle: { color: "rgba(16, 185, 129, 0.10)" },
      }],
    });
  } catch (e) {
    console.warn("[capacity chart] 失败:", e);
    chart.clear();
  }
}

async function loadMonitorAlerts() {
  try {
    const all = await api.warningComprehensiveAll(2025);
    const details = all?.details || {};
    const container = el("monitor-alerts");
    if (!container) return;
    clearChildren(container);
    const entries = Object.entries(details)
      .filter(([_, r]) => r.overall_risk && r.overall_risk !== "低风险")
      .sort((a, b) => {
        const order = { 高风险: 0, 中风险: 1, 低风险: 2 };
        return (order[a[1].overall_risk] || 2) - (order[b[1].overall_risk] || 2);
      })
      .slice(0, 12);
    if (!entries.length) {
      showEmpty("monitor-alerts", "暂无风险事件", "全部 25 县运行正常");
      return;
    }
    entries.forEach(([rid, r]) => {
      const name = state.regions.find((x) => x.id === rid)?.name || rid;
      const level = r.overall_risk;
      const css = level.includes("高") ? "alert-icon-high" : "alert-icon-mid";
      const div = document.createElement("div");
      div.className = "alert";
      const reasons = [];
      if (r.gdi?.risk_level && r.gdi.risk_level !== "低风险") reasons.push(`GDI ${r.gdi.risk_level}`);
      if (r.drought?.level && r.drought.level !== "无旱") reasons.push(`旱灾 ${r.drought.level}`);
      if (r.snow?.level && r.snow.level !== "无") reasons.push(`雪灾 ${r.snow.level}`);
      if (r.ndvi_anomaly) reasons.push("NDVI 异常");
      div.innerHTML = `
        <div class="alert-icon ${css}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z"/></svg>
        </div>
        <div class="alert-content">
          <p class="alert-title">${name} <span class="risk-badge ${getRiskClass(level)}" style="margin-left:8px;">${level}</span></p>
          <p class="alert-desc">${reasons.length ? reasons.join(" · ") : "综合风险偏高，建议关注"}</p>
        </div>
      `;
      container.appendChild(div);
    });
  } catch (e) {
    showEmpty("monitor-alerts", "预警加载失败", e.message);
  }
}

// ============================================================================
// Page Init 注册
// ============================================================================

const pageInits = {
  overview: initOverview,
  data: initData,
  risk: initRisk,
  loan: initLoan,
  monitor: initMonitor,
};

// ============================================================================
// 启动
// ============================================================================

function tickClock() {
  const node = el("topbar-time");
  if (!node) return;
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  node.textContent = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

document.addEventListener("DOMContentLoaded", () => {
  // 侧边栏点击
  document.querySelectorAll(".sidebar-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => navigate(btn.dataset.page));
  });

  // 启动时钟
  tickClock();
  setInterval(tickClock, 30000);

  // 读取 hash 或 ?page= 决定初始页
  const hash = window.location.hash.replace("#", "");
  const qp = new URLSearchParams(window.location.search).get("page");
  const initialPage = (hash && PAGE_TITLES[hash]) ? hash : (qp && PAGE_TITLES[qp]) ? qp : "overview";
  if (initialPage !== "overview") {
    navigate(initialPage);
  } else {
    initOverview();
  }
  state.initialized = true;
});

// 全局错误兜底 - 不让任何 JS 错误白屏
window.addEventListener("error", (e) => {
  console.error("[global error]", e.message, e.filename, e.lineno);
});
window.addEventListener("unhandledrejection", (e) => {
  console.warn("[unhandled promise rejection]", e.reason);
});
