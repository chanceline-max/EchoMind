import { expect, test } from "@playwright/test";

test("loads the foundation page and reports the local backend online", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "EchoMind" })).toBeVisible();
  await expect(page.getByText("MVP Foundation")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("后端在线");
  await expect(page.getByRole("status")).toContainText("echomind-api");
});
