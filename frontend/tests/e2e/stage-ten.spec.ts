import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";

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
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "生成综合人格档案" }).click();
  await expect(page.getByRole("status")).toContainText("新快照已生成");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "生成综合人格档案" }).click();
  await expect(page.getByRole("status")).toContainText("已复用相同来源与配置的快照");
  const profileHref = await page.getByRole("link", { name: /查看详情/ }).getAttribute("href");
  if (!profileHref) throw new Error("generated Profile link is missing");
  await page.goto(profileHref);

  await expect(page.getByRole("heading", { name: "等待真实分析的人格档案" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "人格框架参考" })).toBeVisible();
  await expect(page.getByText("Big Five", { exact: true })).toBeVisible();
  await expect(page.getByText("MBTI", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据索引" })).toHaveCount(0);
  await expect(page.locator(".profile-evidence")).toHaveCount(0);

  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  expect((await markdownDownload).suggestedFilename()).toContain("echoprofile");
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 JSON" }).click();
  expect((await jsonDownload).suggestedFilename()).toContain("echoprofile");

  const source: unknown = await page.evaluate(async ({ profileHref, apiBaseUrl }) => {
    const response = await fetch(`${apiBaseUrl}/api/v1${profileHref}`);
    const value: unknown = await response.json();
    return value;
  }, { profileHref, apiBaseUrl });
  const backgroundSource = findBackgroundSource(source);
  await page.goto(`/insights/${backgroundSource.insightId}`);
  await page.getByRole("button", { name: "编辑候选" }).click();
  await page.getByLabel("陈述").fill("Synthetic Profile statement updated after snapshot.");
  await page.getByRole("button", { name: /保存修订/ }).click();
  await expect(page.getByText("Synthetic Profile statement updated after snapshot.")).toBeVisible();
  await page.goto(profileHref);
  await expect(page.getByText("来源已变化")).toBeVisible();
  await expect(page.getByRole("heading", { name: "等待真实分析的人格档案" })).toBeVisible();
  await expect(page.getByText("Synthetic Profile statement updated after snapshot.")).toHaveCount(0);
});
