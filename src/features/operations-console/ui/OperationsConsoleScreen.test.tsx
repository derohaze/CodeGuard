import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { OperationsConsoleScreen } from "./OperationsConsoleScreen";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...props}>{children}</div>,
  },
}));

describe("OperationsConsoleScreen", () => {
  it("renders autonomy readiness queue without footer navigation buttons", () => {
    render(<OperationsConsoleScreen session={buildBlockedSessionDetail() as never} />);

    expect(screen.getByText(/operations console/i)).toBeInTheDocument();
    expect(screen.getByText(/autonomy readiness queue/i)).toBeInTheDocument();
    expect(screen.getByText(/recommendation reuse queue/i)).toBeInTheDocument();
    expect(screen.getByText(/memory carry-forward/i)).toBeInTheDocument();
    expect(screen.getAllByText(/recovery playbook/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/session memory ledger/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/remediation history signals/i)).toBeInTheDocument();
    expect(screen.getByText(/self-healing controller queue/i)).toBeInTheDocument();
    expect(screen.getByText(/autonomous control plan/i)).toBeInTheDocument();
    expect(screen.getByText(/continuous remediation workflow/i)).toBeInTheDocument();
    expect(screen.getAllByText(/human control required/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/approval hold remains active/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/suppressed strategies must not be reused automatically/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/policy gate blocks continuous remediation/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/suppressed strategy memory must carry forward/i).length).toBeGreaterThan(0);

    expect(screen.queryByRole("button", { name: /open audit trail/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^back$/i })).not.toBeInTheDocument();
  });

  it("launches a controlled apply from the continuous execution queue", () => {
    const onRunContinuousApply = vi.fn();

    render(
      <OperationsConsoleScreen
        session={buildExecutableSessionDetail() as never}
        onRunContinuousApply={onRunContinuousApply}
      />,
    );

    expect(screen.getByText(/continuous execution queue/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /run controlled apply/i }));

    expect(onRunContinuousApply).toHaveBeenCalledWith({
      findingId: "finding-1",
      excludedStrategyIds: ["legacy-guard", "sanitize-query"],
      attemptedStrategyIds: ["legacy-guard", "sanitize-query"],
    });
  });
});

function buildBlockedSessionDetail() {
  return {
    session: {
      id: "session-1",
      title: "April Security Run",
      repo: "secure-scan-studio-main",
      time: "10m ago",
      unread: false,
      status: "completed",
      preview: "Workflow closure is human-controlled while approval pressure remains open.",
      scanMode: "deep",
      criticalCount: 1,
      warningCount: 2,
      findingsCount: 2,
      candidateFindingsCount: 0,
      progress: 100,
      phaseProgress: 100,
      progressMessage: "Completed",
      currentPhase: "Completed",
      elapsedSeconds: 120,
      progressLogs: [],
      progressCounters: null,
      runtimeMetrics: null,
      scanPlan: null,
      repositorySummary: "Repository summary",
      repositoryInventory: null,
      frameworkProfile: null,
      repositoryGraph: null,
      graphSummary: null,
      securityRegistry: null,
      segmentationSummary: null,
      pathInventory: null,
      pathSummary: null,
      reviewQueueSummary: null,
      annotations: [],
      annotationSummary: null,
      coverageSnapshot: null,
      coverageSummary: "Coverage summary",
      coveragePercent: 88,
      reviewedFilesCount: 12,
      eligibleFilesCount: 14,
      reviewedBlocksCount: 50,
      totalBlocksCount: 60,
      reviewedLinesCount: 400,
      totalLinesCount: 450,
      tracedPathsCount: 8,
      totalPathsCount: 10,
      skippedFilesCount: 2,
      highRiskFilesCount: 3,
      isSafe: false,
      securityScore: 76,
      scoreRationale: null,
      targetType: "folder",
      sourcePath: "D:\\HAZE\\projects\\secure-scan-studio-main",
      preset: "balanced",
      lastVerification: null,
      workflowSummary: {
        state: "approval-control",
        label: "Approval hold",
        summary: "Approval is still required before local apply.",
        nextAction: "Collect approval",
        activeController: "approval-controller",
        plannerStage: "apply-ready",
        recoverySummary: null,
        recoveryExecution: {
          selectedPath: "manual-review",
          executionState: "stalled",
          executionLane: "manual-lane",
          reenteredPlanner: false,
          pathReason: "Recovery is waiting for manual review.",
        },
        memorySummary: {
          attemptedStrategyCount: 4,
          rejectedPathCount: 2,
          escalatedPathCount: 1,
          knownStrategyIds: ["strict-escape", "bounded-query", "legacy-guard"],
          suppressedStrategyCount: 2,
          suppressionState: "active",
          nextMemoryAction: "generate-materially-different-patch",
          recentConstraint: "Previous query guard left residual risk open around the auth boundary.",
        },
        operationsSummary: {
          currentLane: "approval-lane",
          nextLane: "closure-lane",
          pendingHandoff: true,
          handoffReason: "Approval is still pending.",
          activeItemCount: 2,
        },
        operationsExecution: {
          currentHandoff: "decision -> approval",
          handoffStatus: "blocked",
          owningController: "approval-controller",
          pendingExecutionStep: "Collect reviewer input",
          stepCompletionState: "waiting",
        },
        workflowClosure: {
          closureState: "human-controlled",
          closureLabel: "Human-controlled",
          closureReason: "Approval and escalation remain open.",
          autonomousReady: false,
          requiresHumanControl: true,
          nextClosureStep: "collect approval",
        },
        blockingItems: 2,
      },
      createdAt: "2026-04-12T02:00:00Z",
      updatedAt: "2026-04-12T03:00:00Z",
    },
    issues: { critical: 1, high: 1, medium: 0, low: 0 },
    findings: [
      {
        id: "finding-1",
        severity: "high",
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
        remediationStatus: "validation_failed",
        approvalStatus: "escalated",
        approvalHistory: [{ status: "escalated", note: "Needs extra review", timestamp: "2026-04-12T00:00:00Z" }],
        appliedStrategyId: null,
        remediationNotes: ["Verification left residual risk open."],
        attemptedStrategyIds: ["legacy-guard", "sanitize-query"],
        decisionSummary: null,
      },
      {
        id: "finding-2",
        severity: "medium",
        title: "Shell command path is now escaped",
        file: "app/features/jobs/runner.py",
        line: 12,
        lineEnd: 13,
        category: "command injection",
        confidence: 73,
        summary: "Escaping strategy closed the sink.",
        impact: "Command execution path is now bounded.",
        explanation: "A verified-safe strategy was recorded for future matching cases.",
        evidence: "escape(command)",
        attackSimulation: { input: "", execution: "", result: "" },
        auditLog: [],
        fixSuggestions: [],
        remediationStatus: "verified_fixed",
        approvalStatus: "approved",
        approvalHistory: [{ status: "approved", note: "Approved after verification", timestamp: "2026-04-12T00:05:00Z" }],
        appliedStrategyId: "strict-escape",
        remediationNotes: [],
        attemptedStrategyIds: ["strict-escape"],
        decisionSummary: null,
      },
    ],
    candidateFindings: [],
    verdict: "issues_found",
    completedAt: "2026-04-12T03:00:00Z",
    errorMessage: null,
  };
}

function buildExecutableSessionDetail() {
  const detail = buildBlockedSessionDetail();

  return {
    ...detail,
    session: {
      ...detail.session,
      workflowSummary: {
        ...detail.session.workflowSummary,
        state: "verification-follow-up",
        label: "Retry-ready",
        summary: "A low-risk controlled apply can proceed for the verified-safe lane.",
        nextAction: "Run controlled apply",
        activeController: "recovery-controller",
        recoverySummary: {
          retryAvailable: true,
          retryableFindings: 1,
          attemptedStrategies: 2,
          latestFailureReason: "Previous retry left residual sink risk open.",
          lastVerificationStatus: "manual_review_required",
          recoveryState: "retry-ready",
          nextTransition: "retry-remediation",
          controllerStatus: "waiting-for-retry",
          plannerReentryReady: false,
        },
        recoveryExecution: {
          selectedPath: "retry-path",
          executionState: "ready",
          executionLane: "retry-lane",
          reenteredPlanner: false,
          pathReason: "A guarded retry can proceed under policy-safe conditions.",
        },
        workflowClosure: {
          closureState: "autonomous-ready",
          closureLabel: "Autonomous-ready",
          closureReason: "Approval is already resolved for the retry candidate.",
          autonomousReady: true,
          requiresHumanControl: false,
          nextClosureStep: "run controlled apply",
        },
      },
    },
    findings: [
      {
        ...detail.findings[0],
        approvalStatus: "approved",
        approvalHistory: [{ status: "approved", note: "Approved for guarded retry", timestamp: "2026-04-12T00:00:00Z" }],
        decisionSummary: {
          ...detail.findings[0].decisionSummary,
          applyReadiness: "approval-required-before-apply",
        },
      },
      detail.findings[1],
    ],
  };
}
