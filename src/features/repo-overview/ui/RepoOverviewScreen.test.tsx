import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { RepoOverviewScreen } from "./RepoOverviewScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("RepoOverviewScreen", () => {
  const session = {
    session: {
      repo: "secure-scan-studio-main",
      targetType: "folder",
      repositorySummary: "Repository contains a web application and supporting auth services.",
      repositoryInventory: { file_count: 42 },
      frameworkProfile: {
        primary_framework: "React",
        languages: ["TypeScript", "Python"],
        runtimes: ["Node.js"],
        package_managers: ["bun"],
      },
      graphSummary: {
        entrypoints: ["src/main.tsx"],
        services: ["api", "ui"],
        trust_boundaries: ["browser -> api"],
        external_surfaces: ["REST API"],
      },
      segmentationSummary: {
        critical_zones: ["auth"],
        sensitive_files: ["src/shared/api/security.ts"],
        identity_surfaces: ["login"],
        config_surfaces: ["vite.config.ts"],
      },
      securityRegistry: {
        auth_components: ["session"],
        data_sinks: ["database"],
        user_inputs: ["forms"],
        network_boundaries: ["http"],
      },
      reviewedFilesCount: 24,
      eligibleFilesCount: 30,
      coverageSummary: "Coverage remained partial because generated assets were skipped.",
      coveragePercent: 80,
      highRiskFilesCount: 4,
      skippedFilesCount: 3,
      tracedPathsCount: 9,
      totalPathsCount: 12,
      elapsedSeconds: 125,
      securityScore: 78,
    },
  };

  it("renders repository-level summaries", () => {
    render(
      <RepoOverviewScreen
        session={session as never}
        repoSummary={{
          sessionCount: 10,
          hotspotCount: 3,
          criticalHotspots: 2,
          identityZones: 1,
          exposureZones: 1,
          dataZones: 1,
          coverageZones: 0,
          topHotspotLabel: "critical - identity-zone",
          topRepositories: { "secure-scan-studio-main": 3 },
        }}
        repoHotspotFeed={[
          {
            sessionId: "session-1",
            repo: "shared-auth-service",
            hotspotClass: "identity-zone",
            priority: "critical",
            label: "Critical identity zone",
          },
        ]}
      />,
    );

    expect(screen.getByText(/repo overview/i)).toBeInTheDocument();
    expect(screen.getByText(/framework profile/i)).toBeInTheDocument();
    expect(screen.getAllByText(/repository graph/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/security segmentation/i)).toBeInTheDocument();
    expect(screen.getAllByText(/security registry/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/repo hotspots/i)).toBeInTheDocument();
    expect(screen.getByText(/repository hotspots/i)).toBeInTheDocument();
    expect(screen.getAllByText(/repo intelligence ledger/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/cross-session repo hotspot feed/i)).toBeInTheDocument();
    expect(screen.getByText(/shared-auth-service/i)).toBeInTheDocument();
  });

  it("does not render footer navigation buttons", () => {
    render(<RepoOverviewScreen session={session as never} />);

    expect(screen.queryByRole("button", { name: /open service exposure/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open team posture/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });
});
