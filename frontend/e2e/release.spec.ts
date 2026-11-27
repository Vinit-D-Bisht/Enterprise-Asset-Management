import { randomBytes, randomUUID } from "node:crypto";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiBase = process.env.EAMMS_E2E_API_URL ?? "http://127.0.0.1:8001";
const runId = randomUUID().slice(0, 8);
const password = `E2e!${randomBytes(28).toString("base64url")}`;
const emails = {
  administrator: `admin-${runId}@example.com`,
  asset_manager: `manager-${runId}@example.com`,
  technician: `technician-${runId}@example.com`,
  employee: `employee-${runId}@example.com`,
};
const roleNames = {
  administrator: "E2E Administrator",
  asset_manager: "E2E Asset Manager",
  technician: "E2E Technician",
  employee: "E2E Employee",
} as const;

async function loginInBrowser(page: Page, email: string) {
  await page.goto("/login");
  await submitLoginForm(page, email);
}

async function submitLoginForm(page: Page, email: string) {
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in securely/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function getAccessToken(request: APIRequestContext, email: string) {
  const response = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password },
  });
  expect(response.status()).toBe(200);
  return (await response.json()).access_token as string;
}

async function apiRequest(
  request: APIRequestContext,
  token: string,
  method: string,
  path: string,
  data?: unknown,
) {
  return request.fetch(`${apiBase}/api/v1${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
}

test.describe("first-run and release workflows", () => {
  test("sample-data setup immediately allows Super Admin sign-in without a reload", async ({ page, request }) => {
    let setupRequestCount = 0;
    page.on("request", (browserRequest) => {
      if (browserRequest.url().endsWith("/api/v1/setup/initial-admin")) setupRequestCount += 1;
    });
    await page.goto("/login");
    await expect(page.getByText("First-run setup", { exact: false })).toBeVisible();
    await page.getByLabel("Full name").fill(roleNames.administrator);
    await page.getByLabel("Email address").fill(emails.administrator);
    await page.getByLabel(/^Password/).fill(password);
    await page.getByLabel("Confirm password").fill(password);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByRole("button", { name: /yes, create sample data/i }).click();
    await page.getByRole("button", { name: /review & create/i }).click();
    await expect(page.getByRole("heading", { name: "Sign in to your workspace" })).toBeVisible();
    await expect(page.getByRole("status")).toContainText("sample data completed successfully");
    await expect(page.getByLabel("Email address")).toHaveValue(emails.administrator);
    await expect(page.getByRole("button", { name: /review & create/i })).toHaveCount(0);
    await expect.poll(() => setupRequestCount).toBe(1);
    await submitLoginForm(page, emails.administrator);

    const repeatSetup = await request.post(`${apiBase}/api/v1/setup/initial-admin`, {
      data: { full_name: roleNames.administrator, email: emails.administrator, password, confirm_password: password, sample_data: true },
    });
    expect(repeatSetup.status()).toBe(409);

    const token = await getAccessToken(request, emails.administrator);
    const assets = await apiRequest(request, token, "GET", "/assets?page_size=100");
    expect(assets.status()).toBe(200);
    expect((await assets.json()).total).toBeGreaterThan(0);
  });

  test("empty first-run setup immediately allows sign-in and cannot be submitted again", async ({ page, request }) => {
    let setupRequestCount = 0;
    page.on("request", (browserRequest) => {
      if (browserRequest.url().endsWith("/api/v1/setup/initial-admin")) setupRequestCount += 1;
    });
    await page.goto("/login");
    await expect(page.getByText("First-run setup", { exact: false })).toBeVisible();
    await page.getByLabel("Full name").fill("E2E Empty Administrator");
    await page.getByLabel("Email address").fill(emails.administrator);
    await page.getByLabel(/^Password/).fill(password);
    await page.getByLabel("Confirm password").fill(password);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByRole("button", { name: /no, start empty/i }).click();
    await page.getByRole("button", { name: /review & create/i }).click();
    await expect(page.getByRole("heading", { name: "Sign in to your workspace" })).toBeVisible();
    await expect(page.getByRole("status")).toContainText("Workspace setup completed successfully");
    await expect(page.getByLabel("Email address")).toHaveValue(emails.administrator);
    await expect(page.getByRole("button", { name: /review & create/i })).toHaveCount(0);
    await expect.poll(() => setupRequestCount).toBe(1);
    await submitLoginForm(page, emails.administrator);

    const accessToken = await getAccessToken(request, emails.administrator);
    const assets = await apiRequest(request, accessToken, "GET", "/assets?page_size=100");
    expect(assets.status()).toBe(200);
    expect((await assets.json()).total).toBe(0);
    const repeatSetup = await request.post(`${apiBase}/api/v1/setup/initial-admin`, {
      data: { full_name: "E2E Empty Administrator", email: emails.administrator, password, confirm_password: password, sample_data: false },
    });
    expect(repeatSetup.status()).toBe(409);
  });

  test("all roles, core operations, exports, themes, and responsive navigation work", async ({ browser, request }) => {
    const badLoginResponses = await Promise.all(
      Array.from({ length: 8 }, () =>
        request.post(`${apiBase}/api/v1/auth/login`, {
          data: { email: `rate-check-${runId}@example.com`, password },
        }),
      ),
    );
    expect(badLoginResponses.filter((response) => response.status() === 401)).toHaveLength(4);
    expect(badLoginResponses.filter((response) => response.status() === 429)).toHaveLength(4);

    const adminToken = await getAccessToken(request, emails.administrator);
    const departmentResponse = await apiRequest(request, adminToken, "POST", "/departments", {
      name: `E2E Operations ${runId}`,
      description: "Disposable Playwright records",
    });
    expect(departmentResponse.status()).toBe(201);
    const department = await departmentResponse.json();

    const userIds: Record<string, string> = {};
    for (const role of ["asset_manager", "technician", "employee"] as const) {
      const response = await apiRequest(request, adminToken, "POST", "/users", {
        full_name: roleNames[role],
        email: emails[role],
        password,
        role,
        department_id: department.id,
      });
      expect(response.status()).toBe(201);
      userIds[role] = (await response.json()).id as string;
    }

    const managerToken = await getAccessToken(request, emails.asset_manager);
    const technicianToken = await getAccessToken(request, emails.technician);
    const employeeToken = await getAccessToken(request, emails.employee);
    expect((await apiRequest(request, adminToken, "GET", "/users")).status()).toBe(200);
    expect((await apiRequest(request, managerToken, "GET", "/users")).status()).toBe(403);
    expect((await apiRequest(request, technicianToken, "GET", "/reports/dashboard")).status()).toBe(403);
    expect((await apiRequest(request, employeeToken, "GET", "/reports/dashboard")).status()).toBe(403);
    expect((await apiRequest(request, managerToken, "GET", "/reports/dashboard")).status()).toBe(200);

    const categoriesResponse = await apiRequest(request, managerToken, "GET", "/categories");
    expect(categoriesResponse.status()).toBe(200);
    const categories = await categoriesResponse.json();
    const categoryId = categories[0].id as string;
    const locationsResponse = await apiRequest(request, managerToken, "GET", "/locations");
    const locations = await locationsResponse.json();
    const locationId = locations[0].id as string;
    const secondLocation = await apiRequest(request, managerToken, "POST", "/locations", {
      name: `E2E Bengaluru Annex ${runId}`,
      code: `E2E-${runId}`,
    });
    expect(secondLocation.status()).toBe(201);
    const secondLocationId = (await secondLocation.json()).id as string;

    const assetResponse = await apiRequest(request, managerToken, "POST", "/assets", {
      asset_tag: `E2E-${runId}`,
      name: "Playwright test laptop",
      category_id: categoryId,
      location_id: locationId,
      purchase_date: "2024-01-15",
      purchase_cost: "92000.00",
      residual_value: "5000.00",
      useful_life_months: 48,
    });
    expect(assetResponse.status()).toBe(201);
    const asset = await assetResponse.json();
    const updated = await apiRequest(request, managerToken, "PATCH", `/assets/${asset.id}`, {
      name: "Playwright test laptop updated",
    });
    expect(updated.status()).toBe(200);

    expect((await apiRequest(request, managerToken, "POST", `/assets/${asset.id}/allocate`, {
      user_id: userIds.employee,
      notes: "E2E allocation",
    })).status()).toBe(201);
    expect((await apiRequest(request, employeeToken, "GET", `/assets/${asset.id}/assignments`)).status()).toBe(200);
    expect((await apiRequest(request, managerToken, "POST", `/assets/${asset.id}/return`, { notes: "E2E return" })).status()).toBe(200);
    expect((await apiRequest(request, managerToken, "POST", `/assets/${asset.id}/transfer`, {
      to_location_id: secondLocationId,
      reason: "E2E relocation",
    })).status()).toBe(201);

    const warranty = await apiRequest(request, managerToken, "POST", `/assets/${asset.id}/warranties`, {
      start_date: "2024-01-15",
      end_date: "2027-01-15",
      terms: "E2E warranty",
    });
    expect(warranty.status()).toBe(201);
    expect((await apiRequest(request, employeeToken, "GET", `/assets/${asset.id}/qr`)).status()).toBe(200);

    const planResponse = await apiRequest(request, managerToken, "POST", "/maintenance-plans", {
      name: `E2E preventive ${runId}`,
      asset_id: asset.id,
      interval_days: 90,
      next_due_date: "2027-01-15",
    });
    expect(planResponse.status()).toBe(201);
    const plan = await planResponse.json();
    const workOrderResponse = await apiRequest(request, employeeToken, "POST", "/work-orders", {
      asset_id: asset.id,
      plan_id: plan.id,
      title: `E2E maintenance ${runId}`,
      priority: "medium",
    });
    expect(workOrderResponse.status()).toBe(201);
    const workOrder = await workOrderResponse.json();
    expect((await apiRequest(request, managerToken, "PATCH", `/work-orders/${workOrder.id}/assign`, {
      assigned_to_id: userIds.technician,
      due_date: "2027-01-16",
    })).status()).toBe(200);
    expect((await apiRequest(request, technicianToken, "PATCH", `/work-orders/${workOrder.id}/status`, {
      status: "in_progress",
    })).status()).toBe(200);
    expect((await apiRequest(request, technicianToken, "PATCH", `/work-orders/${workOrder.id}/status`, {
      status: "completed",
      resolution: "Checked and serviced",
    })).status()).toBe(200);

    const depreciation = await apiRequest(request, managerToken, "GET", "/reports/depreciation.csv?as_of_date=2027-01-15");
    expect(depreciation.status()).toBe(200);
    expect(await depreciation.text()).toContain(`E2E-${runId}`);
    expect((await apiRequest(request, managerToken, "GET", "/reports/audit.csv")).status()).toBe(403);
    expect((await apiRequest(request, adminToken, "GET", "/reports/audit.csv")).status()).toBe(200);

    const roleExpectations = [
      ["administrator", emails.administrator, "Departments", "People & access"],
      ["asset_manager", emails.asset_manager, "Reports & audit", null],
      ["technician", emails.technician, "Maintenance", null],
      ["employee", emails.employee, "Maintenance", null],
    ] as const;
    for (const [role, email, visibleLink, hiddenLink] of roleExpectations) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
      const page = await context.newPage();
      await loginInBrowser(page, email);
      await expect(page.getByRole("link", { name: visibleLink }).first()).toBeVisible();
      if (hiddenLink) await expect(page.getByRole("link", { name: hiddenLink })).toBeVisible();
      if (role !== "administrator") {
        await expect(page.getByRole("link", { name: "Departments" })).toHaveCount(0);
        await expect(page.getByRole("link", { name: "People & access" })).toHaveCount(0);
      }
      if (role === "administrator") {
        const theme = page.getByLabel("Color theme");
        await theme.selectOption("dark");
        await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
        await page.reload();
        await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
        await page.emulateMedia({ colorScheme: "dark" });
        await theme.selectOption("system");
        await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
        await page.emulateMedia({ colorScheme: "light" });
        await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
        await theme.selectOption("light");
      }
      const widths = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        content: document.documentElement.scrollWidth,
      }));
      expect(widths.content).toBeLessThanOrEqual(widths.viewport);
      await context.close();
    }

    const managerContext = await browser.newContext();
    const managerPage = await managerContext.newPage();
    await loginInBrowser(managerPage, emails.asset_manager);
    await managerPage.getByRole("link", { name: "Reports & audit" }).click();
    await expect(managerPage.getByRole("heading", { name: "Reports" })).toBeVisible();
    const downloadPromise = managerPage.waitForEvent("download");
    await managerPage.getByRole("button", { name: "Export CSV" }).first().click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^eamms-depreciation-.*\.csv$/);
    await managerContext.close();
  });
});
