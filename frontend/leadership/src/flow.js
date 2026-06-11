export const steps = [
  { key: "context", label: "信息采集" },
  { key: "dimensions", label: "维度确认" },
  { key: "descriptions", label: "描述建立" },
  { key: "anchors", label: "行为锚定" },
  { key: "export", label: "总览导出" }
];

export const contextFields = [
  { key: "industry", label: "行业/业务", question: "企业所在行业、主营业务或产品服务是什么？" },
  { key: "company_size", label: "规模阶段", question: "企业规模或当前发展阶段是什么？" },
  { key: "strategy_keywords", label: "战略重点", question: "未来1-2年的战略重点有哪些？" },
  { key: "management_pains", label: "管理痛点", question: "当前最需要解决的管理痛点是什么？" },
  { key: "target_group", label: "目标层级", question: "本次只为哪个管理层级建模？" },
  { key: "excellent_behaviors", label: "优秀画像", question: "优秀管理者有哪些具体可观察行为？" }
];

export function currentStepIndex(model) {
  const key = model?.current_step || "context";
  return Math.max(0, steps.findIndex((step) => step.key === key));
}

export function nextContextField(context = {}) {
  return contextFields.find((field) => !hasValue(context[field.key])) || null;
}

export function canConfirmDimensions(dimensions) {
  return (dimensions || []).filter((item) => item.selected !== false).length >= 3;
}

export function normalizeModel(model) {
  if (!model) return null;
  return {
    ...model,
    dimensions: model.dimensions || [],
    descriptions: model.descriptions || [],
    anchors: (model.anchors || []).map((item) => ({
      ...item,
      anchors: item.anchors || {
        excellent: toAnchorObjects(item.excellent, "excellent", item.dimension_id, "E"),
        standard: toAnchorObjects(item.pass, "standard", item.dimension_id, "S"),
        below: toAnchorObjects(item.negative, "below", item.dimension_id, "B")
      }
    })),
    dimension_candidates: model.dimension_candidates || {
      recommended: model.dimensions || [],
      alternatives: []
    }
  };
}

export function selectedDimensions(model, localDimensions) {
  return (localDimensions || model?.dimensions || []).filter((item) => item.selected !== false);
}

function hasValue(value) {
  return Array.isArray(value) ? value.length > 0 : Boolean(String(value || "").trim());
}

function toAnchorObjects(items, level, dimensionId, prefix) {
  return (items || []).map((text, index) => ({
    id: `D${dimensionId}-${prefix}${index + 1}`,
    text,
    level
  }));
}
