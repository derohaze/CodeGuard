import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import Page from "./Page";

const { listSessionsMock, getScanSessionMock, getRuntimeSettingsMock, updateRuntimeSettingsMock } = vi.hoisted(() => ({
  listSessionsMock: vi.fn(),
  getScanSessionMock: vi.fn(),
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
    applyFix: vi.fn(),
    deleteAllScanSessions: vi.fn(),
    deleteScanSession: vi.fn(),
    rejectFix: vi.fn(),
    rollbackFix: vi.fn(),
    retryFixStrategy: vi.fn(),
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

describe("Page policy center flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSessionsMock.mockResolvedValue([buildSessionSummary()]);
    getScanSessionMock.mockResolvedValue(buildSessionDetail());
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

  it("routes from finding detail to decision center to policy center and shows pre-merge guidance", async () => {
    render(<Page />);

    fireEvent.click(await screen.findByRole("button", { name: /April Security Run/i }));
    fireEvent.click((await screen.findAllByText(/dynamic query construction may allow injection/i))[0]!);
    fireEvent.click(await screen.findByRole("button", { name: /^decision center$/i }));
    fireEvent.click(await screen.findByRole("button", { name: /open policy center/i }));

    expect(await screen.findByText(/policy center/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/pre-merge guidance/i)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/prevention ledger/i)).length).toBeGreaterThan(0);
  });
});

function buildSessionSummary() {
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
    findingsCount: 1,
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
    workflowSummary: null,
    createdAt: "2026-04-12T02:00:00Z",
    updatedAt: "2026-04-12T03:00:00Z",
  };
}

function buildSessionDetail() {
  return {
    session: buildSessionSummary(),
    issues: { critical: 1, high: 0, medium: 0, low: 0 },
    findings: [
      {
        id: "finding-1",
        severity: "high",
        title: "Dynamic query construction may allow injection",
        file: "app/features/login/router.py",
        line: 43,
        lineEnd: 44,
        category: "SQL injection auth flow",
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
        remediationNotes: [],
        attemptedStrategyIds: [],
        decisionSummary: null,
      },
    ],
    candidateFindings: [],
    verdict: "issues_found",
    completedAt: "2026-04-12T03:00:00Z",
    errorMessage: null,
  };
}
