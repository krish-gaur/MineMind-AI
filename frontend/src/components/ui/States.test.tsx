import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { describeError, ErrorState } from "./States";

describe("describeError", () => {
  it("explains network failures in plain language", () => {
    const described = describeError(
      new ApiError("The MineMind API could not be reached.", { status: 0, code: "network_error" }),
    );
    expect(described.title).toBe("Backend unreachable");
  });

  it("uses a generic message for unknown errors", () => {
    expect(describeError(new Error("boom at /srv/app.py line 3")).message).not.toContain("/srv");
  });
});

describe("ErrorState", () => {
  it("shows a request reference and retries on click", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        error={new ApiError("Dataset not found.", { status: 404, code: "not_found", requestId: "abc-123" })}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Dataset not found.");
    expect(screen.getByText(/Reference: abc-123/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
