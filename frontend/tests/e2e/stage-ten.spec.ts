import { expect, test } from "@playwright/test";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function findBackgroundSource(value: unknown): { insightId: string; oldStatement: string } {
  if (!isRecord(value) || !isRecord(value.document) || !Array.isArray(value.document.sections)) {
    throw new Error("Profile response has an invalid document shape");
  }
  for (const section of value.document.sections) {
    if (!isRecord(section) || !Array.isArray(section.items)) continue;
    for (const item of section.items) {
      if (
        isRecord(item) &&
        item.title === "Profile background" &&
        typeof item.insight_id === "string" &&
        typeof item.statement === "string"
      ) {
        return { insightId: item.insight_id, oldStatement: item.statement };
      }
    }
  }
  throw new Error("Profile background Insight is missing");
}

test("generates, reuses, stales, and explicitly exports immutable EchoProfiles", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/profiles");
  await expect(page.getByRole("heading", { name: "EchoProfile" })).toBeVisible();
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("新快照已生成");
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("已复用相同来源与配置的快照");
  const profileHref = await page.getByRole("link", { name: /查看详情/ }).getAttribute("href");
  if (!profileHref) throw new Error("generated Profile link is missing");
  await page.goto(profileHref);

  await expect(page.getByText("confirmed-only-1.0")).toBeVisible();
  await expect(page.getByRole("heading", { name: "基础背景" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "稳定偏好" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "矛盾信息" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "待验证假设" })).toBeVisible();
  await expect(page.getByText("部分证据已失效。")).toBeVisible();
  await expect(page.locator(".profile-evidence blockquote")).toHaveCount(0);

  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  expect((await markdownDownload).suggestedFilename()).toContain("echoprofile");
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 JSON" }).click();
  expect((await jsonDownload).suggestedFilename()).toContain("echoprofile");

  const source = await page.evaluate(async (profileHref) => {
    const response = await fetch(`http://127.0.0.1:8000/api/v1${profileHref}`);
    return response.json();
  }, profileHref);
  const backgroundSource = findBackgroundSource(source);
  await page.goto(`/insights/${backgroundSource.insightId}`);
  await page.getByRole("button", { name: "编辑候选" }).click();
  await page.getByLabel("陈述").fill("Synthetic Profile statement updated after snapshot.");
  await page.getByRole("button", { name: /保存 revision/ }).click();
  await expect(page.getByText("Synthetic Profile statement updated after snapshot.")).toBeVisible();
  await page.goto(profileHref);
  await expect(page.getByText("来源已变化")).toBeVisible();
  await expect(page.getByText(backgroundSource.oldStatement)).toBeVisible();
  await expect(page.getByText("Synthetic Profile statement updated after snapshot.")).toHaveCount(0);

  await page.goto("/profiles");
  await page.getByLabel("Evidence 模式").selectOption("excerpts");
  await expect(page.getByText(/敏感导出/)).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("新快照已生成");
  const excerptHref = await page.getByRole("link", { name: /查看详情/ }).getAttribute("href");
  if (!excerptHref) throw new Error("excerpt Profile link is missing");
  await page.goto(excerptHref);
  await expect(page.locator(".profile-evidence blockquote").first()).toBeVisible();
  const targetEvidence = page.locator(".profile-evidence").filter({ hasText: "statement delta" });
  await targetEvidence.getByRole("link", { name: /查看本地原消息/ }).click();
  await page.locator(".message-card.is-highlighted").getByRole("button", { name: "排除分析" }).click();
  await page.goto("/profiles");
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await page.getByRole("link", { name: /查看详情/ }).click();
  await expect(page.getByRole("heading", { name: "证据已失效" })).toBeVisible();
  await expect(page.getByText(/不能作为当前有效结论使用/)).toBeVisible();
  await page.goto(excerptHref);
  await expect(page.getByText("来源已变化")).toBeVisible();
  await expect(page.locator(".profile-evidence blockquote").filter({ hasText: "statement delta" })).toBeVisible();
});
