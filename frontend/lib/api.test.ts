import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, getAccessToken, setAccessToken } from "@/lib/api";

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe("authenticated API client", () => {
  it("sends bearer access tokens and credentials to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ value: 7 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("access-token");

    await expect(api.get<{ value: number }>("/assets")).resolves.toEqual({ value: 7 });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/v1\/assets$/);
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit;
    expect(requestOptions.credentials).toBe("include");
    expect(new Headers(requestOptions.headers).get("Authorization")).toBe("Bearer access-token");
  });

  it("rotates the refresh cookie and retries one unauthorized request", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "renewed-token" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get<{ items: unknown[] }>("/assets")).resolves.toEqual({ items: [] });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/auth\/refresh$/);
    expect(getAccessToken()).toBe("renewed-token");
  });

  it("surfaces backend validation messages without retrying non-auth failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "Request validation failed",
      errors: [{ loc: ["body", "asset_tag"], msg: "Field required", type: "missing" }],
    }), { status: 422, headers: { "Content-Type": "application/json" } })));

    await expect(api.post("/assets", {})).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      message: "Request validation failed",
    } satisfies Partial<ApiError>);
  });
});
