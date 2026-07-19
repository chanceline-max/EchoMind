import { expect, test } from "@playwright/test";

test("reviews an Insight, preserves history, and propagates Evidence validity", async ({ page }) => {
  await page.goto("/insights");
  await expect(page.getByRole("heading", { name: "洞察审核台" })).toBeVisible();
  await page.getByLabel("状态").selectOption("proposed");
  await expect(page.getByText("共 2 条")).toBeVisible();

  const links = page.locator(".insight-row");
  const currentHref = await links.nth(0).getAttribute("href");
  const replacementHref = await links.nth(1).getAttribute("href");
  if (!currentHref || !replacementHref) throw new Error("synthetic Insight links are missing");
  const replacementId = replacementHref.split("/").at(-1);
  if (!replacementId) throw new Error("synthetic replacement ID is missing");
  await page.goto(currentHref);

  await expect(page.getByRole("heading", { name: /Synthetic review candidate/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据链" })).toBeVisible();
  await expect(page.getByText("本人").first()).toBeVisible();

  await page.getByRole("button", { name: "编辑候选" }).click();
  await page.getByLabel("标题").fill("E2E reviewed synthetic title");
  await page.getByRole("button", { name: "保存修订 1" }).click();
  await expect(page.getByRole("heading", { name: "E2E reviewed synthetic title" })).toBeVisible();
  await expect(page.getByText(/第 1 版 · 已编辑/)).toBeVisible();

  await page.getByRole("button", { name: "确认洞察" }).click();
  await expect(page.locator(".status-confirmed")).toHaveText("已确认");
  await page.reload();
  await expect(page.locator(".status-confirmed")).toHaveText("已确认");

  const insightId = currentHref.split("/").at(-1);
  if (!insightId) throw new Error("synthetic Insight ID is missing");
  const externalStatus = await page.evaluate(async ({ insightId }) => {
    const response = await fetch(`http://127.0.0.1:8000/api/v1/insights/${insightId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision: 2, title: "Concurrent synthetic edit" }),
    });
    return response.status;
  }, { insightId });
  expect(externalStatus).toBe(200);
  await page.getByRole("button", { name: "编辑候选" }).click();
  await page.getByLabel("标题").fill("Stale edit must not win");
  await page.getByRole("button", { name: "保存修订 3" }).click();
  await expect(page.getByRole("alert")).toContainText("已在其他页面被修改");
  await page.getByRole("button", { name: "重新加载" }).click();
  await expect(page.getByRole("heading", { name: "Concurrent synthetic edit" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept("Synthetic E2E rejection reason."));
  await page.getByRole("button", { name: "驳回" }).click();
  await expect(page.locator(".status-rejected")).toHaveText("已驳回");
  await page.getByRole("button", { name: "恢复为 proposed" }).click();
  await expect(page.locator(".status-proposed")).toHaveText("待审核");

  await page.getByRole("link", { name: /查看原消息/ }).first().click();
  await expect(page.getByText("证据来源")).toBeVisible();
  const targetMessage = page.locator(".message-card.is-highlighted");
  await targetMessage.getByRole("button", { name: "排除分析" }).click();
  await expect(targetMessage.getByText("已排除分析")).toBeVisible();
  await page.goto(currentHref);
  await expect(page.locator(".evidence-card.is-invalid").first()).toBeVisible();
  await expect(page.locator(".evidence-seal")).not.toHaveClass(/seal-valid/);

  await page.getByRole("link", { name: /查看原消息/ }).first().click();
  await page.locator(".message-card.is-highlighted").getByRole("button", { name: "恢复分析" }).click();
  await page.goto(currentHref);
  await expect(page.locator(".evidence-card.is-invalid")).toHaveCount(0);
  await expect(page.locator(".evidence-seal")).toHaveClass(/seal-valid/);

  await page.getByRole("button", { name: "用其他 Insight 替代" }).click();
  await page.getByLabel("替代 Insight ID").fill(replacementId);
  await page.getByRole("button", { name: "确认替代" }).click();
  await expect(page.locator(".status-superseded")).toHaveText("已替代");
  await expect(page.getByText(/· 已替代/)).toBeVisible();
  await expect(page.locator(".revision-list li")).toHaveCount(8);
});
