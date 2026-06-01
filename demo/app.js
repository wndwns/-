const regionSelect = document.getElementById("region-select");
const metricsGrid = document.getElementById("metrics-grid");
const scoreBars = document.getElementById("score-bars");
const stageToggle = document.getElementById("stage-toggle");
const flowCard = document.getElementById("flow-card");
const borrowerTableBody = document.getElementById("borrower-table-body");
const alertsList = document.getElementById("alerts-list");
const roadmapList = document.getElementById("roadmap-list");
const dataSourceTags = document.getElementById("data-source-tags");

let activeStage = appData.stages[0].key;
let activeRegion = appData.regions[0].id;

function renderSources() {
  dataSourceTags.innerHTML = appData.dataSources
    .map((source) => `<span class="chip">${source}</span>`)
    .join("");
}

function renderRegionOptions() {
  regionSelect.innerHTML = appData.regions
    .map(
      (region) =>
        `<option value="${region.id}" ${region.id === activeRegion ? "selected" : ""}>${region.name}</option>`
    )
    .join("");
}

function renderMetrics() {
  const region = appData.regions.find((item) => item.id === activeRegion);
  metricsGrid.innerHTML = region.metrics
    .map(
      (metric) => `
        <article class="metric-card">
          <p class="metric-title">${metric.title}</p>
          <p class="metric-value">${metric.value}</p>
          <p class="metric-footnote">${metric.footnote}</p>
        </article>
      `
    )
    .join("");
}

function renderScoreBars() {
  scoreBars.innerHTML = appData.scoreDimensions
    .map(
      (item) => `
        <div class="score-row">
          <div class="score-row-header">
            <span>${item.name}</span>
            <span>${item.weight}%</span>
          </div>
          <div class="score-track">
            <div class="score-fill" style="width:${item.weight * 3.4}%"></div>
          </div>
          <div class="small-note">${item.detail}</div>
        </div>
      `
    )
    .join("");
}

function renderStageToggle() {
  stageToggle.innerHTML = appData.stages
    .map(
      (stage) => `
        <button class="stage-button ${stage.key === activeStage ? "active" : ""}" data-stage="${stage.key}">
          ${stage.label}
        </button>
      `
    )
    .join("");

  stageToggle.querySelectorAll("[data-stage]").forEach((button) => {
    button.addEventListener("click", () => {
      activeStage = button.dataset.stage;
      renderStageToggle();
      renderFlowCard();
    });
  });
}

function renderFlowCard() {
  const stage = appData.stages.find((item) => item.key === activeStage);
  flowCard.innerHTML = `
    <h3 class="flow-title">${stage.title}</h3>
    <p class="flow-copy">${stage.copy}</p>
    <div class="flow-list">
      ${stage.steps
        .map(
          (step, index) => `
            <div class="flow-item">
              <span class="flow-step">${index + 1}</span>
              <span>${step}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function getScoreClass(score) {
  if (score >= 80) return "good";
  if (score >= 70) return "mid";
  return "risk";
}

function getStatusClass(status) {
  if (status === "正常监控") return "safe";
  if (status === "关注回款") return "watch";
  return "risk";
}

function renderBorrowers() {
  borrowerTableBody.innerHTML = appData.borrowers
    .map(
      (item) => `
        <tr>
          <td>${item.name}</td>
          <td>${item.region}</td>
          <td>${item.cattle ? `${item.cattle} 头` : "供应链主体"}</td>
          <td>${item.credit}</td>
          <td><span class="score-pill ${getScoreClass(item.score)}">${item.score} 分</span></td>
          <td>${item.coverage}</td>
          <td><span class="status-pill ${getStatusClass(item.status)}">${item.status}</span></td>
        </tr>
      `
    )
    .join("");
}

function levelLabel(level) {
  if (level === "high") return "高风险";
  if (level === "mid") return "中风险";
  return "低风险";
}

function renderAlerts() {
  alertsList.innerHTML = appData.alerts
    .map(
      (alert) => `
        <article class="alert-card">
          <div class="alert-top">
            <h3 class="alert-title">${alert.title}</h3>
            <span class="alert-level ${alert.level}">${levelLabel(alert.level)}</span>
          </div>
          <p class="alert-desc">${alert.description}</p>
        </article>
      `
    )
    .join("");
}

function renderRoadmap() {
  roadmapList.innerHTML = appData.roadmap
    .map(
      (item) => `
        <article class="roadmap-card">
          <h3 class="roadmap-title">${item.title}</h3>
          <p class="roadmap-note">${item.note}</p>
        </article>
      `
    )
    .join("");
}

function bindEvents() {
  regionSelect.addEventListener("change", (event) => {
    activeRegion = event.target.value;
    renderMetrics();
  });
}

function init() {
  renderSources();
  renderRegionOptions();
  renderMetrics();
  renderScoreBars();
  renderStageToggle();
  renderFlowCard();
  renderBorrowers();
  renderAlerts();
  renderRoadmap();
  bindEvents();
}

init();
