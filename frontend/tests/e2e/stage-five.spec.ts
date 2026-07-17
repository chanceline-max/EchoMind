import path from "node:path";

import { expect, test } from "@playwright/test";

const sample = path.resolve("..", "samples", "synthetic", "generic-chat.json");

test("imports a synthetic chat, reads messages, and toggles analysis exclusion", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "EchoMind" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("后端在线");

  await page.getByRole("link", { name: "导入聊天记录" }).click();
  await page.getByLabel(/选择文件/).setInputFiles(sample);
  await page.getByRole("button", { name: "开始导入" }).click();
  await expect(page.getByRole("heading", { name: "导入完成" })).toBeVisible();
  await expect(page.getByText("generic-chat.json")).toBeVisible();

  await page.getByRole("link", { name: "查看本次导入的会话" }).click();
  await expect(page.getByText("Synthetic conversation", { exact: true })).toBeVisible();
  await page.getByText("Synthetic conversation", { exact: true }).click();
  await expect(page.getByText("Synthetic message one", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "原始内容" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "规范化内容" }).first()).toBeVisible();

  await page.getByRole("button", { name: "排除分析" }).first().click();
  await expect(page.getByText("已排除分析").first()).toBeVisible();
  await page.getByRole("button", { name: "恢复分析" }).first().click();
  await expect(page.getByRole("button", { name: "排除分析" }).first()).toBeVisible();
});

test("shows a safe duplicate import error", async ({ page }) => {
  await page.goto("/import");
  await page.getByLabel(/选择文件/).setInputFiles(sample);
  await page.getByRole("button", { name: "开始导入" }).click();
  await expect(page.getByRole("alert")).toContainText("already been imported");
  await expect(page.getByRole("alert")).not.toContainText("test-results");
});
