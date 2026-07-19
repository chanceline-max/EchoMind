import { describe, expect, it } from "vitest";

import {
  categoryLabel,
  evidenceStateLabel,
  insightStatusLabel,
  insightTypeLabel,
  providerLabel,
  senderRoleLabel,
} from "../../src/labels";

describe("localized labels", () => {
  it("maps controlled API values to Chinese without changing their stored values", () => {
    expect(insightStatusLabel("proposed")).toBe("待审核");
    expect(insightTypeLabel("preference")).toBe("偏好");
    expect(evidenceStateLabel("valid")).toBe("有效");
    expect(senderRoleLabel("PROFILE_OWNER")).toBe("本人");
    expect(providerLabel("openai_compatible")).toBe("OpenAI 兼容远程模型");
  });

  it("localizes known categories and preserves unknown free-form categories exactly", () => {
    expect(categoryLabel("background")).toBe("背景信息");
    expect(categoryLabel("thinking_pattern")).toBe("思维模式");
    expect(categoryLabel("values_motivation")).toBe("价值观与动机");
    expect(categoryLabel("CustomCategory")).toBe("CustomCategory");
  });
});
