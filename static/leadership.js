(function () {
  const API = {
    models: "/api/leadership-models",
    detail: (id) => `/api/leadership-models/${encodeURIComponent(id)}`,
    dimensions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/dimensions`,
    generateDimensions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/dimensions:generate`,
    descriptions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/descriptions`,
    generateDescriptions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/descriptions:generate`,
    anchors: (id) => `/api/leadership-models/${encodeURIComponent(id)}/anchors`,
    generateAnchors: (id) => `/api/leadership-models/${encodeURIComponent(id)}/anchors:generate`,
    export: (id, format) => `/api/leadership-models/${encodeURIComponent(id)}/export?format=${format}`,
  };

  const state = { currentModel: null, models: [] };

  const els = {};

  document.addEventListener("DOMContentLoaded", initLeadership);

  function initLeadership() {
    cacheElements();
    if (!els.form) {
      return;
    }
    bindEvents();
    renderModel(null);
  }

  function cacheElements() {
    const ids = {
      form: "leadership-form", reset: "leadership-reset", sourceFile: "leadership-source-file",
      sourceMeta: "leadership-source-meta", message: "leadership-message",
      workflow: "leadership-workflow", currentTitle: "leadership-current-title",
      currentMeta: "leadership-current-meta", context: "leadership-context",
      dimensions: "leadership-dimensions", descriptions: "leadership-descriptions",
      anchors: "leadership-anchors", generateDimensions: "leadership-generate-dimensions",
      saveDimensions: "leadership-save-dimensions", generateDescriptions: "leadership-generate-descriptions",
      saveDescriptions: "leadership-save-descriptions", generateAnchors: "leadership-generate-anchors",
      saveAnchors: "leadership-save-anchors", exportPdf: "leadership-export-pdf",
      exportDocx: "leadership-export-docx", historyReload: "leadership-history-reload",
      historyTbody: "leadership-history-tbody", historyEmpty: "leadership-history-empty",
    };
    Object.entries(ids).forEach(([key, id]) => {
      els[key] = document.getElementById(id);
    });
  }

  function bindEvents() {
    els.form.addEventListener("submit", createModel);
    els.reset.addEventListener("click", () => {
      els.form.reset();
      els.sourceMeta.textContent = "尚未选择文件";
      renderModel(null);
    });
    els.sourceFile.addEventListener("change", () => {
      const file = els.sourceFile.files && els.sourceFile.files[0];
      els.sourceMeta.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "尚未选择文件";
    });
    els.generateDimensions.addEventListener("click", () => runStage("generateDimensions"));
    els.saveDimensions.addEventListener("click", saveDimensions);
    els.generateDescriptions.addEventListener("click", () => runStage("generateDescriptions"));
    els.saveDescriptions.addEventListener("click", saveDescriptions);
    els.generateAnchors.addEventListener("click", () => runStage("generateAnchors"));
    els.saveAnchors.addEventListener("click", saveAnchors);
    els.exportPdf.addEventListener("click", () => exportModel("pdf"));
    els.exportDocx.addEventListener("click", () => exportModel("docx"));
    els.historyReload.addEventListener("click", loadLeadershipHistory);
    document.querySelectorAll('[data-page="leadership-models"]').forEach((button) => {
      button.addEventListener("click", loadLeadershipHistory);
    });
  }

  async function createModel(event) {
    event.preventDefault();
    clearMessage();
    setBusy(true);
    try {
      const formData = new FormData(els.form);
      const payload = await requestJson(API.models, { method: "POST", body: formData });
      renderModel(payload);
      showMessage("建模草稿已创建，可以生成维度框架。", "success");
    } catch (error) {
      showMessage(error.message || "创建建模草稿失败。", "error");
    } finally {
      setBusy(false);
    }
  }

  async function runStage(action) {
    if (!state.currentModel) {
      showMessage("请先创建建模草稿。", "error");
      return;
    }
    clearMessage();
    setBusy(true);
    try {
      const payload = await requestJson(API[action](state.currentModel.model_id), {
        method: "POST",
      });
      renderModel(payload);
      showMessage("阶段内容已生成，请审阅并确认。", "success");
    } catch (error) {
      showMessage(error.message || "生成失败。", "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveDimensions() {
    await saveStage("dimensions", collectDimensions());
  }

  async function saveDescriptions() {
    await saveStage("descriptions", collectDescriptions());
  }

  async function saveAnchors() {
    await saveStage("anchors", collectAnchors());
  }

  async function saveStage(stage, payload) {
    if (!state.currentModel) {
      return;
    }
    clearMessage();
    setBusy(true);
    try {
      const url = API[stage](state.currentModel.model_id);
      const result = await requestJson(url, { method: "PATCH", json: { [stage]: payload } });
      renderModel(result);
      showMessage("已确认当前阶段。", "success");
    } catch (error) {
      showMessage(error.message || "保存失败。", "error");
    } finally {
      setBusy(false);
    }
  }

  async function loadLeadershipHistory() {
    clearMessage();
    try {
      const payload = await requestJson(API.models, { method: "GET" });
      state.models = Array.isArray(payload.items) ? payload.items : [];
      renderHistory();
    } catch (error) {
      renderHistory([]);
      showMessage(error.message || "加载建模历史失败。", "error");
    }
  }

  async function viewModel(id) {
    try {
      const payload = await requestJson(API.detail(id), { method: "GET" });
      renderModel(payload);
      if (typeof showPage === "function") {
        showPage("leadership-model");
      }
    } catch (error) {
      showMessage(error.message || "加载模型失败。", "error");
    }
  }

  async function exportModel(format) {
    if (!state.currentModel || !state.currentModel.export_urls?.[format]) {
      showMessage("请先确认行为锚定后再导出。", "error");
      return;
    }
    try {
      const response = await fetch(API.export(state.currentModel.model_id, format), {
        credentials: "same-origin",
      });
      if (!response.ok) {
        const payload = await safeJson(response);
        throw new Error(payload.message || "导出失败。");
      }
      const blob = await response.blob();
      downloadBlob(blob, `${state.currentModel.title || "leadership_model"}.${format}`);
    } catch (error) {
      showMessage(error.message || "导出失败。", "error");
    }
  }

  function renderModel(model) {
    state.currentModel = model;
    renderWorkflow(model?.workflow || []);
    renderStageButtons(model);
    renderContext(model?.context || null);
    renderDimensions(model?.dimensions || []);
    renderDescriptions(model?.descriptions || []);
    renderAnchors(model?.anchors || []);
    els.currentTitle.textContent = model?.title || "尚未创建";
    els.currentMeta.textContent = model
      ? `${model.status || "--"} · ${model.updated_at || model.created_at || "--"}`
      : "填写左侧信息后开始。";
  }

  function renderWorkflow(workflow) {
    const items = workflow.length
      ? workflow
      : [
          { key: "context", label: "建模背景", state: "available", status_label: "待采集" },
          { key: "dimensions", label: "维度框架", state: "locked", status_label: "待生成" },
          { key: "descriptions", label: "维度描述", state: "locked", status_label: "待生成" },
          { key: "anchors", label: "行为锚定", state: "locked", status_label: "待生成" },
          { key: "export", label: "模型导出", state: "locked", status_label: "待生成" },
        ];
    els.workflow.innerHTML = items
      .map(
        (item, index) => `
          <div class="leadership-step leadership-step-${escapeAttr(item.state)}">
            <div class="leadership-step-index">${index + 1}</div>
            <div>
              <strong>${escapeHtml(item.label)}</strong>
              <span>${escapeHtml(item.status_label || item.state)}</span>
            </div>
          </div>
        `
      )
      .join("");
  }

  function renderStageButtons(model) {
    const workflow = new Map((model?.workflow || []).map((item) => [item.key, item.state]));
    setDisabled(els.generateDimensions, !model || workflow.get("dimensions") === "locked");
    setDisabled(els.saveDimensions, workflow.get("dimensions") !== "pending-review");
    setDisabled(els.generateDescriptions, workflow.get("descriptions") !== "available");
    setDisabled(els.saveDescriptions, workflow.get("descriptions") !== "pending-review");
    setDisabled(els.generateAnchors, workflow.get("anchors") !== "available");
    setDisabled(els.saveAnchors, workflow.get("anchors") !== "pending-review");
    setDisabled(els.exportPdf, workflow.get("export") !== "available");
    setDisabled(els.exportDocx, workflow.get("export") !== "available");
  }

  function renderContext(context) {
    if (!context) {
      els.context.className = "leadership-context empty-state";
      els.context.innerHTML = `
        <div class="empty-icon">◇</div>
        <h3>等待建模信息</h3>
        <p>创建草稿后会展示建模背景摘要。</p>
      `;
      return;
    }
    els.context.className = "leadership-context";
    els.context.innerHTML = `
      <div class="leadership-summary-grid">
        ${summaryItem("企业", context.company_name)}
        ${summaryItem("行业", context.industry || context.business_type)}
        ${summaryItem("对象", context.target_group)}
        ${summaryItem("战略重点", joinList(context.strategy_keywords))}
        ${summaryItem("管理痛点", joinList(context.management_pains))}
        ${summaryItem("参照标准", joinList(context.standard_refs))}
      </div>
      ${
        context.missing_fields?.length
          ? `<div class="inline-alert warning">信息缺口：${escapeHtml(joinList(context.missing_fields))}</div>`
          : ""
      }
    `;
  }

  function renderDimensions(dimensions) {
    els.dimensions.innerHTML = sectionHtml(
      "M02 维度框架",
      dimensions,
      (item) => `
        <article class="leadership-card" data-dimension-id="${escapeAttr(item.id)}">
          <label class="field">
            <span>维度名称</span>
            <input type="text" data-field="name" value="${escapeAttr(item.name || "")}">
          </label>
          <label class="field">
            <span>推荐优先级</span>
            <input type="text" data-field="priority" value="${escapeAttr(item.priority || "")}">
          </label>
          <label class="field full">
            <span>定义说明</span>
            <textarea data-field="definition" rows="3">${escapeHtml(item.definition || "")}</textarea>
          </label>
          <div class="source-list">${(item.sources || [])
            .map((source) => `<span class="tag">${escapeHtml(source.type || "来源")} · ${escapeHtml(source.text || "")}</span>`)
            .join("")}</div>
        </article>
      `
    );
  }

  function renderDescriptions(descriptions) {
    els.descriptions.innerHTML = sectionHtml(
      "M03 维度定位描述",
      descriptions,
      (item) => `
        <article class="leadership-card" data-description-id="${escapeAttr(item.dimension_id)}">
          <h3>${escapeHtml(item.name || "未命名维度")}</h3>
          <label class="field full">
            <span>核心要求</span>
            <textarea data-field="core_requirement" rows="3">${escapeHtml(item.core_requirement || "")}</textarea>
          </label>
          <label class="field full">
            <span>价值贡献</span>
            <textarea data-field="value_contribution" rows="3">${escapeHtml(item.value_contribution || "")}</textarea>
          </label>
          <span class="tag ${item.quality_status?.status === "passed" ? "green" : "orange"}">
            ${item.quality_status?.status === "passed" ? "质检通过" : "待审阅"}
          </span>
        </article>
      `
    );
  }

  function renderAnchors(anchors) {
    els.anchors.innerHTML = sectionHtml(
      "M04 行为锚定",
      anchors,
      (item) => `
        <article class="leadership-card" data-anchor-id="${escapeAttr(item.dimension_id)}">
          <h3>${escapeHtml(item.name || "未命名维度")}</h3>
          ${anchorTextarea("excellent", "优秀行为", item.excellent)}
          ${anchorTextarea("pass", "达标行为", item.pass)}
          ${anchorTextarea("negative", "不达标表现", item.negative)}
        </article>
      `
    );
  }

  function sectionHtml(title, items, renderer) {
    if (!items.length) {
      return "";
    }
    return `
      <section class="leadership-section">
        <h3>${escapeHtml(title)}</h3>
        <div class="leadership-card-grid">${items.map(renderer).join("")}</div>
      </section>
    `;
  }

  function collectDimensions() {
    return [...document.querySelectorAll("[data-dimension-id]")].map((card, index) => {
      const original = state.currentModel.dimensions[index] || {};
      return {
        ...original,
        id: Number(card.dataset.dimensionId || original.id || index + 1),
        name: card.querySelector('[data-field="name"]').value.trim(),
        definition: card.querySelector('[data-field="definition"]').value.trim(),
        priority: card.querySelector('[data-field="priority"]').value.trim(),
      };
    });
  }

  function collectDescriptions() {
    return [...document.querySelectorAll("[data-description-id]")].map((card, index) => {
      const original = state.currentModel.descriptions[index] || {};
      return {
        ...original,
        dimension_id: Number(card.dataset.descriptionId || original.dimension_id),
        core_requirement: card.querySelector('[data-field="core_requirement"]').value.trim(),
        value_contribution: card.querySelector('[data-field="value_contribution"]').value.trim(),
      };
    });
  }

  function collectAnchors() {
    return [...document.querySelectorAll("[data-anchor-id]")].map((card, index) => {
      const original = state.currentModel.anchors[index] || {};
      return {
        ...original,
        dimension_id: Number(card.dataset.anchorId || original.dimension_id),
        excellent: splitLines(card.querySelector('[data-anchor-kind="excellent"]').value),
        pass: splitLines(card.querySelector('[data-anchor-kind="pass"]').value),
        negative: splitLines(card.querySelector('[data-anchor-kind="negative"]').value),
      };
    });
  }

  function renderHistory() {
    if (!state.models.length) {
      els.historyEmpty.hidden = false;
      els.historyTbody.innerHTML = "";
      return;
    }
    els.historyEmpty.hidden = true;
    els.historyTbody.innerHTML = state.models
      .map(
        (item) => `
          <tr>
            <td><div class="strong">${escapeHtml(item.title || "--")}</div></td>
            <td>${escapeHtml(item.company_name || "--")}</td>
            <td>${escapeHtml(item.target_group || "--")}</td>
            <td><span class="tag">${escapeHtml(statusLabel(item))}</span></td>
            <td>${escapeHtml(item.updated_at || "--")}</td>
            <td>
              <div class="history-action">
                <button class="btn btn-ghost btn-sm" type="button" data-leadership-view="${escapeAttr(item.model_id)}">继续编辑</button>
              </div>
            </td>
          </tr>
        `
      )
      .join("");
    els.historyTbody.querySelectorAll("[data-leadership-view]").forEach((button) => {
      button.addEventListener("click", () => viewModel(button.dataset.leadershipView));
    });
  }

  function anchorTextarea(kind, label, items) {
    return `<label class="field full"><span>${escapeHtml(label)}</span><textarea data-anchor-kind="${escapeAttr(kind)}" rows="4">${escapeHtml((items || []).join("\n"))}</textarea></label>`;
  }

  function summaryItem(label, value) {
    return `<div class="leadership-summary-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "--")}</strong></div>`;
  }

  async function requestJson(url, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    const fetchOptions = { method: options.method || "GET", credentials: "same-origin", headers };
    if (options.json !== undefined) {
      headers.set("Content-Type", "application/json");
      fetchOptions.body = JSON.stringify(options.json);
    } else if (options.body !== undefined) {
      fetchOptions.body = options.body;
    }
    const response = await fetch(url, fetchOptions);
    const payload = await safeJson(response);
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`);
    }
    return payload;
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function statusLabel(item) {
    const workflow = item.workflow || [];
    const active = workflow.find((step) => ["available", "pending-review"].includes(step.state));
    return active ? `${active.label} · ${active.status_label}` : item.status || "--";
  }

  function showMessage(message, type) {
    els.message.hidden = false;
    els.message.textContent = message;
    els.message.className = `inline-alert ${type || "info"}`;
  }

  function clearMessage() {
    els.message.hidden = true;
    els.message.textContent = "";
    els.message.className = "inline-alert";
  }

  function setBusy(isBusy) {
    [els.generateDimensions, els.saveDimensions, els.generateDescriptions, els.saveDescriptions, els.generateAnchors, els.saveAnchors, els.exportPdf, els.exportDocx].forEach((button) => button.classList.toggle("is-loading", isBusy));
  }

  function setDisabled(button, disabled) { button.disabled = Boolean(disabled); }
  function joinList(value) { return Array.isArray(value) ? value.filter(Boolean).join("、") : value || ""; }
  function splitLines(value) { return String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean); }
  function formatBytes(size) { return !Number.isFinite(size) ? "--" : size < 1024 ? `${size}B` : size < 1024 * 1024 ? `${(size / 1024).toFixed(1)}KB` : `${(size / 1024 / 1024).toFixed(1)}MB`; }
  function escapeHtml(value) { return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function escapeAttr(value) { return escapeHtml(value); }
})();
