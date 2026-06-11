import { describe, expect, it } from "vitest";
import { canConfirmDimensions, currentStepIndex, nextContextField, normalizeModel } from "./flow";

describe("leadership flow helpers", () => {
  it("requires at least three selected dimensions", () => {
    expect(canConfirmDimensions([{ selected: true }, { selected: true }])).toBe(false);
    expect(canConfirmDimensions([{ selected: true }, { selected: true }, { selected: true }])).toBe(true);
  });

  it("finds the next missing context field", () => {
    expect(nextContextField({ industry: "制造业" })?.key).toBe("company_size");
    expect(
      nextContextField({
        industry: "制造业",
        company_size: "5000人",
        strategy_keywords: ["增长"],
        management_pains: ["协同慢"],
        target_group: "中层",
        excellent_behaviors: ["拆解目标"]
      })
    ).toBeNull();
  });

  it("maps old anchor fields to the new three-level shape", () => {
    const model = normalizeModel({
      current_step: "anchors",
      anchors: [{ dimension_id: 1, excellent: ["识别风险"], pass: ["拆解任务"], negative: ["等待安排"] }]
    });
    expect(currentStepIndex(model)).toBe(3);
    expect(model.anchors[0].anchors.standard[0].text).toBe("拆解任务");
    expect(model.anchors[0].anchors.below[0].level).toBe("below");
  });
});
