const API = {
  authMe: "/api/auth/me",
  authRegister: "/api/auth/register",
  authLogin: "/api/auth/login",
  authLogout: "/api/auth/logout",
  authForgotPassword: "/api/auth/forgot-password",
  authResetPassword: "/api/auth/reset-password",
  score: "/api/score",
  scores: "/api/scores",
  scoreDetail: (id) => `/api/scores/${encodeURIComponent(id)}`,
  exportMd: (id) => `/api/scores/${encodeURIComponent(id)}/export?format=md`,
  exportPdf: (id) => `/api/scores/${encodeURIComponent(id)}/export?format=pdf`,
};

const AUTH_MODES = ["login", "register", "forgot", "reset"];

const state = {
  authed: false,
  authMode: "login",
  authVisible: false,
  resetToken: "",
  user: null,
  currentPage: "score",
  currentScore: null,
  currentHistoryItem: null,
  history: [],
  loadingTimer: null,
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  cacheElements();
  bindEvents();
  setTodayDefault();
  showPage("score");

  const resetToken = getResetTokenFromUrl();
  if (resetToken) {
    state.resetToken = resetToken;
    enterGuestApp({ silent: true });
    openAuthView("reset", "已识别重置链接，请输入新密码完成修改。");
    return;
  }

  await restoreSession();
}

function cacheElements() {
  [
    "auth-screen",
    "auth-message",
    "auth-close-button",
    "auth-entry-button",
    "login-form",
    "register-form",
    "forgot-form",
    "auth-reset-form",
    "login-email",
    "login-password",
    "register-email",
    "register-display-name",
    "register-password",
    "forgot-email",
    "reset-password",
    "reset-token-hint",
    "app-shell",
    "sidebar-user-summary",
    "current-user-name",
    "session-chip-text",
    "logout-button",
    "topbar-title",
    "topbar-subtitle",
    "history-count",
    "score-form",
    "field-name",
    "field-org",
    "field-report-type",
    "field-course-session",
    "field-date",
    "field-note",
    "field-pdf",
    "field-transcript-file",
    "field-transcript",
    "pdf-zone",
    "transcript-zone",
    "pdf-meta",
    "transcript-meta",
    "submit-score",
    "reset-form",
    "loading-panel",
    "loading-subtitle",
    "loading-progress",
    "app-notice",
    "page-score",
    "page-result",
    "page-history",
    "result-breadcrumb",
    "breadcrumb-name",
    "breadcrumb-date",
    "result-meta",
    "result-title",
    "result-person",
    "result-overview",
    "result-total-score",
    "result-level",
    "result-created-at",
    "result-doc-avg",
    "result-audio-avg",
    "result-lowest",
    "result-source",
    "result-dimensions",
    "result-comment",
    "result-strengths",
    "result-improvements",
    "result-disclaimer",
    "export-person",
    "export-pdf",
    "export-md",
    "back-to-history",
    "new-score",
    "history-summary-count",
    "history-summary-latest",
    "history-summary-avg",
    "history-summary-gap",
    "history-reload",
    "history-tbody",
    "history-empty",
    "empty-new-score",
    "topbar-refresh-history",
  ].forEach((id) => {
    const node = document.getElementById(id);
    els[id] = node;
    els[toCamelCase(id)] = node;
  });
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.page));
  });
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => switchAuthMode(button.dataset.authMode));
  });
  document.querySelectorAll("[data-jump-auth]").forEach((button) => {
    button.addEventListener("click", () => switchAuthMode(button.dataset.jumpAuth));
  });

  els.authEntryButton.addEventListener("click", () => openAuthView("login"));
  els.authCloseButton.addEventListener("click", closeAuthView);
  els.authScreen.addEventListener("click", (event) => {
    if (event.target === els.authScreen) {
      closeAuthView();
    }
  });

  els.loginForm.addEventListener("submit", submitLogin);
  els.registerForm.addEventListener("submit", submitRegister);
  els.forgotForm.addEventListener("submit", submitForgotPassword);
  els.authResetForm.addEventListener("submit", submitResetPassword);
  els.logoutButton.addEventListener("click", logout);
  els.scoreForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitScore();
  });
  els.submitScore.addEventListener("click", submitScore);
  els.resetForm.addEventListener("click", resetScoreForm);
  els.exportPdf.addEventListener("click", exportPdf);
  els.exportMd.addEventListener("click", exportMarkdown);
  els.backToHistory.addEventListener("click", () => showPage("history"));
  els.newScore.addEventListener("click", () => showPage("score"));
  els.historyReload.addEventListener("click", () => loadHistory({ force: true, promptLogin: true }));
  els.topbarRefreshHistory.addEventListener("click", () =>
    loadHistory({ force: true, promptLogin: true })
  );
  els.emptyNewScore.addEventListener("click", handleEmptyHistoryAction);

  setupDropzone(els.pdfZone, els.fieldPdf, onPdfSelected);
  setupDropzone(els.transcriptZone, els.fieldTranscriptFile, onTranscriptFileSelected);
}

async function restoreSession() {
  try {
    const payload = await requestJson(API.authMe, { method: "GET" });
    setCurrentUser(payload.user);
    enterAuthedApp({ silent: true });
    await loadHistory({ force: true, silent: true });
  } catch (error) {
    if (isAuthError(error)) {
      enterGuestApp({ silent: true });
      return;
    }
    enterGuestApp({
      message: error.message || "会话校验失败，请稍后重试。",
      type: "error",
    });
  }
}

function enterGuestApp(options = {}) {
  const { message = "", type = "info", silent = false, page = state.currentPage } = options;
  state.authed = false;
  state.currentPage = page || "score";
  setCurrentUser(null);
  toggleSessionActions();
  closeAuthView();
  setSessionChip("游客模式");
  updateSidebarUserSummary(null);
  showPage(state.currentPage);
  if (!silent && message) {
    showAppNotice(message, type);
  }
}

function enterAuthedApp(options = {}) {
  const { message = "", silent = false, page = state.currentPage } = options;
  state.authed = true;
  state.currentPage = page || "score";
  closeAuthView();
  toggleSessionActions();
  setSessionChip("已登录");
  updateSidebarUserSummary(state.user);
  updateUserChip(state.user);
  showPage(state.currentPage);
  if (silent) {
    clearAppNotice();
  } else if (message) {
    showAppNotice(message, "success");
  }
}

function openAuthView(mode, message) {
  state.authVisible = true;
  state.authMode = AUTH_MODES.includes(mode) ? mode : "login";
  document.body.classList.add("auth-modal-open");
  els.authScreen.hidden = false;
  syncAuthMode();
  showAuthMessage(message || "", message ? "info" : "");
}

function closeAuthView() {
  state.authVisible = false;
  document.body.classList.remove("auth-modal-open");
  els.authScreen.hidden = true;
  clearAuthMessage();
}

function switchAuthMode(mode) {
  if (!AUTH_MODES.includes(mode)) {
    return;
  }
  state.authMode = mode;
  syncAuthMode();
  clearAuthMessage();
}

function syncAuthMode() {
  AUTH_MODES.forEach((mode) => {
    const tab = document.querySelector(`[data-auth-mode="${mode}"]`);
    const pane = document.querySelector(`[data-auth-pane="${mode}"]`);
    if (tab) {
      tab.classList.toggle("active", state.authMode === mode);
    }
    if (pane) {
      pane.hidden = state.authMode !== mode;
      pane.classList.toggle("active", state.authMode === mode);
    }
  });
  if (state.resetToken) {
    els.resetTokenHint.textContent = "已识别重置链接，输入新密码即可完成修改。";
  } else {
    els.resetTokenHint.textContent = "未检测到重置 token，请从邮件中的链接进入。";
  }
}

function toggleSessionActions() {
  els.authEntryButton.hidden = state.authed;
  els.logoutButton.hidden = !state.authed;
}

function setCurrentUser(user) {
  state.user = user || null;
  updateUserChip(user);
}

function updateUserChip(user) {
  if (!user) {
    els.currentUserName.textContent = "游客模式";
    return;
  }
  els.currentUserName.textContent = user.display_name || user.name || "已登录用户";
}

function updateSidebarUserSummary(user) {
  if (!user) {
    els.sidebarUserSummary.textContent = "当前为游客模式，可先浏览主界面";
    return;
  }
  const name = user.display_name || user.name || "已登录用户";
  els.sidebarUserSummary.textContent = name;
}

function setSessionChip(text) {
  els.sessionChipText.textContent = text;
}

function showAuthMessage(message, type) {
  if (!message) {
    els.authMessage.hidden = true;
    els.authMessage.textContent = "";
    els.authMessage.className = "inline-alert auth-message";
    return;
  }
  els.authMessage.hidden = false;
  els.authMessage.textContent = message;
  els.authMessage.className = `inline-alert auth-message ${type || "info"}`;
}

function clearAuthMessage() {
  showAuthMessage("", "");
}

function showAppNotice(message, type) {
  if (!message) {
    els.appNotice.hidden = true;
    els.appNotice.textContent = "";
    els.appNotice.className = "inline-alert app-notice";
    return;
  }
  els.appNotice.hidden = false;
  els.appNotice.textContent = message;
  els.appNotice.className = `inline-alert app-notice ${type || "info"}`;
}

function clearAppNotice() {
  showAppNotice("", "");
}

function promptLogin(message, mode = "login") {
  openAuthView(mode, message || "请先登录后再继续当前操作。");
}

function handleAuthFailure(message) {
  state.currentScore = null;
  state.currentHistoryItem = null;
  state.history = [];
  enterGuestApp({ silent: true, page: "score" });
  openAuthView("login", message || "登录状态已失效，请重新登录。");
}

function handleEmptyHistoryAction() {
  if (state.authed) {
    showPage("score");
    return;
  }
  promptLogin("如需查看历史记录，请先登录。");
}

function getResetTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("reset_token") || "";
}

function clearResetTokenFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("reset_token");
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

async function submitLogin(event) {
  event.preventDefault();
  clearAuthMessage();

  const payload = {
    email: els.loginEmail.value.trim(),
    password: els.loginPassword.value,
  };
  if (!payload.email || !payload.password) {
    showAuthMessage("请输入邮箱和密码。", "error");
    return;
  }

  try {
    const response = await requestJson(API.authLogin, {
      method: "POST",
      json: payload,
    });
    setCurrentUser(response.user);
    enterAuthedApp({
      message: "登录成功，现在可以继续操作。",
      page: state.currentPage === "result" ? "score" : state.currentPage,
    });
    await loadHistory({ force: true, silent: true });
  } catch (error) {
    showAuthMessage(error.message || "登录失败，请稍后重试。", "error");
  }
}

async function submitRegister(event) {
  event.preventDefault();
  clearAuthMessage();

  const payload = {
    email: els.registerEmail.value.trim(),
    display_name: els.registerDisplayName.value.trim(),
    password: els.registerPassword.value,
  };
  if (!payload.email || !payload.display_name || !payload.password) {
    showAuthMessage("请完整填写邮箱、显示名称和密码。", "error");
    return;
  }

  try {
    const response = await requestJson(API.authRegister, {
      method: "POST",
      json: payload,
    });
    setCurrentUser(response.user);
    enterAuthedApp({
      message: "注册成功，现在可以继续操作。",
      page: state.currentPage === "result" ? "score" : state.currentPage,
    });
    await loadHistory({ force: true, silent: true });
  } catch (error) {
    showAuthMessage(error.message || "注册失败，请稍后重试。", "error");
  }
}

async function submitForgotPassword(event) {
  event.preventDefault();
  clearAuthMessage();

  const email = els.forgotEmail.value.trim();
  if (!email) {
    showAuthMessage("请输入邮箱。", "error");
    return;
  }

  try {
    await requestJson(API.authForgotPassword, {
      method: "POST",
      json: { email },
    });
    els.loginEmail.value = email;
    switchAuthMode("login");
    showAuthMessage("如果邮箱存在，将收到重置邮件。请检查收件箱和垃圾箱。", "success");
  } catch (error) {
    showAuthMessage(error.message || "找回密码请求失败，请稍后重试。", "error");
  }
}

async function submitResetPassword(event) {
  event.preventDefault();
  clearAuthMessage();

  if (!state.resetToken) {
    showAuthMessage("未检测到有效重置 token，请从邮件链接重新进入。", "error");
    return;
  }

  const password = els.resetPassword.value;
  if (!password) {
    showAuthMessage("请输入新密码。", "error");
    return;
  }

  try {
    await requestJson(API.authResetPassword, {
      method: "POST",
      json: {
        token: state.resetToken,
        password,
      },
    });
    state.resetToken = "";
    els.authResetForm.reset();
    clearResetTokenFromUrl();
    switchAuthMode("login");
    showAuthMessage("密码已重置，请重新登录。", "success");
  } catch (error) {
    showAuthMessage(error.message || "重置密码失败，请稍后重试。", "error");
  }
}

async function logout() {
  try {
    await requestJson(API.authLogout, { method: "POST" });
  } catch (error) {
    console.warn("logout failed", error);
  } finally {
    state.currentScore = null;
    state.currentHistoryItem = null;
    state.history = [];
    enterGuestApp({
      message: "已退出登录。",
      type: "success",
      page: "score",
    });
  }
}

function showPage(page) {
  state.currentPage = page;

  document.querySelectorAll(".page").forEach((pageEl) => {
    pageEl.classList.toggle("active", pageEl.id === `page-${page}`);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === page);
  });

  const pages = {
    score: ["新建评分", "提交汇报材料，生成结构化评分报告"],
    result: ["评分结果", "查看结构化评分结果、维度明细与导出内容"],
    history: ["评分历史", "查看历史记录并回看任意报告详情"],
  };
  const config = pages[page] || ["智能体评分系统", ""];
  els.topbarTitle.textContent = config[0];
  els.topbarSubtitle.textContent = config[1];

  if (page === "history") {
    if (state.authed) {
      if (!state.history.length) {
        loadHistory({ silent: true });
      }
    } else {
      renderHistory([]);
      updateHistorySummary([]);
      clearAppNotice();
    }
    return;
  }

  clearAppNotice();
}

async function submitScore() {
  if (!state.authed) {
    promptLogin("登录后即可提交评分并保存报告。");
    return;
  }

  const formState = readForm();
  const errors = validateForm(formState);
  if (errors.length) {
    showAppNotice(errors[0], "error");
    return;
  }

  const formData = new FormData();
  formData.append("name", formState.name);
  formData.append("org", formState.org);
  formData.append("report_type", formState.reportType);
  formData.append("course_session", formState.courseSession);
  formData.append("date", formState.date);
  formData.append("note", formState.note || "");
  formData.append("transcript", formState.transcript || "");
  formData.append("pdf_file", formState.pdfFile);
  if (formState.transcriptFile) {
    formData.append("transcript_file", formState.transcriptFile);
  }

  showLoading("正在上传材料并提取文本", 12);
  disableScoreForm(true);
  clearAppNotice();

  try {
    const response = await fetch(API.score, {
      method: "POST",
      credentials: "same-origin",
      body: formData,
      headers: { Accept: "application/json" },
    });
    const payload = await safeJson(response);
    if (!response.ok) {
      throw createHttpError(response.status, payload);
    }

    const score = normalizeScore(payload, formState);
    state.currentScore = score;
    state.currentHistoryItem = null;
    upsertLocalHistoryFromScore(score);
    renderResult(score, { fromHistory: false });
    showPage("result");
    await loadHistory({ force: true, silent: true });
  } catch (error) {
    if (isAuthError(error)) {
      handleAuthFailure();
      return;
    }
    showAppNotice(error.message || "提交评分失败，请稍后重试。", "error");
  } finally {
    hideLoading();
    disableScoreForm(false);
  }
}

function readForm() {
  return {
    name: els.fieldName.value.trim(),
    org: els.fieldOrg.value.trim(),
    reportType: els.fieldReportType.value.trim(),
    courseSession: els.fieldCourseSession.value.trim(),
    date: els.fieldDate.value,
    note: els.fieldNote.value.trim(),
    transcript: els.fieldTranscript.value.trim(),
    pdfFile: els.fieldPdf.files && els.fieldPdf.files[0] ? els.fieldPdf.files[0] : null,
    transcriptFile:
      els.fieldTranscriptFile.files && els.fieldTranscriptFile.files[0]
        ? els.fieldTranscriptFile.files[0]
        : null,
  };
}

function validateForm(formState) {
  const errors = [];
  if (!formState.name) errors.push("请输入姓名。");
  if (!formState.org) errors.push("请输入所属组织 / 部门。");
  if (!formState.reportType) errors.push("请选择汇报类型。");
  if (!formState.courseSession) errors.push("请选择对应课次。");
  if (!formState.date) errors.push("请选择评分日期。");
  if (!formState.pdfFile) errors.push("请上传 PDF 文件。");
  return errors;
}

function disableScoreForm(disabled) {
  [
    els.fieldName,
    els.fieldOrg,
    els.fieldReportType,
    els.fieldCourseSession,
    els.fieldDate,
    els.fieldNote,
    els.fieldPdf,
    els.fieldTranscriptFile,
    els.fieldTranscript,
    els.submitScore,
    els.resetForm,
  ].forEach((node) => {
    if (node) {
      node.disabled = disabled;
    }
  });
}

function resetScoreForm() {
  els.scoreForm.reset();
  els.fieldTranscript.value = "";
  els.fieldPdf.value = "";
  els.fieldTranscriptFile.value = "";
  els.pdfMeta.textContent = "尚未选择文件";
  els.transcriptMeta.textContent = "可直接粘贴到下方文本框";
  setTodayDefault();
  clearAppNotice();
}

function setupDropzone(zone, input, onSelect) {
  if (!zone || !input) {
    return;
  }
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
    if (event.dataTransfer.files && event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      onSelect({ target: input });
    }
  });
  input.addEventListener("change", onSelect);
}

function onPdfSelected(event) {
  const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
  els.pdfMeta.textContent = file
    ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
    : "尚未选择文件";
}

function onTranscriptFileSelected(event) {
  const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
  if (!file) {
    els.transcriptMeta.textContent = "可直接粘贴到下方文本框";
    return;
  }

  const baseMeta = `${file.name} · ${formatFileSize(file.size)}`;
  const hasManualText = Boolean(els.fieldTranscript.value.trim());
  els.transcriptMeta.textContent = `${baseMeta} · 文件会随评分请求一并上传`;
  const reader = new FileReader();
  reader.onload = () => {
    const preview = decodeTranscriptPreviewSafe(reader.result);
    if (hasManualText) {
      els.transcriptMeta.textContent = `${baseMeta} · 已保留当前文本框内容`;
      return;
    }
    if (!preview.text) {
      els.fieldTranscript.value = "";
      els.transcriptMeta.textContent = `${baseMeta} · 已附带原始文件，未自动填充预览`;
      return;
    }
    els.fieldTranscript.value = preview.text;
    els.transcriptMeta.textContent = preview.warning
      ? `${baseMeta} · ${preview.warning}`
      : `${baseMeta} · 已自动预览，可继续修改`;
  };
  reader.onerror = () => {
    els.transcriptMeta.textContent = `${baseMeta} · 读取预览失败，但原始文件仍会上传`;
  };
  reader.readAsArrayBuffer(file);
}

function showLoading(text, progress) {
  els.loadingPanel.classList.add("show");
  els.loadingPanel.setAttribute("aria-hidden", "false");
  els.loadingSubtitle.textContent = text;
  els.loadingProgress.style.width = `${progress}%`;
  clearInterval(state.loadingTimer);

  const steps = [
    ["正在提取 PDF 文本", 24],
    ["正在组装评分请求", 48],
    ["正在生成结构化结果", 72],
    ["正在整理总分与等级", 92],
  ];

  let index = 0;
  state.loadingTimer = setInterval(() => {
    const step = steps[Math.min(index, steps.length - 1)];
    els.loadingSubtitle.textContent = step[0];
    els.loadingProgress.style.width = `${step[1]}%`;
    index += 1;
  }, 700);
}

function hideLoading() {
  clearInterval(state.loadingTimer);
  state.loadingTimer = null;
  els.loadingProgress.style.width = "0%";
  els.loadingPanel.classList.remove("show");
  els.loadingPanel.setAttribute("aria-hidden", "true");
}

async function loadHistory(options = {}) {
  const force = Boolean(options.force);
  const silent = Boolean(options.silent);
  const prompt = Boolean(options.promptLogin);

  if (!state.authed) {
    state.history = [];
    renderHistory([]);
    updateHistorySummary([]);
    if (prompt) {
      promptLogin("如需查看历史记录，请先登录。");
    } else if (!silent && state.currentPage === "history") {
      clearAppNotice();
    }
    return [];
  }

  if (state.history.length && !force) {
    renderHistory(state.history);
    updateHistorySummary(state.history);
    if (!silent) {
      clearAppNotice();
    }
    return state.history;
  }

  try {
    const payload = await requestJson(API.scores, { method: "GET" });
    state.history = mergeServerHistoryWithCurrentScore(normalizeHistoryList(payload));
    renderHistory(state.history);
    updateHistorySummary(state.history);
    if (!silent) {
      clearAppNotice();
    }
    return state.history;
  } catch (error) {
    if (isAuthError(error)) {
      handleAuthFailure();
      return [];
    }
    renderHistory(state.history);
    updateHistorySummary(state.history);
    if (!silent) {
      showAppNotice(error.message || "加载历史失败，请稍后重试。", "error");
    }
    return state.history;
  }
}

function renderHistory(list) {
  els.historyCount.textContent = String(list.length);
  els.historySummaryCount.textContent = String(list.length);
  updateHistoryEmptyState();

  if (!list.length) {
    els.historyEmpty.hidden = false;
    els.historyTbody.innerHTML = "";
    return;
  }

  els.historyEmpty.hidden = true;
  els.historyTbody.innerHTML = list
    .map(
      (item) => `
        <tr>
          <td>
            <div class="strong">${escapeHtml(item.name || "--")}</div>
            <div class="muted">${escapeHtml(item.id || "")}</div>
          </td>
          <td>${escapeHtml(item.org || "--")}</td>
          <td><span class="tag">${escapeHtml(item.reportType || "--")}</span></td>
          <td>${escapeHtml(item.courseSession || "--")}</td>
          <td><strong>${formatScore(item.totalScore)}</strong></td>
          <td>${escapeHtml(item.date || "--")}</td>
          <td>
            <div class="history-action">
              <button class="btn btn-ghost btn-sm" type="button" data-history-view="${escapeAttr(item.id)}">查看报告</button>
              <button class="btn btn-ghost btn-sm" type="button" data-history-export-pdf="${escapeAttr(item.id)}">导出 PDF</button>
              <button class="btn btn-secondary btn-sm" type="button" data-history-export="${escapeAttr(item.id)}">导出 MD</button>
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  els.historyTbody.querySelectorAll("[data-history-view]").forEach((button) => {
    button.addEventListener("click", () => viewHistory(button.dataset.historyView));
  });
  els.historyTbody.querySelectorAll("[data-history-export]").forEach((button) => {
    button.addEventListener("click", () => exportHistoryMarkdown(button.dataset.historyExport));
  });
  els.historyTbody.querySelectorAll("[data-history-export-pdf]").forEach((button) => {
    button.addEventListener("click", () => exportHistoryPdf(button.dataset.historyExportPdf));
  });
}

function updateHistoryEmptyState() {
  const title = els.historyEmpty.querySelector("h3");
  const copy = els.historyEmpty.querySelector("p");
  if (!state.authed) {
    title.textContent = "历史记录暂未展示";
    copy.textContent = "如需查看你的评分记录与导出内容，请先登录。";
    els.emptyNewScore.textContent = "登录后查看";
    return;
  }
  title.textContent = "暂无历史记录";
  copy.textContent = "当前账号还没有可查看的评分记录。";
  els.emptyNewScore.textContent = "去新建评分";
}

function updateHistorySummary(list) {
  if (!list.length) {
    els.historySummaryLatest.textContent = "--";
    els.historySummaryAvg.textContent = "--";
    els.historySummaryGap.textContent = "待接入";
    return;
  }

  const latest = [...list].sort((left, right) => {
    return new Date(right.createdAt || right.date || 0) - new Date(left.createdAt || left.date || 0);
  })[0];
  const avg =
    list.reduce((sum, item) => sum + (Number(item.totalScore) || 0), 0) / list.length;
  const gapList = list.filter(
    (item) => typeof item.manualAvg === "number" && typeof item.totalScore === "number"
  );
  const avgGap = gapList.length
    ? gapList.reduce((sum, item) => sum + Math.abs(item.totalScore - item.manualAvg), 0) /
      gapList.length
    : null;

  els.historySummaryLatest.textContent = `${latest.name || "--"} · ${latest.date || "--"}`;
  els.historySummaryAvg.textContent = formatScore(avg);
  els.historySummaryGap.textContent = avgGap == null ? "待接入" : `±${formatScore(avgGap)}`;
}

async function viewHistory(id) {
  if (!state.authed) {
    promptLogin("如需查看历史详情，请先登录。");
    return;
  }

  try {
    const payload = await requestJson(API.scoreDetail(id), { method: "GET" });
    const score = normalizeScore(payload, {});
    state.currentScore = score;
    state.currentHistoryItem = { id };
    renderResult(score, { fromHistory: true });
    showPage("result");
    clearAppNotice();
  } catch (error) {
    if (isAuthError(error)) {
      handleAuthFailure();
      return;
    }
    showAppNotice(error.message || "加载历史详情失败，请稍后重试。", "error");
  }
}

async function exportMarkdown() {
  await exportCurrentScoreFile("md");
}

async function exportPdf() {
  await exportCurrentScoreFile("pdf");
}

async function exportCurrentScoreFile(format) {
  if (!state.authed) {
    promptLogin("登录后可导出评分报告。");
    return;
  }

  const score = state.currentScore;
  if (!score || !score.id) {
    showAppNotice("当前结果缺少导出 ID，请先重新加载该记录。", "error");
    return;
  }

  try {
    const blob = await fetchProtectedBlob(getExportUrl(format, score.id), {
      headers: { Accept: exportAcceptHeader(format) },
    });
    downloadBlob(blob, getDownloadName(score, format));
  } catch (error) {
    if (isAuthError(error)) {
      handleAuthFailure();
      return;
    }
    showAppNotice(error.message || "导出失败，请稍后重试。", "error");
  }
}

async function exportHistoryMarkdown(id) {
  await exportHistoryScoreFile(id, "md");
}

async function exportHistoryPdf(id) {
  await exportHistoryScoreFile(id, "pdf");
}

async function exportHistoryScoreFile(id, format) {
  if (!state.authed) {
    promptLogin("如需导出历史报告，请先登录。");
    return;
  }

  try {
    const blob = await fetchProtectedBlob(getExportUrl(format, id), {
      headers: { Accept: exportAcceptHeader(format) },
    });
    const item = state.history.find((entry) => String(entry.id) === String(id));
    downloadBlob(
      blob,
      getDownloadName(
        item || { name: `history_${id}`, reportType: "report", date: "" },
        format
      )
    );
  } catch (error) {
    if (isAuthError(error)) {
      handleAuthFailure();
      return;
    }
    showAppNotice(error.message || "导出历史报告失败，请稍后重试。", "error");
  }
}

function renderResult(score, options = {}) {
  const fromHistory = Boolean(options.fromHistory);
  els.resultBreadcrumb.hidden = !fromHistory;
  if (fromHistory) {
    els.breadcrumbName.textContent = `${score.name || "历史报告"} · ${
      score.reportType || score.type || ""
    }`;
    els.breadcrumbDate.textContent = score.date || "";
  }

  els.resultMeta.textContent = [score.date, score.reportType || score.type, score.courseSession]
    .filter(Boolean)
    .join(" · ") || "--";
  els.resultPerson.textContent = [score.name, score.org].filter(Boolean).join(" · ") || "--";
  els.resultOverview.textContent =
    score.overview || score.overall_comment || score.overall || "暂无总评。";
  els.resultTotalScore.textContent = formatScore(score.totalScore);
  els.resultLevel.textContent = score.levelLabel || score.level || score.grade || "--";
  els.resultCreatedAt.textContent = score.createdAt ? `生成时间：${score.createdAt}` : "";
  els.resultDocAvg.textContent =
    score.documentAverage == null ? "--" : formatScore(score.documentAverage);
  els.resultAudioAvg.textContent =
    score.audioAverage == null
      ? score.audioMissing
        ? "待补充"
        : "--"
      : formatScore(score.audioAverage);
  els.resultLowest.textContent = score.lowestDimension
    ? `${score.lowestDimension.name || "--"} · ${formatScore(score.lowestDimension.score)}`
    : "--";
  els.resultSource.textContent = score.audioMissing ? "无录音" : "文档 + 录音";
  els.resultComment.textContent =
    score.overall_comment || score.overall || score.overview || "--";
  els.resultDisclaimer.textContent =
    score.disclaimer || "本报告由系统自动生成，仅供参考，最终结论以人工审核为准。";
  els.exportPerson.textContent = score.name || "--";

  renderArrayList(els.resultStrengths, score.strengths || []);
  renderArrayList(els.resultImprovements, score.improvements || []);
  renderDimensions(score.dimensions || []);
}

function renderArrayList(container, items) {
  container.innerHTML = items.length
    ? items.map((item) => `<li>${escapeHtml(String(item))}</li>`).join("")
    : "<li>--</li>";
}

function renderDimensions(dimensions) {
  const groups = groupDimensions(dimensions);
  if (!groups.length) {
    els.resultDimensions.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">▣</div>
        <h3>暂无维度明细</h3>
        <p>后端返回的 dimensions 为空，或当前记录尚未包含维度数据。</p>
      </div>
    `;
    return;
  }

  els.resultDimensions.innerHTML = groups
    .map((group, index) => {
      return `
        <details class="dim-group"${index === 0 ? " open" : ""}>
          <summary>
            <div>
              <div class="dim-group-title">${escapeHtml(group.name)}</div>
              <div class="dim-group-meta">
                <span class="tag">${escapeHtml(group.source || "维度组")}</span>
                <span class="tag orange">${escapeHtml(group.weight || "权重未知")}</span>
              </div>
            </div>
            <div class="group-score">${group.score == null ? "--" : formatScore(group.score)}</div>
          </summary>
          <div class="group-body">${group.items.map(renderDimensionItem).join("")}</div>
        </details>
      `;
    })
    .join("");
}

function renderDimensionItem(item) {
  const scoreText = item.score == null ? "待补充" : formatScore(item.score);
  return `
    <article class="dim-item">
      <div class="dim-head">
        <div>
          <div class="dim-name">${escapeHtml(item.name || "未命名维度")}</div>
          <div class="dim-meta">
            <span class="tag">${escapeHtml(item.source || "文档")}</span>
            <span class="tag orange">权重 ${escapeHtml(item.weight || "--")}</span>
            <span class="tag ${item.score == null ? "orange" : "green"}">${escapeHtml(
    item.score == null ? "无录音" : scoreText
  )}</span>
          </div>
        </div>
        <div class="score-pill">
          <div class="score-pill-num">${escapeHtml(scoreText)}</div>
          <div class="score-pill-level ${levelClassName(item.levelLabel || item.level || "")}">${escapeHtml(
    item.levelLabel || item.level || "--"
  )}</div>
        </div>
      </div>
      <div class="dim-evidence"><strong>评分依据：</strong>${escapeHtml(item.evidence || "--")}</div>
      <div class="dim-comment"><strong>维度评语：</strong>${escapeHtml(item.comment || "--")}</div>
    </article>
  `;
}

function levelClassName(label) {
  const text = String(label);
  if (["卓越", "excellent", "excellent-level", "优秀", "优"].includes(text)) {
    return "level-excellent";
  }
  if (["良好", "good", "good-plus"].includes(text)) {
    return "level-good";
  }
  if (["合格", "pass"].includes(text)) {
    return "level-pass";
  }
  if (["不合格", "fail"].includes(text)) {
    return "level-fail";
  }
  return "level-pending";
}

function groupDimensions(dimensions) {
  const groups = new Map();

  dimensions.forEach((item, index) => {
    const groupName =
      item.group || item.groupName || item.parent_group || item.level1_name || "未分组维度";
    if (!groups.has(groupName)) {
      groups.set(groupName, {
        name: groupName,
        weight:
          item.groupWeight || item.level1_weight || item.weightGroup || item.group_weight || "",
        source: item.groupSource || item.source_group || item.groupSourceType || "维度组",
        score: item.groupScore == null ? item.group_score || null : item.groupScore,
        items: [],
      });
    }

    groups.get(groupName).items.push({
      id: item.id == null ? index + 1 : item.id,
      name: item.name || item.dimension_name || item.title,
      source: item.source || item.material_source || item.materialSource || "文档",
      weight: item.weight || item.dimension_weight || item.ratio || "",
      score: item.score == null ? null : Number(item.score),
      levelLabel: item.level_label || item.levelLabel || item.level || "",
      evidence: item.evidence || "",
      comment: item.comment || "",
    });
  });

  return Array.from(groups.values()).map((group) => {
    if (group.score != null) {
      return group;
    }
    const scored = group.items.filter(
      (item) => typeof item.score === "number" && !Number.isNaN(item.score)
    );
    return {
      ...group,
      score: scored.length
        ? Number(
            (scored.reduce((sum, item) => sum + item.score, 0) / scored.length).toFixed(1)
          )
        : null,
    };
  });
}

function normalizeScore(payload, fallbackMeta) {
  const dimensions = normalizeDimensions(payload);
  const totalScore = numberOrNull(
    payload.total_score ??
      payload.totalScore ??
      payload.score ??
      payload.total ??
      payload.final_score
  );
  const reportType = payload.report_type ?? payload.type ?? fallbackMeta.reportType ?? "";
  const courseSession =
    payload.course_session ?? payload.courseSession ?? fallbackMeta.courseSession ?? "";
  const name = payload.name ?? payload.person_name ?? fallbackMeta.name ?? "";
  const org = payload.org ?? payload.department ?? fallbackMeta.org ?? "";
  const date = payload.date ?? fallbackMeta.date ?? "";
  const overall =
    payload.overall_comment ?? payload.overall ?? payload.comment ?? payload.summary ?? "";
  const strengths = payload.strengths ?? payload.highlights ?? [];
  const improvements = payload.improvements ?? payload.suggestions ?? [];
  const summary = computeScoreSummary(dimensions);

  return {
    id: payload.score_id ?? payload.id ?? payload.uuid ?? null,
    name,
    org,
    reportType,
    type: reportType,
    courseSession,
    date,
    totalScore: totalScore == null ? summary.totalScore : totalScore,
    level: payload.total_level ?? payload.level ?? payload.grade ?? "",
    levelLabel:
      payload.total_level ??
      payload.level_label ??
      payload.levelLabel ??
      payload.level ??
      payload.grade ??
      "",
    overview: overall,
    overall_comment: overall,
    createdAt:
      payload.created_at ??
      payload.createdAt ??
      payload.generated_at ??
      payload.generatedAt ??
      "",
    documentAverage: numberOrNull(
      payload.doc_average ?? payload.document_average ?? payload.doc_avg ?? summary.documentAverage
    ),
    audioAverage: numberOrNull(
      payload.audio_average ?? payload.aud_avg ?? summary.audioAverage
    ),
    audioMissing:
      payload.transcript_present === false ||
      Boolean(payload.audio_missing ?? payload.noAudio ?? summary.audioMissing),
    lowestDimension: payload.lowest_dimension || payload.lowest || summary.lowestDimension,
    strengths: Array.isArray(strengths) ? strengths : [],
    improvements: Array.isArray(improvements) ? improvements : [],
    disclaimer: payload.disclaimer || "本报告由系统自动生成，仅供参考，最终结论以人工审核为准。",
    dimensions,
  };
}

function normalizeDimensions(payload) {
  const raw =
    payload.dimensions ?? payload.dims ?? payload.dimension_results ?? payload.dimensionResults ?? [];
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw.map((item, index) => {
    return {
      id: item.id ?? item.dimension_id ?? index + 1,
      name: item.name ?? item.dimension_name ?? item.title ?? `维度 ${index + 1}`,
      group:
        item.group ?? item.level1_name ?? item.parent_group ?? item.group_name ?? "未分组维度",
      groupWeight: formatWeight(
        item.group_weight ?? item.groupWeight ?? item.level1_weight ?? item.weightGroup
      ),
      source: item.material_source ?? item.source ?? item.source_type ?? "文档",
      weight: formatWeight(
        item.weight ?? item.actual_weight ?? item.dimension_weight ?? item.ratio
      ),
      score: item.score == null ? null : Number(item.score),
      levelLabel: item.level_label ?? item.levelLabel ?? item.level ?? "",
      evidence: item.evidence ?? "",
      comment: item.comment ?? "",
    };
  });
}

function computeScoreSummary(dimensions) {
  const scored = dimensions.filter(
    (item) => typeof item.score === "number" && !Number.isNaN(item.score)
  );
  const totalScore = scored.length
    ? scored.reduce((sum, item) => sum + item.score, 0) / scored.length
    : 0;
  const documentScored = scored.filter((item) => String(item.source || "").includes("文档"));
  const audioScored = scored.filter((item) => String(item.source || "").includes("录音"));
  const lowestDimension = scored.reduce((lowest, item) => {
    if (!lowest) {
      return item;
    }
    return item.score < lowest.score ? item : lowest;
  }, null);

  return {
    totalScore: Number.isFinite(totalScore) ? Number(totalScore.toFixed(1)) : 0,
    documentAverage: documentScored.length
      ? Number(
          (
            documentScored.reduce((sum, item) => sum + item.score, 0) / documentScored.length
          ).toFixed(1)
        )
      : null,
    audioAverage: audioScored.length
      ? Number(
          (audioScored.reduce((sum, item) => sum + item.score, 0) / audioScored.length).toFixed(1)
        )
      : null,
    audioMissing: audioScored.some((item) => item.score == null),
    lowestDimension,
  };
}

function normalizeHistoryList(payload) {
  const source = Array.isArray(payload)
    ? payload
    : Array.isArray(payload.items)
    ? payload.items
    : Array.isArray(payload.data)
    ? payload.data
    : Array.isArray(payload.records)
    ? payload.records
    : Array.isArray(payload.results)
    ? payload.results
    : [];

  return source.map((item, index) => normalizeHistoryItem(item, index));
}

function normalizeHistoryItem(item, index) {
  return {
    id: item.id ?? item.score_id ?? item.uuid ?? index + 1,
    name: item.name ?? item.person_name ?? item.subject_name ?? "--",
    org: item.org ?? item.department ?? item.organization ?? "--",
    reportType: item.report_type ?? item.type ?? item.reportType ?? "--",
    courseSession: item.course_session ?? item.courseSession ?? "--",
    totalScore: numberOrNull(item.total_score ?? item.totalScore ?? item.ai_score ?? item.score),
    manualAvg: numberOrNull(
      item.manual_score ??
        item.manual_avg ??
        item.manualAvg ??
        item.human_avg ??
        item.humanAverage
    ),
    date: item.date ?? item.scored_at ?? item.created_at ?? item.createdAt ?? "--",
    createdAt: item.created_at ?? item.createdAt ?? item.date ?? "",
  };
}

function historyItemFromScore(score) {
  return {
    id: score?.id ?? null,
    name: score?.name ?? "--",
    org: score?.org ?? "--",
    reportType: score?.reportType ?? score?.type ?? "--",
    totalScore: numberOrNull(score?.totalScore),
    manualAvg: null,
    date: score?.date ?? "--",
    createdAt: score?.createdAt ?? score?.date ?? "",
  };
}

function upsertLocalHistoryFromScore(score) {
  const item = historyItemFromScore(score);
  if (!item.id) {
    return;
  }
  const existing = state.history.filter((entry) => String(entry.id) !== String(item.id));
  state.history = [item, ...existing];
}

function mergeServerHistoryWithCurrentScore(serverItems) {
  const merged = Array.isArray(serverItems) ? [...serverItems] : [];
  if (!state.currentScore || !state.currentScore.id) {
    return merged;
  }
  if (merged.some((item) => String(item.id) === String(state.currentScore.id))) {
    return merged;
  }
  return [historyItemFromScore(state.currentScore), ...merged];
}

async function requestJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const fetchOptions = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers,
  };

  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    fetchOptions.body = JSON.stringify(options.json);
  } else if (options.body !== undefined) {
    fetchOptions.body = options.body;
  }

  const response = await fetch(url, fetchOptions);
  const payload = await safeJson(response);
  if (!response.ok) {
    throw createHttpError(response.status, payload);
  }
  return payload;
}

async function fetchProtectedBlob(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: options.headers || {},
  });
  if (!response.ok) {
    const payload = await safeJson(response);
    throw createHttpError(response.status, payload);
  }
  return response.blob();
}

function createHttpError(status, payload) {
  const error = new Error(
    payload?.message || payload?.error || payload?.detail || payload?.raw || `请求失败（${status}）`
  );
  error.status = status;
  error.payload = payload;
  return error;
}

function isAuthError(error) {
  return Boolean(error && (error.status === 401 || error.status === 403));
}

function setTodayDefault() {
  if (!els.fieldDate.value) {
    els.fieldDate.value = new Date().toISOString().slice(0, 10);
  }
}

function formatScore(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toFixed(1);
}

function numberOrNull(value) {
  if (value === "" || value == null) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Number(parsed.toFixed(1)) : null;
}

function formatWeight(value) {
  if (value === "" || value == null) {
    return "";
  }
  if (typeof value === "number") {
    return `${value}%`;
  }
  return String(value).includes("%") ? String(value) : `${value}%`;
}

function formatFileSize(size) {
  if (!Number.isFinite(size) || size <= 0) {
    return "0 KB";
  }
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
  }
  return `${(size / 1024).toFixed(1)} KB`;
}

function decodeTranscriptPreview(buffer) {
  const bytes = buffer instanceof ArrayBuffer ? new Uint8Array(buffer) : new Uint8Array(0);
  if (!bytes.length || typeof TextDecoder === "undefined") {
    return { text: "", warning: "" };
  }

  const candidates = ["utf-8", "utf-8-sig", "gb18030", "utf-16le", "utf-16be"]
    .map((encoding) => decodeTranscriptCandidate(bytes, encoding))
    .filter(Boolean)
    .sort((left, right) => right.score - left.score);

  if (!candidates.length) {
    return { text: "", warning: "" };
  }

  const best = candidates[0];
  if (best.garbled) {
    return { text: "", warning: "检测到文本编码不稳定，已改为仅上传原始文件" };
  }
  return {
    text: best.text,
    warning: best.fromFallback ? "预览已按兼容编码解码，提交时仍会上传原始文件" : "",
  };
}

function decodeTranscriptCandidate(bytes, encoding) {
  try {
    const decoder = new TextDecoder(encoding === "utf-8-sig" ? "utf-8" : encoding, {
      fatal: false,
    });
    let text = decoder.decode(bytes);
    if (encoding === "utf-8-sig" && text.charCodeAt(0) === 0xfeff) {
      text = text.slice(1);
    }
    const normalized = String(text || "")
      .replace(/\u0000/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!normalized) {
      return null;
    }
    const garbled = looksLikeClientGarbledText(normalized);
    const compact = normalized.replace(/\s+/g, "");
    const meaningful = (compact.match(/[A-Za-z0-9\u4e00-\u9fff]/g) || []).length;
    const suspicious = (compact.match(/[�閿熼垾閵嗛張鐠囬崣閻ㄨぐ闂傞柅娴犵紒]/g) || []).length;
    return {
      text: normalized,
      score: meaningful - suspicious * 4 - (garbled ? 1000 : 0),
      garbled,
      fromFallback: !["utf-8", "utf-8-sig"].includes(encoding),
    };
  } catch {
    return null;
  }
}

function looksLikeClientGarbledText(value) {
  const compact = String(value || "").replace(/\s+/g, "");
  if (!compact) {
    return false;
  }
  const suspicious = (compact.match(/[�閿熼垾閵嗛張鐠囬崣閻ㄨぐ闂傞柅娴犵紒]/g) || []).length;
  return suspicious >= 2 && suspicious / compact.length >= 0.15;
}

function decodeTranscriptPreviewSafe(buffer) {
  const bytes = buffer instanceof ArrayBuffer ? new Uint8Array(buffer) : new Uint8Array(0);
  if (!bytes.length || typeof TextDecoder === "undefined") {
    return { text: "", warning: "" };
  }

  const bomEncoding = detectTranscriptBomSafe(bytes);
  if (bomEncoding) {
    const bomDecoded = tryDecodeTranscriptSafe(bytes, bomEncoding, {
      fatal: false,
      stripBom: true,
    });
    if (bomDecoded && !bomDecoded.garbled) {
      return {
        text: bomDecoded.text,
        warning:
          bomEncoding === "utf-8"
            ? ""
            : "预览已按文件编码解码，提交时仍会上传原始文件",
      };
    }
  }

  const utf8Decoded = tryDecodeTranscriptSafe(bytes, "utf-8", {
    fatal: true,
    stripBom: true,
  });
  if (utf8Decoded && !utf8Decoded.garbled) {
    return { text: utf8Decoded.text, warning: "" };
  }

  const gb18030Decoded = tryDecodeTranscriptSafe(bytes, "gb18030", {
    fatal: true,
    stripBom: false,
  });
  if (gb18030Decoded && !gb18030Decoded.garbled) {
    return {
      text: gb18030Decoded.text,
      warning: "预览已按兼容编码解码，提交时仍会上传原始文件",
    };
  }

  if (looksLikeUtf16PayloadSafe(bytes)) {
    const utf16leDecoded = tryDecodeTranscriptSafe(bytes, "utf-16le", {
      fatal: false,
      stripBom: true,
    });
    if (utf16leDecoded && !utf16leDecoded.garbled) {
      return {
        text: utf16leDecoded.text,
        warning: "预览已按 UTF-16 编码解码，提交时仍会上传原始文件",
      };
    }

    const utf16beDecoded = tryDecodeTranscriptSafe(bytes, "utf-16be", {
      fatal: false,
      stripBom: true,
    });
    if (utf16beDecoded && !utf16beDecoded.garbled) {
      return {
        text: utf16beDecoded.text,
        warning: "预览已按 UTF-16 编码解码，提交时仍会上传原始文件",
      };
    }
  }

  return { text: "", warning: "检测到文本编码不稳定，已改为仅上传原始文件" };
}

function detectTranscriptBomSafe(bytes) {
  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    return "utf-8";
  }
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return "utf-16le";
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return "utf-16be";
  }
  return "";
}

function looksLikeUtf16PayloadSafe(bytes) {
  if (!bytes.length || bytes.length % 2 !== 0) {
    return false;
  }

  let zeroBytes = 0;
  for (let index = 0; index < bytes.length; index += 1) {
    if (bytes[index] === 0x00) {
      zeroBytes += 1;
    }
  }
  return zeroBytes / bytes.length >= 0.08;
}

function tryDecodeTranscriptSafe(bytes, encoding, options = {}) {
  try {
    const decoder = new TextDecoder(encoding, { fatal: Boolean(options.fatal) });
    let text = decoder.decode(bytes);
    if (options.stripBom && text.charCodeAt(0) === 0xfeff) {
      text = text.slice(1);
    }
    const normalized = String(text || "")
      .replace(/\u0000/g, " ")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    if (!normalized) {
      return null;
    }
    return {
      text: normalized,
      garbled: looksLikeClientGarbledTextSafe(normalized),
    };
  } catch {
    return null;
  }
}

function looksLikeClientGarbledTextSafe(value) {
  const compact = String(value || "").replace(/\s+/g, "");
  if (!compact) {
    return false;
  }

  const suspiciousChars =
    (compact.match(/[�锟銆锛鈥鎴鐨鏄鍦鍙浠闂璇鏈鍚鏉瀵澶绗寮鍥鎺]/g) || []).length;
  const suspiciousFragments =
    (
      compact.match(
        /(?:澶у|鍥犱负|鎴戜滑|浠婂ぉ|绗竴|绗簩|鐩爣|闂|琛屽姩|缁撴灉|鎬荤粨|璇存槑|褰撳墠|鏉愭枡|姹囨姤|鍚庣画)/g
      ) || []
    ).length;

  return suspiciousFragments >= 1 || (suspiciousChars >= 3 && suspiciousChars / compact.length >= 0.08);
}

function getExportUrl(format, id) {
  return format === "pdf" ? API.exportPdf(id) : API.exportMd(id);
}

function exportAcceptHeader(format) {
  return format === "pdf" ? "application/pdf,*/*" : "text/markdown,*/*";
}

function getDownloadName(score, ext) {
  const name =
    [score?.name, score?.reportType || score?.type, score?.date].filter(Boolean).join("_") ||
    "score";
  return `${sanitizeFilename(name)}.${ext}`;
}

function sanitizeFilename(value) {
  return String(value).replace(/[\\/:*?"<>|]/g, "_");
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

async function safeJson(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

function toCamelCase(value) {
  return String(value).replace(/-([a-z])/g, (_, char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/"/g, "&quot;");
}
