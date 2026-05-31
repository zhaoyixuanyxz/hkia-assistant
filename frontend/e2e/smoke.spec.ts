import { expect, test } from "@playwright/test";

async function seedSession(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("hkia_token", "test-token");
  });
  await page.route("**/auth/me", async (route) => {
    await route.fulfill({ json: { email: "advisor@example.com" } });
  });
}

function isConversationsListUrl(url: URL) {
  return url.pathname === "/conversations";
}

function isConversationDetailUrl(url: URL) {
  return /^\/conversations\/\d+$/.test(url.pathname);
}

function isKnowledgeProductsKeywordUrl(url: URL) {
  return (
    url.pathname === "/knowledge/products" &&
    url.searchParams.get("mode") === "keyword"
  );
}

test.describe("smoke", () => {
  test("login page renders (zh-CN explicit path)", async ({ page }) => {
    await page.goto("/zh-CN/login");
    await expect(page.getByRole("button", { name: "登录" })).toBeVisible();
  });

  test("viewport keeps vertical scrolling via panes (html not overflow-y-hidden)", async ({
    page,
  }) => {
    await page.goto("/zh-CN/login");

    const htmlY = await page.evaluate(
      () => window.getComputedStyle(document.documentElement).overflowY,
    );
    expect(htmlY).not.toBe("hidden");
  });

  test("authenticated shell main pane allows vertical overflow scrolling", async ({
    page,
  }) => {
    await seedSession(page);
    await page.route(isConversationsListUrl, async (route) => {
      await route.fulfill({ json: [] });
    });

    await page.goto("/zh-CN/conversations");
    await expect(page.locator("main")).toBeVisible({ timeout: 15_000 });

    const shell = await page.evaluate(() => ({
      main: window.getComputedStyle(document.querySelector("main")!).overflowY,
    }));
    expect(shell.main).not.toBe("hidden");
  });

  test("mouse wheel scrolls main pane on chat page (single scroll container)", async ({
    page,
  }) => {
    await seedSession(page);
    const messages = Array.from({ length: 60 }, (_, i) => ({
      id: i + 1,
      role: i % 2 === 0 ? "user" : "assistant",
      content: `段落 ${i + 1}\n`.repeat(22),
      created_at: "2026-05-01T00:00:00Z",
    }));

    await page.route(isConversationDetailUrl, async (route) => {
      await route.fulfill({
        json: {
          id: 1,
          title: "测试会话",
          status: "active",
          is_pinned: false,
          pinned_at: null,
          created_at: "2026-05-01T00:00:00Z",
          updated_at: "2026-05-01T00:00:00Z",
          messages,
          profile_summary: "",
          profile_structured: null,
          key_memories: [],
        },
      });
    });

    await page.setViewportSize({ width: 900, height: 520 });
    await page.goto("/zh-CN/conversations/1/chat");

    const log = page.getByRole("log");
    await expect(log).toBeVisible({ timeout: 15_000 });

    const dims = await page.evaluate(() => {
      const main = document.querySelector("main");
      return {
        mainScrollHeight: main?.scrollHeight ?? 0,
        mainClientHeight: main?.clientHeight ?? 0,
      };
    });
    expect(dims.mainScrollHeight).toBeGreaterThan(dims.mainClientHeight + 200);

    await page.mouse.move(460, 260);

    const before = await page.evaluate(() => document.querySelector("main")?.scrollTop ?? 0);
    await page.mouse.wheel(0, 1400);

    await expect
      .poll(() => page.evaluate(() => document.querySelector("main")?.scrollTop ?? 0))
      .toBeGreaterThan(before);

    const logScrollTop = await log.evaluate((el) => (el as HTMLElement).scrollTop);
    expect(logScrollTop).toBe(0);
  });

  test("register page renders (zh-CN)", async ({ page }) => {
    await page.goto("/zh-CN/register");
    await expect(
      page.getByRole("button", { name: "注册并登录" }),
    ).toBeVisible();
  });

  test("english login renders", async ({ page }) => {
    await page.goto("/en/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("public guide renders", async ({ page }) => {
    await page.goto("/guide");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /去登录|Sign in|前往登入/i }),
    ).toBeVisible();
  });

  test("authenticated shell exposes logout and clears the session", async ({
    page,
  }) => {
    await seedSession(page);
    await page.route(isConversationsListUrl, async (route) => {
      await route.fulfill({ json: [] });
    });

    await page.goto("/zh-CN/conversations");
    await expect(page.locator("main")).toBeVisible({ timeout: 15_000 });

    await page
      .getByRole("banner")
      .getByRole("button", { name: "退出登录" })
      .click();

    await expect(page).toHaveURL(/\/login$/);
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("hkia_token")))
      .toBeNull();
  });

  test("product source link stays inside the product library", async ({ page }) => {
    await seedSession(page);
    await page.route(isKnowledgeProductsKeywordUrl, async (route) => {
      await route.fulfill({
        json: [
          {
            id: "sample-prod-1",
            name: "示例高端医疗（演示）",
            category: "医疗",
            summary: "用于演示的知识库条目。",
            source_url: "https://example.com/sample-medical",
            is_sample: true,
            updated_at: "2026-05-01",
          },
        ],
      });
    });

    await page.goto("/zh-CN/knowledge");

    const source = page.getByRole("link", { name: "资料来源" });
    await expect(source).toHaveAttribute(
      "href",
      "/knowledge/sample-prod-1",
    );
  });
});
