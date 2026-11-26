import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { validateSetupDetails } from "@/lib/setup";

const valid = { full_name: "Meera Krishnan", email: "meera@example.com", password: "a-unique-secure-password-42", confirm_password: "a-unique-secure-password-42" };

afterEach(() => vi.unstubAllGlobals());

describe("first-run setup", () => {
  it("detects a fresh database that requires setup", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ setup_required: true }), { status: 200, headers: { "content-type": "application/json" } })));
    await expect(api.setupStatus()).resolves.toEqual({ setup_required: true });
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/setup/status"), expect.objectContaining({ credentials: "include" }));
  });

  it("detects completed setup and uses the normal login path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ setup_required: false }), { status: 200, headers: { "content-type": "application/json" } })));
    await expect(api.setupStatus()).resolves.toEqual({ setup_required: false });
  });

  it.each([true, false])("sends sample_data=%s using backend request contract", async (sample_data) => {
    const result = { setup_complete: true, sample_data_created: sample_data, administrator: { id: "id-1", full_name: valid.full_name, email: valid.email, role: "administrator", is_active: true } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 201, headers: { "content-type": "application/json" } })));
    await expect(api.initialize({ ...valid, sample_data })).resolves.toEqual(result);
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toEqual({ ...valid, sample_data });
  });

  it("validates name, email, password length, and confirmation before API submission", () => {
    expect(validateSetupDetails({ ...valid, full_name: " " })).toMatch(/full name/);
    expect(validateSetupDetails({ ...valid, email: "bad" })).toMatch(/email/);
    expect(validateSetupDetails({ ...valid, password: "short", confirm_password: "short" })).toMatch(/12 and 200/);
    expect(validateSetupDetails({ ...valid, confirm_password: "not-the-same-password" })).toMatch(/confirmation/);
    expect(validateSetupDetails(valid)).toBe("");
  });

  it("surfaces API failure for the wizard to display", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Initial setup has already been completed" }), { status: 409, headers: { "content-type": "application/json" } })));
    await expect(api.initialize({ ...valid, sample_data: false })).rejects.toMatchObject({ status: 409, message: "Initial setup has already been completed", name: "ApiError" });
  });
});
