import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { AuditTrailScreen } from "./AuditTrailScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("AuditTrailScreen", () => {
  const session = {
    session: {
      repo: "secure-scan-studio-main",
      workflowSummary: {
        label: "Approval hold",
        workflowClosure: {
          closureLabel: "Human-controlled",
          closureState: "human-controlled" as const,
          closureReason: "Approval is still required before local apply.",
          autonomousReady: false,
          requiresHumanControl: true,
          nextClosureStep: "collect approval",
        },
        operationsExecution: {
          currentHandoff: "decision -> approval",
          handoffStatus: "pending" as const,
          owningController: "approval-controller" as const,
          pendingExecutionStep: "Collect reviewer input",
          stepCompletionState: "waiting",
        },
        recoveryExecution: {
          selectedPath: "manual-review" as const,
          executionState: "held" as const,
          executionLane: "manual-lane" as const,
          reenteredPlanner: false,
          pathReason: "The previous apply attempt was held for review.",
        },
      },
    },
    findings: [
      {
        id: "finding-1",
        severity: "high" as const,
        title: "Dynamic query construction may allow injection",
        file: "app/features/login/router.py",
        line: 43,
        lineEnd: 44,
        category: "SQL injection",
        confidence: 84,
        summary: "Dynamic query is built from user input.",
        impact: "Authentication lookups may be bypassed.",
        explanation: "User-controlled input reaches the query sink.",
        evidence: "query = f\"SELECT ...\"",
        attackSimulation: {
          input: "POST /login",
          execution: "router -> service -> query builder",
          result: "Authentication bypass",
        },
        auditLog: ["Approval gate held the patch for reviewer confirmation."],
        fixSuggestions: [],
        remediationStatus: "patch_generated" as const,
        approvalStatus: "pending" as const,
        approvalHistory: [
          {
            status: "pending" as const,
            note: "Waiting for the platform owner to approve the patch.",
            timestamp: "2026-04-12T01:10:00Z",
          },
        ],
        appliedStrategyId: null,
        remediationNotes: ["Patch generated and queued for review."],
        attemptedStrategyIds: ["guard-1"],
        decisionSummary: null,
      },
    ],
  };

  it("renders audit trail workflow and a normalized recent timeline", () => {
    render(<AuditTrailScreen session={session as never} onSelectFinding={vi.fn()} />);

    expect(screen.getByText(/audit trail/i)).toBeInTheDocument();
    expect(screen.getAllByText(/workflow closure/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/run audit log/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/finding trail/i)).toBeInTheDocument();
    expect(screen.getByText(/latest audit signal/i)).toBeInTheDocument();
    expect(screen.getByText(/recent timeline/i)).toBeInTheDocument();
    expect(screen.getAllByText(/approval pending/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/dynamic query construction may allow injection/i)).toBeInTheDocument();
  });

  it("opens the selected finding without footer navigation buttons", () => {
    const onSelectFinding = vi.fn();
    render(<AuditTrailScreen session={session as never} onSelectFinding={onSelectFinding} />);

    fireEvent.click(screen.getByRole("button", { name: /dynamic query construction may allow injection/i }));

    expect(onSelectFinding).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /open governance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });
});
