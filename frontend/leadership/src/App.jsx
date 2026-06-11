import { useEffect, useMemo, useState } from "react";
import { downloadFile, endpoints, requestJson } from "./api";
import { canConfirmDimensions, contextFields, currentStepIndex, nextContextField, normalizeModel, selectedDimensions, steps } from "./flow";

export default function App() {
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ email: "", display_name: "", password: "" });
  const [model, setModelState] = useState(null);
  const [history, setHistory] = useState([]);
  const [view, setView] = useState(new URLSearchParams(window.location.search).get("view") === "history" ? "history" : "model");
  const [activeStep, setActiveStep] = useState("context");
  const [draftCompany, setDraftCompany] = useState("");
  const [contextField, setContextField] = useState("industry");
  const [contextMessage, setContextMessage] = useState("");
  const [dimensions, setDimensions] = useState([]);
  const [descriptions, setDescriptions] = useState([]);
  const [anchors, setAnchors] = useState([]);
  const [directions, setDirections] = useState({});
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    requestJson(endpoints.me).then((payload) => setUser(payload.user)).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (user && view === "history") loadHistory();
  }, [user, view]);

  const stepIndex = currentStepIndex(model);
  const nextField = nextContextField(model?.context || {});
  const candidates = model?.dimension_candidates || { recommended: [], alternatives: [] };

  function setModel(payload) {
    const normalized = normalizeModel(payload);
    setModelState(normalized);
    setDimensions((normalized?.dimensions || []).map((item) => ({ ...item, selected: true })));
    setDescriptions(normalized?.descriptions || []);
    setAnchors(normalized?.anchors || []);
    setActiveStep(normalized?.current_step || "context");
  }

  async function run(action, success) {
    setBusy(true);
    setNotice("");
    try {
      await action();
      if (success) setNotice(success);
    } catch (error) {
      setNotice(error.message || "操作失败。");
    } finally {
      setBusy(false);
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    await run(async () => {
      const payload = await requestJson(authMode === "login" ? endpoints.login : endpoints.register, {
        method: "POST",
        json: authForm
      });
      setUser(payload.user);
    }, "已登录。");
  }

  async function createDraft() {
    await run(async () => {
      const data = new FormData();
      data.append("company_name", draftCompany || "未命名企业");
      setModel(await requestJson(endpoints.models, { method: "POST", body: data }));
    }, "建模草稿已创建。");
  }

  async function sendContextMessage() {
    if (!model || !contextMessage.trim()) return;
    await run(async () => {
      const payload = await requestJson(endpoints.contextMessage(model.model_id), {
        method: "POST",
        json: { field: contextField, message: contextMessage }
      });
      setModel(payload);
      setContextMessage("");
      setContextField(payload.next_question || nextContextField(payload.context)?.key || contextField);
    }, "信息已记录。");
  }

  async function uploadSource(event) {
    const file = event.target.files?.[0];
    if (!file || !model) return;
    await run(async () => {
      const data = new FormData();
      data.append("source_file", file);
      setModel(await requestJson(endpoints.sourceFiles(model.model_id), { method: "POST", body: data }));
    }, "文件已解析并纳入建模上下文。");
  }

  async function confirmContext() {
    if (!model) return;
    await run(async () => {
      setModel(await requestJson(endpoints.contextConfirm(model.model_id), { method: "POST" }));
    }, "摘要已确认，维度候选已生成。");
  }

  async function saveDimensions() {
    const selected = selectedDimensions(model, dimensions);
    if (!canConfirmDimensions(selected)) {
      setNotice("至少确认 3 个维度才能进入下一步。");
      return;
    }
    await run(async () => {
      setModel(await requestJson(endpoints.dimensions(model.model_id), { method: "PATCH", json: { dimensions: selected } }));
    }, "维度已确认。");
  }

  async function generateDescriptions() {
    await run(async () => {
      setModel(await requestJson(endpoints.generateDescriptions(model.model_id), { method: "POST" }));
    }, "描述已生成。");
  }

  async function regenerateDescription(dimensionId) {
    await run(async () => {
      const payload = await requestJson(endpoints.regenerateDescription(model.model_id, dimensionId), {
        method: "POST",
        json: { direction: directions[`desc-${dimensionId}`] || "补充业务证据和行为侧重点" }
      });
      setModel(payload);
    }, "描述已重写。");
  }

  async function saveDescriptions() {
    await run(async () => {
      setModel(await requestJson(endpoints.descriptions(model.model_id), { method: "PATCH", json: { descriptions } }));
    }, "描述已确认。");
  }

  async function generateAnchors() {
    await run(async () => {
      setModel(await requestJson(endpoints.generateAnchors(model.model_id), { method: "POST" }));
    }, "行为锚定已生成。");
  }

  async function regenerateAnchor(anchorId) {
    await run(async () => {
      const payload = await requestJson(endpoints.regenerateAnchor(model.model_id, anchorId), {
        method: "POST",
        json: { direction: directions[`anchor-${anchorId}`] || "补充协同节奏" }
      });
      setModel(payload);
    }, "行为锚定已重写。");
  }

  async function saveAnchors() {
    await run(async () => {
      setModel(await requestJson(endpoints.anchors(model.model_id), { method: "PATCH", json: { anchors } }));
    }, "行为锚定已确认。");
  }

  async function exportModel(format) {
    await run(async () => {
      await downloadFile(endpoints.export(model.model_id, format), `${model.title || "leadership-model"}.${format}`);
    });
  }

  async function loadHistory() {
    const payload = await requestJson(endpoints.models);
    setHistory(payload.items || []);
  }

  async function openHistoryModel(id) {
    await run(async () => {
      setModel(await requestJson(endpoints.detail(id)));
      setView("model");
    });
  }

  const summaryRows = useMemo(() => {
    const summary = model?.context?.context_summary || {};
    return [
      ["企业背景", summary.enterprise],
      ["目标对象", summary.target],
      ["战略重点", summary.strategy],
      ["管理痛点", summary.pains],
      ["优秀画像", summary.excellent_profile],
      ["文档关键词", summary.documents],
      ["标准库", summary.standards]
    ];
  }, [model]);

  if (!user) {
    return (
      <main className="login-shell">
        <section className="login-panel">
          <h1>领导力建模智能体</h1>
          <p>使用现有评分系统账号进入建模流程，登录态继续由同源 Cookie 保护。</p>
          <form onSubmit={submitAuth} className="auth-form">
            <div className="segmented">
              <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>登录</button>
              <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>注册</button>
            </div>
            <input type="email" placeholder="邮箱" value={authForm.email} onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })} required />
            {authMode === "register" && <input placeholder="显示名称" value={authForm.display_name} onChange={(event) => setAuthForm({ ...authForm, display_name: event.target.value })} required />}
            <input type="password" placeholder="密码" value={authForm.password} onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })} required />
            <button className="primary" type="submit" disabled={busy}>{authMode === "login" ? "登录" : "注册并进入"}</button>
          </form>
          {notice && <div className="notice">{notice}</div>}
        </section>
      </main>
    );
  }

  return (
    <main className="lm-shell">
      <aside className="lm-sidebar">
        <a className="back-link" href="/">返回评分系统</a>
        <h1>领导力建模</h1>
        <p>{user.display_name || user.email}</p>
        <nav>
          <button className={view === "model" ? "active" : ""} onClick={() => setView("model")}>建模工作台</button>
          <button className={view === "history" ? "active" : ""} onClick={() => setView("history")}>建模历史</button>
        </nav>
        <div className="step-rail">
          {steps.map((step, index) => (
            <button key={step.key} className={index <= stepIndex ? "enabled" : ""} onClick={() => index <= stepIndex && setActiveStep(step.key)}>
              <span>{index + 1}</span>{step.label}
            </button>
          ))}
        </div>
      </aside>

      <section className="lm-main">
        <header className="lm-topbar">
          <div>
            <h2>{view === "history" ? "建模历史" : "五步建模工作台"}</h2>
            <p>{model?.title || "先创建草稿，再按信息采集、维度、描述、行为、导出推进。"}</p>
          </div>
          {notice && <div className="notice">{notice}</div>}
        </header>

        {view === "history" ? (
          <HistoryView history={history} onReload={loadHistory} onOpen={openHistoryModel} />
        ) : (
          <>
            {activeStep === "context" && (
              <section className="workspace two-col">
                <div className="panel">
                  <h3>M01 信息采集</h3>
                  {!model ? (
                    <div className="start-box">
                      <input placeholder="公司名称，例如：中集车辆" value={draftCompany} onChange={(event) => setDraftCompany(event.target.value)} />
                      <button className="primary" onClick={createDraft} disabled={busy}>开始建模</button>
                    </div>
                  ) : (
                    <>
                      <div className="question-card">
                        <strong>{nextField?.question || "关键信息已基本齐备，请确认摘要。"}</strong>
                        <select value={contextField} onChange={(event) => setContextField(event.target.value)}>
                          {contextFields.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
                        </select>
                        <textarea rows="4" value={contextMessage} onChange={(event) => setContextMessage(event.target.value)} placeholder="输入本轮信息，支持用分号分隔多个要点。" />
                        <button className="primary" onClick={sendContextMessage} disabled={busy}>发送并记录</button>
                      </div>
                      <label className="upload-box">
                        上传战略文档 / JD / 绩效报告
                        <input type="file" accept=".pdf,.docx,.txt,.md" onChange={uploadSource} />
                      </label>
                    </>
                  )}
                </div>
                <SummaryPanel rows={summaryRows} missing={model?.context?.missing_fields || []} onConfirm={confirmContext} disabled={!model || busy} />
              </section>
            )}

            {activeStep === "dimensions" && (
              <section className="workspace">
                <SectionHead title="M02 维度确认" action="确认维度，生成描述" onAction={saveDimensions} disabled={!canConfirmDimensions(dimensions) || busy} />
                <div className="card-grid">
                  {dimensions.map((item, index) => (
                    <DimensionCard key={item.id} item={item} onChange={(next) => setDimensions(replaceAt(dimensions, index, next))} />
                  ))}
                </div>
                <h3>备选维度池</h3>
                <div className="alt-pool">
                  {candidates.alternatives.map((item) => (
                    <button key={item.id} onClick={() => setDimensions([...dimensions, { ...item, selected: true }])}>{item.name}</button>
                  ))}
                </div>
              </section>
            )}

            {activeStep === "descriptions" && (
              <section className="workspace">
                <SectionHead title="M03 描述建立" action="确认描述，生成行为锚定" onAction={saveDescriptions} disabled={!descriptions.length || busy} secondary="生成描述" onSecondary={generateDescriptions} />
                <div className="card-grid">
                  {descriptions.map((item, index) => (
                    <DescriptionCard key={item.dimension_id} item={item} direction={directions[`desc-${item.dimension_id}`] || ""} onDirection={(value) => setDirections({ ...directions, [`desc-${item.dimension_id}`]: value })} onRegen={() => regenerateDescription(item.dimension_id)} onChange={(next) => setDescriptions(replaceAt(descriptions, index, next))} />
                  ))}
                </div>
              </section>
            )}

            {activeStep === "anchors" && (
              <section className="workspace">
                <SectionHead title="M04 行为锚定" action="完成确认，查看总览" onAction={saveAnchors} disabled={!anchors.length || busy} secondary="生成行为锚定" onSecondary={generateAnchors} />
                <div className="anchor-stack">
                  {anchors.map((item, index) => (
                    <AnchorCard key={item.dimension_id} item={item} directions={directions} setDirections={setDirections} onRegen={regenerateAnchor} onChange={(next) => setAnchors(replaceAt(anchors, index, next))} />
                  ))}
                </div>
              </section>
            )}

            {activeStep === "export" && (
              <section className="workspace">
                <div className="complete-hero">
                  <h3>领导力模型构建完成</h3>
                  <p>{model?.context?.target_group || "目标管理者"} · {model?.dimensions?.length || 0} 个维度 · 完整行为锚定</p>
                  <button onClick={() => exportModel("docx")} className="primary">导出 Word</button>
                  <button onClick={() => exportModel("pdf")}>导出 PDF</button>
                </div>
                <Overview model={model} />
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function HistoryView({ history, onReload, onOpen }) {
  return <section className="workspace"><SectionHead title="建模历史" secondary="刷新" onSecondary={onReload} /><div className="table">{history.map((item) => <button key={item.model_id} className="history-row" onClick={() => onOpen(item.model_id)}><strong>{item.title}</strong><span>{item.target_group || "--"}</span><span>{item.updated_at}</span></button>)}</div></section>;
}

function SummaryPanel({ rows, missing, onConfirm, disabled }) {
  return <aside className="panel"><h3>摘要确认</h3>{rows.map(([label, value]) => <div className="summary-row" key={label}><span>{label}</span><strong>{value || "--"}</strong></div>)}{missing.length > 0 && <div className="warning">信息缺口：{missing.join("、")}</div>}<button className="primary wide" onClick={onConfirm} disabled={disabled}>确认摘要，进入维度生成</button></aside>;
}

function SectionHead({ title, action, onAction, disabled, secondary, onSecondary }) {
  return <div className="section-head"><h3>{title}</h3><div>{secondary && <button onClick={onSecondary}>{secondary}</button>}{action && <button className="primary" onClick={onAction} disabled={disabled}>{action}</button>}</div></div>;
}

function DimensionCard({ item, onChange }) {
  return <article className={`model-card ${item.selected === false ? "muted" : ""}`}><label><input type="checkbox" checked={item.selected !== false} onChange={(event) => onChange({ ...item, selected: event.target.checked })} />确认该维度</label><input value={item.name || ""} onChange={(event) => onChange({ ...item, name: event.target.value })} /><textarea rows="4" value={item.definition || ""} onChange={(event) => onChange({ ...item, definition: event.target.value })} /><small>{(item.sources || []).map((source) => `${source.type}:${source.text}`).join(" / ")}</small></article>;
}

function DescriptionCard({ item, direction, onDirection, onRegen, onChange }) {
  const passed = item.quality_check?.passed;
  return <article className="model-card"><h4>{item.dimension_name || item.name}</h4><textarea rows="5" value={item.description || ""} onChange={(event) => onChange({ ...item, description: event.target.value, core_requirement: event.target.value })} /><span className={passed ? "badge green" : "badge orange"}>{passed ? "质检通过" : (item.quality_check?.issues || ["待审阅"]).join("、")}</span><div className="regen-row"><input value={direction} placeholder="重写方向" onChange={(event) => onDirection(event.target.value)} /><button onClick={onRegen}>单条重写</button></div></article>;
}

function AnchorCard({ item, directions, setDirections, onRegen, onChange }) {
  const labels = { excellent: "优秀", standard: "达标", below: "不达标" };
  function update(level, idx, text) {
    const next = { ...item, anchors: { ...item.anchors } };
    next.anchors[level] = next.anchors[level].map((row, index) => index === idx ? { ...row, text } : row);
    onChange(next);
  }
  return <details className="anchor-card" open><summary>{item.dimension_name || item.name}</summary>{Object.entries(labels).map(([level, label]) => <div className="anchor-level" key={level}><h4>{label}</h4>{(item.anchors?.[level] || []).map((row, index) => <div className="anchor-line" key={row.id}><input value={row.text} onChange={(event) => update(level, index, event.target.value)} /><input className="mini" placeholder="重写方向" value={directions[`anchor-${row.id}`] || ""} onChange={(event) => setDirections({ ...directions, [`anchor-${row.id}`]: event.target.value })} /><button onClick={() => onRegen(row.id)}>重写</button></div>)}</div>)}</details>;
}

function Overview({ model }) {
  return <div className="overview">{(model?.dimensions || []).map((dimension) => <article key={dimension.id} className="model-card"><h4>{dimension.name}</h4><p>{dimension.definition}</p>{(model.anchors || []).filter((item) => String(item.dimension_id) === String(dimension.id)).map((item) => <div key={item.dimension_id}><strong>行为锚定</strong><ul>{["excellent", "standard", "below"].flatMap((level) => (item.anchors?.[level] || []).map((row) => <li key={row.id}>{row.text}</li>))}</ul></div>)}</article>)}</div>;
}

function replaceAt(items, index, value) {
  return items.map((item, itemIndex) => itemIndex === index ? value : item);
}
