import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { SettingsScreen } from "./SettingsScreen";
import { DEFAULT_RUNTIME_SETTINGS } from "@/features/settings/model/runtimeSettings";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: { children?: ReactNode }) => <button {...props}>{children}</button>,
  },
}));

describe("SettingsScreen", () => {
  it("emits preset patch when aggressive is selected", () => {
    const onPatchSettings = vi.fn();
    render(
      <SettingsScreen
        onBack={() => undefined}
        settings={{ ...DEFAULT_RUNTIME_SETTINGS, updatedAt: "2026-04-14T00:00:00Z" }}
        isSaving={false}
        onPatchSettings={onPatchSettings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /aggressive/i }));

    expect(onPatchSettings).toHaveBeenCalledWith({
      defaultPreset: "aggressive",
      defaultScanMode: "fast",
    });
  });

  it("emits switch patch for auto-open results", () => {
    const onPatchSettings = vi.fn();
    render(
      <SettingsScreen
        onBack={() => undefined}
        settings={{ ...DEFAULT_RUNTIME_SETTINGS, updatedAt: "2026-04-14T00:00:00Z" }}
        isSaving={false}
        onPatchSettings={onPatchSettings}
      />,
    );

    const switchButton = screen.getAllByRole("switch")[0];
    fireEvent.click(switchButton);

    expect(onPatchSettings).toHaveBeenCalledWith({ autoOpenResults: false });
  });
});
