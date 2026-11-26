import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("department API workflows", () => {
  it("lists and searches departments from the admin endpoint", async () => {
    const rows = [{ id: "dept-1", name: "Finance", description: null, employee_count: 2 }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(rows), { status: 200, headers: { "content-type": "application/json" } })));
    await expect(api.get<typeof rows>("/departments?search=fin")).resolves.toEqual(rows);
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/departments?search=fin"), expect.anything());
  });

  it("creates and edits using validated name and description payloads", async () => {
    const response = () => new Response(JSON.stringify({ id: "dept-1", name: "Finance", description: "Accounting", employee_count: 0 }), { status: 200, headers: { "content-type": "application/json" } });
    const fetchMock = vi.fn().mockResolvedValueOnce(response()).mockResolvedValueOnce(response());
    vi.stubGlobal("fetch", fetchMock);
    await api.post("/departments", { name: "Finance", description: null });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ name: "Finance", description: null });
    await api.patch("/departments/dept-1", { name: "Finance", description: "Accounting" });
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PATCH");
  });

  it("deletes a department and surfaces the employee-reference conflict", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Department is assigned to employees; reassign them before deleting it" }), { status: 409, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.delete<void>("/departments/dept-1")).resolves.toBeUndefined();
    await expect(api.delete<void>("/departments/dept-2")).rejects.toMatchObject({ status: 409, message: expect.stringContaining("reassign") });
  });
});
