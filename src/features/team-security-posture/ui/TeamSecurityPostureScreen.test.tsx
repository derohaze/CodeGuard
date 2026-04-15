import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { TeamSecurityPostureScreen } from "./TeamSecurityPostureScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("TeamSecurityPostureScreen", () => {
  const sessions = [
    {
      id: "session-1",
      repo: "secure-scan-studio-main",
      status: "completed",
      scanMode: "deep",
      currentPhase: "Completed",
      findingsCount: 6,
      candidateFindingsCount: 2,
      criticalCount: 1,
      warningCount: 3,
      securityScore: 72,
      isSafe: false,
      coveragePercent: 84,
      highRiskFilesCount: 3,
      skippedFilesCount: 1,
      workflowSummary: {
        state: "approval-control",
        label: "Approval hold",
        summary: "Approval is still required.",
        nextAction: "Collect approval",
        activeController: "approval-controller",
        blockingItems: 1,
        workflowClosure: {
          closureState: "human-controlled",
          closureLabel: "Human-controlled",
          closureReason: "Approval is still required.",
          autonomousReady: false,
          requiresHumanControl: true,
          nextClosureStep: "collect approval",
        },
      },
    },
    {
      id: "session-2",
      repo: "internal-auth-service",
      status: "completed",
      scanMode: "fast",
      currentPhase: "Completed",
      findingsCount: 1,
      candidateFindingsCount: 0,
      criticalCount: 0,
      warningCount: 1,
      securityScore: 91,
      isSafe: true,
      coveragePercent: 92,
      highRiskFilesCount: 1,
      skippedFilesCount: 0,
      workflowSummary: null,
    },
  ];

  it("renders workspace posture summaries", () => {
    render(
      <TeamSecurityPostureScreen
        sessions={sessions as never}
        activeSessionId="session-1"
        teamSummary={{
          sessionCount: 2,
          hotspotCount: 3,
          criticalHotspots: 1,
          controlDrag: 1,
          riskDrag: 1,
          coverageDrag: 1,
          throughputDrag: 0,
          topHotspotLabel: "critical - shared-auth-service",
        }}
        teamPostureFeed={[
          {
            sessionId: "session-1",
            repo: "shared-auth-service",
            status: "completed",
            hotspotClass: "control-drag",
            priority: "critical",
            findingCount: 4,
            coveragePercent: 67,
          },
        ]}
      />,
    );

    expect(screen.getByText(/team security posture/i)).toBeInTheDocument();
    expect(screen.getByText(/session posture breakdown/i)).toBeInTheDocument();
    expect(screen.getByText(/highest-risk repositories/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace hotspot queue/i)).toBeInTheDocument();
    expect(screen.getAllByText(/secure-scan-studio-main/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/shared-auth-service/i).length).toBeGreaterThan(0);
  });

  it("does not render footer back button", () => {
    render(<TeamSecurityPostureScreen sessions={sessions as never} activeSessionId="session-1" />);

    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });
});
