import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourceBadge } from "@/components/ui/Badges";
import { SyntheticBanner } from "./SyntheticBanner";

describe("synthetic labelling", () => {
  it("states that synthetic data is not MOIL data", () => {
    render(<SyntheticBanner />);
    expect(screen.getByText("SYNTHETIC DEMONSTRATION DATA")).toBeInTheDocument();
    expect(screen.getByText(/Not MOIL operational records/)).toBeInTheDocument();
  });

  it("labels every source type explicitly", () => {
    const { rerender } = render(<SourceBadge sourceType="synthetic" />);
    expect(screen.getByText("SYNTHETIC")).toBeInTheDocument();
    rerender(<SourceBadge sourceType="user_provided" />);
    expect(screen.getByText("USER-PROVIDED")).toBeInTheDocument();
    rerender(<SourceBadge sourceType="public" />);
    expect(screen.getByText("PUBLIC")).toBeInTheDocument();
  });
});
