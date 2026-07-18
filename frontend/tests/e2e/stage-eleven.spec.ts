import path from "node:path";

import { expect, test } from "@playwright/test";

const sample = path.resolve("..", "samples", "synthetic", "generic-chat.json");

test("completes the user-reachable MVP loop from an empty database", async ({ page }) => {
  test.setTimeout(120_000);
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) externalRequests.push(request.url());
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "EchoMind" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("后端在线");

  await page.getByRole("link", { name: "导入聊天记录" }).click();
  await page.getByLabel(/选择文件/).setInputFiles(sample);
  await page.getByRole("button", { name: "开始导入" }).click();
  await expect(page.getByRole("heading", { name: "导入完成" })).toBeVisible();
  await expect(page.getByText("generic-chat.json")).toBeVisible();
  await page.getByRole("link", { name: "查看本次导入的会话" }).click();
  await page.getByText("Synthetic conversation", { exact: true }).click();
  await expect(page.getByText("Synthetic message one", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "原始内容" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "规范化内容" }).first()).toBeVisible();

  await page.getByRole("link", { name: "分析", exact: true }).click();
  await expect(page.getByText("mock", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: /Synthetic conversation/ }).check();
  await page.getByRole("button", { name: "开始分析" }).click();
  await expect(page.getByRole("heading", { name: "分析完成" })).toBeVisible();
  await expect(page.locator(".analysis-metrics")).toContainText("1 新 Insight");
  await expect(page.locator(".analysis-metrics")).toContainText("1 已评分");
  await page.getByRole("link", { name: "查看生成的 Insights" }).click();
  await page.getByRole("link", { name: /Synthetic end-to-end fact/ }).click();
  const insightUrl = page.url();
  await expect(page.getByRole("heading", { name: "证据链" })).toBeVisible();
  await expect(page.locator(".evidence-card blockquote")).toContainText("Synthetic message one");
  await expect(page.locator(".evidence-seal strong")).not.toHaveText("未提供");
  await page.getByRole("link", { name: /查看原消息/ }).click();
  await expect(page.locator(".message-card.is-highlighted")).toContainText("Synthetic message one");
  await page.goto(insightUrl);

  await page.getByRole("button", { name: "编辑候选" }).click();
  await page.getByLabel("陈述").fill("Synthetic user-reviewed end-to-end fact.");
  await page.getByRole("button", { name: /保存 revision/ }).click();
  await expect(page.getByText("Synthetic user-reviewed end-to-end fact.")).toBeVisible();
  await page.getByRole("button", { name: "确认 Insight" }).click();
  await expect(page.getByText("confirmed", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Revision 历史" })).toBeVisible();
  await expect(page.locator(".revision-list li")).toHaveCount(2);

  await page.getByRole("link", { name: "Profiles", exact: true }).click();
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("新快照已生成");
  await page.getByRole("link", { name: /查看详情/ }).click();
  const originalProfileUrl = page.url();
  await expect(page.getByText("Synthetic user-reviewed end-to-end fact.")).toBeVisible();
  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  expect((await markdownDownload).suggestedFilename()).toContain("echoprofile");
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 JSON" }).click();
  expect((await jsonDownload).suggestedFilename()).toContain("echoprofile");

  await page.getByRole("link", { name: /查看本地原消息/ }).click();
  await page.locator(".message-card.is-highlighted").getByRole("button", { name: "排除分析" }).click();
  await expect(page.locator(".message-card.is-highlighted")).toContainText("已排除分析");
  await page.goto(insightUrl);
  await expect(page.getByText("invalid", { exact: true })).toBeVisible();
  await page.goto(originalProfileUrl);
  await expect(page.getByText("来源已变化")).toBeVisible();

  await page.getByRole("link", { name: "Profiles", exact: true }).click();
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("新快照已生成");
  await page.getByRole("link", { name: /查看详情/ }).click();
  await expect(page.getByRole("heading", { name: "证据已失效" })).toBeVisible();
  await page.getByRole("link", { name: /查看本地原消息/ }).click();
  await page.locator(".message-card.is-highlighted").getByRole("button", { name: "恢复分析" }).click();
  await expect(page.locator(".message-card.is-highlighted")).not.toContainText("已排除分析");
  await page.goto(insightUrl);
  await expect(page.getByText("valid", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Profiles", exact: true }).click();
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText(/新快照已生成|已复用/);
  await page.getByRole("button", { name: "生成 Profile" }).click();
  await expect(page.getByRole("status")).toContainText("已复用相同来源与配置的快照");

  await page.getByRole("link", { name: "导入" }).click();
  await page.getByLabel(/选择文件/).setInputFiles(sample);
  await page.getByRole("button", { name: "开始导入" }).click();
  await expect(page.getByRole("alert")).toContainText("already been imported");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();

  const persistence = await page.evaluate(async () => ({
    localStorage: window.localStorage.length,
    sessionStorage: window.sessionStorage.length,
    indexedDatabases: typeof indexedDB.databases === "function" ? (await indexedDB.databases()).length : 0,
    serviceWorkers: "serviceWorker" in navigator ? (await navigator.serviceWorker.getRegistrations()).length : 0,
    caches: "caches" in window ? (await caches.keys()).length : 0,
  }));
  expect(persistence).toEqual({ localStorage: 0, sessionStorage: 0, indexedDatabases: 0, serviceWorkers: 0, caches: 0 });
  expect(externalRequests).toEqual([]);
});
