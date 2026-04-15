import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { ServiceExposureScreen } from "./ServiceExposureScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("ServiceExposureScreen", () => {
  const session = {
    session: {
      repo: "secure-scan-studio-main",
      tracedPathsCount: 9,
      totalPathsCount: 12,
      graphSummary: {
        external_surfaces: ["REST API", "Webhook"],
        trust_boundaries: ["browser -> api", "api -> database"],
      },
      repositoryGraph: {
        public_entrypoints: ["src/main.tsx"],
        service_boundaries: ["ui/api"],
        external_calls: ["auth provider"],
        data_flows: ["request -> service -> sink"],
      },
      securityRegistry: {
        network_boundaries: ["http", "db"],
        user_inputs: ["forms"],
        data_sinks: ["database"],
        auth_components: ["session"],
      },
      pathSummary: {
        dominant_path_type: "request-driven",
      },
    },
  };

  it("renders exposure summaries", () => {
    render(
      <ServiceExposureScreen
        session={session as never}
        serviceSummary={{
          sessionCount: 4,
          hotspotCount: 3,
          criticalHotspots: 2,
          boundaryDrag: 1,
          networkDrag: 1,
          pathDrag: 1,
          entrypointDrag: 1,
          topHotspotLabel: "high - path concentration",
          topServices: { api: 3 },
        }}
        serviceExposureFeed={[
          {
            sessionId: "session-1",
            repo: "shared-api-surface",
            hotspotClass: "path-drag",
            priority: "high",
            label: "High path concentration",
          },
        ]}
      />,
    );

    expect(screen.getByText(/service exposure view/i)).toBeInTheDocument();
    expect(screen.getByText(/repository exposure graph/i)).toBeInTheDocument();
    expect(screen.getByText(/security registry exposure/i)).toBeInTheDocument();
    expect(screen.getAllByText(/external surfaces/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/exposure hotspots/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/cross-session exposure feed/i)).toBeInTheDocument();
    expect(screen.getByText(/shared-api-surface/i)).toBeInTheDocument();
  });

  it("does not render footer back button", () => {
    render(<ServiceExposureScreen session={session as never} />);

    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });
});
