import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { GovernanceCenterScreen } from "./GovernanceCenterScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("GovernanceCenterScreen", () => {
  const session = {
    session: {
      repo: "secure-scan-studio-main",
      workflowSummary: {
        workflowClosure: {
          closureLabel: "Human-controlled",
          closureReason: "Approval and escalation remain open.",
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
        attackSimulation: { input: "", execution: "", result: "" },
        auditLog: [],
        fixSuggestions: [],
        remediationStatus: "patch_generated" as const,
        approvalStatus: "pending" as const,
        approvalHistory: [],
        appliedStrategyId: null,
        remediationNotes: [],
        attemptedStrategyIds: [],
        decisionSummary: null,
      },
    ],
  };

  it("renders governance summaries and review queue", () => {
    render(<GovernanceCenterScreen session={session as never} />);

    expect(screen.getByText(/governance center/i)).toBeInTheDocument();
    expect(screen.getByText(/approval posture/i)).toBeInTheDocument();
    expect(screen.getAllByText(/policy posture/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/queue pressure/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/governance ledger/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/governance review queue/i)).toBeInTheDocument();
    expect(screen.getByText(/blocker class/i)).toBeInTheDocument();
    expect(screen.getByText(/approval-hold/i)).toBeInTheDocument();
    expect(screen.getByText(/next review action/i)).toBeInTheDocument();
    expect(screen.getAllByText(/dynamic query construction may allow injection/i).length).toBeGreaterThan(0);
  });

  it("does not render footer navigation buttons", () => {
    render(<GovernanceCenterScreen session={session as never} />);

    expect(screen.queryByRole("button", { name: /open analytics/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });
});
