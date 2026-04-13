import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import Page from "./Page";

const { listSessionsMock, getScanSessionMock, retryFixStrategyMock, applyFixMock, getRuntimeSettingsMock, updateRuntimeSettingsMock } = vi.hoisted(() => ({
  listSessionsMock: vi.fn(),
  getScanSessionMock: vi.fn(),
  retryFixStrategyMock: vi.fn(),
  applyFixMock: vi.fn(),
  getRuntimeSettingsMock: vi.fn(),
  updateRuntimeSettingsMock: vi.fn(),
}));

function stripMotionProps(props: Record<string, unknown>) {
  const {
    animate,
    exit,
    initial,
    transition,
    whileHover,
    whileTap,
    layout,
    drag,
    dragConstraints,
    ...rest
  } = props;
  void animate;
  void exit;
  void initial;
  void transition;
  void whileHover;
  void whileTap;
  void layout;
  void drag;
  void dragConstraints;
  return rest;
}

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  Reorder: {
    Group: ({ children, ...props }: { children?: ReactNode }) => <div {...stripMotionProps(props)}>{children}</div>,
    Item: ({ children, ...props }: { children?: ReactNode }) => <div {...stripMotionProps(props)}>{children}</div>,
  },
  motion: {
    div: ({ children, ...props }: { children?: ReactNode }) => <div {...stripMotionProps(props)}>{children}</div>,
    button: ({ children, ...props }: { children?: ReactNode }) => <button {...stripMotionProps(props)}>{children}</button>,
    span: ({ children, ...props }: { children?: ReactNode }) => <span {...stripMotionProps(props)}>{children}</span>,
  },
}));

vi.mock("@/widgets/app-shell", () => ({
  AppShell: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/features/sidebar-navigation", () => ({
  Sidebar: ({
    sessions,
    onOpenSession,
  }: {
    sessions: Array<{ id: string; title: string }>;
    onOpenSession: (session: { id: string; title: string }) => void;
  }) => (
    <div>
      {sessions.map((session) => (
        <button key={session.id} onClick={() => onOpenSession(session)}>
          {session.title}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("@/features/builder-agent", () => ({
  BuilderChatScreen: () => null,
  BuilderSidebar: () => null,
  useBuilderAgent: () => ({
    activeConversation: null,
    activeConversationId: null,
    addAttachment: vi.fn(),
    addWorkspace: vi.fn(),
    archiveWorkspaceThreads: vi.fn(),
    archiveThread: vi.fn(),
    collapseAllWorkspaces: vi.fn(),
    composerSettings: null,
    createPermanentWorktree: vi.fn(),
    createWorkspaceThread: vi.fn(),
    currentWorkspace: null,
    draft: "",
    expandedWorkspaceIds: [],
    expandAllWorkspaces: vi.fn(),
    hasPreviousConversation: false,
    isStreaming: false,
    messages: [],
    openConversation: vi.fn(),
    openWorkspaceInExplorer: vi.fn(),
    promptSuggestions: [],
    removeWorkspace: vi.fn(),
    removeThread: vi.fn(),
    removeAttachment: vi.fn(),
    reorderWorkspaces: vi.fn(),
    renameWorkspace: vi.fn(),
    renameThread: vi.fn(),
    reopenPreviousConversation: vi.fn(),
    sendMessage: vi.fn(),
    setPermissionMode: vi.fn(),
    setPlanMode: vi.fn(),
    setDraft: vi.fn(),
    stopStreaming: vi.fn(),
    showAllWorkspaceIds: [],
    threadGroups: [],
    toggleWorkspace: vi.fn(),
    toggleWorkspaceShowAll: vi.fn(),
  }),
}));

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children?: ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children?: ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children?: ReactNode }) => <>{children}</>,
}));

vi.mock("@/shared/api/security", async () => {
  const actual = await vi.importActual<object>("@/shared/api/security");
  return {
    ...actual,
    listSessions: listSessionsMock,
    getScanSession: getScanSessionMock,
    getRuntimeSettings: getRuntimeSettingsMock,
    updateRuntimeSettings: updateRuntimeSettingsMock,
    startScan: vi.fn(),
    subscribeToScanEvents: vi.fn(() => vi.fn()),
    applyFix: applyFixMock,
    deleteAllScanSessions: vi.fn(),
    deleteScanSession: vi.fn(),
    rejectFix: vi.fn(),
    rollbackFix: vi.fn(),
    retryFixStrategy: retryFixStrategyMock,
  };
});

vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  AlertDialogAction: ({ children, ...props }: { children?: ReactNode }) => <button {...props}>{children}</button>,
  AlertDialogCancel: ({ children, ...props }: { children?: ReactNode }) => <button {...props}>{children}</button>,
  AlertDialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  AlertDialogDescription: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe("Page operations console flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    retryFixStrategyMock.mockResolvedValue(buildRetryPlan());
    applyFixMock.mockResolvedValue(buildApplyExecution());
    listSessionsMock.mockResolvedValue([buildBlockedSessionSummary()]);
    getScanSessionMock.mockResolvedValue(buildBlockedSessionDetail());
    getRuntimeSettingsMock.mockResolvedValue({
      defaultPreset: "balanced",
      defaultScanMode: "deep",
      autoOpenResults: true,
      rememberSidebarState: true,
      motionProfile: "fluid",
      theme: "light",
      surfaceContrast: "soft",
      remediationMaxAttempts: 3,
      remediationReuseExplanation: true,
      externalIngestionMaxRps: 10,
      externalIngestionRetryAttempts: 3,
      externalIngestionBackoffSeconds: 0.5,
      updatedAt: "2026-04-14T00:00:00Z",
    });
    updateRuntimeSettingsMock.mockResolvedValue({
      defaultPreset: "balanced",
      defaultScanMode: "deep",
      autoOpenResults: true,
      rememberSidebarState: true,
      motionProfile: "fluid",
      theme: "light",
      surfaceContrast: "soft",
      remediationMaxAttempts: 3,
      remediationReuseExplanation: true,
      externalIngestionMaxRps: 10,
      externalIngestionRetryAttempts: 3,
      externalIngestionBackoffSeconds: 0.5,
      updatedAt: "2026-04-14T00:00:00Z",
    });
  });

  it("routes into operations console and shows the continuous remediation workflow in the real app flow", async () => {
    render(<Page />);

    fireEvent.click(await screen.findByRole("button", { name: /April Security Run/i }));
    fireEvent.click(await screen.findByRole("button", { name: /open operations/i }));

    expect(await screen.findByText(/operations console/i)).toBeInTheDocument();
    expect(await screen.findByText(/autonomy readiness queue/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/recovery playbook/i)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/session memory ledger/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/recommendation reuse queue/i)).toBeInTheDocument();
    expect(await screen.findByText(/memory carry-forward/i)).toBeInTheDocument();
    expect(await screen.findByText(/learning loop signals/i)).toBeInTheDocument();
    expect(await screen.findByText(/self-healing controller queue/i)).toBeInTheDocument();
    expect(await screen.findByText(/autonomous control plan/i)).toBeInTheDocument();
    expect(await screen.findByText(/continuous remediation workflow/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/suppressed strategies must not be reused automatically/i)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/policy gate blocks continuous remediation/i)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/suppressed strategy memory must carry forward/i)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/approval hold remains active/i)).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /open audit trail/i }));
    expect(await screen.findByText(/audit trail/i)).toBeInTheDocument();
  });

  it("runs a controlled apply from operations console into verification", async () => {
    listSessionsMock.mockResolvedValue([buildExecutableSessionSummary()]);
    getScanSessionMock.mockResolvedValue(buildExecutableSessionDetail());

    render(<Page />);

    fireEvent.click(await screen.findByRole("button", { name: /April Security Run/i }));
    fireEvent.click(await screen.findByRole("button", { name: /open operations/i }));
    fireEvent.click(await screen.findByRole("button", { name: /run controlled apply/i }));

    expect(retryFixStrategyMock).toHaveBeenCalledWith({
      sessionId: "session-1",
      findingId: "finding-1",
      mode: "single",
      excludedStrategyIds: ["legacy-guard", "sanitize-query"],
      attemptedStrategyIds: ["legacy-guard", "sanitize-query"],
    });
    await waitFor(() =>
      expect(applyFixMock).toHaveBeenCalledWith({
        sessionId: "session-1",
        findingId: "finding-1",
        strategyId: "parameterized-query",
        file: "app/features/login/router.py",
        beforeSnippet: "query = f\"SELECT * FROM users WHERE email = '{email}'\"",
        afterSnippet: "query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
        diff: "--- a/router.py\n+++ b/router.py",
        manualEdit: false,
        approvalAcknowledged: true,
        mode: "single",
      }),
    );
    expect((await screen.findAllByText(/deterministic verification passed\./i)).length).toBeGreaterThan(0);
  });
});

function buildBlockedSessionSummary() {
  return {
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
      blockingItems: 2,
      workflowClosure: {
        closureState: "human-controlled",
        closureLabel: "Human-controlled",
        closureReason: "Approval and escalation remain open.",
        autonomousReady: false,
        requiresHumanControl: true,
        nextClosureStep: "collect approval",
      },
    },
    createdAt: "2026-04-12T02:00:00Z",
    updatedAt: "2026-04-12T03:00:00Z",
  };
}

function buildBlockedSessionDetail() {
  const session = {
    ...buildBlockedSessionSummary(),
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
  };

  return {
    session,
    issues: { critical: 1, high: 1, medium: 1, low: 0 },
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
        approvalHistory: [
          {
            status: "escalated",
            note: "Security lead requested an additional review before local apply.",
            timestamp: "2026-04-12T00:00:00Z",
          },
        ],
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
        approvalHistory: [
          {
            status: "approved",
            note: "Approved after verification",
            timestamp: "2026-04-12T00:05:00Z",
          },
        ],
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

function buildExecutableSessionSummary() {
  return {
    ...buildBlockedSessionSummary(),
    preview: "A controlled apply window is available for one approved finding.",
    workflowSummary: {
      state: "verification-follow-up",
      label: "Retry-ready",
      summary: "A low-risk controlled apply can proceed.",
      nextAction: "Run controlled apply",
      activeController: "recovery-controller",
      blockingItems: 0,
      workflowClosure: {
        closureState: "autonomous-ready",
        closureLabel: "Autonomous-ready",
        closureReason: "Approval is already resolved for the retry candidate.",
        autonomousReady: true,
        requiresHumanControl: false,
        nextClosureStep: "run controlled apply",
      },
    },
  };
}

function buildExecutableSessionDetail() {
  const detail = buildBlockedSessionDetail();
  return {
    ...detail,
    session: {
      ...detail.session,
      ...buildExecutableSessionSummary(),
      workflowSummary: {
        state: "verification-follow-up",
        label: "Retry-ready",
        summary: "A low-risk controlled apply can proceed.",
        nextAction: "Run controlled apply",
        activeController: "recovery-controller",
        plannerStage: "apply-ready",
        recoverySummary: {
          retryAvailable: true,
          retryableFindings: 1,
          attemptedStrategies: 2,
          latestFailureReason: "Previous remediation left residual sink risk open.",
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
          currentLane: "verification-lane",
          nextLane: "remediation-lane",
          pendingHandoff: false,
          handoffReason: "Retry lane is ready.",
          activeItemCount: 1,
        },
        operationsExecution: {
          currentHandoff: "verification -> remediation",
          handoffStatus: "active",
          owningController: "recovery-controller",
          pendingExecutionStep: "Run controlled apply",
          stepCompletionState: "ready",
        },
        workflowClosure: {
          closureState: "autonomous-ready",
          closureLabel: "Autonomous-ready",
          closureReason: "Approval is already resolved for the retry candidate.",
          autonomousReady: true,
          requiresHumanControl: false,
          nextClosureStep: "run controlled apply",
        },
        blockingItems: 0,
      },
    },
    findings: [
      {
        ...detail.findings[0],
        approvalStatus: "approved",
        approvalHistory: [
          {
            status: "approved",
            note: "Approved for guarded retry",
            timestamp: "2026-04-12T00:00:00Z",
          },
        ],
        attemptedStrategyIds: ["legacy-guard", "sanitize-query"],
        decisionSummary: {
          ...detail.findings[0].decisionSummary,
          applyReadiness: "approval-required-before-apply",
        },
      },
      detail.findings[1],
    ],
  };
}

function buildRetryPlan() {
  return {
    mode: "single",
    findingIds: ["finding-1"],
    reviewSummary: "Prepared a review-ready retry patch.",
    explanation: null,
    strategies: [
      {
        id: "parameterized-query",
        label: "Parameterized query",
        kind: "refactor",
        confidence: 92,
        impact: "high",
        effort: "medium",
        summary: "Replace interpolation with a parameterized query.",
        rationale: "Derived from the traced path.",
        diff: "--- a/router.py\n+++ b/router.py",
        recommended: true,
        fixType: "full_fix",
        securityStrength: "high",
        regressionRisk: "low",
        selectionReason: "Strongest safe option.",
        nonSelectionReason: "",
        residualRisks: [],
        policyCompliant: true,
        policyViolations: [],
      },
    ],
    recommendedStrategyId: "parameterized-query",
    patch: {
      file: "app/features/login/router.py",
      language: "python",
      summary: "Parameterize the login query.",
      diff: "--- a/router.py\n+++ b/router.py",
      validationNotes: ["The patch modifies the traced sink."],
      beforeSnippet: "query = f\"SELECT * FROM users WHERE email = '{email}'\"",
      afterSnippet: "query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
      fixType: "full_fix",
      rationale: "Protect the sink.",
      residualRisks: [],
      manualReviewRequired: false,
    },
    steps: [],
    metrics: null,
    score: {
      total: 88,
      strategyQuality: 91,
      fixCompleteness: 87,
      sinkAlignment: 96,
      residualRisk: 74,
      confidence: 92,
      rationale: ["Looks good."],
    },
  };
}

function buildApplyExecution() {
  const detail = buildExecutableSessionDetail();

  return {
    action: {
      findingId: "finding-1",
      status: "applied",
      file: "app/features/login/router.py",
      appliedStrategyId: "parameterized-query",
      fixType: "full_fix",
      validationNotes: ["Patch validation passed."],
      manualEditApplied: false,
      checkpointId: "checkpoint-1",
      rollbackAvailable: true,
      verificationStatus: "verified",
      verificationNotes: ["Deterministic verification passed."],
      verificationConfidence: 96,
      verificationConfidenceValid: true,
      approvalGateOutcome: "auto-approved",
      approvalGateReason: "The retry remained within the approved write scope.",
      writeScope: "single-file",
      networkPolicy: "offline-only",
    },
    session: detail.session,
    findings: detail.findings.map((finding) =>
      finding.id === "finding-1"
        ? {
            ...finding,
            remediationStatus: "verified_fixed",
            appliedStrategyId: "parameterized-query",
            remediationNotes: [],
          }
        : finding,
    ),
    candidateFindings: detail.candidateFindings,
  };
}
