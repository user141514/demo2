const endpoints = {
  me: "/api/auth/status",
  login: "/api/auth/login",
  register: "/api/auth/register",
  models: "/api/leadership-models",
  detail: (id) => `/api/leadership-models/${encodeURIComponent(id)}`,
  sourceFiles: (id) => `/api/leadership-models/${encodeURIComponent(id)}/source-files`,
  contextMessage: (id) => `/api/leadership-models/${encodeURIComponent(id)}/context/message`,
  contextConfirm: (id) => `/api/leadership-models/${encodeURIComponent(id)}/context/confirm`,
  dimensions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/dimensions`,
  descriptions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/descriptions`,
  generateDescriptions: (id) => `/api/leadership-models/${encodeURIComponent(id)}/descriptions:generate`,
  regenerateDescription: (id, dimensionId) =>
    `/api/leadership-models/${encodeURIComponent(id)}/descriptions/${encodeURIComponent(dimensionId)}:regenerate`,
  anchors: (id) => `/api/leadership-models/${encodeURIComponent(id)}/anchors`,
  generateAnchors: (id) => `/api/leadership-models/${encodeURIComponent(id)}/anchors:generate`,
  regenerateAnchor: (id, anchorId) =>
    `/api/leadership-models/${encodeURIComponent(id)}/anchors/${encodeURIComponent(anchorId)}:regenerate`,
  export: (id, format) => `/api/leadership-models/${encodeURIComponent(id)}/export?format=${format}`
};

export async function requestJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  const request = { method: options.method || "GET", credentials: "same-origin", headers };
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    request.body = JSON.stringify(options.json);
  } else if (options.body !== undefined) {
    request.body = options.body;
  }
  const response = await fetch(url, request);
  const payload = await safeJson(response);
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `请求失败：${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function downloadFile(url, filename) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) {
    const payload = await safeJson(response);
    throw new Error(payload.message || "导出失败。");
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export { endpoints };
