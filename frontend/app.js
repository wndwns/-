/**
 * 工银牧融 - 前端应用
 * ============================================================================
 * Vue 3 SPA + ECharts
 *
 * 页面:
 *   home          - 首页（全屏 Hero + 要闻 + 能力 + 数据纵览 + 赋能 + 页脚）
 *   dashboard     - 风险评估
 *   overview      - 平台概览
 *   modules       - 业务模块列表
 *   module-detail - 模块详情
 *   data          - 数据底座
 *   roadmap       - 实施路线
 *   insurance     - 保险协同
 *   supply-chain  - 产业链资金闭环
 *   green-performance - 绿色绩效
 *   livelihood    - 边疆民生
 *
 * 管理端: /admin (独立页面)
 */

const { createApp } = Vue;

// ============================================================================
// API
// ============================================================================

const api = {
  async platform() {
    const res = await fetch("/api/platform", { cache: "no-store" });
    return res.json();
  },
  async modelStatus() {
    const res = await fetch("/api/model/status");
    return res.json();
  },
  async modelPredict() {
    const res = await fetch("/api/model/predict", { method: "POST" });
    return res.json();
  },
  async modelTrain() {
    const res = await fetch("/api/model/train", { method: "POST" });
    return res.json();
  },
  async dataQuality() {
    const res = await fetch("/api/data-quality", { cache: "no-store" });
    return res.json();
  },
  async integrationsStatus() {
    const res = await fetch("/api/integrations/status", { cache: "no-store" });
    return res.json();
  },
  async amapWeather(city = "那曲市") {
    const res = await fetch(`/api/integrations/amap/weather?city=${encodeURIComponent(city)}`, { cache: "no-store" });
    return res.json();
  },
  async openMeteoNow(latitude = 31.36, longitude = 90.01) {
    const res = await fetch(`/api/integrations/open-meteo/now?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`, { cache: "no-store" });
    return res.json();
  },
  async amapMapConfig() {
    const res = await fetch("/api/integrations/amap/map-config", { cache: "no-store" });
    return res.json();
  },
  async forageSummary() {
    const res = await fetch("/api/forage-supply-demand/summary", { cache: "no-store" });
    return res.json();
  },
  async closedLoop() {
    const res = await fetch("/api/closed-loop", { cache: "no-store" });
    return res.json();
  },
  async cooperativeRanking(regionId, topN = 20) {
    const res = await fetch(`/api/cooperative-ranking/${encodeURIComponent(regionId)}?top_n=${topN}`, { cache: "no-store" });
    return res.json();
  },
  // 预警系统
  async warningAll() {
    const res = await fetch("/api/warning/comprehensive-all", { cache: "no-store" });
    return res.json();
  },
  async warningComprehensive(regionId) {
    const res = await fetch(`/api/warning/comprehensive/${encodeURIComponent(regionId)}`, { cache: "no-store" });
    return res.json();
  },
  async warningGdi() {
    const res = await fetch("/api/warning/gdi", { cache: "no-store" });
    return res.json();
  },
  async warningNdvi() {
    const res = await fetch("/api/warning/ndvi", { cache: "no-store" });
    return res.json();
  },
  async warningDisaster(regionId) {
    const res = await fetch(`/api/warning/disaster/${encodeURIComponent(regionId)}`, { cache: "no-store" });
    return res.json();
  },
  async carryingCapacityDaily(regionId, days = 30) {
    const res = await fetch(`/api/carrying-capacity/daily?region_id=${encodeURIComponent(regionId)}&days=${days}`, { cache: "no-store" });
    return res.json();
  },
  // 时空网格
  async gridStatus() {
    const res = await fetch("/api/grid/status", { cache: "no-store" });
    return res.json();
  },
  async gridAll() {
    const res = await fetch("/api/grid/all", { cache: "no-store" });
    return res.json();
  },
  async gridRegion(regionId) {
    const res = await fetch(`/api/grid/${encodeURIComponent(regionId)}`, { cache: "no-store" });
    return res.json();
  },
  async modelExplain(regionId) {
    const res = await fetch(`/api/model/explain/${encodeURIComponent(regionId)}`, { cache: "no-store" });
    return res.json();
  },
  // 保单画像
  async portfolioProfile() {
    const res = await fetch("/api/insurance-portfolio/profile", { cache: "no-store" });
    return res.json();
  },
  async portfolioFarmers() {
    const res = await fetch("/api/insurance-portfolio/farmers", { cache: "no-store" });
    return res.json();
  },
  async portfolioSynergy() {
    const res = await fetch("/api/insurance-portfolio/synergy", { cache: "no-store" });
    return res.json();
  },
  async portfolioComprehensive() {
    const res = await fetch("/api/insurance-portfolio/comprehensive-risk", { cache: "no-store" });
    return res.json();
  },
  async portfolioDueDiligence() {
    const res = await fetch("/api/insurance-portfolio/due-diligence", { cache: "no-store" });
    return res.json();
  },
  // 授信与贷后工作台
  async creditCases() {
    const res = await fetch("/api/credit-cases", { cache: "no-store" });
    return res.json();
  },
  async creditEvaluate(caseId, inputs = {}) {
    const res = await fetch("/api/credit-decision/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: caseId, inputs }),
    });
    return res;
  },
};

// ============================================================================
// 高原风景 SVG Hero 图片
// ============================================================================

function heroImage(scene) {
  const s = {
    snow:      { sky: ["#6ca6c8", "#3f789c", "#19384f"], ridge: ["#f6fbff", "#b9cad7", "#71889b"], land: ["#244937", "#69a05e"], accent: "#f3c86b", water: "#7cc6d8" },
    grassland: { sky: ["#7bc0d9", "#397f9e", "#123b52"], ridge: ["#d6e3d4", "#789f80", "#395b46"], land: ["#265c2e", "#82b953"], accent: "#e9c35f", water: "#6fb6bd" },
    river:     { sky: ["#79c4e5", "#347aab", "#14395e"], ridge: ["#d9e8df", "#6f9d8b", "#305866"], land: ["#2e633d", "#73a85b"], accent: "#f1d07a", water: "#52b6d1" },
    sunset:    { sky: ["#f1ad63", "#b95756", "#26334f"], ridge: ["#efd9b2", "#96795f", "#473943"], land: ["#314832", "#7c8a45"], accent: "#ffca73", water: "#7aa6b0" },
  }[scene] || {
    sky: ["#7bc0d9", "#397f9e", "#123b52"], ridge: ["#d6e3d4", "#789f80", "#395b46"], land: ["#265c2e", "#82b953"], accent: "#e9c35f", water: "#6fb6bd",
  };

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">
      <defs>
        <linearGradient id="sk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${s.sky[0]}"/><stop offset="48%" stop-color="${s.sky[1]}"/><stop offset="100%" stop-color="${s.sky[2]}"/></linearGradient>
        <linearGradient id="field" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${s.land[1]}"/><stop offset="100%" stop-color="${s.land[0]}"/></linearGradient>
        <linearGradient id="river" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${s.water}" stop-opacity="0.95"/><stop offset="100%" stop-color="#dff8fb" stop-opacity="0.55"/></linearGradient>
        <radialGradient id="sun" cx="74%" cy="18%" r="32%"><stop offset="0%" stop-color="${s.accent}" stop-opacity="0.86"/><stop offset="100%" stop-color="${s.accent}" stop-opacity="0"/></radialGradient>
        <filter id="soft"><feGaussianBlur stdDeviation="18"/></filter>
      </defs>
      <rect width="1600" height="900" fill="url(#sk)"/>
      <rect width="1600" height="900" fill="url(#sun)"/>
      <g opacity="0.42" fill="#fff" filter="url(#soft)">
        <ellipse cx="260" cy="128" rx="190" ry="48"/><ellipse cx="940" cy="118" rx="180" ry="44"/><ellipse cx="1320" cy="170" rx="150" ry="38"/>
      </g>
      <polygon points="0,385 140,260 255,330 380,170 520,315 645,225 790,350 910,235 1045,330 1185,165 1308,320 1440,220 1600,340 1600,900 0,900" fill="${s.ridge[0]}" opacity="0.98"/>
      <polygon points="0,455 190,315 330,400 535,270 730,430 880,350 1045,445 1248,290 1420,405 1600,325 1600,900 0,900" fill="${s.ridge[1]}" opacity="0.92"/>
      <polygon points="0,555 210,465 470,505 760,430 1040,500 1310,452 1600,512 1600,900 0,900" fill="url(#field)"/>
      <path d="M 0,690 C 250,612 440,666 615,602 C 820,532 1035,595 1220,548 C 1385,508 1505,548 1600,514 L 1600,900 L 0,900 Z" fill="${s.land[0]}" opacity="0.58"/>
      <path d="M 610,520 C 710,608 805,652 900,700 C 1040,770 1142,825 1235,900 L 970,900 C 888,824 790,760 675,710 C 560,660 462,615 352,538 Z" fill="url(#river)" opacity="${scene === 'snow' ? '0.48' : '0.78'}"/>
      <g opacity="0.34" stroke="#ffffff" stroke-width="1">
        <path d="M120,678 C350,640 520,658 730,625 C1000,584 1190,612 1460,560" fill="none"/>
        <path d="M60,736 C300,700 485,724 760,680 C1065,632 1260,662 1540,620" fill="none"/>
        <path d="M1180,130 L1260,205 L1188,285 L1110,210 Z" fill="none" opacity="0.5"/>
        <circle cx="1185" cy="206" r="5" fill="#fff"/><circle cx="1260" cy="205" r="5" fill="#fff"/><circle cx="1188" cy="285" r="5" fill="#fff"/><circle cx="1110" cy="210" r="5" fill="#fff"/>
      </g>
      <g fill="#1d2f27" opacity="0.72">
        <ellipse cx="248" cy="730" rx="42" ry="18"/><rect x="220" y="700" width="20" height="38" rx="8"/><rect x="256" y="702" width="18" height="34" rx="8"/><path d="M278 715 L325 694 L300 726 Z"/>
        <ellipse cx="360" cy="758" rx="34" ry="15"/><rect x="338" y="734" width="15" height="29" rx="7"/><rect x="366" y="735" width="14" height="28" rx="7"/><path d="M383 746 L420 728 L402 754 Z"/>
      </g>
    </svg>
  `;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function buildHeroSlides() {
  return [
    { scene: "snow", kicker: "ICBC 绿色金融", title: "牧融绿链", desc: "面向高原牧区，把气象遥感、经营台账、授信还款、产业链资金和保险协同转化为工行客户经理可执行的风险评估结论。", image: "" },
    { scene: "grassland", kicker: "授信准入", title: "让高原畜牧数据进入工行风控链路", desc: "从缺抵押、难核验、灾害风险高的牧区场景出发，形成风险筛查、证据核验和客户经理处置清单。", image: "" },
    { scene: "river", kicker: "贷后管理", title: "从放款到回款的闭环监测", desc: "围绕贷款用途、饲草采购、活体交易、物流回款和保险保障，支撑工行贷后核查和风险处置。", image: "" },
    { scene: "sunset", kicker: "银保协同", title: "绿色信贷与保险资料核验", desc: "用雪灾、草场退化、NDVI 和待核验理赔资料形成风险筛查清单，沉淀可复核的普惠服务证据。", image: "" },
  ];
}

// ============================================================================
// ECharts
// ============================================================================

function makeChart(domId) {
  const dom = document.getElementById(domId);
  if (!dom) return null;
  const inst = echarts.getInstanceByDom(dom) || echarts.init(dom, null, { renderer: "canvas" });
  setTimeout(() => inst.resize(), 0);
  if (!dom.__chartResizeObserver) {
    dom.__chartResizeObserver = new ResizeObserver(() => inst.resize());
    dom.__chartResizeObserver.observe(dom);
  }
  return inst;
}

function renderScoreChart(data) {
  const chart = makeChart("chart-score");
  if (!chart) return;
  chart.setOption({
    tooltip: { trigger: "item" },
    radar: {
      center: ["50%", "55%"], radius: "65%",
      axisName: { color: "#666", fontSize: 11 },
      indicator: data.map((d) => ({ name: d.name, max: 25 })),
      axisLine: { lineStyle: { color: "#e0e0e0" } },
      splitLine: { lineStyle: { color: "#eee" } },
      splitArea: { areaStyle: { color: ["#fafafa", "#fff"] } },
    },
    series: [{
      type: "radar",
      data: [{ value: data.map((d) => d.weight), name: "权重", areaStyle: { color: "rgba(45,125,79,0.15)" }, lineStyle: { color: "#2d7d4f", width: 2 }, itemStyle: { color: "#2d7d4f" } }],
      symbol: "circle", symbolSize: 6,
    }],
  });
}

function renderRiskChart(data) {
  const chart = makeChart("chart-risk");
  if (!chart) return;
  const names = data.map((d) => d.region_name.replace("市", ""));
  const scores = data.map((d) => d.score);
  const colors = scores.map((s) => (s >= 70 ? "#d44a4a" : s >= 55 ? "#d98a3a" : "#2d7d4f"));
  chart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: "3%", right: "6%", bottom: "3%", top: "10%", containLabel: true },
    xAxis: { type: "category", data: names, axisLabel: { color: "#666", fontSize: 12 }, axisLine: { lineStyle: { color: "#e0e0e0" } } },
    yAxis: { type: "value", name: "风险评分", min: 0, max: 100, axisLabel: { color: "#999" }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
    series: [{
      type: "bar", data: scores.map((v, i) => ({ value: v, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })), barWidth: "45%",
      label: { show: true, position: "top", color: "#333", fontSize: 13, fontWeight: 700 },
      markLine: { silent: true, data: [
        { yAxis: 70, lineStyle: { color: "#d44a4a", type: "dashed", width: 1 }, label: { formatter: "高风险线", color: "#d44a4a", fontSize: 10 } },
        { yAxis: 50, lineStyle: { color: "#d98a3a", type: "dashed", width: 1 }, label: { formatter: "中风险线", color: "#d98a3a", fontSize: 10 } },
      ]},
    }],
  });
}

function renderDashboardTrend(rows) {
  const chart = makeChart("chart-dashboard-trend");
  if (!chart) return;
  renderTrendChart(chart, rows);
}

function renderTrendChart(chart, rows) {
  const months = rows.map((r) => r.month);
  chart.setOption({
    color: ["#2d7d4f", "#d98a3a"],
    tooltip: { trigger: "axis" },
    grid: { left: 42, right: 20, top: 30, bottom: 38 },
    xAxis: {
      type: "category",
      data: months,
      boundaryGap: false,
      axisLabel: { color: "#7a857d", fontSize: 11 },
      axisLine: { lineStyle: { color: "#dfe8e2" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: "#7a857d" },
      splitLine: { lineStyle: { color: "#edf3ef" } },
    },
    series: [{
      name: "平均风险",
      type: "line",
      smooth: true,
      showSymbol: false,
      areaStyle: { color: "rgba(45,125,79,0.10)" },
      lineStyle: { width: 3 },
      data: rows.map((r) => r.avg),
    }, {
      name: "最高风险",
      type: "line",
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, type: "dashed" },
      data: rows.map((r) => r.max),
    }],
  }, true);
}

function renderDashboardDrivers(rows) {
  const chart = makeChart("chart-dashboard-driver");
  if (!chart) return;
  chart.setOption({
    color: ["#2d7d4f", "#4a9d6a", "#d98a3a", "#3a8a9a"],
    tooltip: { trigger: "item" },
    radar: {
      center: ["50%", "52%"],
      radius: "66%",
      indicator: rows.map((r) => ({ name: r.name, max: 40 })),
      axisName: { color: "#617066", fontSize: 11 },
      axisLine: { lineStyle: { color: "#dfe8e2" } },
      splitLine: { lineStyle: { color: "#edf3ef" } },
      splitArea: { areaStyle: { color: ["#fbfdfb", "#fff"] } },
    },
    series: [{
      type: "radar",
      data: [{
        value: rows.map((r) => r.value),
        areaStyle: { color: "rgba(45,125,79,0.16)" },
        lineStyle: { color: "#2d7d4f", width: 2 },
        itemStyle: { color: "#2d7d4f" },
      }],
      symbolSize: 4,
    }],
  });
}

function renderDashboardQuality(rows) {
  const chart = makeChart("chart-dashboard-quality");
  if (!chart) return;
  renderQualityChart(chart, rows);
}

function renderPublicRiskTrend(rows) {
  const chart = makeChart("chart-public-risk-trend");
  if (!chart) return;
  renderTrendChart(chart, rows);
}

function renderPublicRadar(row) {
  const chart = makeChart("chart-public-radar");
  if (!chart) return;
  if (!row) {
    chart.clear();
    return;
  }
  const dims = row.dim_scores || [];
  chart.setOption({
    color: ["#2d7d4f"],
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        const lines = dims.map((item, idx) => `${item.name}: ${params.value[idx]}`);
        return `${row.region_name}<br />${lines.join("<br />")}`;
      },
    },
    radar: {
      center: ["50%", "52%"],
      radius: "67%",
      indicator: dims.map((item) => ({ name: item.name, max: 100 })),
      axisName: { color: "#52625a", fontSize: 11 },
      axisLine: { lineStyle: { color: "#d9e4df" } },
      splitLine: { lineStyle: { color: "#e8efeb" } },
      splitArea: { areaStyle: { color: ["#fbfdfb", "#ffffff"] } },
    },
    series: [{
      name: "6维风险子分",
      type: "radar",
      data: [{
        value: dims.map((item) => item.value),
        name: row.region_name,
        areaStyle: { color: "rgba(45,125,79,0.16)" },
        lineStyle: { color: "#2d7d4f", width: 2 },
        itemStyle: { color: "#2d7d4f" },
      }],
      symbol: "circle",
      symbolSize: 4,
    }],
  }, true);
}

function renderDataQuality(rows) {
  const chart = makeChart("chart-data-quality");
  if (!chart) return;
  renderQualityChart(chart, rows);
}

function renderOverviewMix(rows) {
  const chart = makeChart("chart-overview-mix");
  if (!chart) return;
  chart.setOption({
    color: ["#2d7d4f", "#d98a3a", "#c8ced0"],
    tooltip: { trigger: "item" },
    legend: { bottom: 8, left: "center", textStyle: { fontSize: 11, color: "#637067" } },
    series: [{
      name: "数据结构",
      type: "pie",
      radius: ["48%", "72%"],
      center: ["50%", "44%"],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: "#fff", borderWidth: 3 },
      label: { color: "#26332b", formatter: "{b}\n{d}%" },
      data: [
        { name: "真实数据", value: rows?.real_rows || 0 },
        { name: "样例数据", value: rows?.sample_rows || 0 },
        { name: "模拟数据", value: rows?.simulated_rows || 0 },
      ],
    }],
  });
}

function renderOverviewModel(rows) {
  const chart = makeChart("chart-overview-model");
  if (!chart) return;
  const data = rows.slice(0, 8).reverse();
  chart.setOption({
    color: ["#2d7d4f"],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 92, right: 18, top: 24, bottom: 22 },
    xAxis: {
      type: "value",
      max: 100,
      axisLabel: { color: "#7a857d" },
      splitLine: { lineStyle: { color: "#edf3ef" } },
    },
    yAxis: {
      type: "category",
      data: data.map((row) => row.region_name.replace(/.*市/, "")),
      axisLabel: { color: "#536158", fontSize: 11 },
      axisLine: { lineStyle: { color: "#dfe8e2" } },
    },
    series: [{
      type: "bar",
      barWidth: 14,
      data: data.map((row) => ({
        value: Number(row.predicted_score) || 0,
        itemStyle: { borderRadius: [0, 4, 4, 0], color: Number(row.predicted_score) >= 70 ? "#d44a4a" : Number(row.predicted_score) >= 55 ? "#d98a3a" : "#2d7d4f" },
      })),
    }],
  });
}

function renderQualityChart(chart, rows) {
  const labels = rows.map((r) => r.short_label || r.dataset || "-");
  const rotate = labels.length > 8 ? 32 : 0;
  chart.setOption({
    color: ["#2d7d4f", "#d98a3a"],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, right: 6, textStyle: { fontSize: 11, color: "#6c766f" } },
    grid: { left: 48, right: 20, top: 40, bottom: rotate ? 78 : 42 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: {
        color: "#7a857d",
        fontSize: 10,
        interval: 0,
        rotate,
        width: 72,
        overflow: "truncate",
      },
      axisLine: { lineStyle: { color: "#dfe8e2" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#7a857d", fontSize: 11 },
      splitLine: { lineStyle: { color: "#edf3ef" } },
    },
    series: [{
      name: "真实",
      type: "bar",
      stack: "total",
      barWidth: 16,
      data: rows.map((r) => r.real_rows || 0),
    }, {
      name: "样例",
      type: "bar",
      stack: "total",
      barWidth: 16,
      data: rows.map((r) => r.sample_rows || 0),
    }],
  });
}

function summarizeMonthlyRows(rows, dateField, fields) {
  const groups = new Map();
  (rows || []).forEach((row) => {
    const month = String(row[dateField] || "").slice(0, 7);
    if (!month) return;
    if (!groups.has(month)) groups.set(month, []);
    groups.get(month).push(row);
  });
  return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b)).map(([month, items]) => {
    const out = { month, count: items.length };
    fields.forEach((field) => {
      const vals = items.map((item) => Number(String(item[field] ?? "").replace("%", ""))).filter((n) => Number.isFinite(n));
      out[field] = vals.length ? Number(avg(vals).toFixed(2)) : 0;
    });
    return out;
  });
}

function renderWeatherTrend(rows) {
  const chart = makeChart("chart-weather-trend");
  if (!chart) return;
  const data = summarizeMonthlyRows(rows, "observed_at", ["temperature_c", "precipitation_mm_24h"]).slice(-24);
  chart.setOption({
    color: ["#2d7d4f", "#3a8a9a"],
    tooltip: { trigger: "axis" },
    legend: { top: 6, right: 16, itemGap: 16, textStyle: { fontSize: 12, color: "#637067" } },
    grid: { left: 52, right: 52, top: 50, bottom: 42 },
    xAxis: { type: "category", data: data.map((r) => r.month), axisLabel: { color: "#7a857d", fontSize: 10, interval: 1 }, axisLine: { lineStyle: { color: "#dfe8e2" } } },
    yAxis: [
      { type: "value", name: "温度", nameGap: 18, axisLabel: { color: "#7a857d", fontSize: 11 }, splitLine: { lineStyle: { color: "#edf3ef" } } },
      { type: "value", name: "降水", nameGap: 18, axisLabel: { color: "#7a857d", fontSize: 11 }, splitLine: { show: false } },
    ],
    series: [
      { name: "平均温度", type: "line", smooth: true, showSymbol: false, data: data.map((r) => r.temperature_c) },
      { name: "降水均值", type: "bar", yAxisIndex: 1, barWidth: 10, data: data.map((r) => r.precipitation_mm_24h) },
    ],
  });
}

function renderRemoteTrend(rows) {
  const chart = makeChart("chart-remote-trend");
  if (!chart) return;
  const data = summarizeMonthlyRows(rows, "scene_date", ["ndvi", "snow_cover"]).slice(-24);
  chart.setOption({
    color: ["#4a9d6a", "#3a8a9a"],
    tooltip: { trigger: "axis" },
    legend: { top: 6, right: 16, itemGap: 16, textStyle: { fontSize: 12, color: "#637067" } },
    grid: { left: 52, right: 52, top: 50, bottom: 42 },
    xAxis: { type: "category", data: data.map((r) => r.month), axisLabel: { color: "#7a857d", fontSize: 10, interval: 1 }, axisLine: { lineStyle: { color: "#dfe8e2" } } },
    yAxis: [
      { type: "value", name: "NDVI", min: 0, max: 1, nameGap: 18, axisLabel: { color: "#7a857d", fontSize: 11 }, splitLine: { lineStyle: { color: "#edf3ef" } } },
      { type: "value", name: "积雪%", nameGap: 18, axisLabel: { color: "#7a857d", fontSize: 11 }, splitLine: { show: false } },
    ],
    series: [
      { name: "NDVI 均值", type: "line", smooth: true, showSymbol: false, areaStyle: { color: "rgba(74,157,106,0.10)" }, data: data.map((r) => r.ndvi) },
      { name: "积雪覆盖", type: "line", yAxisIndex: 1, smooth: true, showSymbol: false, data: data.map((r) => r.snow_cover) },
    ],
  });
}

function avg(nums) {
  if (!nums.length) return 0;
  return nums.reduce((sum, n) => sum + n, 0) / nums.length;
}

// ============================================================================
// Vue App
// ============================================================================

createApp({
  data() {
    return {
      loading: true,
      data: null,
      page: "dashboard",
      selectedModule: null,
      dataTab: "weather",
      scrolled: false,
      // 导航分组（14 个逻辑页面全部保留）
      navGroups: [
        {
          label: "核心业务",
          items: [
            { page: "dashboard", name: "授信与贷后工作台" },
            { page: "supply-chain", name: "产业链" },
            { page: "insurance", name: "保险协同" },
            { page: "green-performance", name: "绿色绩效" },
            { page: "livelihood", name: "边疆民生" },
          ],
        },
        {
          label: "生态证据",
          items: [
            { page: "data", name: "数据底座" },
            { page: "disaster-forecast", name: "灾害预测" },
          ],
        },
        {
          label: "辅助能力",
          items: [
            { page: "home", name: "首页" },
            { page: "overview", name: "平台概览" },
            { page: "modules", name: "业务模块" },
            { page: "roadmap", name: "实施路线" },
            { page: "cooperative-ranking", name: "合作社排序" },
            { page: "insurance-portfolio", name: "资产/保险资料核验" },
          ],
        },
      ],

      // Hero
      heroSlides: buildHeroSlides(),
      heroIndex: 0,
      heroTimer: null,

      // 模型
      modelStatus: {},
      modelPrediction: null,
      modelTraining: false,
      dataQuality: null,
      closedLoop: {},
      selectedRegionId: "",
      assessmentMode: "region",
      selectedAssessmentKey: "",
      assessmentSearch: "",
      integrations: null,
      liveWeather: null,
      mapConfig: null,
      amapReady: false,
      amapError: "",
      evidenceMap: null,
      evidenceMapMarkers: [],
      evidenceMapLayers: {},
      selectedMapRegionId: "",
      selectedMapLayer: "satellite",
      selectedMapWeather: null,
      mapWeatherLoading: false,
      mapWeatherError: "",
      mapWeatherTimer: null,
      liveWeatherTimer: null,
      weatherRefreshMs: 10 * 60 * 1000,
      mapWeatherRequestId: 0,
      forageSummary: null,
      selectedPublicRiskRegionId: "",
      // 合作社排序
      coopSelectedRegion: "",
      coopTopN: 20,
      coopLoading: false,
      coopRegions: [],
      coopRanking: [],
      coopSummary: null,
      coopDataQuality: "--",
      coopDetailOpen: null,
      coopDetailRow: null,
      // 保单画像
      portfolioProfile: null,
      portfolioFarmers: [],
      portfolioSynergy: null,
      portfolioComprehensive: null,
      portfolioDueDiligence: null,
      portfolioLoading: false,
      // 灾害预测
      disasterInput: "",
      disasterRegions: [],
      disasterResult: null,
      disasterLoading: false,
      disasterError: "",
      disasterChartRef: null,
      // 预警系统
      warningData: null,
      warningLoading: false,
      warningSelectedRegion: "",
      dailyCapacity: null,
      dailyCapacityLoading: false,
      // 时空网格
      gridData: null,
      gridLoading: false,
      gridSelectedRegion: "",
      gridAgeFilter: "adult",
      gridGrassFilter: "alpine_steppe",
      // SHAP 风险解释报告
      explainData: null,
      explainLoading: false,
      explainSelectedRegion: "",
      // 授信与贷后工作台
      creditCases: [],
      creditCaseId: "",
      creditEvaluating: false,
      creditResult: null,
      creditError: "",
      creditMonthTab: "snow",
      creditUserModified: false,
      creditForm: {
        total_mu: 42000,
        own_funds_wan: 35,
        product_cap_wan: 120,
        dscr_threshold: 1.2,
      },
    };
  },

  computed: {
    pageTitle() {
      const m = {
        home: "首页",
        dashboard: "授信与贷后工作台",
        overview: "平台概览",
        modules: "业务模块",
        "module-detail": "模块详情",
        data: "数据底座",
        roadmap: "实施路线",
        insurance: "保险协同",
        "supply-chain": "产业链",
        "green-performance": "绿色绩效",
        livelihood: "边疆民生",
        "cooperative-ranking": "合作社排序",
        "insurance-portfolio": "资产/保险资料核验",
        "disaster-forecast": "灾害预测",
      };
      return m[this.page] || "牧融绿链";
    },
    activeAlertCount() {
      if (!this.data) return 0;
      return this.data.alerts.filter((a) => a.level === "高风险" || a.level === "中风险").length;
    },
    // ---- 授信与贷后工作台 ----
    creditScenarioCards() {
      if (!this.creditResult || this.creditResult.status === "blocked" || !this.creditResult.qualified_demand) return [];
      const r = this.creditResult;
      return [
        {
          key: "baseline",
          cls: "cw-baseline",
          label: "基准情景 · 合格融资需求",
          rows: [
            { label: "必要采购总额", value: this.formatWan(r.qualified_demand.purchase_total_yuan) + " 万元" },
            { label: "已确认自有资金", value: this.formatWan(r.qualified_demand.own_funds_yuan) + " 万元" },
            { label: "合格融资需求", value: this.formatWan(r.qualified_demand.qualified_demand_yuan) + " 万元" },
            { label: "必要外购饲草", value: this.formatKg(r.monthly_scenarios.baseline.total_purchase_kg) + " 千克" },
          ],
          note: "基准情景回答“合理经营需要多少资金”。",
        },
        {
          key: "snow",
          cls: "cw-snow",
          label: "标准雪灾 · 偿债支持上限",
          rows: [
            { label: "可用于偿债经营现金", value: this.formatMoney(r.limits.snow_available_cash_yuan) + " 元" },
            { label: "偿债支持上限", value: this.formatWan(r.limits.snow_support_limit_yuan) + " 万元" },
            { label: "最低外部融资需求", value: this.formatWan(r.qualified_demand.min_external_financing_yuan) + " 万元" },
            { label: "可行性", value: r.status === "feasible" ? "可行" : r.status === "infeasible" ? "暂不可行" : "—" },
          ],
          note: "标准雪灾回答“在可解释压力下最多能承受多少新增债务”。",
        },
        {
          key: "composite",
          cls: "cw-comp",
          label: "复合极端 · 脆弱性提示",
          rows: [
            { label: "采购成本", value: this.formatMoney(r.composite.purchase_cost_yuan) + " 元" },
            { label: "建议金额下 DSCR", value: Number(r.composite.dscr).toFixed(4) },
            { label: r.composite.min_cash_month + " 月末现金", value: this.formatMoney(r.composite.min_cash_yuan) + " 元" },
            { label: "现金缺口", value: this.formatMoney(r.composite.min_cash_gap_yuan) + " 元" },
          ],
          note: "复合极端只揭示脆弱性和核查建议，不生成第二个推荐金额。",
        },
      ];
    },
    creditMonthlyRows() {
      if (!this.creditResult || this.creditResult.status === "blocked") return [];
      return this.creditResult.monthly_cashflow[this.creditMonthTab] || [];
    },
    creditStorageRows() {
      if (!this.creditResult || this.creditResult.status === "blocked") return [];
      const plan = this.creditResult.monthly_scenarios[this.creditMonthTab];
      return plan && plan.rows ? plan.rows : [];
    },
    creditMinReserve() {
      if (this.creditResult && this.creditResult.snow_cashflow && this.creditResult.snow_cashflow.minimum_cash_reserve_yuan) {
        return Number(this.creditResult.snow_cashflow.minimum_cash_reserve_yuan);
      }
      return 150000;
    },
    creditCheckActions() {
      if (!this.creditResult || this.creditResult.status === "blocked") return [];
      const r = this.creditResult;
      const actions = [];
      if (r.status === "infeasible") {
        actions.push("核验采购前可用的自有资金、补贴、供应商账期或采购锁价，确认后可重新测算");
      }
      actions.push(`在 ${r.snow_cashflow.min_cash_month} 重点核验现金与回款，标准雪灾最低现金 ${this.formatMoney(r.snow_cashflow.min_cash_yuan)} 元`);
      if (r.composite && r.composite.vulnerable) {
        actions.push(`复合极端 ${r.composite.min_cash_month} 现金缺口约 ${this.formatMoney(r.composite.min_cash_gap_yuan)} 元，核验应急储草、采购锁价、回款提前或非贷款应急资金`);
      }
      actions.push("核验草场与储草月度守恒记录，确认不存在重复计量");
      actions.push("核验资金用途与回款来源，由客户经理决定后续核查动作");
      return actions;
    },
    highRiskCount() {
      if (!this.data) return 0;
      return this.data.regions.filter((r) => r.risk_level === "高").length;
    },
    relatedModules() {
      if (!this.selectedModule || !this.data) return [];
      return this.data.modules.filter((m) => m.code !== this.selectedModule.code);
    },
    businessModules() {
      const current = this.data?.modules || [];
      const byCode = new Map(current.map((item) => [item.code, item]));
      const preferred = [
        { code: "eco-monitor", name: "高原生态与气候风险监测" },
        { code: "grass-balance", name: "草畜平衡与绿色养殖管理" },
        { code: "supply-chain", name: "畜牧产业链数字化协同" },
        { code: "green-finance", name: "银行绿色金融风控" },
        { code: "insurance", name: "保险风险减量与理赔协同" },
        { code: "green-perf", name: "生态价值与绿色绩效评价" },
        { code: "livelihood", name: "边疆民生与治理辅助" },
      ];
      return preferred.map((item) => {
        const source = byCode.get(item.code) || {};
        return {
          ...source,
          ...item,
          value: source.value || this.moduleFallbackValue(item.code),
          features: source.features || this.moduleFallbackFeatures(item.code),
        };
      });
    },
    regionalRiskRows() {
      const rows = this.modelPrediction?.predictions || [];
      const groups = new Map();
      rows.forEach((row) => {
        if (!row.region_id) return;
        if (!groups.has(row.region_id)) groups.set(row.region_id, []);
        groups.get(row.region_id).push(row);
      });
      return Array.from(groups.entries()).map(([region_id, items]) => {
        const sorted = [...items].sort((a, b) => String(a.month || "").localeCompare(String(b.month || "")));
        const latest = sorted[sorted.length - 1] || {};
        const scores = sorted.map((item) => Number(item.predicted_score) || 0);
        const driverParts = [
          { key: "weather", name: "气象", value: latest.drivers?.weather?.score_part || 0, detail: latest.drivers?.weather?.detail || "" },
          { key: "remote", name: "遥感", value: latest.drivers?.remote?.score_part || 0, detail: latest.drivers?.remote?.detail || "" },
          { key: "business", name: "经营", value: latest.drivers?.business?.score_part || 0, detail: latest.drivers?.business?.detail || "" },
          { key: "finance", name: "金融", value: latest.drivers?.finance?.score_part || 0, detail: latest.drivers?.finance?.detail || "" },
        ];
        const primary = [...driverParts].sort((a, b) => b.value - a.value)[0];
        return {
          region_id,
          region_name: latest.region_name || region_id,
          month: latest.month || "-",
          predicted_score: Number(latest.predicted_score || 0).toFixed(1),
          predicted_level: latest.predicted_level || "低",
          avg_score: avg(scores).toFixed(1),
          max_score: Math.max(...scores, 0).toFixed(1),
          primary_driver: primary ? primary.name : "-",
          driver_details: driverParts,
          history: sorted,
        };
      }).sort((a, b) => Number(b.predicted_score) - Number(a.predicted_score));
    },
    topRiskRegions() {
      return this.regionalRiskRows.slice(0, 10);
    },
    selectedRegion() {
      return this.regionalRiskRows.find((row) => row.region_id === this.selectedRegionId) || this.regionalRiskRows[0] || null;
    },
    mapRegions() {
      const riskByRegion = new Map(this.regionalRiskRows.map((row) => [row.region_id, row]));
      return (this.data?.regions || [])
        .map((region) => {
          const lng = Number(region.longitude);
          const lat = Number(region.latitude);
          if (!Number.isFinite(lng) || !Number.isFinite(lat) || !lng || !lat) return null;
          const weather = this.latestRowByRegion(this.data?.weather || [], region.id, "observed_at");
          const remote = this.latestRowByRegion(this.data?.remote_sensing || [], region.id, "scene_date");
          const risk = riskByRegion.get(region.id) || {};
          return {
            ...region,
            lng,
            lat,
            altitude_value: Number(region.altitude || 0),
            risk_score: Number(risk.predicted_score || 0),
            risk_level: this.levelForScore(Number(risk.predicted_score || 0)),
            primary_driver: risk.primary_driver || "-",
            weather,
            remote,
          };
        })
        .filter(Boolean);
    },
    selectedMapRegion() {
      return this.mapRegions.find((row) => row.id === this.selectedMapRegionId) || this.mapRegions[0] || null;
    },
    selectedMapEvidence() {
      const region = this.selectedMapRegion;
      if (!region) return [];
      const weather = region.weather || {};
      const remote = region.remote || {};
      return [
        { label: "县域", value: region.name, note: `${region.longitude}, ${region.latitude}` },
        { label: "海拔", value: region.altitude ? `${region.altitude}m` : "-", note: region.pasture_type || "高原牧区" },
        { label: "实时天气", value: this.currentWeatherText, note: this.mapWeatherLoading ? "正在刷新实时天气" : (this.mapWeatherError || this.selectedMapWeather?.reporttime || this.selectedMapWeather?.obsTime || this.selectedMapWeather?.provider || "高德/Open-Meteo API") },
        { label: "本地气象", value: weather.observed_at ? `${weather.temperature_c}℃ / 雪深${weather.snow_depth_cm}cm` : "-", note: weather.observed_at || "CMFD 月度样本" },
        { label: "遥感 NDVI", value: remote.ndvi ?? "-", note: remote.scene_date ? `${remote.scene_date} / 积雪${remote.snow_cover}` : "MODIS/TPDC" },
        { label: "风险评分", value: region.risk_score ? region.risk_score.toFixed(1) : "-", note: `${region.risk_level} / ${region.primary_driver}` },
      ];
    },
    currentWeatherText() {
      const row = this.selectedMapWeather;
      if (!row) return this.mapWeatherLoading ? "加载中" : "待获取";
      if (row.provider === "CMFD 本地数据") return `本地气象 ${row.temperature ?? "-"}℃`;
      const extra = row.humidity ? ` / 湿度${row.humidity}%` : "";
      return `${row.weather || row.text || "-"} ${row.temperature || row.temp || "-"}℃${extra}`;
    },
    amapConfigured() {
      return Boolean(this.mapConfig?.configured && this.mapConfig?.key);
    },
    riskTrendRows() {
      const rows = this.modelPrediction?.predictions || [];
      const groups = new Map();
      rows.forEach((row) => {
        const month = row.month || "-";
        if (!groups.has(month)) groups.set(month, []);
        groups.get(month).push(Number(row.predicted_score) || 0);
      });
      return Array.from(groups.entries())
        .sort(([a], [b]) => String(a).localeCompare(String(b)))
        .map(([month, scores]) => ({
          month,
          avg: Number(avg(scores).toFixed(1)),
          max: Number(Math.max(...scores, 0).toFixed(1)),
        }));
    },
    qualityRows() {
      const tables = this.dataQuality?.tables || {};
      const labelMap = {
        weather_data: "气象",
        remote_sensing_data: "遥感",
        forage_supply_demand: "饲草",
        business_subjects: "经营",
        finance_credit: "金融",
        risk_event_labels: "标签",
        insurance_claims: "理赔",
        supply_chain_orders: "订单",
        supply_chain_payments: "支付",
        post_loan_workflow: "贷后",
        green_performance_metrics: "绩效",
      };
      return Object.entries(tables).map(([key, val]) => ({
        key,
        label: val.label || key,
        short_label: labelMap[key] || key,
        row_count: val.row_count || 0,
        real_rows: val.real_rows || 0,
        sample_rows: val.sample_rows || 0,
        warnings: val.quality_warnings || [],
      }));
    },
    qualityWarnings() {
      const warningSet = new Set();
      (this.modelStatus.data_quality_warnings || []).forEach((w) => warningSet.add(w));
      this.qualityRows.forEach((row) => row.warnings.forEach((w) => warningSet.add(`${row.short_label}: ${w}`)));
      return Array.from(warningSet).slice(0, 6);
    },
    opsTasks() {
      const tasks = [];
      if ((this.modelStatus.real_data_ratio || 0) < 0.9) {
        tasks.push({
          level: "warn",
          title: "补齐真实数据占比",
          desc: `当前真实数据占比 ${this.percent(this.modelStatus.real_data_ratio || 0)}，优先替换样例经营与金融数据。`,
          action: "数据底座",
          page: "data",
        });
      }
      if (this.qualityWarnings.length) {
        tasks.push({
          level: "warn",
          title: "处理数据质量告警",
          desc: this.qualityWarnings[0],
          action: "查看缺口",
          page: "data",
        });
      }
      if (!this.integrations?.amap_weather?.configured) {
        tasks.push({
          level: "info",
          title: "配置实时天气接口",
          desc: "接入高德 Web 服务 Key 后，评估工作台可读取实时天气状态。",
          action: "管理端",
          href: "/admin",
        });
      }
      if ((this.dataAssetCards.find((c) => c.key === "risk_event_labels")?.row_count || 0) === 0) {
        tasks.push({
          level: "danger",
          title: "接入真实风险标签",
          desc: "当前仍是规则弱标签，缺少灾害、理赔或逾期标签，模型不能作为监督预测结论。",
          action: "导入标签",
          page: "data",
        });
      }
      if (!tasks.length) {
        tasks.push({
          level: "ok",
          title: "系统状态可用",
          desc: "核心气象、遥感与模型样本已就绪，可进入县域风险排查。",
          action: "查看风险",
          page: "dashboard",
        });
      }
      return tasks.slice(0, 4);
    },
    icbcRoleCards() {
      return [
        { step: "01", title: "授信准入", desc: "客户经理选择县域或主体，查看风险筛查结果、来源证据和待核验字段。" },
        { step: "02", title: "资金用途核验", desc: "贷款资金绑定饲草采购、活体交易和物流回款，减少资金空转。" },
        { step: "03", title: "贷后预警", desc: "NDVI、积雪、回款、逾期和保险资料异常进入客户经理人工核查队列。" },
        { step: "04", title: "银保协同", desc: "承保、出险、查勘、理赔结果回流贷后策略，形成风险缓释闭环。" },
      ];
    },
    systemHealthItems() {
      return [
        {
          label: "数据闭环",
          value: this.percent(this.modelStatus.real_data_ratio || 0),
          state: (this.modelStatus.real_data_ratio || 0) >= 0.9 ? "ok" : "warn",
        },
        {
          label: "模型状态",
          value: this.modelStatus.model_type || "rule",
          state: this.modelStatus.model_type === "ml_hybrid" ? "ok" : "warn",
        },
        {
          label: "风险标签",
          value: (this.dataAssetCards.find((c) => c.key === "risk_event_labels")?.row_count || 0) > 0 ? "已接入" : "弱标签",
          state: (this.dataAssetCards.find((c) => c.key === "risk_event_labels")?.row_count || 0) > 0 ? "ok" : "danger",
        },
        {
          label: "天气接口",
          value: this.integrations?.open_meteo?.configured ? "开放天气" : (this.integrations?.amap_weather?.configured ? "已配置" : "本地兜底"),
          state: this.integrations?.open_meteo?.configured || this.integrations?.amap_weather?.configured ? "ok" : "warn",
        },
      ];
    },
    highPriorityRegions() {
      return this.regionalRiskRows
        .filter((row) => ["高", "高风险", "中", "中风险"].includes(row.predicted_level) || Number(row.predicted_score) >= 60)
        .slice(0, 4);
    },
    opsSummary() {
      return {
        warning_count: this.qualityWarnings.length,
        high_region_count: this.highPriorityRegions.length,
        task_count: this.opsTasks.filter((t) => t.level !== "ok").length,
        last_month: this.riskTrendRows[this.riskTrendRows.length - 1]?.month || "-",
      };
    },
    creditPortfolio() {
      const rows = this.data?.finance || [];
      const line = rows.reduce((sum, row) => sum + (Number(row.credit_line) || 0), 0);
      const used = rows.reduce((sum, row) => sum + (Number(row.used_credit) || 0), 0);
      const overdue = rows.reduce((sum, row) => sum + (Number(row.overdue_times) || 0), 0);
      const watch = rows.filter((row) => row.repayment_status && row.repayment_status !== "正常").length;
      return {
        line,
        used,
        available: Math.max(line - used, 0),
        usage_rate: line ? used / line : 0,
        overdue,
        watch,
        count: rows.length,
      };
    },
    riskPoolRows() {
      return this.regionalRiskRows.slice(0, 12).map((row, idx) => ({
        ...row,
        rank: idx + 1,
        exposure: this.creditPortfolio.count ? Math.round((this.creditPortfolio.used / this.creditPortfolio.count) * (1 + Number(row.predicted_score) / 200)) : 0,
        action: Number(row.predicted_score) >= 65 ? "冻结增额" : Number(row.predicted_score) >= 55 ? "人工复核" : "持续监测",
      }));
    },
    allRiskPoolRows() {
      return this.regionalRiskRows.map((row, idx) => ({
        ...row,
        rank: idx + 1,
        exposure: this.creditPortfolio.count ? Math.round((this.creditPortfolio.used / Math.max(this.creditPortfolio.count, 1)) * (1 + Number(row.predicted_score) / 200)) : 0,
        action: this.decisionForScore(Number(row.predicted_score || 0)),
      }));
    },
    creditSubjectRows() {
      const financeByName = new Map((this.data?.finance || []).map((row) => [row.subject_name, row]));
      return (this.data?.subjects || []).map((subject) => {
        const finance = financeByName.get(subject.name) || {};
        const regionRisk = this.regionalRiskRows.find((row) => row.region_id === subject.region_id) || {};
        const needsVerification = ["real_insurance", "asset_register_reference"].includes(subject.data_source) || ["real_insurance", "asset_register_reference"].includes(finance.data_source);
        const line = Number(finance.credit_line) || Number(subject.credit_value) || 0;
        const used = Number(finance.used_credit) || Number(subject.credit_value) || 0;
        const usage = line ? used / line : 0;
        const score = Number(subject.score) || 0;
        const riskScore = needsVerification ? null : Math.max(0, Math.min(100, 100 - score + usage * 35 + (Number(finance.overdue_times) || 0) * 12 + Number(regionRisk.predicted_score || 0) * 0.12));
        return {
          key: subject.name,
          name: subject.name,
          region_id: subject.region_id || "",
          region: subject.region_name || subject.region || "-",
          type: subject.subject_type || subject.type || "-",
          line,
          used,
          usage,
          score,
          insurance: subject.insurance_coverage || "-",
          repayment: finance.repayment_status || "-",
          overdue: Number(finance.overdue_times) || 0,
          status: subject.status || "-",
          customer_manager: subject.customer_manager || "",
          admission_stage: subject.admission_stage || "",
          loan_purpose: finance.loan_purpose || subject.loan_use || "",
          post_loan_action: finance.post_loan_action || "",
          insurance_status: finance.insurance_status || "",
          sample_note: subject.sample_note || finance.sample_note || "",
          needsVerification,
          is_sample: subject.is_sample === true || finance.is_sample === true || subject.data_source === "sample" || finance.data_source === "sample",
          riskScore: riskScore === null ? null : Number(riskScore.toFixed(1)),
          regionRiskScore: Number(regionRisk.predicted_score || 0),
          regionRiskDriver: regionRisk.primary_driver || "-",
          action: needsVerification ? "人工核验" : this.decisionForScore(riskScore, Number(finance.overdue_times) || 0),
        };
      }).sort((a, b) => (b.riskScore ?? -1) - (a.riskScore ?? -1));
    },
    assessmentObjects() {
      const search = this.assessmentSearch.trim().toLowerCase();
      const rows = this.assessmentMode === "subject"
        ? this.creditSubjectRows.map((row, idx) => ({
          key: row.name,
          type: "subject",
          rank: idx + 1,
          title: row.name,
          sub: `${row.region} / ${row.type}`,
          score: row.riskScore,
          level: row.needsVerification ? "待核验" : this.levelForScore(row.riskScore),
          driver: row.needsVerification ? "资产登记资料" : row.overdue > 0 ? "逾期记录" : row.regionRiskDriver,
          action: row.action,
          raw: row,
        }))
        : this.allRiskPoolRows.map((row) => ({
          key: row.region_id,
          type: "region",
          rank: row.rank,
          title: row.region_name,
          sub: `${row.month} / ${row.region_id}`,
          score: Number(row.predicted_score),
          level: this.levelForScore(Number(row.predicted_score)),
          driver: row.primary_driver,
          action: row.action,
          raw: row,
        }));
      return rows.filter((row) => {
        if (!search) return true;
        return `${row.title} ${row.sub} ${row.driver}`.toLowerCase().includes(search);
      });
    },
    selectedAssessmentObject() {
      const objects = this.assessmentObjects;
      if (!objects.length) return null;
      return objects.find((row) => row.key === this.selectedAssessmentKey) || objects[0];
    },
    selectedAssessment() {
      const item = this.selectedAssessmentObject;
      if (!item) return null;
      if (item.type === "subject") return this.buildSubjectAssessment(item.raw);
      return this.buildRegionAssessment(item.raw);
    },
    creditDecisionCards() {
      return this.buildCreditDecisionCards(this.selectedAssessment);
    },
    assessmentEvidence() {
      const assessment = this.selectedAssessment;
      if (!assessment) return [];
      const regionId = assessment.region_id;
      const latestWeather = this.latestRowByRegion(this.data?.weather || [], regionId, "observed_at");
      const latestRemote = this.latestRowByRegion(this.data?.remote_sensing || [], regionId, "scene_date");
      const evidence = [
        {
          group: "气象",
          title: latestWeather ? `${latestWeather.observed_at || "-"} 县域气象` : "气象数据缺失",
          rows: latestWeather ? [
            `温度 ${this.formatFixed(latestWeather.temperature_c, 1)}℃`,
            `降水 ${this.formatFixed(latestWeather.precipitation_mm_24h, 2)}mm`,
            `风速 ${this.formatFixed(latestWeather.wind_speed_mps, 1)}m/s`,
          ] : ["未匹配到该对象所在县域的气象记录"],
          state: latestWeather ? "ok" : "warn",
        },
        {
          group: "遥感",
          title: latestRemote ? `${latestRemote.scene_date || "-"} 遥感观测` : "遥感数据缺失",
          rows: latestRemote ? [
            `NDVI ${this.formatFixed(latestRemote.ndvi, 3)}`,
            `积雪 ${this.formatFixed(latestRemote.snow_cover, 1)}%`,
            `退化 ${latestRemote.degradation_level || "待评估"}`,
            `载畜量 ${this.formatFixed(latestRemote.carrying_capacity_sheep_unit, 0)}羊单位`,
          ] : ["未匹配到该对象所在县域的遥感记录"],
          state: latestRemote ? "ok" : "warn",
        },
      ];
      if (assessment.type === "subject") {
        evidence.push({
          group: "授信",
          title: `${assessment.raw.repayment} / 用信率 ${this.percent(assessment.raw.usage)}`,
          rows: [
            `授信 ${this.formatNumber(assessment.raw.line)}万`,
            `用信 ${this.formatNumber(assessment.raw.used)}万`,
            `保险覆盖 ${assessment.raw.insurance}`,
            `逾期次数 ${assessment.raw.overdue}`,
          ],
          state: assessment.raw.overdue > 0 ? "danger" : "ok",
        });
      } else {
        evidence.push({
          group: "模型",
          title: `${this.modelStatus.model_type || "rule"} / ${this.modelStatus.label_type || "rule_label"}`,
          rows: [
            `训练样本 ${this.formatNumber(this.modelStatus.n_samples || 0)}`,
            `县域 ${this.modelStatus.county_count || 0} 个`,
            `月份 ${this.modelStatus.month_count || 0} 个`,
            `真实数据 ${this.percent(this.modelStatus.real_data_ratio || 0)}`,
          ],
          state: this.modelStatus.model_type === "ml_hybrid" ? "ok" : "warn",
        });
      }
      return evidence;
    },
    managerWorkflowSteps() {
      const assessment = this.selectedAssessment;
      if (!assessment) return [];
      const workflow = this.closedLoop?.post_loan_workflow || [];
      const matched = workflow.find((row) => row.subject_name === assessment.title || row.region_id === assessment.region_id);
      const score = Number(assessment.score) || 0;
      const hasOverdue = assessment.type === "subject" && assessment.raw.overdue > 0;
      const state = (step) => {
        if (step <= 2) return step === 2 ? "active" : "done";
        if (step === 3) return score >= 55 || hasOverdue ? "active" : "pending";
        if (step === 4) return score >= 65 || hasOverdue ? "active" : "pending";
        return score >= 70 || hasOverdue ? "active" : "pending";
      };
      return [
        { key: "01", title: "准入申请", note: assessment.type === "subject" ? "主体画像已匹配" : "县域风险已入池", state: state(1) },
        { key: "02", title: "评估报告", note: `${assessment.level} / ${assessment.decision}`, state: state(2) },
        { key: "03", title: "人工复核", note: score >= 55 || hasOverdue ? "需客户经理复核" : "暂不触发", state: state(3) },
        { key: "04", title: "贷后核查", note: matched?.task_status || (score >= 65 || hasOverdue ? "进入核查队列" : "持续观察"), state: state(4) },
        { key: "05", title: "处置记录", note: matched?.next_action || (score >= 70 || hasOverdue ? "生成处置建议" : "保留监测记录"), state: state(5) },
      ];
    },
    subjectProfileRows() {
      const assessment = this.selectedAssessment;
      if (!assessment || assessment.type !== "subject") return [];
      const row = assessment.raw;
      return [
        { label: "主体类型", value: row.type || "-" },
        { label: "所在县域", value: row.region || "-" },
        { label: "客户经理", value: row.customer_manager || "工行牧区客户经理" },
        { label: "授信阶段", value: row.admission_stage || row.status || "-" },
        { label: "授信额度", value: `${this.formatNumber(row.line)}万` },
        { label: "已用额度", value: `${this.formatNumber(row.used)}万` },
        { label: "用信率", value: this.percent(row.usage) },
        { label: "还款状态", value: row.repayment || "-" },
        { label: "逾期次数", value: `${row.overdue || 0} 次` },
        { label: "保险状态", value: row.insurance_status || row.insurance || "-" },
        { label: "贷款用途", value: row.loan_purpose || "-" },
        { label: "数据属性", value: row.is_sample ? "sample / demo" : "real" },
      ];
    },
    labelDisclosure() {
      const labelRows = this.dataAssetCards.find((c) => c.key === "risk_event_labels")?.row_count || 0;
      if (labelRows > 0) {
        return `当前已接入 ${labelRows} 条 demo/sample 风险事件标签，用于跑通灾害、理赔、逾期标签链路；仍不等同于真实监督预测。`;
      }
      return "当前模型使用真实环境数据与规则弱标签评分，尚未接入足够真实灾害、理赔、逾期标签。";
    },
    assessmentActions() {
      const assessment = this.selectedAssessment;
      if (!assessment) return [];
      const actions = [];
      if (assessment.score >= 70) {
        actions.push({ priority: "P0", title: "暂停新增授信", desc: "进入人工复核前，不建议扩大额度或新增提款。" });
        actions.push({ priority: "P0", title: "触发贷后核查", desc: "核查经营台账、牲畜存栏、保险状态与资金用途。" });
      } else if (assessment.score >= 55) {
        actions.push({ priority: "P1", title: "人工复核", desc: "复核主风险因子对应的数据来源和异常月份。" });
        actions.push({ priority: "P1", title: "调整额度策略", desc: "将增额审批改为观察名单审批。" });
      } else {
        actions.push({ priority: "P2", title: "持续监测", desc: "保留月度自动评估，出现异常驱动时再升级处置。" });
      }
      if (assessment.type === "subject" && assessment.raw.overdue > 0) {
        actions.unshift({ priority: "P0", title: "还款行为核查", desc: "该主体存在逾期记录，需优先确认现金流和还款安排。" });
      }
      this.qualityWarnings.slice(0, 2).forEach((warning) => {
        actions.push({ priority: "DATA", title: "数据缺口处理", desc: warning });
      });
      return actions.slice(0, 5);
    },
    assessmentDetailRows() {
      const regionRows = this.allRiskPoolRows.slice(0, 10).map((row) => ({
        key: row.region_id,
        object: row.region_name,
        type: "县域",
        score: Number(row.predicted_score),
        level: this.levelForScore(Number(row.predicted_score)),
        exposure: row.exposure,
        driver: row.primary_driver,
        admission: this.creditDecisionBrief("region", Number(row.predicted_score), row).admission,
        limitPolicy: this.creditDecisionBrief("region", Number(row.predicted_score), row).limitPolicy,
        action: row.action,
      }));
      const subjectRows = this.creditSubjectRows.slice(0, 8).map((row) => ({
        key: row.name,
        object: row.name,
        type: "主体",
        score: row.riskScore,
        level: row.needsVerification ? "待核验" : this.levelForScore(row.riskScore),
        exposure: row.used,
        driver: row.needsVerification ? "资产登记资料" : row.overdue > 0 ? "逾期记录" : row.regionRiskDriver,
        admission: this.creditDecisionBrief("subject", row.riskScore, row).admission,
        limitPolicy: this.creditDecisionBrief("subject", row.riskScore, row).limitPolicy,
        action: row.action,
      }));
      return [...regionRows, ...subjectRows].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    },
    assessmentStats() {
      const scores = this.assessmentDetailRows.map((row) => Number(row.score) || 0);
      const high = scores.filter((score) => score >= 70).length;
      const medium = scores.filter((score) => score >= 55 && score < 70).length;
      return [
        { label: "待评估对象", value: this.assessmentObjects.length, note: this.assessmentMode === "region" ? "县域对象池" : "主体授信池" },
        { label: "高风险", value: high, note: "建议立即核查" },
        { label: "中风险", value: medium, note: "进入人工复核" },
        { label: "模型样本", value: this.formatNumber(this.modelStatus.n_samples || 0), note: this.modelStatus.model_type || "rule" },
      ];
    },
    publicRiskKpis() {
      const totalRows = (this.data?.weather?.length || 0) + (this.data?.remote_sensing?.length || 0);
      const counties = this.modelStatus.county_count || this.data?.regions?.length || 0;
      const months = this.modelStatus.month_count || 0;
      const high = this.regionalRiskRows.filter((row) => Number(row.predicted_score) >= 70).length;
      return [
        { label: "接入数据量条", value: this.formatNumber(totalRows || 3000) },
        { label: "覆盖县域个", value: counties || 25 },
        { label: "监测时段个月", value: months || 60 },
        { label: "高风险县域个", value: high, danger: true },
      ];
    },
    publicRiskHeatRows() {
      return this.regionalRiskRows.slice(0, 5).map((row) => {
        const normalized = Number(row.predicted_score || 0);
        const drivers = row.driver_details || [];
        const driverVal = (key) => Number(drivers.find((item) => item.key === key)?.value || 0);
        const regionSubjects = this.creditSubjectRows.filter((item) => item.region_id === row.region_id);
        const avgSubjectScore = regionSubjects.length ? avg(regionSubjects.map((item) => Number(item.score) || 0)) : 75;
        const avgCoverage = regionSubjects.length
          ? avg(regionSubjects.map((item) => Number(String(item.insurance || "0").replace("%", "")) || 0))
          : 70;
        const overdue = regionSubjects.reduce((sum, item) => sum + (Number(item.overdue) || 0), 0);
        const usage = regionSubjects.length ? avg(regionSubjects.map((item) => Number(item.usage) || 0)) : 0.6;
        const dimScores = [
          { name: "信用", value: Math.round(Math.min(100, Math.max(0, 100 - avgSubjectScore + overdue * 12 + usage * 20))) },
          { name: "经营", value: Math.round(Math.min(100, Math.max(0, 100 - avgSubjectScore + usage * 18))) },
          { name: "生态", value: Math.round(Math.min(100, driverVal("remote") * 3.8 + 30)) },
          { name: "气象", value: Math.round(Math.min(100, driverVal("weather") * 4.2 + 28)) },
          { name: "金融", value: Math.round(Math.min(100, driverVal("finance") * 3.4 + overdue * 10 + usage * 18)) },
          { name: "保险", value: Math.round(Math.min(100, Math.max(0, 95 - avgCoverage + overdue * 8))) },
        ];
        return {
          ...row,
          display_score: normalized.toFixed(1),
          display_level: normalized >= 70 ? "高风险" : normalized >= 55 ? "中风险" : "低风险",
          dim_scores: dimScores,
          dim_summary: `信用/经营基于主体评分和用信率，生态/气象来自模型因子，金融/保险来自授信、逾期和覆盖率。`,
        };
      });
    },
    selectedPublicRiskRow() {
      return this.publicRiskHeatRows.find((row) => row.region_id === this.selectedPublicRiskRegionId) || this.publicRiskHeatRows[0] || null;
    },
    disposalQueue() {
      const queue = [];
      this.riskPoolRows.slice(0, 4).forEach((row) => {
        queue.push({
          type: "县域",
          target: row.region_name,
          level: Number(row.predicted_score) >= 65 ? "high" : "medium",
          issue: `${row.primary_driver}驱动风险 ${row.predicted_score}`,
          action: row.action,
        });
      });
      this.creditSubjectRows.filter((row) => row.riskScore >= 45 || row.overdue > 0).slice(0, 4).forEach((row) => {
        queue.push({
          type: "客户",
          target: row.name,
          level: row.overdue > 0 ? "high" : "medium",
          issue: `用信率 ${this.percent(row.usage)} / 逾期 ${row.overdue}`,
          action: row.overdue > 0 ? "贷后核查" : "额度复核",
        });
      });
      return queue.slice(0, 6);
    },
    terminalMetrics() {
      return [
        { label: "工行用信敞口", value: `${this.formatNumber(this.creditPortfolio.used)}万`, note: `总授信 ${this.formatNumber(this.creditPortfolio.line)}万` },
        { label: "用信率", value: this.percent(this.creditPortfolio.usage_rate), note: `可用额度 ${this.formatNumber(this.creditPortfolio.available)}万` },
        { label: "风险资产池", value: this.riskPoolRows.length, note: `${this.opsSummary.last_month} 最新评分` },
        { label: "处置队列", value: this.disposalQueue.length, note: `${this.creditPortfolio.watch} 个关注客户` },
      ];
    },
    dataAssetCards() {
      const byKey = Object.fromEntries(this.qualityRows.map((row) => [row.key, row]));
      const card = (key, title, desc, status) => ({
        key,
        title,
        desc,
        status,
        row_count: byKey[key]?.row_count || 0,
        real_rows: byKey[key]?.real_rows || 0,
        sample_rows: byKey[key]?.sample_rows || 0,
        warnings: byKey[key]?.warnings || [],
      });
      return [
        card("weather_data", "CMFD 气象数据", "2020-2024，25 县 × 60 个月，温度/降水/风速。", "真实接入"),
        card("remote_sensing_data", "MODIS/TPDC 遥感数据", "NDVI、积雪、草地退化与临时载畜量字段。", "部分真实"),
        card("forage_supply_demand", "Geodoi 饲草供需", "2000-2020 全国/区域年度宏观饲草供需。", "真实宏观"),
        card("business_subjects", "经营主体台账", "合作社、家庭牧场、供应商经营信息。", "样例待替换"),
        card("finance_credit", "工行授信与保险台账", "授信、用信、还款、逾期、保单信息。", "样例待替换"),
        card("risk_event_labels", "来源事件样本", "带来源 URL 的公开灾害事件；其余月份保持未确认。", "42 条来源事件"),
        card("insurance_claims", "银保理赔查勘", "出险、查勘、理赔金额和贷后回流动作。", "脱敏样例"),
        card("supply_chain_orders", "产业链订单台账", "饲草采购、活体交易、物流验收和关联授信。", "脱敏样例"),
        card("supply_chain_payments", "工行资金流向", "定向支付、收款方、到账状态和用途核验。", "脱敏样例"),
        card("post_loan_workflow", "客户经理工作流", "准入、评估、复核、贷后核查和处置记录。", "脱敏样例"),
        card("green_performance_metrics", "绿色绩效指标", "绿色信贷、减灾减损、牧户覆盖和民生指标。", "脱敏样例"),
      ];
    },
    dataSourceSnapshot() {
      return [
        { label: "TPDC CMFD 气象", value: this.formatNumber(this.dataAssetCards.find((c) => c.key === "weather_data")?.row_count || 0), note: "县域月度温度/降水/风速" },
        { label: "MODIS/TPDC 遥感", value: this.formatNumber(this.dataAssetCards.find((c) => c.key === "remote_sensing_data")?.row_count || 0), note: "NDVI、积雪、退化、载畜量字段" },
        { label: "Geodoi 宏观饲草", value: this.formatNumber(this.dataAssetCards.find((c) => c.key === "forage_supply_demand")?.row_count || 0), note: "年度区域参考，不参与训练" },
        { label: "来源事件", value: 42, note: "公开灾害事件；不等于完整灾害或贷损标签" },
      ];
    },
    moduleLoopItems() {
      return [
        { step: "01", title: "数据接入", desc: "接入气象遥感、经营主体、授信还款、保险协同和产业链台账。" },
        { step: "02", title: "工行准入", desc: "形成授信对象池、综合风险分、主风险因子和可解释证据链。" },
        { step: "03", title: "人工核验", desc: "结合生态证据、经营资料、保险合同和用信记录形成核验清单。" },
        { step: "04", title: "贷后预警", desc: "对寒潮、积雪、NDVI 异常、逾期和回款异常触发核查任务。" },
        { step: "05", title: "绩效回流", desc: "沉淀绿色信贷投放、风险减量、银保协同和边疆民生绩效。" },
      ];
    },
    latestWeatherSummary() {
      const rows = this.data?.weather || [];
      if (!rows.length) return [];
      const sorted = [...rows].sort((a, b) => String(b.observed_at || "").localeCompare(String(a.observed_at || "")));
      const latestMonth = String(sorted[0]?.observed_at || "").slice(0, 7);
      const latestRows = sorted.filter((row) => String(row.observed_at || "").slice(0, 7) === latestMonth);
      const num = (field) => latestRows.map((row) => Number(row[field]) || 0);
      return [
        { label: "月份", value: latestMonth || "-", note: `${latestRows.length} 个县域样本` },
        { label: "平均温度", value: `${avg(num("temperature_c")).toFixed(1)}℃`, note: "CMFD 县域均值" },
        { label: "日降水均值", value: `${avg(num("precipitation_mm_24h")).toFixed(2)}mm`, note: "月内日尺度折算值" },
        { label: "平均风速", value: `${avg(num("wind_speed_mps")).toFixed(1)}m/s`, note: "高原风速监测" },
      ];
    },
    latestRemoteSummary() {
      const rows = this.data?.remote_sensing || [];
      if (!rows.length) return [];
      const sorted = [...rows].sort((a, b) => String(b.scene_date || "").localeCompare(String(a.scene_date || "")));
      const latestMonth = String(sorted[0]?.scene_date || "").slice(0, 7);
      const latestRows = sorted.filter((row) => String(row.scene_date || "").slice(0, 7) === latestMonth);
      const num = (field) => latestRows.map((row) => Number(String(row[field] ?? "").replace("%", "")) || 0);
      return [
        { label: "月份", value: latestMonth || "-", note: `${latestRows.length} 个县域样本` },
        { label: "NDVI 均值", value: avg(num("ndvi")).toFixed(3), note: "MODIS 月度合成" },
        { label: "积雪覆盖", value: `${avg(num("snow_cover")).toFixed(1)}%`, note: "MOD10A1 聚合" },
        { label: "退化字段", value: `${latestRows.filter((r) => r.degradation_level && r.degradation_level !== "待评估").length}/${latestRows.length}`, note: "TPDC 静态退化等级" },
      ];
    },
    overviewMetrics() {
      const total = this.dataQuality?.total || {};
      return [
        { label: "真实数据行", value: this.formatNumber(total.real_rows || 0), note: "气象、遥感、宏观饲草供需" },
        { label: "样例数据行", value: this.formatNumber(total.sample_rows || 0), note: "经营主体、工行授信和保险台账仍需替换" },
        { label: "模型样本", value: this.formatNumber(this.modelStatus.n_samples || 0), note: `${this.modelStatus.county_count || 0} 县 / ${this.modelStatus.month_count || 0} 月` },
        { label: "来源事件", value: 42, note: "其余月份为未确认状态，不等于无灾" },
      ];
    },
    insuranceRows() {
      return this.creditSubjectRows.map((row) => ({
        name: row.name,
        type: row.type,
        region: row.region,
        insurance: row.insurance,
        repayment: row.repayment,
        overdue: row.overdue,
        used: row.used,
        action: row.overdue > 0 ? "优先贷后核查" : Number(String(row.insurance).replace("%", "")) < 65 ? "核验保险资料" : row.action,
      })).slice(0, 12);
    },
    insuranceSummary() {
      const rows = this.creditSubjectRows;
      const vals = rows.map((row) => Number(String(row.insurance || "").replace("%", ""))).filter((n) => Number.isFinite(n));
      const coverage = vals.length ? `${avg(vals).toFixed(0)}%` : "待接入";
      const low = vals.filter((v) => v < 65).length;
      return { coverage, low, count: rows.length };
    },
    insuranceKpis() {
      const claims = this.closedLoop?.insurance_claims || [];
      const claimAmount = claims.reduce((sum, row) => sum + (Number(row.claim_amount) || 0), 0);
      return [
        { label: "授信主体", value: this.formatNumber(this.insuranceSummary.count), note: "经营主体样例池" },
        { label: "样例覆盖字段", value: this.insuranceSummary.coverage, note: "仅作资料核验线索" },
        { label: "待核验主体", value: this.insuranceSummary.low, note: "需补齐合同和责任范围" },
        { label: "理赔样例", value: this.formatNumber(claims.length), note: `脱敏流程数据，赔付 ${claimAmount.toFixed(1)} 万` },
      ];
    },
    insuranceEvidence() {
      const claims = this.closedLoop?.insurance_claims || [];
      const claimAmount = claims.reduce((sum, row) => sum + (Number(row.claim_amount) || 0), 0);
      const surveying = claims.filter((row) => String(row.claim_status || "").includes("查勘")).length;
      const lowNames = this.insuranceRows
        .filter((row) => Number(String(row.insurance || "").replace("%", "")) < 65)
        .map((row) => row.name)
        .slice(0, 2);
      return [
        {
          group: "资料核验",
          title: `${this.insuranceSummary.coverage} 样例覆盖字段`,
          rows: [
            `待核验主体 ${this.insuranceSummary.low} 个`,
            lowNames.length ? `需核验：${lowNames.join("、")}` : "暂无待核验主体",
            "需补齐保单号、保额、责任范围后才能进入人工授信核验",
          ],
          state: this.insuranceSummary.low > 0 ? "warn" : "ok",
        },
        {
          group: "灾害",
          title: `${this.latestWeatherSummary[0]?.value || "2024-12"} 气象遥感触发`,
          rows: [
            `气象：${this.latestWeatherSummary[1]?.value || "-"} / ${this.latestWeatherSummary[2]?.value || "-"}`,
            `遥感：NDVI ${this.latestRemoteSummary[1]?.value || "-"}`,
            "寒潮、积雪、NDVI 异常进入客户经理人工核查名单",
          ],
          state: "ok",
        },
        {
          group: "理赔",
          title: `${claims.length || 0} 条理赔/查勘样例`,
          rows: [
            `查勘中 ${surveying} 条，样例赔付 ${claimAmount.toFixed(1)} 万元`,
            "理赔结果接入后再回流贷后核查；当前仅展示流程",
            "当前仅作流程演示，不作为真实理赔结论",
          ],
          state: claims.length ? "ok" : "warn",
        },
      ];
    },
    insuranceActions() {
      return [
        { priority: "P1", title: "保险资料核验", desc: "对覆盖字段缺失或偏低的主体，提示客户经理核验保单号、保额、期限和责任范围。" },
        { priority: "P1", title: "灾害触发查勘", desc: "当气象、积雪、NDVI 异常与授信主体重叠时，推送银保协同查勘名单。" },
        { priority: "DATA", title: "理赔接口补齐", desc: "当前理赔数据为接口预留，后续接入真实 claim_id、claim_amount、claim_date 后回流风险模型。" },
      ];
    },
    insuranceAssessmentRows() {
      return this.insuranceRows.slice(0, 8).map((row, idx) => {
        return {
          key: `${row.name}-${idx}`,
          object: row.name,
          type: row.type || "授信主体",
          score: null,
          level: "待核验",
          exposure: row.used || 0,
          driver: Number(row.overdue || 0) > 0 ? "逾期待核验" : "保险资料待核验",
          action: row.action,
        };
      });
    },
    supplyChainFlow() {
      return [
        { icon: "ICBC", title: "工行放款", note: "绑定贷款用途" },
        { icon: "PO", title: "饲草采购", note: "定向支付备案供应商" },
        { icon: "LOG", title: "物流配送", note: "物流单据核验" },
        { icon: "IN", title: "牧场入库", note: "存栏同步更新" },
        { icon: "PAY", title: "产品回款", note: "销售回款闭环" },
        { icon: "OK", title: "贷后核销", note: "还款与风险更新" },
      ];
    },
    supplyChainUploadFields() {
      return ["order_id", "subject_name", "order_type", "supplier", "amount", "linked_credit_id", "payment_id", "from_account", "to_account"];
    },
    supplyChainOrderSchema() {
      return [
        { field: "order_id", label: "订单号", example: "ORD-2024-001" },
        { field: "subject_name", label: "采购主体", example: "扎西高原牧业合作社" },
        { field: "region_id", label: "所在县域", example: "naqu-bange" },
        { field: "order_type", label: "订单类型", example: "饲草采购" },
        { field: "supplier", label: "供应商", example: "仁青冷链供草中心" },
        { field: "amount", label: "金额（万元）", example: "85.5" },
        { field: "linked_credit_id", label: "关联授信", example: "CRD-2024-003" },
      ];
    },
    supplyChainPaymentSchema() {
      return [
        { field: "payment_id", label: "流水号", example: "PAY-2024-001" },
        { field: "order_id", label: "关联订单", example: "ORD-2024-001" },
        { field: "from_account", label: "付款方", example: "工行绿色信贷账户" },
        { field: "to_account", label: "收款方", example: "仁青冷链供草中心" },
        { field: "amount", label: "金额（万元）", example: "85.5" },
        { field: "channel", label: "支付渠道", example: "工行网银定向支付" },
        { field: "status", label: "状态", example: "已到账" },
      ];
    },
    supplyChainOrders() {
      const rows = this.closedLoop?.supply_chain_orders || [];
      if (rows.length) {
        return rows.slice(0, 12).map((row) => ({
          ...row,
          action: row.fund_usage_status || row.delivery_status || row.risk_note || "待核验",
        }));
      }
      return [
        { order_id: "ORD-2024-001", subject_name: "扎西高原牧业合作社", order_type: "饲草采购", supplier: "仁青冷链供草中心", amount: 85.5, linked_credit_id: "CRD-2024-003", action: "已到账" },
        { order_id: "ORD-2024-002", subject_name: "德吉牦牛养殖联合体", order_type: "活体交易", supplier: "昌都牲畜交易服务站", amount: 62.8, linked_credit_id: "CRD-2024-006", action: "回款观察" },
        { order_id: "ORD-2024-003", subject_name: "央金家庭牧场", order_type: "补饲采购", supplier: "那曲冬储饲草库", amount: 24.6, linked_credit_id: "CRD-2024-011", action: "需补保单" },
      ];
    },
    supplyChainPreviewRows() {
      return this.creditSubjectRows.slice(0, 10).map((row) => ({
        name: row.name,
        region: row.region,
        loan_purpose: row.loan_purpose || "饲草采购 / 经营周转",
        line: row.line,
        used: row.used,
        action: row.usage > 0.75 ? "核验资金用途和回款" : "纳入定向支付观察",
      }));
    },
    greenPerformance() {
      return {
        years: ["2020", "2021", "2022", "2023", "2024"],
        firstYear: "2020-01",
        lastYear: "2024-12",
        first: 0.113,
        last: 0.136,
        ndviChange: "+20.9%",
      };
    },
    ndviYearPoints() {
      const points = [
        { year: "2020", value: 0.113 },
        { year: "2021", value: 0.116 },
        { year: "2022", value: 0.103 },
        { year: "2023", value: 0.115 },
        { year: "2024", value: 0.136 },
      ];
      const min = 0;
      const max = 0.16;
      return points.map((point, idx) => ({
        ...point,
        x: 10 + idx * 20,
        y: 16 + ((point.value - min) / (max - min)) * 62,
      }));
    },
    greenPerformanceKpis() {
      const green = this.closedLoop?.green_performance_metrics || [];
      const regions = new Set(green.map((row) => row.region_id).filter(Boolean));
      const highCount = this.regionalRiskRows.filter((row) => Number(row.predicted_score) >= 70).length;
      return [
        { label: "覆盖县域", value: regions.size || 25, note: "高原牧区示范县" },
        { label: "NDVI 2020→2024", value: "+20.9%", note: "5年改善趋势" },
        { label: "高风险县域", value: highCount, note: "需重点关注" },
        { label: "碳账户", value: "预留", note: "接入真实 NPP 后启用" },
      ];
    },
    greenMetricFramework() {
      const rows = this.closedLoop?.green_performance_metrics || [];
      const sum = (type) => rows
        .filter((row) => row.metric_type === type)
        .reduce((total, row) => total + (Number(row.metric_value) || 0), 0);
      const credit = sum("green_credit");
      const households = sum("livelihood");
      const reduction = sum("risk_reduction");
      return [
        { label: "绿色信贷余额", value: credit ? `${this.formatNumber(credit.toFixed(1))}万` : "待接入", note: credit ? "脱敏样例汇总" : "需对接工行授信台账" },
        { label: "支持牧户数", value: households ? `${this.formatNumber(households)}户` : "300+", note: "脱敏样例，待真实数据替换" },
        { label: "减灾减损金额", value: reduction ? `${this.formatNumber(reduction.toFixed(1))}万` : "待接入", note: "由理赔/减损样例回流" },
        { label: "碳减排当量", value: "接口预留", note: "待接入真实 NPP/碳汇核算" },
        { label: "GEP 生态产值", value: "接口预留", note: "草地生态系统生产总值" },
        { label: "可持续评分", value: "接口预留", note: "绿色养殖监测接入后启用" },
      ];
    },
    greenRiskDistribution() {
      const rows = this.regionalRiskRows;
      const low = rows.filter((row) => Number(row.predicted_score) < 55).length;
      const mid = rows.filter((row) => Number(row.predicted_score) >= 55 && Number(row.predicted_score) < 70).length;
      const high = rows.filter((row) => Number(row.predicted_score) >= 70).length;
      const dist = [
        { label: "低风险", value: low },
        { label: "中风险", value: mid || (rows.length ? 0 : 25) },
        { label: "高风险", value: high },
      ];
      const total = rows.length || 25;
      return dist.map((item, idx) => ({ ...item, percent: Math.round((item.value / total) * 100), className: ["low", "mid", "high"][idx] }));
    },
    riskDonutGradient() {
      const dist = this.greenRiskDistribution;
      const high = dist.find((d) => d.className === "high")?.percent || 0;
      const mid = dist.find((d) => d.className === "mid")?.percent || 0;
      const low = dist.find((d) => d.className === "low")?.percent || 0;
      const hEnd = high;
      const mEnd = high + mid;
      const lEnd = high + mid + low;
      return `conic-gradient(#ef6b6b 0 ${hEnd}%, #ffa10a ${hEnd}% ${mEnd}%, #1fc9a7 ${mEnd}% ${lEnd}%, #e8ece9 ${lEnd}% 100%)`;
    },
    greenEvidence() {
      return [
        {
          group: "气象",
          title: `${this.latestWeatherSummary[0]?.value || "2024-12"} 县域气象`,
          rows: [
            `温度 ${this.latestWeatherSummary[1]?.value || "-10.3℃"}`,
            `降水 ${this.latestWeatherSummary[2]?.value || "0.13mm"}`,
            `风速 ${this.latestWeatherSummary[3]?.value || "2.4m/s"}`,
          ],
          state: "ok",
        },
        {
          group: "遥感",
          title: "2024-12-15 遥感观测",
          rows: [
            "NDVI 0.136",
            "积雪 6.9%",
            "退化 重点变化",
            "载畜量 25800羊单位",
          ],
          state: "ok",
        },
        {
          group: "模型",
          title: `${this.modelStatus.model_type || "rule"} / ${this.modelStatus.label_type || "rule_label"}`,
          rows: [
            `训练样本 ${this.formatNumber(this.modelStatus.n_samples || 0)}`,
            `县域 ${this.modelStatus.county_count || 0} 个`,
            `月份 ${this.modelStatus.month_count || 0} 个`,
            `真实数据 ${this.percent(this.modelStatus.real_data_ratio || 0)}`,
          ],
          state: "warn",
        },
      ];
    },
    greenActions() {
      return [
        { priority: "P1", title: "人工复核", desc: "复核生态改善趋势与风险评分口径，避免把弱标签误认为真实监督预测。" },
        { priority: "P1", title: "绿色绩效归档", desc: "将 NDVI 改善、风险分布和绿色信贷指标纳入答辩材料。" },
        { priority: "DATA", title: "数据缺口处理", desc: "碳账户、GEP、减灾减损金额仍为接口预留，需后续真实数据接入。" },
      ];
    },
    greenAssessmentRows() {
      return this.publicRiskHeatRows.map((row) => ({
        key: row.region_id,
        object: row.region_name,
        type: "县域",
        score: Number(row.display_score),
        level: row.display_level,
        exposure: row.exposure || 0,
        driver: row.primary_driver || "生态",
        action: Number(row.display_score) >= 55 ? "人工复核" : "持续监测",
      }));
    },
    borderCountyRows() {
      const keywords = ["日喀则", "阿里", "山南", "林芝", "昌都", "那曲", "甘孜", "阿坝", "果洛"];
      const rows = this.regionalRiskRows.filter((row) => keywords.some((key) => String(row.region_name).includes(key)));
      return (rows.length ? rows : this.regionalRiskRows).slice(0, 9).map((row) => {
        const weather = row.driver_details?.find((d) => d.key === "weather")?.value || 0;
        const remote = row.driver_details?.find((d) => d.key === "remote")?.value || 0;
        return {
          ...row,
          climateRisk: Math.round(Number(weather) * 3.2 + 30),
          ecologyConstraint: Math.round(Number(remote) * 3.6 + 40),
        };
      });
    },
    livelihoodKpis() {
      const rows = this.borderCountyRows;
      const avgScore = rows.length ? avg(rows.map((r) => Number(r.predicted_score) || 0)).toFixed(0) : "-";
      const green = this.closedLoop?.green_performance_metrics || [];
      const households = green
        .filter((row) => row.metric_type === "livelihood")
        .reduce((sum, row) => sum + (Number(row.metric_value) || 0), 0);
      return [
        { label: "边境重点县域", value: rows.length, note: "公网展示口径为重点县池" },
        { label: "总覆盖县域", value: this.modelStatus.county_count || this.data?.regions?.length || 0, note: "模型覆盖县域" },
        { label: "高风险边境县", value: rows.filter((r) => Number(r.predicted_score) >= 70).length, note: "触发贷后核查" },
        { label: "支持牧户", value: households ? `${this.formatNumber(households)}户` : avgScore, note: households ? "脱敏样例民生指标" : "基于当前弱标签评分" },
      ];
    },
    fourPartyCards() {
      return [
        { icon: "GOV", role: "生态保护 · 草场管理 · 乡村振兴", title: "地方政府", desc: "县域畜牧统计、生态补偿政策", status: "数据接口预留" },
        { icon: "ICBC", role: "绿色授信 · 贷后预警 · 普惠金融", title: "工商银行", desc: "授信台账、还款记录、贷后核查", status: "样本待替换" },
        { icon: "INS", role: "承保定损 · 理赔协同 · 风险减量", title: "保险机构", desc: "保单明细、出险记录、理赔结果", status: "表结构就绪" },
        { icon: "COOP", role: "养殖管理 · 产品销售 · 数据上报", title: "牧户合作社", desc: "存栏数据、交易记录、防疫档案", status: "样本待替换" },
      ];
    },
    livelihoodEvidence() {
      const weather = this.latestWeatherSummary;
      const remote = this.latestRemoteSummary;
      return [
        {
          group: "气象",
          title: `${weather[0]?.value || "2024-12"} 县域气象`,
          rows: [
            `温度 ${weather[1]?.value || "-"}`,
            `降水 ${weather[2]?.value || "-"}`,
            `风速 ${weather[3]?.value || "-"}`,
          ],
          state: "ok",
        },
        {
          group: "遥感",
          title: `${remote[0]?.value || "2024-12"} 遥感观测`,
          rows: [
            `NDVI ${remote[1]?.value || "-"}`,
            `积雪 ${remote[2]?.value || "-"}`,
            `退化 ${remote[3]?.value || "-"}`,
          ],
          state: "ok",
        },
        {
          group: "工作流",
          title: `${(this.closedLoop?.post_loan_workflow || []).length} 条客户经理任务`,
          rows: [
            `模型 ${this.modelStatus.model_type || "rule"} / ${this.modelStatus.label_type || "rule_label"}`,
            `训练样本 ${this.formatNumber(this.modelStatus.n_samples || 0)}`,
            "准入、复核、贷后核查、处置记录进入同一闭环",
          ],
          state: "warn",
        },
      ];
    },
    livelihoodActions() {
      const rows = this.borderCountyRows;
      const avgScore = rows.length ? avg(rows.map((r) => Number(r.predicted_score) || 0)) : 0;
      const actions = [
        {
          priority: "P1",
          title: "人工复核",
          desc: "复核边境重点县对应的数据来源和异常月份。",
        },
        {
          priority: "P1",
          title: "调整额度策略",
          desc: "将边境重点县增额审批改为观察名单审批。",
        },
        {
          priority: "DATA",
          title: "数据缺口处理",
          desc: "经营主体、保单和真实理赔数据仍需后续接入。",
        },
      ];
      if (avgScore >= 55) {
        actions.unshift({
          priority: "P0",
          title: "边境重点县贷后核查",
          desc: "对平均风险偏高县域提高贷后走访和保险覆盖核验频率。",
        });
      }
      return actions;
    },
    livelihoodAssessmentRows() {
      const regionRows = this.borderCountyRows.slice(0, 9).map((row) => ({
        key: row.region_id,
        object: row.region_name,
        type: "县域",
        score: Number(row.predicted_score),
        level: this.levelForScore(Number(row.predicted_score)),
        exposure: row.exposure || 0,
        driver: row.primary_driver || "气象",
        action: this.decisionForScore(Number(row.predicted_score)),
      }));
      const subjectRows = this.creditSubjectRows
        .filter((row) => regionRows.some((region) => region.key === row.region_id))
        .slice(0, 5)
        .map((row) => ({
          key: row.name,
          object: row.name,
          type: "主体",
          score: row.riskScore,
          level: row.needsVerification ? "待核验" : this.levelForScore(row.riskScore),
          exposure: row.used,
          driver: row.needsVerification ? "资产登记资料" : row.overdue > 0 ? "逾期记录" : row.regionRiskDriver,
          action: row.action,
        }));
      return [...regionRows, ...subjectRows].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)).slice(0, 12);
    },
  },

  methods: {
    async loadWarningData() {
      this.warningLoading = true;
      try {
        const [gdiData, ndviData] = await Promise.all([
          api.warningGdi(),
          api.warningNdvi(),
        ]);
        this.warningData = {
          gdi: gdiData,
          ndvi: ndviData,
          loaded_at: new Date().toISOString(),
        };
      } catch (e) {
        console.warn("预警数据加载失败:", e);
        this.warningData = null;
      }
      this.warningLoading = false;
    },

    async loadDailyCapacity(regionId, days = 30) {
      if (!regionId) return;
      this.dailyCapacityLoading = true;
      try {
        this.dailyCapacity = await api.carryingCapacityDaily(regionId, days);
      } catch (e) {
        console.warn("逐日载畜量加载失败:", e);
        this.dailyCapacity = null;
      }
      this.dailyCapacityLoading = false;
    },

    async loadGridData() {
      if (!this.gridSelectedRegion) return;
      this.gridLoading = true;
      try {
        this.gridData = await api.gridRegion(this.gridSelectedRegion);
      } catch (e) {
        console.warn("时空网格加载失败:", e);
        this.gridData = null;
      }
      this.gridLoading = false;
    },

    gridRiskColor(risk) {
      if (!risk) return "transparent";
      if (risk >= 65) return "#EF4444";
      if (risk >= 50) return "#F59E0B";
      if (risk >= 40) return "#EAB308";
      return "#10B981";
    },

    async loadExplainData() {
      if (!this.explainSelectedRegion) return;
      this.explainLoading = true;
      try {
        this.explainData = await api.modelExplain(this.explainSelectedRegion);
      } catch (e) {
        console.warn("SHAP解释报告加载失败:", e);
        this.explainData = null;
      }
      this.explainLoading = false;
    },

    async loadDisaster(regionId) {
      if (!regionId) return null;
      try {
        return await api.warningDisaster(regionId);
      } catch (e) {
        console.warn("灾害风险加载失败:", e);
        return null;
      }
    },

    navigate(page) {
      const previousPage = this.page;
      if (previousPage === "data" && page !== "data") this.disposeEvidenceMap();
      this.page = page;
      window.location.hash = page;
      window.scrollTo({ top: 0, behavior: "smooth" });
      if (page === "home") this.startHero(); else this.stopHero();
      this.$nextTick(() => {
        if (page === "dashboard") {
          this.loadModelData();
        }
        if (page === "overview") this.renderOverviewChartsSoon();
        if (page === "data") { this.renderDataChartsSoon(); this.loadWarningData(); }
        if (page === "green-performance") this.renderOverviewChartsSoon();
        if (page === "data" && this.dataTab === "risk") renderRiskChart(this.data?.risk_assessment);
        if (page === "cooperative-ranking" && !this.coopRegions.length) {
          this.coopRegions = (this.data?.regions || []).map(r => ({ id: r.id, name: r.name }));
        }
        if (page === "insurance-portfolio") this.loadPortfolio();
        if (page === "disaster-forecast") {
          if (!this.disasterRegions || !this.disasterRegions.length) this.loadDisasterRegions();
          this.$nextTick(() => this.renderDisasterChart());
        }
      });
    },

    async loadCooperativeRanking() {
      if (!this.coopSelectedRegion) return;
      this.coopLoading = true;
      try {
        const [rankingData, verifyData] = await Promise.all([
          api.cooperativeRanking(this.coopSelectedRegion, this.coopTopN),
          fetch(`/api/cooperative-verify/${encodeURIComponent(this.coopSelectedRegion)}`).then(r => r.json()),
        ]);
        this.coopRanking = rankingData.ranking || [];
        this.coopSummary = rankingData.summary || null;
        this.coopDataQuality = verifyData.data_quality_score != null
          ? verifyData.data_quality_score + '分 (' + verifyData.quality_label + ')'
          : '--';
      } catch (e) {
        console.error("合作社排序加载失败:", e);
        this.coopRanking = [];
        this.coopSummary = null;
        this.coopDataQuality = "--";
      } finally {
        this.coopLoading = false;
      }
    },

    // ========================================================================
    // 保单画像
    // ========================================================================

    async loadPortfolio() {
      if (this.portfolioLoading) return;
      this.portfolioLoading = true;
      try {
        const [profile, farmers, synergy, comprehensive, dueDiligence] = await Promise.all([
          api.portfolioProfile(),
          api.portfolioFarmers(),
          api.portfolioSynergy(),
          api.portfolioComprehensive(),
          api.portfolioDueDiligence(),
        ]);
        this.portfolioProfile = profile;
        this.portfolioFarmers = farmers;
        this.portfolioSynergy = synergy;
        this.portfolioComprehensive = comprehensive;
        this.portfolioDueDiligence = dueDiligence;
        this.$nextTick(() => {
          this.renderPortfolioScaleChart();
          this.renderPortfolioFarmersChart();
        });
      } catch (e) {
        console.error("loadPortfolio error:", e);
      } finally {
        this.portfolioLoading = false;
      }
    },

    // ========================================================================
    // 灾害预测
    // ========================================================================

    async loadDisasterRegions() {
      try {
        const res = await fetch("/api/disaster-forecast/regions", { cache: "no-store" });
        const data = await res.json();
        if (data.ok) this.disasterRegions = data.regions || [];
      } catch (e) {
        console.error("loadDisasterRegions error:", e);
      }
    },

    async runDisasterForecast() {
      const q = (this.disasterInput || "").trim();
      if (!q) {
        this.disasterError = "请输入地区名（如：班戈县 / 拉萨 / 那曲）";
        return;
      }
      this.disasterError = "";
      this.disasterLoading = true;
      this.disasterResult = null;
      try {
        const url = `/api/disaster-forecast?region=${encodeURIComponent(q)}`;
        const res = await fetch(url, { cache: "no-store" });
        const data = await res.json();
        if (data.ok) {
          this.disasterResult = data;
          this.$nextTick(() => this.renderDisasterChart());
        } else {
          this.disasterError = data.message || "预测失败";
        }
      } catch (e) {
        this.disasterError = `请求失败: ${e.message}`;
      } finally {
        this.disasterLoading = false;
      }
    },

    disasterLevelColor(level) {
      if (level === "高") return "#ea4335";
      if (level === "中") return "#f9ab00";
      return "#34a853";
    },

    renderDisasterChart() {
      const el = this.$refs.disasterChartRef;
      if (!el || !this.disasterResult) return;
      if (typeof echarts === "undefined") return;
      const chart = echarts.init(el);
      const weeks = this.disasterResult.composite.weekly.map(w => `第${w.week}周`);
      const disasterColors = {
        cold_wave: "#1a73e8",
        snowstorm: "#00bcd4",
        drought: "#ff9800",
        blizzard: "#9c27b0",
        ecological: "#4caf50",
      };
      const series = Object.entries(this.disasterResult.disasters).map(([key, d]) => ({
        name: d.name,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2, color: disasterColors[key] },
        itemStyle: { color: disasterColors[key] },
        data: d.weekly.map(w => w.risk_score),
      }));
      // 综合风险加粗 + 三段置信度背景
      series.push({
        name: "综合",
        type: "line",
        smooth: true,
        symbol: "diamond",
        symbolSize: 8,
        lineStyle: { width: 3, color: "#c00", type: "dashed" },
        itemStyle: { color: "#c00" },
        data: this.disasterResult.composite.weekly.map(w => w.risk_score),
        markArea: {
          silent: true,
          data: [
            [{ xAxis: "第1周", itemStyle: { color: "rgba(52,168,83,0.08)" } }, { xAxis: "第2周" }],
            [{ xAxis: "第3周", itemStyle: { color: "rgba(249,171,0,0.08)" } }, { xAxis: "第4周" }],
            [{ xAxis: "第5周", itemStyle: { color: "rgba(234,67,53,0.08)" } }, { xAxis: "第12周" }],
          ],
        },
      });
      chart.setOption({
        tooltip: { trigger: "axis" },
        legend: { data: series.map(s => s.name), top: 5 },
        grid: { left: 50, right: 20, top: 50, bottom: 40 },
        xAxis: { type: "category", data: weeks, axisLabel: { interval: 0 } },
        yAxis: {
          type: "value",
          name: "风险分",
          min: 0, max: 100,
          axisLabel: { formatter: "{value}" },
          splitLine: { lineStyle: { type: "dashed" } },
        },
        series,
      });
      window.addEventListener("resize", () => chart.resize());
    },

    renderPortfolioScaleChart() {
      const chart = makeChart("chart-portfolio-scale");
      if (!chart || !this.portfolioProfile?.scale_distribution) return;
      const dist = this.portfolioProfile.scale_distribution;
      const names = Object.keys(dist);
      const values = Object.values(dist);
      chart.setOption({
        color: ["#2d7d4f"],
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: "3%", right: "6%", bottom: "3%", top: "10%", containLabel: true },
        xAxis: { type: "category", data: names, axisLabel: { color: "#666" } },
        yAxis: { type: "value", name: "农户数", axisLabel: { color: "#999" }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
        series: [{
          type: "bar",
          data: values.map(v => ({ value: v, itemStyle: { color: "#2d7d4f", borderRadius: [4, 4, 0, 0] } })),
          barWidth: "50%",
          label: { show: true, position: "top", color: "#333", fontSize: 13, fontWeight: 700 },
        }],
      });
    },

    renderPortfolioFarmersChart() {
      const chart = makeChart("chart-portfolio-farmers");
      if (!chart || !this.portfolioFarmers.length) return;
      // 取前15名（避免太挤）
      const top = this.portfolioFarmers.slice(0, 15);
      const names = top.map(f => f.farmer_name);
      const scores = top.map(f => f.credit_score);
      const colors = scores.map(s => s >= 85 ? "#2d7d4f" : s >= 70 ? "#d98a3a" : "#d44a4a");
      chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: "3%", right: "6%", bottom: "3%", top: "10%", containLabel: true },
        xAxis: { type: "category", data: names, axisLabel: { color: "#666", rotate: 30 } },
        yAxis: { type: "value", name: "增信分", min: 0, max: 100, axisLabel: { color: "#999" }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
        series: [{
          type: "bar",
          data: scores.map((v, i) => ({ value: v, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })),
          barWidth: "50%",
          label: { show: true, position: "top", color: "#333", fontSize: 12, fontWeight: 600 },
        }],
      });
    },

    scoreLevelClass(score) {
      if (score >= 80) return "score-green";
      if (score >= 65) return "score-blue";
      if (score >= 50) return "score-yellow";
      return "score-red";
    },

    verifyScoreClass(score) {
      if (score >= 80) return "score-green";
      if (score >= 60) return "score-blue";
      if (score >= 40) return "score-yellow";
      return "score-red";
    },

    toggleCoopDetail(name) {
      if (this.coopDetailOpen === name) {
        this.coopDetailOpen = null;
        this.coopDetailRow = null;
      } else {
        this.coopDetailOpen = name;
        this.coopDetailRow = this.coopRanking.find(c => c.name === name) || null;
      }
    },

    legalStatusClass(row) {
      const s = row?.verification?.dimensions?.legal_representative?.status;
      if (s === "warning") return "coop-check-err";
      if (s === "info") return "coop-check-warn";
      if (s === "missing") return "coop-check-na";
      return "coop-check-ok";
    },

    legalStatusLabel(row) {
      const s = row?.verification?.dimensions?.legal_representative?.status;
      if (s === "warning") return "关联风险";
      if (s === "info") return "有关联";
      if (s === "missing") return "无数据";
      return "唯一";
    },

    historyStatusClass(row) {
      const s = row?.verification?.dimensions?.name_history?.status;
      if (s === "warning") return "coop-check-err";
      if (s === "info") return "coop-check-warn";
      return "coop-check-ok";
    },

    statusClass(row) {
      const s = row?.verification?.dimensions?.business_status?.status;
      if (s === "warning") return "coop-check-err";
      return "coop-check-ok";
    },

    startHero() {
      if (this.heroTimer) return;
      this.heroTimer = setInterval(() => { this.heroIndex = (this.heroIndex + 1) % this.heroSlides.length; }, 5000);
    },

    stopHero() {
      if (this.heroTimer) { clearInterval(this.heroTimer); this.heroTimer = null; }
    },

    moduleIcon(code) {
      const icons = { "eco-monitor":"EO", "grass-balance":"GB", "supply-chain":"SC", "green-finance":"GF", "insurance":"IN", "green-perf":"GP", "livelihood":"ML" };
      return icons[code] || "⊟";
    },

    dataAssetPurpose(key) {
      const map = {
        weather_data: "识别寒潮、降水、风速等环境风险，支撑贷后预警。",
        remote_sensing_data: "识别 NDVI、积雪、退化和载畜量变化，形成绿色信贷证据。",
        forage_supply_demand: "作为宏观饲草供需背景，不参与县域月度模型训练。",
        business_subjects: "形成工行评估对象池，用于准入申请和客户经理复核。",
        finance_credit: "记录授信、用信、还款、逾期和保险覆盖，支撑额度与处置建议。",
        risk_event_labels: "接入灾害、理赔、逾期标签后，才可升级为真实监督预测。",
        insurance_claims: "把查勘和理赔结果回流工行贷后策略，形成风险缓释证据。",
        supply_chain_orders: "核验贷款资金用途是否进入饲草、活体交易和物流履约环节。",
        supply_chain_payments: "保留工行定向支付和回款核验链路，支撑资金闭环。",
        post_loan_workflow: "承接客户经理的人工复核、贷后核查、处置记录和下一步动作。",
        green_performance_metrics: "汇总绿色信贷、支持牧户、减灾减损等答辩展示指标。",
      };
      return map[key] || "用于补充工行绿色金融风控证据链。";
    },

    dataAssetStatusClass(asset) {
      return asset.sample_rows ? "warn" : asset.row_count ? "ok" : "empty";
    },

    moduleFallbackValue(code) {
      const map = {
        "eco-monitor": "为工行绿色信贷准入、额度管理和保险协同提供环境风险底座。",
        "grass-balance": "把生态约束转化为工行绿色金融可识别、可核验、可跟踪的经营指标。",
        "supply-chain": "围绕工行贷款资金用途，连接饲草采购、活体交易、物流、回款和授信台账。",
        "green-finance": "帮助工行从看抵押物转向看产业数据、生态数据、保险保障和经营现金流。",
        "insurance": "把保险作为工行贷前增信、贷中保障和贷后减损的风险缓释工具。",
        "green-perf": "沉淀绿色信贷、生态改善、风险减量和普惠覆盖成效。",
        "livelihood": "体现项目对边疆地区稳定、牧民增收、乡村振兴和民族团结的支撑作用。",
      };
      return map[code] || "服务工行高原畜牧绿色金融风控业务。";
    },

    moduleFallbackFeatures(code) {
      const map = {
        "green-finance": ["牧户和合作社信用画像", "活体资产确权和经营能力评估", "草场生态风险、气候风险、交易履约和保险覆盖纳入授信评分", "贷款用途绑定、贷中资金流向监控", "贷后动态预警和续贷、展期、减额建议"],
        "livelihood": ["重点区域产业风险监测", "牧户收入和产业稳定性趋势分析", "灾害前预警、灾害中处置、灾害后金融保险支持跟踪", "为政府、银行、保险、合作社提供协同工作台"],
      };
      return map[code] || ["数据接入", "工行准入", "贷后预警", "处置回流"];
    },

    prevModule() {
      if (!this.data || !this.selectedModule) return;
      const idx = this.businessModules.findIndex((m) => m.code === this.selectedModule.code);
      this.selectedModule = this.businessModules[(idx - 1 + this.businessModules.length) % this.businessModules.length];
    },

    nextModule() {
      if (!this.data || !this.selectedModule) return;
      const idx = this.businessModules.findIndex((m) => m.code === this.selectedModule.code);
      this.selectedModule = this.businessModules[(idx + 1) % this.businessModules.length];
    },

    onScroll() {
      this.scrolled = window.scrollY > 50;
    },

    async loadModelData() {
      try { this.modelStatus = await api.modelStatus(); } catch (_) {}
      try { this.modelPrediction = await api.modelPredict(); } catch (_) {}
      try { this.dataQuality = await api.dataQuality(); } catch (_) {}
      try { this.integrations = await api.integrationsStatus(); } catch (_) {}
      try { this.forageSummary = await api.forageSummary(); } catch (_) {}
      try { this.closedLoop = await api.closedLoop(); } catch (_) { this.closedLoop = this.data?.closed_loop || {}; }
      if (!this.selectedPublicRiskRegionId && this.publicRiskHeatRows.length) {
        this.selectedPublicRiskRegionId = this.publicRiskHeatRows[0].region_id;
      }
      if (!this.selectedRegionId && this.regionalRiskRows.length) {
        this.selectedRegionId = this.regionalRiskRows[0].region_id;
      }
      if (!this.selectedAssessmentKey && this.assessmentObjects.length) {
        this.selectedAssessmentKey = this.assessmentObjects[0].key;
        if (this.assessmentObjects[0].type === "region") this.selectedRegionId = this.assessmentObjects[0].key;
      }
      this.renderDashboardChartsSoon();
      this.renderOverviewChartsSoon();
      this.renderDataChartsSoon();
      this.loadLiveWeather();
    },
    renderDashboardChartsSoon() {
      if (this.page !== "dashboard") return;
      this.$nextTick(() => {
        renderDashboardTrend(this.selectedAssessment?.raw?.history?.length ? this.selectedAssessment.raw.history.map((row) => ({
          month: row.month,
          avg: Number(row.predicted_score || 0),
          max: Number(row.predicted_score || 0),
        })) : this.riskTrendRows);
        renderPublicRiskTrend(this.riskTrendRows);
        renderDashboardDrivers(this.selectedAssessment?.driver_details || this.selectedRegion?.driver_details || []);
        renderDashboardQuality(this.qualityRows);
        renderPublicRadar(this.selectedPublicRiskRow);
      });
    },
    renderOverviewChartsSoon() {
      if (this.page !== "overview") return;
      this.$nextTick(() => {
        renderOverviewMix(this.dataQuality?.total || {});
        renderOverviewModel(this.regionalRiskRows);
      });
    },
    renderDataChartsSoon() {
      if (this.page !== "data") return;
      this.$nextTick(() => {
        renderDataQuality(this.qualityRows);
        renderWeatherTrend(this.data?.weather || []);
        renderRemoteTrend(this.data?.remote_sensing || []);
        this.initEvidenceMap();
      });
    },
    formatNumber(val) {
      const n = Number(val) || 0;
      return n.toLocaleString("zh-CN");
    },
    formatWan(yuan) {
      const n = Number(yuan) || 0;
      return (n / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
    },
    formatMoney(yuan) {
      const n = Number(yuan) || 0;
      return Math.round(n).toLocaleString("zh-CN");
    },
    formatKg(kg) {
      const n = Number(kg) || 0;
      return Math.round(n).toLocaleString("zh-CN");
    },
    // ---- 授信与贷后工作台 ----
    async loadCreditCases() {
      try {
        const d = await api.creditCases();
        this.creditCases = Array.isArray(d.cases) ? d.cases : [];
        if (this.creditCases.length && !this.creditCaseId) {
          // 默认进入主案例（班戈县绿色牧业合作社），优先选非阻断案例
          const main = this.creditCases.find((c) => !c.blocked) || this.creditCases[0];
          this.creditCaseId = main.id;
          await this.loadCreditCase();
          await this.runCreditEvaluation();
        }
      } catch (e) {
        this.creditError = "案例列表加载失败：" + (e && e.message ? e.message : e);
      }
    },
    loadCreditCase() {
      this._skipCreditFormWatch = true;
      this.creditResult = null;
      this.creditError = "";
      this.creditUserModified = false;
      this.creditForm = { total_mu: 42000, own_funds_wan: 35, product_cap_wan: 120, dscr_threshold: 1.2 };
      this.$nextTick(() => { this._skipCreditFormWatch = false; });
      const selected = this.creditCases.find((c) => c.id === this.creditCaseId);
      if (selected && selected.blocked) this.runCreditEvaluation();
    },
    buildCreditInputs() {
      if (!this.creditUserModified) return {};
      const total = Number(this.creditForm.total_mu) || 0;
      const inputs = {};
      // 42000 样例按 24000/14000/4000 拆分；用户修改总面积后按原比例拆分
      inputs.pasture = {
        total_mu: total,
        summer_mu: Math.round(total * (24000 / 42000)),
        winter_mu: Math.round(total * (14000 / 42000)),
        non_use_mu: Math.round(total * (4000 / 42000)),
      };
      inputs.operating = { own_purchase_funds_yuan: (Number(this.creditForm.own_funds_wan) || 0) * 10000 };
      inputs.credit = {
        product_cap_yuan: (Number(this.creditForm.product_cap_wan) || 0) * 10000,
        dscr_threshold: Number(this.creditForm.dscr_threshold) || 1.2,
      };
      return inputs;
    },
    async runCreditEvaluation() {
      if (this.creditEvaluating) return; // 同一时间只允许一个测算请求
      this.creditEvaluating = true;
      this.creditError = "";
      this.creditResult = null;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10000); // 10 秒超时
      try {
        const inputs = this.buildCreditInputs();
        const res = await api.creditEvaluate(this.creditCaseId, inputs || {});
        clearTimeout(timer);
        if (!res.ok) {
          let msg = `请求失败（${res.status}）`;
          try {
            const body = await res.json();
            const detail = body && body.detail;
            if (typeof detail === "string") msg = detail;
            else if (detail && detail.message) msg = detail.message;
          } catch (_) { /* 忽略响应体解析失败 */ }
          if (res.status === 422) msg = "输入校验失败：" + msg;
          if (res.status === 500) msg = "案例数据不可用（credit_case_unavailable）";
          this.creditError = msg;
          return;
        }
        this.creditResult = await res.json();
      } catch (e) {
        clearTimeout(timer);
        this.creditError = e && e.name === "AbortError"
          ? "测算请求超时（10 秒），请重试"
          : "网络错误：" + (e && e.message ? e.message : e);
      } finally {
        this.creditEvaluating = false;
      }
    },
    percent(val) {
      return `${Math.round((Number(val) || 0) * 100)}%`;
    },
    formatFixed(val, digits = 1) {
      if (val === null || val === undefined || val === "") return "-";
      const n = Number(String(val ?? "").replace("%", ""));
      return Number.isFinite(n) ? n.toFixed(digits) : "-";
    },
    levelForScore(score) {
      const n = Number(score) || 0;
      if (n >= 70) return "高风险";
      if (n >= 55) return "中风险";
      return "低风险";
    },
    decisionForScore(score, overdue = 0) {
      const n = Number(score) || 0;
      if (overdue > 0 || n >= 70) return "暂停增额";
      if (n >= 60) return "贷后核查";
      if (n >= 55) return "人工复核";
      return "持续监测";
    },
    creditDecisionBrief(type, score, row = {}) {
      const n = Number(score) || 0;
      const overdue = Number(row.overdue ?? row.overdue_times ?? 0) || 0;
      if (type === "region") {
        if (n >= 70) return { admission: "区域收紧", limitPolicy: "系数0.80" };
        if (n >= 55) return { admission: "审慎准入", limitPolicy: "系数0.90" };
        return { admission: "正常准入", limitPolicy: "系数1.00" };
      }
      if (row.needsVerification) return { admission: "资料待核验", limitPolicy: "不生成额度建议" };
      const line = Number(row.line ?? row.credit_line ?? row.credit_value ?? 0) || 0;
      const used = Number(row.used ?? row.used_credit ?? 0) || 0;
      const insurance = Number(String(row.insurance ?? row.insurance_coverage ?? "0").replace("%", "")) || 0;
      let admission = "建议准入";
      let factor = insurance >= 80 && Number(row.usage || 0) < 0.75 ? 1.1 : 1.05;
      if (overdue > 0 || n >= 70) {
        admission = "暂缓新增";
        factor = 0.85;
      } else if (n >= 60) {
        admission = "审慎准入";
        factor = 0.95;
      } else if (n >= 55) {
        admission = "复核后准入";
        factor = 1;
      }
      const proposedLine = line ? Math.max(used, Math.round(line * factor)) : 0;
      return {
        admission,
        limitPolicy: proposedLine ? `建议${this.formatNumber(proposedLine)}万` : "额度待测算",
      };
    },
    buildCreditDecisionCards(assessment) {
      if (!assessment) return [];
      const score = Number(assessment.score) || 0;
      const state = this.riskLevelClass(assessment.level);
      if (assessment.type === "region") {
        const brief = this.creditDecisionBrief("region", score, assessment.raw || {});
        const factor = score >= 70 ? 0.8 : score >= 55 ? 0.9 : 1;
        const exposure = Number(assessment.exposure || 0) || 0;
        const adjustedExposure = exposure ? Math.round(exposure * factor) : 0;
        const reviewCycle = score >= 70 ? "7日核查" : score >= 55 ? "月度复核" : "月度监测";
        const disposal = score >= 70 ? "暂停区域增额" : score >= 55 ? "逐户复核" : "持续观察";
        return [
          {
            key: "admission",
            step: "01",
            title: "能不能贷",
            value: brief.admission,
            note: "县域维度只给准入策略，不替代单户审批。",
            basis: `${assessment.primary_driver || "风险因子"}驱动，风险分 ${score.toFixed(1)}`,
            state,
          },
          {
            key: "limit",
            step: "02",
            title: "贷多少",
            value: brief.limitPolicy,
            note: adjustedExposure ? `参考敞口由 ${this.formatNumber(exposure)}万 调整为 ${this.formatNumber(adjustedExposure)}万。` : "待接入该县域真实授信敞口后测算。",
            basis: "用于区域额度池和增额节奏控制。",
            state: score >= 70 ? "danger" : score >= 55 ? "warn" : "safe",
          },
          {
            key: "postLoan",
            step: "03",
            title: "贷后有没有风险",
            value: reviewCycle,
            note: "联动气象、遥感、主体用信和还款记录形成贷后预警。",
            basis: "当前为真实环境数据 + 规则弱标签。",
            state: score >= 55 ? "warn" : "safe",
          },
          {
            key: "disposal",
            step: "04",
            title: "出风险怎么处置",
            value: disposal,
            note: "推送客户经理核查、保险协同或暂停增额动作。",
            basis: "处置建议用于比赛演示，不代表真实工行审批结论。",
            state,
          },
        ];
      }

      const row = assessment.raw || {};
      if (row.needsVerification) {
        return [
          { key: "admission", step: "01", title: "能不能贷", value: "资料待核验", note: "当前仅有牲畜资产登记参考记录。", basis: "不含授信审批、还款和保险合同字段。", state: "warn" },
          { key: "limit", step: "02", title: "贷多少", value: "不生成额度建议", note: "先核验授信、还款和保险合同资料。", basis: "资产登记不能单独作为额度依据。", state: "warn" },
          { key: "postLoan", step: "03", title: "贷后有没有风险", value: "人工复核", note: "环境信号只用于筛查和任务派发。", basis: "需客户经理补充核验记录。", state: "warn" },
          { key: "disposal", step: "04", title: "出风险怎么处置", value: "建立核验任务", note: "核对耳标、保险合同和实际经营资料。", basis: "不输出自动审批或赔付结论。", state: "warn" },
        ];
      }
      const line = Number(row.line || 0) || 0;
      const used = Number(row.used || 0) || 0;
      const usage = Number(row.usage || 0) || 0;
      const overdue = Number(row.overdue || 0) || 0;
      const insurance = Number(String(row.insurance || "0").replace("%", "")) || 0;
      const brief = this.creditDecisionBrief("subject", score, row);
      const proposedLine = Number(String(brief.limitPolicy).replace(/[^\d.]/g, "")) || line;
      const availableAfter = Math.max(proposedLine - used, 0);
      const postLoan = overdue > 0 || score >= 70 ? "7日内核查" : score >= 60 ? "纳入观察名单" : score >= 55 ? "月度复核" : "自动监测";
      const disposal = overdue > 0 ? "还款核验+银保协同" : score >= 70 ? "暂停增额+现场核查" : score >= 55 ? "额度复核+补充材料" : "持续监测";
      return [
        {
          key: "admission",
          step: "01",
          title: "能不能贷",
          value: brief.admission,
          note: `${row.region || "所在县域"}，还款状态：${row.repayment || "-"}。`,
          basis: `用信率 ${this.percent(usage)}，逾期 ${overdue} 次，保险 ${row.insurance || "-"}。`,
          state,
        },
        {
          key: "limit",
          step: "02",
          title: "贷多少",
          value: brief.limitPolicy,
          note: `当前授信 ${this.formatNumber(line)}万，已用 ${this.formatNumber(used)}万，建议可用 ${this.formatNumber(availableAfter)}万。`,
          basis: insurance >= 80 ? "保险覆盖较充分，可作为额度缓释依据。" : "保险覆盖偏低，增额前建议补充保障。",
          state: score >= 70 || overdue > 0 ? "danger" : score >= 55 ? "warn" : "safe",
        },
        {
          key: "postLoan",
          step: "03",
          title: "贷后有没有风险",
          value: postLoan,
          note: `重点监测 ${assessment.primary_driver || "主风险因子"}、用信率和回款状态。`,
          basis: row.post_loan_action || "由客户经理工作流生成核查任务。",
          state: score >= 55 || overdue > 0 ? "warn" : "safe",
        },
        {
          key: "disposal",
          step: "04",
          title: "出风险怎么处置",
          value: disposal,
          note: "将处置动作沉淀为贷后记录，并回流下一轮评分。",
          basis: "脱敏样例测算，非真实授信审批或监管报送结论。",
          state,
        },
      ];
    },
    riskLevelClass(level) {
      return String(level).includes("高") ? "danger" : String(level).includes("中") ? "warn" : "safe";
    },
    latestRowByRegion(rows, regionId, dateField) {
      return [...(rows || [])]
        .filter((row) => row.region_id === regionId)
        .sort((a, b) => String(b[dateField] || "").localeCompare(String(a[dateField] || "")))[0] || null;
    },
    buildRegionAssessment(row) {
      const score = Number(row.predicted_score || 0);
      return {
        type: "region",
        key: row.region_id,
        title: row.region_name,
        region_id: row.region_id,
        score,
        level: this.levelForScore(score),
        decision: this.decisionForScore(score),
        exposure: row.exposure || 0,
        month: row.month || "-",
        primary_driver: row.primary_driver || "-",
        driver_details: row.driver_details || [],
        raw: row,
        metrics: [
          { label: "评估月份", value: row.month || "-" },
          { label: "估算敞口", value: `${this.formatNumber(row.exposure || 0)}万` },
          { label: "均值/峰值", value: `${row.avg_score || "-"} / ${row.max_score || "-"}` },
          { label: "主风险因子", value: row.primary_driver || "-" },
        ],
      };
    },
    buildSubjectAssessment(row) {
      const region = this.regionalRiskRows.find((item) => item.region_id === row.region_id) || {};
      const score = Number(row.riskScore || 0);
      const financePart = Math.min(40, row.usage * 28 + row.overdue * 8);
      const regionPart = Math.min(30, Number(region.predicted_score || 0) * 0.3);
      const businessPart = Math.min(25, Math.max(0, 100 - Number(row.score || 0)) * 0.4);
      const insuranceNum = Number(String(row.insurance || "").replace("%", "")) || 0;
      const insurancePart = Math.min(20, Math.max(0, 80 - insuranceNum) * 0.35);
      return {
        type: "subject",
        key: row.name,
        title: row.name,
        region_id: row.region_id,
        score,
        level: this.levelForScore(score),
        decision: this.decisionForScore(score, row.overdue),
        exposure: row.used,
        month: region.month || "-",
        primary_driver: row.overdue > 0 ? "逾期记录" : row.regionRiskDriver,
        driver_details: [
          { key: "finance", name: "用信", value: Number(financePart.toFixed(1)), detail: `用信率 ${this.percent(row.usage)}` },
          { key: "region", name: "县域", value: Number(regionPart.toFixed(1)), detail: `县域风险 ${Number(region.predicted_score || 0).toFixed(1)}` },
          { key: "business", name: "经营", value: Number(businessPart.toFixed(1)), detail: `主体评分 ${row.score}` },
          { key: "insurance", name: "保险", value: Number(insurancePart.toFixed(1)), detail: `覆盖率 ${row.insurance}` },
        ],
        raw: row,
        metrics: [
          { label: "所在县域", value: row.region || "-" },
          { label: "授信/用信", value: `${this.formatNumber(row.line)} / ${this.formatNumber(row.used)}万` },
          { label: "用信率", value: this.percent(row.usage) },
          { label: "还款状态", value: row.repayment || "-" },
        ],
      };
    },
    selectAssessment(item) {
      if (!item) return;
      this.assessmentMode = item.type;
      this.selectedAssessmentKey = item.key;
      if (item.type === "region") {
        this.selectedRegionId = item.key;
      } else if (item.raw?.region_id) {
        this.selectedRegionId = item.raw.region_id;
      }
      this.renderDashboardChartsSoon();
    },
    selectPublicRiskRow(row) {
      if (!row) return;
      this.selectedPublicRiskRegionId = row.region_id;
      this.selectedRegionId = row.region_id;
      this.$nextTick(() => renderPublicRadar(this.selectedPublicRiskRow));
    },
    async initEvidenceMap() {
      await this.$nextTick();
      if (!this.mapConfig) {
        try { this.mapConfig = await api.amapMapConfig(); } catch (err) { this.amapError = `地图配置读取失败：${err.message || err}`; }
      }
      if (!this.selectedMapRegionId && this.mapRegions.length) {
        this.selectedMapRegionId = this.mapRegions[0].id;
      }
      if (!this.mapConfig?.configured || !this.mapConfig?.key) return;
      try {
        await this.loadAmapScript();
        this.buildEvidenceMap();
        this.fetchMapWeather();
      } catch (err) {
        try {
          this.disposeEvidenceMap();
          this.buildEvidenceMap();
          this.fetchMapWeather();
        } catch (retryErr) {
          this.amapError = `高德地图加载失败：${retryErr.message || retryErr}`;
        }
      }
    },
    loadAmapScript() {
      if (window.AMap) return Promise.resolve();
      if (this.mapConfig?.security_js_code) {
        window._AMapSecurityConfig = { securityJsCode: this.mapConfig.security_js_code };
      }
      if (window.__amapLoadingPromise) return window.__amapLoadingPromise;
      window.__amapLoadingPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(this.mapConfig.key)}&plugin=AMap.Scale,AMap.ToolBar,AMap.ControlBar`;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("AMap JS API script load failed"));
        document.head.appendChild(script);
      });
      return window.__amapLoadingPromise;
    },
    buildEvidenceMap() {
      const dom = document.getElementById("amap-evidence-map");
      if (!dom || !window.AMap) return;
      const selected = this.selectedMapRegion;
      const center = selected ? [selected.lng, selected.lat] : this.mapConfig.center;
      if (!this.evidenceMap) {
        this.evidenceMap = new AMap.Map(dom, {
          viewMode: "3D",
          pitch: this.selectedMapLayer === "terrain" ? 46 : 28,
          rotation: 0,
          zoom: this.selectedMapLayer === "terrain" ? 6.2 : 5,
          center,
          mapStyle: "amap://styles/normal",
          layers: [new AMap.TileLayer()],
          doubleClickZoom: false,
        });
        this.evidenceMap.addControl(new AMap.Scale());
        this.evidenceMap.addControl(new AMap.ToolBar({ position: { right: "14px", top: "70px" } }));
        this.evidenceMap.addControl(new AMap.ControlBar({ position: { right: "14px", top: "130px" } }));
      }
      this.syncMapLayers();
      this.renderEvidenceMarkers();
      if (selected) this.evidenceMap.setCenter([selected.lng, selected.lat]);
      this.amapReady = true;
      this.amapError = "";
    },
    syncMapLayers() {
      if (!this.evidenceMap || !window.AMap) return;
      this.evidenceMapLayers = {};
      this.evidenceMap.setPitch(this.selectedMapLayer === "terrain" ? 46 : 28);
      this.evidenceMap.setMapStyle("amap://styles/normal");
      if (this.selectedMapLayer === "satellite") {
        this.evidenceMapLayers.satellite = new AMap.TileLayer.Satellite();
        this.evidenceMapLayers.roadNet = new AMap.TileLayer.RoadNet();
        this.evidenceMap.setLayers([this.evidenceMapLayers.satellite, this.evidenceMapLayers.roadNet]);
      } else {
        this.evidenceMapLayers.standard = new AMap.TileLayer();
        this.evidenceMap.setLayers([this.evidenceMapLayers.standard]);
      }
      this.renderEvidenceMarkers();
    },
    renderEvidenceMarkers() {
      if (!this.evidenceMap || !window.AMap) return;
      if (this.evidenceMapMarkers.length) {
        try {
          this.evidenceMap.remove(this.evidenceMapMarkers);
        } catch (_) {
          this.evidenceMapMarkers.forEach((marker) => {
            try { marker.setMap(null); } catch (_) {}
          });
        }
      }
      this.evidenceMapMarkers = this.mapRegions.map((region) => {
        const score = Number(region.risk_score || 0);
        const cls = score >= 70 ? "high" : score >= 55 ? "mid" : "low";
        const altitude = Number(region.altitude || 0);
        const label = this.selectedMapLayer === "terrain" && altitude ? `${Math.round(altitude)}m` : Math.round(score || 0);
        const extraClass = this.selectedMapLayer === "terrain" ? " altitude" : "";
        const marker = new AMap.Marker({
          position: [region.lng, region.lat],
          anchor: "center",
          zIndex: this.selectedMapRegionId === region.id ? 120 : 100,
          content: `<div class="geo-marker ${cls}${extraClass}" title="${region.name}" role="button" tabindex="-1"><span>${label}</span></div>`,
          extData: region,
        });
        marker.on("click", (event) => {
          event?.originEvent?.stopPropagation?.();
          this.selectMapRegion(region, false);
        });
        marker.on("dblclick", (event) => {
          event?.originEvent?.stopPropagation?.();
          this.selectMapRegion(region, false);
        });
        return marker;
      });
      this.evidenceMap.add(this.evidenceMapMarkers);
      if (this.evidenceMapMarkers.length && !this.selectedMapRegion) {
        this.evidenceMap.setFitView(this.evidenceMapMarkers, false, [50, 50, 50, 50]);
      }
    },
    disposeEvidenceMap() {
      if (this.evidenceMapMarkers.length) {
        this.evidenceMapMarkers.forEach((marker) => {
          try { marker.setMap(null); } catch (_) {}
        });
      }
      this.evidenceMapMarkers = [];
      this.evidenceMapLayers = {};
      if (this.evidenceMap) {
        try { this.evidenceMap.destroy(); } catch (_) {}
      }
      this.evidenceMap = null;
      this.amapReady = false;
      this.amapError = "";
    },
    switchMapLayer(layer) {
      this.selectedMapLayer = layer;
      this.$nextTick(() => {
        if (this.evidenceMap) {
          this.syncMapLayers();
          if (layer === "terrain" && this.selectedMapRegion) this.selectMapRegion(this.selectedMapRegion, false);
        } else {
          this.initEvidenceMap();
        }
      });
    },
    focusMapRegion(region) {
      if (!region || !this.evidenceMap) return;
      const currentZoom = Number(this.evidenceMap.getZoom?.() || 5);
      const targetZoom = Math.min(Math.max(currentZoom + 1, 6.8), this.selectedMapLayer === "terrain" ? 8.6 : 9);
      this.evidenceMap.setPitch(this.selectedMapLayer === "terrain" ? 46 : 28);
      this.evidenceMap.setZoomAndCenter(targetZoom, [region.lng, region.lat], false, 500);
    },
    selectMapRegion(region, focus = false) {
      if (!region) return;
      this.selectedMapRegionId = region.id;
      this.selectedRegionId = region.id;
      this.renderEvidenceMarkers();
      if (focus) this.focusMapRegion(region);
      this.fetchMapWeather();
    },
    async fetchMapWeather() {
      const region = this.selectedMapRegion;
      if (!region) return;
      const requestId = ++this.mapWeatherRequestId;
      this.mapWeatherLoading = true;
      this.selectedMapWeather = null;
      this.mapWeatherError = "";
      try {
        const payload = await api.amapWeather(region.name);
        if (requestId !== this.mapWeatherRequestId) return;
        const live = payload?.raw?.lives?.[0] || null;
        if (payload?.ok && live) {
          this.selectedMapWeather = { ...live, provider: "高德天气" };
        } else {
          const amapInfo = payload?.raw?.info || payload?.message || "高德天气未返回实时数据";
          const open = await api.openMeteoNow(region.lat, region.lng);
          if (requestId !== this.mapWeatherRequestId) return;
          const now = open?.current || null;
          if (open?.ok && now) {
            this.selectedMapWeather = { ...now, provider: "Open-Meteo 开放天气" };
          } else {
            this.mapWeatherError = open?.message || amapInfo;
          }
        }
      } catch (err) {
        if (requestId !== this.mapWeatherRequestId) return;
        this.mapWeatherError = err?.message || "实时天气请求失败";
        this.selectedMapWeather = null;
      }
      if (!this.selectedMapWeather && region.weather) {
        this.selectedMapWeather = {
          weather: "本地气象",
          temperature: region.weather.temperature_c,
          reporttime: region.weather.observed_at,
          provider: "CMFD 本地数据",
        };
        if (!this.mapWeatherError) this.mapWeatherError = "外部实时天气不可用，已回退本地气象";
      }
      this.mapWeatherLoading = false;
    },
    startWeatherAutoRefresh() {
      this.stopWeatherAutoRefresh();
      this.mapWeatherTimer = window.setInterval(() => {
        if (this.page === "data" && this.selectedMapRegion) this.fetchMapWeather();
      }, this.weatherRefreshMs);
      this.liveWeatherTimer = window.setInterval(() => {
        this.loadLiveWeather();
      }, this.weatherRefreshMs);
    },
    stopWeatherAutoRefresh() {
      if (this.mapWeatherTimer) window.clearInterval(this.mapWeatherTimer);
      if (this.liveWeatherTimer) window.clearInterval(this.liveWeatherTimer);
      this.mapWeatherTimer = null;
      this.liveWeatherTimer = null;
    },
    handleVisibilityChange() {
      if (document.visibilityState !== "visible") return;
      this.loadLiveWeather();
      if (this.page === "data" && this.selectedMapRegion) this.fetchMapWeather();
    },
    async trainModel() {
      this.modelTraining = true;
      try {
        this.modelStatus = await api.modelTrain();
        this.modelPrediction = await api.modelPredict();
        try { this.dataQuality = await api.dataQuality(); } catch (_) {}
        try { this.integrations = await api.integrationsStatus(); } catch (_) {}
        this.renderDashboardChartsSoon();
      } catch (_) {}
      this.modelTraining = false;
    },
    async loadLiveWeather() {
      try { this.liveWeather = await api.openMeteoNow(31.36, 90.01); } catch (_) {}
    },

    async init() {
      const hash = window.location.hash.replace("#", "");
      const valid = ["home","dashboard","overview","modules","data","roadmap","insurance","supply-chain","green-performance","livelihood","cooperative-ranking","insurance-portfolio","disaster-forecast"];
      if (hash && valid.includes(hash)) this.page = hash;

      this.data = await api.platform();
      if (Array.isArray(this.data.slides) && this.data.slides.length) {
        this.heroSlides = this.data.slides.map((slide, idx) => ({
          scene: slide.scene || ["snow", "grassland", "river", "sunset"][idx % 4],
          kicker: slide.kicker || "",
          title: slide.title || "",
          desc: slide.desc || "",
          image: slide.image || "",
        }));
        this.heroIndex = 0;
      }
      if (!this.selectedModule) this.selectedModule = this.businessModules[0] || this.data.modules[0];
      this.closedLoop = this.data?.closed_loop || {};
      await this.loadModelData();
      this.loadCreditCases(); // 授信与贷后工作台默认加载主案例并自动测算

      this.loading = false;
      if (this.page === "home") this.startHero();

      await this.$nextTick();
      if (this.page === "dashboard") {
        this.renderDashboardChartsSoon();
      }
      if (this.page === "overview") this.renderOverviewChartsSoon();
      if (this.page === "data") { this.renderDataChartsSoon(); this.loadWarningData(); }
      if (this.page === "data" && this.dataTab === "risk") renderRiskChart(this.data?.risk_assessment);

      window.addEventListener("hashchange", () => {
        const h = window.location.hash.replace("#", "");
        if (h && valid.includes(h) && this.page !== h) this.navigate(h);
      });
      window.addEventListener("scroll", this.onScroll);
      document.addEventListener("visibilitychange", this.handleVisibilityChange);
      this.startWeatherAutoRefresh();
    },
  },

  watch: {
    page(p, oldPage) {
      if (oldPage === "data" && p !== "data") this.disposeEvidenceMap();
      if (p === "dashboard") {
        this.$nextTick(() => {
          this.loadModelData();
          if (!this.creditCases.length) this.loadCreditCases();
        });
      }
      if (p === "overview") this.$nextTick(() => this.renderOverviewChartsSoon());
      if (p === "data") this.$nextTick(() => this.renderDataChartsSoon());
      if (p === "data" && this.dataTab === "risk") this.$nextTick(() => renderRiskChart(this.data?.risk_assessment));
    },
    creditForm: {
      deep: true,
      handler() {
        if (this._skipCreditFormWatch) return;
        this.creditUserModified = true;
      },
    },
    dataTab(t) {
      if (t === "risk") this.$nextTick(() => renderRiskChart(this.data?.risk_assessment));
    },
    assessmentMode() {
      this.$nextTick(() => this.renderDashboardChartsSoon());
    },
    selectedAssessmentKey() {
      this.$nextTick(() => this.renderDashboardChartsSoon());
    },
    assessmentSearch() {
      this.$nextTick(() => this.renderDashboardChartsSoon());
    },
  },

  async mounted() { await this.init(); },

  beforeUnmount() {
    this.stopHero();
    this.stopWeatherAutoRefresh();
    window.removeEventListener("scroll", this.onScroll);
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
  },
}).mount("#app");
