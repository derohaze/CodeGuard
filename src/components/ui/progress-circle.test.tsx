import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressCircle } from "./progress-circle";

describe("ProgressCircle", () => {
  it("updates the visible stroke geometry when the value changes", () => {
    const { rerender } = render(<ProgressCircle aria-label="Context usage" value={0} />);

    const indicator = screen.getByLabelText("Context usage").querySelector(
      '[data-slot="progress-circle-indicator"]',
    );

    expect(indicator).not.toBeNull();
    const initialDashOffset = indicator?.getAttribute("stroke-dashoffset");
    const initialDashArray = indicator?.getAttribute("stroke-dasharray");

    rerender(<ProgressCircle aria-label="Context usage" value={19} />);

    expect(indicator?.getAttribute("stroke-dasharray")).toBe(initialDashArray);
    expect(indicator?.getAttribute("stroke-dashoffset")).not.toBe(initialDashOffset);
  });

  it("supports separate track and indicator colors", () => {
    render(
      <ProgressCircle
        aria-label="Context usage"
        value={55}
        trackColor="#d4d4d8"
        indicatorColor="#ef4444"
      />,
    );

    const root = screen.getByLabelText("Context usage");
    const track = root.querySelector('[data-slot="progress-circle-track"]');
    const indicator = root.querySelector('[data-slot="progress-circle-indicator"]');

    expect(track?.getAttribute("stroke")).toBe("#d4d4d8");
    expect(indicator?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("keeps a visible progress segment for small non-zero values", () => {
    render(<ProgressCircle aria-label="Context usage" value={1} size={18} strokeWidth={3} />);

    const indicator = screen
      .getByLabelText("Context usage")
      .querySelector('[data-slot="progress-circle-indicator"]');

    expect(indicator).not.toBeNull();
    expect(indicator?.getAttribute("stroke-dashoffset")).toBe("94");
  });
});
