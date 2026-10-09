import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, buildUrl } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("buildUrl", () => {
  it("drops empty query values and encodes the rest", () => {
    expect(buildUrl("/api/overview", { dataset_id: "demo", start: undefined, mine_id: "", zone_id: "A B" })).toBe(
      "/api/overview?dataset_id=demo&zone_id=A+B",
    );
  });
});

describe("apiGet error handling", () => {
  it("maps the backend error envelope to a typed ApiError without leaking internals", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        { error: { code: "validation_failed", message: "Mine 'X' is not in this dataset.", request_id: "req-123" } },
        422,
      ),
    );
    const error = await apiGet("/api/overview").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    const typed = error as ApiError;
    expect(typed.status).toBe(422);
    expect(typed.code).toBe("validation_failed");
    expect(typed.message).toBe("Mine 'X' is not in this dataset.");
    expect(typed.requestId).toBe("req-123");
    expect(typed.stack ?? "").not.toContain("Traceback");
  });

  it("falls back to a plain message when the body is not JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html>502 bad gateway</html>", { status: 502 }));
    const error = (await apiGet("/api/overview").catch((caught: unknown) => caught)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.message).toBe("The server could not complete the request. Try again shortly.");
    expect(error.message).not.toContain("html");
  });

  it("reports network failures as a backend-unreachable error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed: ECONNREFUSED 127.0.0.1:8000"));
    const error = (await apiGet("/api/overview").catch((caught: unknown) => caught)) as ApiError;
    expect(error.code).toBe("network_error");
    expect(error.message).toContain("could not be reached");
    expect(error.message).not.toContain("ECONNREFUSED");
  });

  it("returns parsed JSON on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ status: "ok" }));
    await expect(apiGet<{ status: string }>("/api/health")).resolves.toEqual({ status: "ok" });
  });
});
