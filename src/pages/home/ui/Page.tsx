import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PanelLeftOpen } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "@/components/ui/sonner";
import { ApprovalQueueScreen } from "@/features/approval-queue";
import { BuilderChatScreen, BuilderSidebar, useBuilderAgent } from "@/features/builder-agent";
import { DecisionCenterScreen } from "@/features/decision-center";
import { HomeScreen } from "@/features/dashboard";
import { ExportPatchScreen } from "@/features/export-patch";
import { OperationsConsoleScreen } from "@/features/operations-console";
import { PatchReadyScreen } from "@/features/patch-review";
import { PolicyCenterScreen } from "@/features/policy-center";
import { FindingDetailPanel } from "@/features/review-finding";
import { ScanEmptyScreen, ScanProgressScreen, ScanResultsScreen } from "@/features/scan-project";
import { SettingsScreen } from "@/features/settings";
import { Sidebar } from "@/features/sidebar-navigation";
import { SuggestFixScreen } from "@/features/suggest-fix";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AnalyticsDashboardScreen } from "@/features/analytics-dashboard";
import { AuditTrailScreen } from "@/features/audit-trail";
import { GovernanceCenterScreen } from "@/features/governance-center";
import { RepoOverviewScreen } from "@/features/repo-overview";
import { ServiceExposureScreen } from "@/features/service-exposure";
import { TeamSecurityPostureScreen } from "@/features/team-security-posture";
import { VerificationScreen } from "@/features/verification";
import type { Finding, PatchExportSnapshot, RemediationPlan } from "@/entities/finding/model/types";
import type { Session } from "@/entities/session/model/types";
import { mergeSessionOrder } from "@/entities/session/lib/session-order";
import {
  applyFix,
  deleteAllScanSessions,
  deleteScanSession,
  getRepoHotspots,
  getRepoIntelligenceSummary,
  getScanSession,
  getServiceExposureFeed,
  getServiceExposureSummary,
  getTeamPostureFeed,
  getTeamPostureSummary,
  listSessions,
  rejectFix,
  rollbackFix,
  retryFixStrategy,
  startScan,
  subscribeToScanEvents,
  type RemediationExecutionResult,
  type ScanSessionDetail,
  type StartScanPayload,
  type WorkflowRepoHotspotItem,
  type WorkflowRepoIntelligenceSummary,
  type WorkflowServiceExposureItem,
  type WorkflowServiceExposureSummary,
  type WorkflowTeamPostureItem,
  type WorkflowTeamPostureSummary,
} from "@/shared/api/security";
import { Loader } from "@/shared/ui/Loader";
import { toAnalystCopy } from "@/shared/lib/analyst-copy";
import type { AppScreen, AppView, WorkspaceMode } from "@/shared/types/app";
import { AppShell } from "@/widgets/app-shell";
import {
  resolveApprovalQueueFindingRoute,
  resolveFindingDismissScreen,
  resolvePostApplyRoute,
  resolvePostRejectScreen,
  resolvePostRollbackScreen,
  resolveReviewEntryRoute,
  resolveSessionOpenScreen,
  shouldRetainFindingContext,
  shouldRetainReviewContext,
  type RemediationWorkflowPhase,
} from "../lib/remediation-workflow";

type DeleteTarget =
  | { type: "single"; session: Session }
  | { type: "all" };

type RemediationRequest =
  | { mode: "single"; finding: Finding; findings: Finding[] }
  | { mode: "batch"; finding: Finding | null; findings: Finding[] };

type RemediationFlowState = {
  phase: RemediationWorkflowPhase;
  mode: "single" | "batch";
};

type SeverityCounts = ScanSessionDetail["issues"];
type RemediationPlanCache = Record<string, RemediationPlan>;
type RemediationExecutionCache = Record<string, RemediationExecutionResult>;
type PatchExportSnapshotCache = Record<string, PatchExportSnapshot>;

export default function Page() {
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("security");
  const [screen, setScreen] = useState<AppScreen>("home");
  const [findingOriginScreen, setFindingOriginScreen] = useState<AppScreen | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ScanSessionDetail | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionOrder, setSessionOrder] = useState<string[]>([]);
  const [pendingCompletionSessionId, setPendingCompletionSessionId] = useState<string | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [view, setView] = useState<AppView>("workspace");
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [remediationRequest, setRemediationRequest] = useState<RemediationRequest | null>(null);
  const [remediationPlan, setRemediationPlan] = useState<RemediationPlan | null>(null);
  const [remediationFlow, setRemediationFlow] = useState<RemediationFlowState | null>(null);
  const [lastRemediationExecution, setLastRemediationExecution] = useState<RemediationExecutionResult | null>(null);
  const [lastAppliedPatchSnapshot, setLastAppliedPatchSnapshot] = useState<PatchExportSnapshot | null>(null);
  const [isRunningContinuousApply, setIsRunningContinuousApply] = useState(false);
  const [policyCenterReturnScreen, setPolicyCenterReturnScreen] = useState<AppScreen>("decision-center");
  const [remediationPlanCache, setRemediationPlanCache] = useState<RemediationPlanCache>({});
  const [remediationExecutionCache, setRemediationExecutionCache] = useState<RemediationExecutionCache>({});
  const [patchExportSnapshotCache, setPatchExportSnapshotCache] = useState<PatchExportSnapshotCache>({});
  const [repoIntelligenceSummary, setRepoIntelligenceSummary] = useState<WorkflowRepoIntelligenceSummary | null>(null);
  const [repoHotspotFeed, setRepoHotspotFeed] = useState<WorkflowRepoHotspotItem[] | null>(null);
  const [teamPostureSummary, setTeamPostureSummary] = useState<WorkflowTeamPostureSummary | null>(null);
  const [teamPostureFeed, setTeamPostureFeed] = useState<WorkflowTeamPostureItem[] | null>(null);
  const [serviceExposureSummary, setServiceExposureSummary] = useState<WorkflowServiceExposureSummary | null>(null);
  const [serviceExposureFeed, setServiceExposureFeed] = useState<WorkflowServiceExposureItem[] | null>(null);
  const {
    activeConversation,
    activeConversationId,
    addAttachment,
    addWorkspace,
    archiveWorkspaceThreads,
    archiveThread,
    collapseAllWorkspaces,
    composerSettings,
    createPermanentWorktree,
    createWorkspaceThread,
    currentWorkspace,
    draft,
    expandedWorkspaceIds,
    expandAllWorkspaces,
    hasPreviousConversation,
    isStreaming,
    messages,
    openConversation,
    openWorkspaceInExplorer,
    promptSuggestions,
    removeWorkspace,
    removeThread,
    removeAttachment,
    reorderWorkspaces,
    renameWorkspace,
    renameThread,
    reopenPreviousConversation,
    sendMessage,
    setPermissionMode,
    setPlanMode,
    setDraft,
    stopStreaming,
    showAllWorkspaceIds,
    threadGroups,
    toggleWorkspace,
    toggleWorkspaceShowAll,
  } = useBuilderAgent();

  const mergeSessionSummary = useCallback((session: Session) => {
    setSessions((current) => {
      const existingIndex = current.findIndex((item) => item.id === session.id);
      if (existingIndex === -1) {
        return [session, ...current];
      }

      const next = [...current];
      next[existingIndex] = session;
      return next;
    });
  }, []);

  const clearRemediationContext = useCallback(() => {
    setSelectedFinding(null);
    setFindingOriginScreen(null);
    setRemediationRequest(null);
    setRemediationPlan(null);
    setRemediationFlow(null);
    setLastRemediationExecution(null);
    setLastAppliedPatchSnapshot(null);
    setPolicyCenterReturnScreen("decision-center");
  }, []);

  const clearReviewContext = useCallback(() => {
    setRemediationRequest(null);
    setRemediationPlan(null);
    setRemediationFlow(null);
  }, []);

  const buildRemediationCacheKey = useCallback((sessionId: string, findingId: string) => `${sessionId}:${findingId}`, []);

  const clearCachedArtifactsForSession = useCallback((sessionId: string) => {
    const predicate = (key: string) => key.startsWith(`${sessionId}:`);
    setRemediationPlanCache((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !predicate(key))));
    setRemediationExecutionCache((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !predicate(key))));
    setPatchExportSnapshotCache((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !predicate(key))));
  }, []);

  const clearAllCachedArtifacts = useCallback(() => {
    setRemediationPlanCache({});
    setRemediationExecutionCache({});
    setPatchExportSnapshotCache({});
  }, []);

  const syncSessionOrder = useCallback((nextSessions: Session[]) => {
    setSessionOrder((current) => {
      return mergeSessionOrder(current, nextSessions);
    });
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      syncSessionOrder(nextSessions);
    } catch (error) {
      console.error("[CodeGuard] Failed to refresh sessions", error);
      setSessions([]);
      setSessionOrder([]);
    }
  }, [syncSessionOrder]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    let isCancelled = false;

    if (screen !== "repo-overview" || !activeSession) {
      return () => {
        isCancelled = true;
      };
    }

    void Promise.allSettled([getRepoIntelligenceSummary(), getRepoHotspots()]).then((results) => {
      if (isCancelled) return;
      const [summaryResult, feedResult] = results;
      if (summaryResult.status === "fulfilled") {
        setRepoIntelligenceSummary(summaryResult.value);
      } else {
        console.error("[CodeGuard] Failed to load repo intelligence summary", summaryResult.reason);
        setRepoIntelligenceSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setRepoHotspotFeed(feedResult.value);
      } else {
        console.error("[CodeGuard] Failed to load repo hotspot feed", feedResult.reason);
        setRepoHotspotFeed(null);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [activeSession, screen]);

  useEffect(() => {
    let isCancelled = false;

    if (screen !== "team-security-posture" || sessions.length === 0) {
      return () => {
        isCancelled = true;
      };
    }

    void Promise.allSettled([getTeamPostureSummary(), getTeamPostureFeed()]).then((results) => {
      if (isCancelled) return;
      const [summaryResult, feedResult] = results;
      if (summaryResult.status === "fulfilled") {
        setTeamPostureSummary(summaryResult.value);
      } else {
        console.error("[CodeGuard] Failed to load team posture summary", summaryResult.reason);
        setTeamPostureSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setTeamPostureFeed(feedResult.value);
      } else {
        console.error("[CodeGuard] Failed to load team posture feed", feedResult.reason);
        setTeamPostureFeed(null);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [screen, sessions.length]);

  useEffect(() => {
    let isCancelled = false;

    if (screen !== "service-exposure" || !activeSession) {
      return () => {
        isCancelled = true;
      };
    }

    void Promise.allSettled([getServiceExposureSummary(), getServiceExposureFeed()]).then((results) => {
      if (isCancelled) return;
      const [summaryResult, feedResult] = results;
      if (summaryResult.status === "fulfilled") {
        setServiceExposureSummary(summaryResult.value);
      } else {
        console.error("[CodeGuard] Failed to load service exposure summary", summaryResult.reason);
        setServiceExposureSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setServiceExposureFeed(feedResult.value);
      } else {
        console.error("[CodeGuard] Failed to load service exposure feed", feedResult.reason);
        setServiceExposureFeed(null);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [activeSession, screen]);

  useEffect(() => {
    if (!activeSessionId || !activeSession) return;
    if (!["queued", "scanning"].includes(activeSession.session.status)) return;
    let isClosed = false;
    let fallbackTimer: number | null = null;
    let livePollTimer: number | null = null;
    let fallbackAttempt = 0;

    const applyDetail = (detail: ScanSessionDetail) => {
      setActiveSession((current) => (hasMeaningfulSessionChange(current, detail) ? detail : current));
      mergeSessionSummary(detail.session);
      if (detail.session.status === "completed" && screen === "scan-progress") {
        setPendingCompletionSessionId(detail.session.id);
      }
    };

    const pollWithBackoff = () => {
      if (isClosed) return;
      const delay = fallbackAttempt < 2 ? 1000 : fallbackAttempt < 5 ? 2000 : 5000;
      fallbackTimer = window.setTimeout(() => {
        void getScanSession(activeSessionId)
          .then((detail) => {
            applyDetail(detail);
            if (!["completed", "failed"].includes(detail.session.status)) {
              fallbackAttempt += 1;
              pollWithBackoff();
            }
          })
          .catch(() => {
            fallbackAttempt += 1;
            pollWithBackoff();
          });
      }, delay);
    };

    const pollLiveSession = () => {
      if (isClosed) return;
      void getScanSession(activeSessionId)
        .then((detail) => {
          applyDetail(detail);
          if (!["completed", "failed"].includes(detail.session.status)) {
            livePollTimer = window.setTimeout(pollLiveSession, 1200);
          }
        })
        .catch(() => {
          livePollTimer = window.setTimeout(pollLiveSession, 1800);
        });
    };

    let cleanup = () => undefined;
    if (typeof window !== "undefined" && "EventSource" in window) {
      cleanup = subscribeToScanEvents(activeSessionId, {
        onSession: applyDetail,
        onTerminal: applyDetail,
        onError: () => {
          if (!isClosed) {
            pollWithBackoff();
          }
        },
      });
    } else {
      pollWithBackoff();
    }

    livePollTimer = window.setTimeout(pollLiveSession, 700);

    return () => {
      isClosed = true;
      cleanup();
      if (fallbackTimer !== null) {
        window.clearTimeout(fallbackTimer);
      }
      if (livePollTimer !== null) {
        window.clearTimeout(livePollTimer);
      }
    };
  }, [activeSession, activeSessionId, mergeSessionSummary, screen]);

  useEffect(() => {
    if (!pendingCompletionSessionId || activeSession?.session.id !== pendingCompletionSessionId) return;
    if (activeSession.session.progress < 100) return;

    const timer = window.setTimeout(() => {
      setScreen("scan-completed");
      setPendingCompletionSessionId(null);
    }, 450);

    return () => window.clearTimeout(timer);
  }, [activeSession, pendingCompletionSessionId]);

  const handleStartScan = useCallback(async (payload: StartScanPayload) => {
    try {
      const detail = await startScan(payload);
      setActiveSession(detail);
      setActiveSessionId(detail.session.id);
      setPendingCompletionSessionId(null);
      clearRemediationContext();
      mergeSessionSummary(detail.session);
      syncSessionOrder([detail.session, ...sessions.filter((item) => item.id !== detail.session.id)]);
      setScreen("scan-progress");
    } catch (error) {
      console.error("[CodeGuard] Failed to start scan", error);
      const message = error instanceof Error ? error.message : "Unable to start the scan.";
      toast.error(message);
    }
  }, [clearRemediationContext, mergeSessionSummary, sessions, syncSessionOrder]);

  const handleSelectFinding = useCallback((finding: Finding, originScreen: AppScreen = "scan-completed") => {
    setFindingOriginScreen(originScreen);
    setSelectedFinding(finding);
    setScreen("finding-detail");
  }, []);

  const handleSelectApprovalQueueFinding = useCallback((finding: Finding) => {
    if (!activeSessionId) {
      handleSelectFinding(finding, "approval-queue");
      return;
    }

    const cacheKey = buildRemediationCacheKey(activeSessionId, finding.id);
    const nextScreen = resolveApprovalQueueFindingRoute({
      finding,
      hasPlan: Boolean(remediationPlanCache[cacheKey]),
      hasExecution: Boolean(remediationExecutionCache[cacheKey]),
    });

    setFindingOriginScreen("approval-queue");
    setSelectedFinding(finding);

    if (nextScreen === "patch-ready") {
      setRemediationRequest({
        mode: "single",
        finding,
        findings: [finding],
      });
      setRemediationPlan(remediationPlanCache[cacheKey] ?? null);
      setRemediationFlow({ phase: "review", mode: "single" });
      setLastRemediationExecution(remediationExecutionCache[cacheKey] ?? null);
      setLastAppliedPatchSnapshot(patchExportSnapshotCache[cacheKey] ?? null);
      setScreen("patch-ready");
      return;
    }

    if (nextScreen === "verification") {
      clearReviewContext();
      setLastRemediationExecution(remediationExecutionCache[cacheKey] ?? null);
      setLastAppliedPatchSnapshot(patchExportSnapshotCache[cacheKey] ?? null);
      setScreen("verification");
      return;
    }

    clearReviewContext();
    setLastRemediationExecution(remediationExecutionCache[cacheKey] ?? null);
    setLastAppliedPatchSnapshot(patchExportSnapshotCache[cacheKey] ?? null);
    setScreen("finding-detail");
  }, [
    activeSessionId,
    buildRemediationCacheKey,
    clearReviewContext,
    handleSelectFinding,
    patchExportSnapshotCache,
    remediationExecutionCache,
    remediationPlanCache,
  ]);

  const handleSuggestFindingFix = useCallback((finding: Finding) => {
    setSelectedFinding(finding);
    setRemediationPlan(null);
    setRemediationFlow({ phase: "suggesting", mode: "single" });
    setRemediationRequest({
      mode: "single",
      finding,
      findings: [finding],
    });
    setScreen("suggest-fix");
  }, []);

  const handleInvalidatedRemediationFinding = useCallback(async () => {
    if (!activeSessionId) {
      clearRemediationContext();
      setScreen("scan-completed");
      return;
    }
    try {
      const detail = await getScanSession(activeSessionId);
      setActiveSession(detail);
      mergeSessionSummary(detail.session);
      setSelectedFinding(null);
      clearRemediationContext();
      setScreen("scan-completed");
      toast.success("The stale finding was removed during remediation preflight. The saved results have been refreshed.");
    } catch {
      clearRemediationContext();
      setScreen("scan-completed");
      toast.error("The selected finding was invalidated, but the refreshed scan results could not be loaded automatically.");
    }
  }, [activeSessionId, clearRemediationContext, mergeSessionSummary]);

  const handleFixComplete = useCallback((plan: RemediationPlan) => {
    const reviewEntry = resolveReviewEntryRoute();
    if (activeSessionId && remediationRequest?.finding) {
      const cacheKey = buildRemediationCacheKey(activeSessionId, remediationRequest.finding.id);
      setRemediationPlanCache((current) => ({
        ...current,
        [cacheKey]: plan,
      }));
    }
    setRemediationPlan(plan);
    setRemediationFlow((current) => ({ phase: reviewEntry.phase, mode: current?.mode ?? plan.mode }));
    setScreen(reviewEntry.screen);
  }, [activeSessionId, buildRemediationCacheKey, remediationRequest?.finding]);

  const syncRemediationExecution = useCallback((result: RemediationExecutionResult) => {
    setActiveSession((current) =>
      current
        ? {
            ...current,
            session: result.session,
            issues: countFindingSeverities(result.findings),
            findings: result.findings,
            candidateFindings: result.candidateFindings,
            verdict: result.session.isSafe ? "safe" : "issues_found",
          }
        : current,
    );
    mergeSessionSummary(result.session);
    const nextSelected =
      result.findings.find((item) => item.id === result.action.findingId)
      ?? result.candidateFindings.find((item) => item.id === result.action.findingId)
      ?? null;
    setSelectedFinding(nextSelected);
  }, [mergeSessionSummary]);

  const handleApproveFix = useCallback(async (input: {
    strategyId: string | null;
    strategyLabel: string | null;
    file: string;
    beforeSnippet: string;
    afterSnippet: string;
    diff: string;
    fixType: "full_fix" | "partial_mitigation" | "temporary_guard" | "risky_workaround";
    summary: string;
    rationale: string;
    residualRisks: string[];
    manualEdit: boolean;
    mode: "single" | "batch";
  }) => {
    if (!activeSessionId || !selectedFinding) return null;
    setRemediationFlow((current) => ({ phase: "applying", mode: current?.mode ?? input.mode }));
    let result: RemediationExecutionResult;
    try {
      result = await applyFix({
        sessionId: activeSessionId,
        findingId: selectedFinding.id,
        strategyId: input.strategyId,
        file: input.file,
        beforeSnippet: input.beforeSnippet,
        afterSnippet: input.afterSnippet,
        diff: input.diff,
        manualEdit: input.manualEdit,
        approvalAcknowledged: true,
        mode: input.mode,
      });
    } catch (error) {
      setRemediationFlow((current) => ({ phase: "review", mode: current?.mode ?? input.mode }));
      const message = error instanceof Error ? toAnalystCopy(error.message) : "Unable to apply the selected remediation.";
      toast.error(message);
      return null;
    }
    syncRemediationExecution(result);
    setLastRemediationExecution(result);
    const nextRoute = resolvePostApplyRoute(result.action);
    if (activeSessionId) {
      const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
      setRemediationExecutionCache((current) => ({
        ...current,
        [cacheKey]: result,
      }));
    }
    if (result.action.status === "applied") {
      const snapshot: PatchExportSnapshot = {
        file: input.file,
        diff: input.diff,
        beforeSnippet: input.beforeSnippet,
        afterSnippet: input.afterSnippet,
        strategyId: input.strategyId,
        strategyLabel: input.strategyLabel,
        fixType: input.fixType,
        summary: input.summary,
        rationale: input.rationale,
        residualRisks: input.residualRisks,
        manualEdit: input.manualEdit,
        mode: input.mode,
      };
      setLastAppliedPatchSnapshot(snapshot);
      if (activeSessionId) {
        const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
        setPatchExportSnapshotCache((current) => ({
          ...current,
          [cacheKey]: snapshot,
        }));
      }
      toast.success(
        result.action.verificationStatus === "verified"
          ? "The patch was applied to the selected workspace and passed deterministic verification."
          : "The patch was applied to the selected workspace. Review the verification notes before closing the finding.",
      );
      if (shouldRetainReviewContext(nextRoute.screen)) {
        setRemediationFlow((current) => ({ phase: nextRoute.phase, mode: current?.mode ?? input.mode }));
      } else if (shouldRetainFindingContext(nextRoute.screen)) {
        clearReviewContext();
      } else {
        clearRemediationContext();
      }
      setScreen(nextRoute.screen);
    } else {
      setLastAppliedPatchSnapshot(null);
      if (activeSessionId) {
        const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
        setPatchExportSnapshotCache((current) => {
          const next = { ...current };
          delete next[cacheKey];
          return next;
        });
      }
      toast.error(result.action.validationNotes[0] ?? "Patch validation failed.");
      if (shouldRetainReviewContext(nextRoute.screen)) {
        setRemediationFlow((current) => ({ phase: nextRoute.phase, mode: current?.mode ?? input.mode }));
      } else if (shouldRetainFindingContext(nextRoute.screen)) {
        clearReviewContext();
      } else {
        clearRemediationContext();
      }
      setScreen(nextRoute.screen);
    }
    return result;
  }, [activeSessionId, buildRemediationCacheKey, clearRemediationContext, clearReviewContext, selectedFinding, syncRemediationExecution]);

  const handleRejectFix = useCallback(async (strategyId: string | null) => {
    if (!activeSessionId || !selectedFinding) return null;
    const result = await rejectFix({
      sessionId: activeSessionId,
      findingId: selectedFinding.id,
      strategyId,
    });
    syncRemediationExecution(result);
    setLastRemediationExecution(result);
    setLastAppliedPatchSnapshot(null);
    if (activeSessionId) {
      const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
      setRemediationExecutionCache((current) => ({
        ...current,
        [cacheKey]: result,
      }));
      setPatchExportSnapshotCache((current) => {
        const next = { ...current };
        delete next[cacheKey];
        return next;
      });
    }
    clearRemediationContext();
    toast.success("The remediation proposal was rejected. No file changes were applied.");
    setScreen(resolvePostRejectScreen(result.findings, result.action.findingId));
    return result;
  }, [activeSessionId, buildRemediationCacheKey, clearRemediationContext, selectedFinding, syncRemediationExecution]);

  const handleRollbackFix = useCallback(async (checkpointId: string | null) => {
    if (!activeSessionId || !selectedFinding) return null;
    const result = await rollbackFix({
      sessionId: activeSessionId,
      findingId: selectedFinding.id,
      checkpointId,
    });
    syncRemediationExecution(result);
    setLastRemediationExecution(result);
    if (activeSessionId) {
      const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
      setRemediationExecutionCache((current) => ({
        ...current,
        [cacheKey]: result,
      }));
    }
    if (result.action.status === "rolled_back") {
      setLastAppliedPatchSnapshot(null);
      if (activeSessionId) {
        const cacheKey = buildRemediationCacheKey(activeSessionId, result.action.findingId);
        setPatchExportSnapshotCache((current) => {
          const next = { ...current };
          delete next[cacheKey];
          return next;
        });
      }
      clearRemediationContext();
      toast.success("The local patch was rolled back and the previous scan state was restored.");
      setScreen(resolvePostRollbackScreen(result.action));
    } else {
      toast.error(result.action.validationNotes[0] ?? "Rollback could not be completed.");
    }
    return result;
  }, [activeSessionId, buildRemediationCacheKey, clearRemediationContext, selectedFinding, syncRemediationExecution]);

  const handleRetryFix = useCallback(async (input: { excludedStrategyIds: string[]; attemptedStrategyIds: string[] }) => {
    if (!activeSessionId || !selectedFinding) return null;
    setRemediationFlow((current) => ({ phase: "suggesting", mode: current?.mode ?? remediationRequest?.mode ?? "single" }));
    const nextPlan = await retryFixStrategy({
      sessionId: activeSessionId,
      findingId: selectedFinding.id,
      mode: remediationRequest?.mode ?? "single",
      excludedStrategyIds: input.excludedStrategyIds,
      attemptedStrategyIds: input.attemptedStrategyIds,
    });
    const reviewEntry = resolveReviewEntryRoute();
    if (activeSessionId) {
      const cacheKey = buildRemediationCacheKey(activeSessionId, selectedFinding.id);
      setRemediationPlanCache((current) => ({
        ...current,
        [cacheKey]: nextPlan,
      }));
    }
    setRemediationPlan(nextPlan);
    setRemediationFlow((current) => ({ phase: reviewEntry.phase, mode: current?.mode ?? remediationRequest?.mode ?? "single" }));
    setScreen(reviewEntry.screen);
    toast.success("Generated a materially different remediation strategy.");
    return nextPlan;
  }, [activeSessionId, buildRemediationCacheKey, remediationRequest?.mode, selectedFinding]);

  const handleRunContinuousApply = useCallback(async (input: {
    findingId: string;
    excludedStrategyIds: string[];
    attemptedStrategyIds: string[];
  }) => {
    if (!activeSessionId || !activeSession) return null;

    const finding = activeSession.findings.find((item) => item.id === input.findingId);
    if (!finding) return null;

    setIsRunningContinuousApply(true);
    setSelectedFinding(finding);
    setFindingOriginScreen("operations-console");
    setRemediationRequest({
      mode: "single",
      finding,
      findings: [finding],
    });
    setRemediationFlow({ phase: "suggesting", mode: "single" });

    try {
      const nextPlan = await retryFixStrategy({
        sessionId: activeSessionId,
        findingId: finding.id,
        mode: "single",
        excludedStrategyIds: input.excludedStrategyIds,
        attemptedStrategyIds: input.attemptedStrategyIds,
      });
      const recommendedStrategy =
        nextPlan.strategies.find((strategy) => strategy.id === nextPlan.recommendedStrategyId)
        ?? nextPlan.strategies.find((strategy) => strategy.recommended)
        ?? null;
      const patch = nextPlan.patch;
      const cacheKey = buildRemediationCacheKey(activeSessionId, finding.id);
      setRemediationPlanCache((current) => ({
        ...current,
        [cacheKey]: nextPlan,
      }));

      if (!patch || !recommendedStrategy || !recommendedStrategy.policyCompliant || patch.manualReviewRequired) {
        setRemediationPlan(nextPlan);
        setRemediationFlow({ phase: "review", mode: "single" });
        setScreen("patch-ready");
          toast.success("Generated a guarded retry patch. Manual review is still required before workspace apply.");
        return nextPlan;
      }

      setRemediationPlan(nextPlan);
      setRemediationFlow({ phase: "applying", mode: "single" });

      const result = await applyFix({
        sessionId: activeSessionId,
        findingId: finding.id,
        strategyId: recommendedStrategy.id,
        file: patch.file,
        beforeSnippet: patch.beforeSnippet,
        afterSnippet: patch.afterSnippet,
        diff: recommendedStrategy.diff || patch.diff,
        manualEdit: false,
        approvalAcknowledged: true,
        mode: "single",
      });

      syncRemediationExecution(result);
      setLastRemediationExecution(result);
      setRemediationExecutionCache((current) => ({
        ...current,
        [cacheKey]: result,
      }));

      if (result.action.status === "applied") {
        const snapshot: PatchExportSnapshot = {
          file: patch.file,
          diff: recommendedStrategy.diff || patch.diff,
          beforeSnippet: patch.beforeSnippet,
          afterSnippet: patch.afterSnippet,
          strategyId: recommendedStrategy.id,
          strategyLabel: recommendedStrategy.label,
          fixType: recommendedStrategy.fixType,
          summary: patch.summary,
          rationale: patch.rationale || recommendedStrategy.selectionReason || recommendedStrategy.rationale,
          residualRisks: recommendedStrategy.residualRisks.length ? recommendedStrategy.residualRisks : patch.residualRisks,
          manualEdit: false,
          mode: "single",
        };
        setLastAppliedPatchSnapshot(snapshot);
        setPatchExportSnapshotCache((current) => ({
          ...current,
          [cacheKey]: snapshot,
        }));
        setRemediationFlow({ phase: "review", mode: "single" });
        setScreen("verification");
        toast.success(
          result.action.verificationStatus === "verified"
            ? "Controlled apply completed and deterministic verification passed."
            : "Controlled apply completed. Verification still requires follow-up.",
        );
        return result;
      }

      setScreen("approval-queue");
      toast.error(result.action.validationNotes[0] ?? "Controlled apply could not complete local validation.");
      return result;
    } catch (error) {
      setRemediationFlow({ phase: "review", mode: "single" });
      const message = error instanceof Error ? toAnalystCopy(error.message) : "Unable to run the controlled apply.";
      toast.error(message);
      return null;
    } finally {
      setIsRunningContinuousApply(false);
    }
  }, [activeSession, activeSessionId, buildRemediationCacheKey, syncRemediationExecution]);

  const handleNavigate = useCallback((nextScreen: AppScreen) => {
    setScreen(nextScreen);
    if (nextScreen === "home" || nextScreen === "scan-empty") {
      clearRemediationContext();
    }
  }, [clearRemediationContext]);

  const openPolicyCenter = useCallback((returnScreen: AppScreen) => {
    setPolicyCenterReturnScreen(returnScreen);
    setScreen("policy-center");
  }, []);

  const handleOpenSession = useCallback(async (session: Session) => {
    try {
      const detail = await getScanSession(session.id);
      setActiveSessionId(detail.session.id);
      setActiveSession(detail);
      setPendingCompletionSessionId(null);
      mergeSessionSummary(detail.session);
      clearRemediationContext();
      setScreen(
        resolveSessionOpenScreen({
          currentScreen: screen,
          sessionStatus: detail.session.status,
          findings: detail.findings,
          findingOriginScreen,
        }),
      );
    } catch (error) {
      console.error("[CodeGuard] Failed to open scan session", error);
      const message = error instanceof Error ? toAnalystCopy(error.message) : "Unable to open the analyst session.";
      toast.error(message);
    }
  }, [clearRemediationContext, findingOriginScreen, mergeSessionSummary, screen]);

  const resetActiveSessionState = useCallback(() => {
    setActiveSessionId(null);
    setActiveSession(null);
    clearRemediationContext();
    setPendingCompletionSessionId(null);
    setScreen("home");
  }, [clearRemediationContext]);

  const handleDeleteSession = useCallback((session: Session) => {
    setDeleteTarget({ type: "single", session });
  }, []);

  const handleDeleteAllSessions = useCallback(() => {
    setDeleteTarget({ type: "all" });
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget || isDeleting) return;

    setIsDeleting(true);
    try {
      if (deleteTarget.type === "single") {
        const { session } = deleteTarget;
        await deleteScanSession(session.id);
        setSessions((current) => current.filter((item) => item.id !== session.id));
        setSessionOrder((current) => current.filter((id) => id !== session.id));
        clearCachedArtifactsForSession(session.id);

        if (activeSessionId === session.id) {
          resetActiveSessionState();
        }

        toast.success("The session was deleted successfully.");
      } else {
        await deleteAllScanSessions();
        setSessions([]);
        setSessionOrder([]);
        clearAllCachedArtifacts();
        resetActiveSessionState();
        toast.success("All analyst sessions were deleted successfully.");
      }
    } catch (error) {
      console.error("[CodeGuard] Failed to delete scan session", error);
      const message = error instanceof Error ? toAnalystCopy(error.message) : "Unable to delete the analyst session.";
      toast.error(message);
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  }, [activeSessionId, clearAllCachedArtifacts, clearCachedArtifactsForSession, deleteTarget, isDeleting, resetActiveSessionState]);

  const handleReorderSessions = useCallback((orderedSessionIds: string[]) => {
    setSessionOrder(orderedSessionIds);
  }, []);

  const renderContent = () => {
    switch (screen) {
      case "home":
        return <HomeScreen key="home" onStartScan={handleStartScan} />;
      case "scan-empty":
        return <ScanEmptyScreen key="scan-empty" onStartScan={() => setScreen("home")} />;
      case "scan-progress":
        return <ScanProgressScreen key="scan-progress" session={activeSession} />;
      case "scan-completed":
        return (
          <ScanResultsScreen
            key="scan-results"
            session={activeSession}
            onSelectFinding={(finding) => handleSelectFinding(finding, "scan-completed")}
            onOpenApprovalQueue={() => setScreen("approval-queue")}
            onOpenOperationsConsole={() => setScreen("operations-console")}
            onOpenAuditTrail={() => setScreen("audit-trail")}
          />
        );
      case "audit-trail":
        return (
          <AuditTrailScreen
            key="audit-trail"
            session={activeSession}
            onBack={() => setScreen("scan-completed")}
            onSelectFinding={(finding) => handleSelectFinding(finding, "audit-trail")}
            onOpenGovernanceCenter={() => setScreen("governance-center")}
          />
        );
      case "governance-center":
        return (
          <GovernanceCenterScreen
            key="governance-center"
            session={activeSession}
            onOpenAnalyticsDashboard={() => setScreen("analytics-dashboard")}
            onBack={() => setScreen("audit-trail")}
          />
        );
      case "analytics-dashboard":
        return (
          <AnalyticsDashboardScreen
            key="analytics-dashboard"
            session={activeSession}
            onOpenRepoOverview={() => setScreen("repo-overview")}
            onBack={() => setScreen("governance-center")}
          />
        );
      case "repo-overview":
        return (
          <RepoOverviewScreen
            key="repo-overview"
            session={activeSession}
            repoSummary={repoIntelligenceSummary}
            repoHotspotFeed={repoHotspotFeed}
            onOpenServiceExposure={() => setScreen("service-exposure")}
            onOpenTeamSecurityPosture={() => setScreen("team-security-posture")}
            onBack={() => setScreen("analytics-dashboard")}
          />
        );
      case "service-exposure":
        return (
          <ServiceExposureScreen
            key="service-exposure"
            session={activeSession}
            serviceSummary={serviceExposureSummary}
            serviceExposureFeed={serviceExposureFeed}
            onBack={() => setScreen("repo-overview")}
          />
        );
      case "team-security-posture":
        return (
          <TeamSecurityPostureScreen
            key="team-security-posture"
            sessions={sessions}
            activeSessionId={activeSessionId}
            teamSummary={teamPostureSummary}
            teamPostureFeed={teamPostureFeed}
            onBack={() => setScreen("repo-overview")}
          />
        );
      case "operations-console":
        return (
          <OperationsConsoleScreen
            key="operations-console"
            session={activeSession}
            onOpenAuditTrail={() => setScreen("audit-trail")}
            onRunContinuousApply={handleRunContinuousApply}
            isRunningContinuousApply={isRunningContinuousApply}
            onBack={() => setScreen(activeSession?.session.status === "completed" ? "scan-completed" : "scan-progress")}
          />
        );
      case "approval-queue":
        return (
          <ApprovalQueueScreen
            key="approval-queue"
            session={activeSession}
            onSelectFinding={handleSelectApprovalQueueFinding}
            onOpenResults={() => setScreen("scan-completed")}
          />
        );
      case "finding-detail":
        return selectedFinding ? (
          <FindingDetailPanel
            key="finding-detail"
            finding={selectedFinding}
            sessionId={activeSessionId}
            onDismiss={() => setScreen(resolveFindingDismissScreen(findingOriginScreen))}
            onOpenDecisionCenter={() => setScreen("decision-center")}
            onSuggestFix={() => handleSuggestFindingFix(selectedFinding)}
          />
        ) : null;
      case "decision-center":
        return (
          <DecisionCenterScreen
            key="decision-center"
            finding={selectedFinding}
            onBack={() => setScreen("finding-detail")}
            onSuggestFix={() => selectedFinding && handleSuggestFindingFix(selectedFinding)}
            onOpenPolicyCenter={() => openPolicyCenter("decision-center")}
          />
        );
      case "policy-center":
        return (
          <PolicyCenterScreen
            key="policy-center"
            finding={selectedFinding}
            onBack={() => setScreen(policyCenterReturnScreen)}
            onSuggestFix={() => selectedFinding && handleSuggestFindingFix(selectedFinding)}
          />
        );
      case "verification":
        return (
          <VerificationScreen
            key="verification"
            finding={selectedFinding}
            action={lastRemediationExecution?.action ?? null}
            onRollback={handleRollbackFix}
            onOpenExportPatch={() => setScreen("export-patch")}
            onOpenApprovalQueue={() => setScreen("approval-queue")}
            onOpenResults={() => {
              clearRemediationContext();
              setScreen("scan-completed");
            }}
          />
        );
      case "export-patch":
        return (
          <ExportPatchScreen
            key="export-patch"
            finding={selectedFinding}
            action={lastRemediationExecution?.action ?? null}
            snapshot={lastAppliedPatchSnapshot}
            onBack={() => setScreen("verification")}
            onOpenResults={() => {
              clearRemediationContext();
              setScreen("scan-completed");
            }}
          />
        );
      case "suggest-fix":
        return (
          <SuggestFixScreen
            key="suggest-fix"
            onComplete={handleFixComplete}
            onInvalidatedFinding={handleInvalidatedRemediationFinding}
            finding={remediationRequest?.finding ?? selectedFinding}
            findings={remediationRequest?.findings ?? (selectedFinding ? [selectedFinding] : [])}
            mode={remediationRequest?.mode ?? "single"}
            sessionId={activeSessionId}
          />
        );
      case "patch-ready":
        return (
          <PatchReadyScreen
            key="patch-ready"
            onApprove={handleApproveFix}
            onReject={handleRejectFix}
            onRollback={handleRollbackFix}
            onRetry={handleRetryFix}
            onViewResults={() => {
              clearRemediationContext();
              setScreen("scan-completed");
            }}
            onOpenPolicyCenter={() => openPolicyCenter("patch-ready")}
            finding={remediationRequest?.finding ?? selectedFinding}
            findings={remediationRequest?.findings ?? (selectedFinding ? [selectedFinding] : [])}
            mode={remediationRequest?.mode ?? "single"}
            plan={remediationPlan}
          />
        );
      default:
        return <HomeScreen key="home" onStartScan={handleStartScan} />;
    }
  };

  return (
    <AppShell>
      {view === "workspace" ? (
        <motion.div
          key="workspace-view"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="flex min-h-0 min-w-0 flex-1 overflow-hidden"
        >
          {workspaceMode === "security" ? (
            <Sidebar
              sessions={sessions}
              currentScreen={screen}
              onNavigate={handleNavigate}
              activeSessionId={activeSessionId}
              onOpenSession={handleOpenSession}
              onDeleteSession={handleDeleteSession}
              onDeleteAllSessions={handleDeleteAllSessions}
              onReorderSessions={handleReorderSessions}
              sessionOrder={sessionOrder}
              isCollapsed={isSidebarCollapsed}
              mode={workspaceMode}
              onModeChange={setWorkspaceMode}
              onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
              onOpenSettings={() => setView("settings")}
            />
          ) : (
            <BuilderSidebar
              activeConversationId={activeConversationId}
              currentWorkspaceId={currentWorkspace?.id ?? null}
              expandedWorkspaceIds={expandedWorkspaceIds}
              isCollapsed={isSidebarCollapsed}
              onAddWorkspace={addWorkspace}
              onArchiveThread={archiveThread}
              onArchiveWorkspaceThreads={archiveWorkspaceThreads}
              onCollapseAllWorkspaces={collapseAllWorkspaces}
              onCreatePermanentWorktree={createPermanentWorktree}
              onCreateWorkspaceThread={createWorkspaceThread}
              onExpandAllWorkspaces={expandAllWorkspaces}
              onOpenConversation={openConversation}
              onOpenSettings={() => setView("settings")}
              onOpenWorkspaceInExplorer={openWorkspaceInExplorer}
              onRemoveWorkspace={removeWorkspace}
              onRemoveThread={removeThread}
              onReorderWorkspaces={reorderWorkspaces}
              onRenameWorkspace={renameWorkspace}
              onRenameThread={renameThread}
              onReopenPreviousConversation={reopenPreviousConversation}
              onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
              onToggleWorkspace={toggleWorkspace}
              onToggleWorkspaceShowAll={toggleWorkspaceShowAll}
              onWorkspaceModeChange={setWorkspaceMode}
              hasPreviousConversation={hasPreviousConversation}
              showAllWorkspaceIds={showAllWorkspaceIds}
              threadGroups={threadGroups}
              workspaceMode={workspaceMode}
            />
          )}
          <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
            <AnimatePresence>
              {isSidebarCollapsed && (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <motion.button
                      key="sidebar-reopen"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      transition={{ duration: 0.18, ease: "easeOut" }}
                      onClick={() => setIsSidebarCollapsed(false)}
                      className="app-no-drag absolute left-4 top-4 z-40 rounded-xl border bg-card p-2 text-txt-secondary shadow-sm transition-colors hover:bg-secondary hover:text-txt-primary"
                      style={{ borderColor: "hsl(var(--border-soft))" }}
                      aria-label="Show sidebar"
                    >
                      <PanelLeftOpen size={16} />
                    </motion.button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="bottom"
                    align="start"
                    sideOffset={8}
                    className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md"
                  >
                    Show sidebar
                  </TooltipContent>
                </Tooltip>
              )}
            </AnimatePresence>
            <AnimatePresence initial={false} mode="wait">
              {workspaceMode === "security" ? (
                <motion.div
                  key={`security-content-${screen}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.1, ease: "linear" }}
                  className="flex min-h-0 min-w-0 flex-1"
                >
                  {renderContent()}
                </motion.div>
              ) : (
                <motion.div
                  key={`builder-content-${activeConversationId ?? "empty"}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.1, ease: "linear" }}
                  className="flex min-h-0 min-w-0 flex-1"
                >
                  <BuilderChatScreen
                    activeConversationId={activeConversationId}
                    composerSettings={composerSettings}
                    currentWorkspaceId={currentWorkspace?.id ?? null}
                    currentWorkspacePath={currentWorkspace?.path ?? null}
                    conversationTitle={activeConversation?.title ?? "New chat"}
                    conversationSubtitle={activeConversation?.subtitle ?? (currentWorkspace?.label ?? "Choose a workspace")}
                    draft={draft}
                    isNewChat={activeConversationId === null}
                    isStreaming={isStreaming}
                    messages={messages}
                    promptSuggestions={promptSuggestions}
                    onArchiveConversation={archiveThread}
                    onOpenWorkspaceInExplorer={openWorkspaceInExplorer}
                    onPermissionModeChange={setPermissionMode}
                    onPickAttachment={addAttachment}
                    onPlanModeChange={setPlanMode}
                    onRenameConversation={renameThread}
                    onDraftChange={setDraft}
                    onRemoveAttachment={removeAttachment}
                    onSend={sendMessage}
                    onStopStreaming={stopStreaming}
                    onCreatePermanentWorktree={createPermanentWorktree}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      ) : (
        <SettingsScreen onBack={() => setView("workspace")} />
      )}
      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => {
        if (!open && !isDeleting) {
          setDeleteTarget(null);
        }
      }}>
        <AlertDialogContent className="max-w-[420px] rounded-[28px] border border-border-soft bg-surface p-0 shadow-[0_28px_80px_rgba(52,42,28,0.14)]">
          <div className="space-y-5 p-6">
            <AlertDialogHeader className="space-y-2 text-left">
              <AlertDialogTitle className="font-brand text-[26px] font-medium tracking-[-0.02em] text-txt-primary">
                {deleteTarget?.type === "all" ? "Delete all analyst sessions?" : "Delete this analyst session?"}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-sm leading-6 text-txt-secondary">
                {deleteTarget?.type === "all"
                  ? "This will permanently remove every saved analyst session from the sidebar and results history."
                  : `This will permanently remove "${toAnalystCopy(deleteTarget?.session.title ?? "this session")}" from the sidebar and results history.`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="gap-2 sm:justify-start sm:space-x-0">
              <AlertDialogCancel
                className="mt-0 rounded-full border border-border-soft bg-transparent px-5 text-txt-primary hover:bg-secondary"
                disabled={isDeleting}
              >
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={(event) => {
                  event.preventDefault();
                  void handleConfirmDelete();
                }}
                className="rounded-full bg-[#1e1b16] px-5 text-white hover:bg-[#29241d]"
              >
                {isDeleting ? (
                  <>
                    <Loader variant="spin" className="size-4 text-white" />
                    Deleting...
                  </>
                ) : (
                  "Delete"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}

function hasMeaningfulSessionChange(
  current: ScanSessionDetail | null,
  next: ScanSessionDetail,
) {
  if (!current) return true;
  const currentLogs = current.session.progressLogs.join("|");
  const nextLogs = next.session.progressLogs.join("|");
  const currentCounters = JSON.stringify(current.session.progressCounters ?? {});
  const nextCounters = JSON.stringify(next.session.progressCounters ?? {});
  const currentRuntime = JSON.stringify(current.session.runtimeMetrics ?? {});
  const nextRuntime = JSON.stringify(next.session.runtimeMetrics ?? {});
  const currentQueue = JSON.stringify(current.session.reviewQueueSummary ?? {});
  const nextQueue = JSON.stringify(next.session.reviewQueueSummary ?? {});
  return !(
    current.session.updatedAt === next.session.updatedAt
    && current.session.status === next.session.status
    && current.session.progress === next.session.progress
    && current.session.phaseProgress === next.session.phaseProgress
    && current.session.currentPhase === next.session.currentPhase
    && current.session.findingsCount === next.session.findingsCount
    && current.session.candidateFindingsCount === next.session.candidateFindingsCount
    && current.errorMessage === next.errorMessage
    && currentLogs === nextLogs
    && currentCounters === nextCounters
    && currentRuntime === nextRuntime
    && currentQueue === nextQueue
  );
}

function countFindingSeverities(findings: Finding[]): SeverityCounts {
  return findings.reduce<SeverityCounts>(
    (summary, finding) => {
      summary[finding.severity] += 1;
      return summary;
    },
    {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    },
  );
}
