import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
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
import { DecisionCenterScreen } from "@/features/decision-center";
import { HomeScreen } from "@/features/dashboard";
import { ExportPatchScreen } from "@/features/export-patch";
import { OperationsConsoleScreen } from "@/features/operations-console";
import { PatchReadyScreen } from "@/features/patch-review";
import { PolicyCenterScreen } from "@/features/policy-center";
import { FindingDetailPanel } from "@/features/review-finding";
import { ScanEmptyScreen, ScanProgressScreen, ScanResultsScreen } from "@/features/scan-project";
import { SettingsScreen } from "@/features/settings";
import { SIDEBAR_COLLAPSED_STORAGE_KEY, useRuntimeSettings } from "@/features/settings/model/runtimeSettings";
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
import type { AppScreen, AppView } from "@/shared/types/app";
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
    settings: runtimeSettings,
    isLoading: runtimeSettingsLoading,
    isSaving: runtimeSettingsSaving,
    patchSettings: patchRuntimeSettings,
  } = useRuntimeSettings();
  const sessionWorkspaceTabs = buildSessionWorkspaceTabs(activeSession, screen);

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
      console.error("[Aegix] Failed to refresh sessions", error);
      setSessions([]);
      setSessionOrder([]);
    }
  }, [syncSessionOrder]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    root.dataset.themeMode = runtimeSettings.theme;
    root.dataset.surfaceContrast = runtimeSettings.surfaceContrast;
    root.dataset.motionProfile = runtimeSettings.motionProfile;
  }, [runtimeSettings.motionProfile, runtimeSettings.surfaceContrast, runtimeSettings.theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!runtimeSettings.rememberSidebarState) {
      window.localStorage.removeItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
      setIsSidebarCollapsed(false);
      return;
    }
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
    if (stored === "1") {
      setIsSidebarCollapsed(true);
      return;
    }
    if (stored === "0") {
      setIsSidebarCollapsed(false);
    }
  }, [runtimeSettings.rememberSidebarState]);

  useEffect(() => {
    if (typeof window === "undefined" || !runtimeSettings.rememberSidebarState) {
      return;
    }
    window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, isSidebarCollapsed ? "1" : "0");
  }, [isSidebarCollapsed, runtimeSettings.rememberSidebarState]);

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
        console.error("[Aegix] Failed to load repo intelligence summary", summaryResult.reason);
        setRepoIntelligenceSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setRepoHotspotFeed(feedResult.value);
      } else {
        console.error("[Aegix] Failed to load repo hotspot feed", feedResult.reason);
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
        console.error("[Aegix] Failed to load team posture summary", summaryResult.reason);
        setTeamPostureSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setTeamPostureFeed(feedResult.value);
      } else {
        console.error("[Aegix] Failed to load team posture feed", feedResult.reason);
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
        console.error("[Aegix] Failed to load service exposure summary", summaryResult.reason);
        setServiceExposureSummary(null);
      }
      if (feedResult.status === "fulfilled") {
        setServiceExposureFeed(feedResult.value);
      } else {
        console.error("[Aegix] Failed to load service exposure feed", feedResult.reason);
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
    if (!runtimeSettings.autoOpenResults) return;
    if (!pendingCompletionSessionId || activeSession?.session.id !== pendingCompletionSessionId) return;
    if (activeSession.session.progress < 100) return;

    const timer = window.setTimeout(() => {
      setScreen("scan-completed");
      setPendingCompletionSessionId(null);
    }, 450);

    return () => window.clearTimeout(timer);
  }, [activeSession, pendingCompletionSessionId, runtimeSettings.autoOpenResults]);

  useEffect(() => {
    if (!runtimeSettings.autoOpenResults && pendingCompletionSessionId) {
      setPendingCompletionSessionId(null);
    }
  }, [pendingCompletionSessionId, runtimeSettings.autoOpenResults]);

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
      console.error("[Aegix] Failed to start scan", error);
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
      console.error("[Aegix] Failed to open scan session", error);
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
      console.error("[Aegix] Failed to delete scan session", error);
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
        return (
          <HomeScreen
            key="home"
            onStartScan={handleStartScan}
            defaultPreset={runtimeSettings.defaultPreset}
            defaultScanMode={runtimeSettings.defaultScanMode}
          />
        );
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
          />
        );
      case "audit-trail":
        return (
          <AuditTrailScreen
            key="audit-trail"
            session={activeSession}
            onSelectFinding={(finding) => handleSelectFinding(finding, "audit-trail")}
          />
        );
      case "governance-center":
        return (
          <GovernanceCenterScreen
            key="governance-center"
            session={activeSession}
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
          />
        );
      case "service-exposure":
        return (
          <ServiceExposureScreen
            key="service-exposure"
            session={activeSession}
            serviceSummary={serviceExposureSummary}
            serviceExposureFeed={serviceExposureFeed}
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
          />
        );
      case "operations-console":
        return (
          <OperationsConsoleScreen
            key="operations-console"
            session={activeSession}
            onRunContinuousApply={handleRunContinuousApply}
            isRunningContinuousApply={isRunningContinuousApply}
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
        return (
          <HomeScreen
            key="home"
            onStartScan={handleStartScan}
            defaultPreset={runtimeSettings.defaultPreset}
            defaultScanMode={runtimeSettings.defaultScanMode}
          />
        );
    }
  };

  return (
    <AppShell>
      {view === "workspace" ? (
        <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
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
            onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
            onOpenSettings={() => setView("settings")}
          />
          <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden pt-8">
            {isSidebarCollapsed && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => setIsSidebarCollapsed(false)}
                    className="app-no-drag absolute left-4 top-4 z-40 rounded-xl border bg-card p-2 text-txt-secondary shadow-sm transition-colors hover:bg-secondary hover:text-txt-primary"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                    aria-label="Show sidebar"
                  >
                    <PanelLeftOpen size={16} />
                  </button>
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
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              {sessionWorkspaceTabs.length > 0 && (
                <SessionWorkspaceTabs
                  session={activeSession}
                  currentScreen={screen}
                  tabs={sessionWorkspaceTabs}
                  onNavigate={(nextScreen) => setScreen(nextScreen)}
                />
              )}
              <div className="flex min-h-0 min-w-0 flex-1">{renderContent()}</div>
            </div>
          </div>
        </div>
      ) : (
        <SettingsScreen
          onBack={() => setView("workspace")}
          settings={runtimeSettings}
          isSaving={runtimeSettingsSaving || runtimeSettingsLoading}
          onPatchSettings={async (patch) => {
            try {
              await patchRuntimeSettings(patch);
            } catch (error) {
              const message = error instanceof Error ? toAnalystCopy(error.message) : "Unable to save runtime settings.";
              toast.error(message);
            }
          }}
        />
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
                className="mt-0 rounded-full border border-[#ddd1bf] bg-[#f6efe6] px-5 !text-[#1e1b16] hover:bg-[#eee3d5]"
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

function buildSessionWorkspaceTabs(session: ScanSessionDetail | null, currentScreen: AppScreen): Array<{ screen: AppScreen; label: string }> {
  if (!session || session.session.status !== "completed") {
    return [];
  }

  const allowedScreens = new Set<AppScreen>([
    "scan-completed",
    "approval-queue",
    "operations-console",
    "audit-trail",
    "governance-center",
    "analytics-dashboard",
    "repo-overview",
    "service-exposure",
    "team-security-posture",
  ]);

  if (!allowedScreens.has(currentScreen)) {
    return [];
  }

  return [
    { screen: "scan-completed", label: "Results" },
    { screen: "approval-queue", label: "Approval" },
    { screen: "operations-console", label: "Operations" },
    { screen: "audit-trail", label: "Audit" },
    { screen: "governance-center", label: "Governance" },
    { screen: "analytics-dashboard", label: "Analytics" },
    { screen: "repo-overview", label: "Repo" },
    { screen: "service-exposure", label: "Exposure" },
  ];
}

function SessionWorkspaceTabs({
  session,
  currentScreen,
  tabs,
  onNavigate,
}: {
  session: ScanSessionDetail | null;
  currentScreen: AppScreen;
  tabs: Array<{ screen: AppScreen; label: string }>;
  onNavigate: (screen: AppScreen) => void;
}) {
  if (!session) {
    return null;
  }

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{ active: boolean; startX: number; startScrollLeft: number; moved: boolean }>({
    active: false,
    startX: 0,
    startScrollLeft: 0,
    moved: false,
  });
  const suppressNextTabClickRef = useRef(false);
  const [isDraggingTabs, setIsDraggingTabs] = useState(false);

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    dragStateRef.current = {
      active: true,
      startX: event.clientX,
      startScrollLeft: container.scrollLeft,
      moved: false,
    };
    setIsDraggingTabs(true);
    event.preventDefault();
  };

  const handleMouseMove = useCallback((clientX: number) => {
    const container = scrollRef.current;
    if (!container || !dragStateRef.current.active) {
      return;
    }
    const deltaX = clientX - dragStateRef.current.startX;
    if (Math.abs(deltaX) > 3) {
      dragStateRef.current.moved = true;
    }
    container.scrollLeft = dragStateRef.current.startScrollLeft - deltaX;
  }, []);

  const handleMouseRelease = useCallback(() => {
    if (dragStateRef.current.active && dragStateRef.current.moved) {
      suppressNextTabClickRef.current = true;
    }
    dragStateRef.current.active = false;
    dragStateRef.current.moved = false;
    setIsDraggingTabs(false);
  }, []);

  const handleTabClick = (event: ReactMouseEvent<HTMLButtonElement>, screen: AppScreen) => {
    if (suppressNextTabClickRef.current) {
      suppressNextTabClickRef.current = false;
      event.preventDefault();
      return;
    }
    onNavigate(screen);
  };

  useEffect(() => {
    if (!isDraggingTabs) {
      return;
    }

    const handleWindowMouseMove = (event: MouseEvent) => {
      handleMouseMove(event.clientX);
    };
    const handleWindowMouseUp = () => {
      handleMouseRelease();
    };

    window.addEventListener("mousemove", handleWindowMouseMove);
    window.addEventListener("mouseup", handleWindowMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleWindowMouseMove);
      window.removeEventListener("mouseup", handleWindowMouseUp);
    };
  }, [handleMouseMove, handleMouseRelease, isDraggingTabs]);

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    const dominantDelta = Math.abs(event.deltaY) > Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
    if (dominantDelta === 0) {
      return;
    }
    container.scrollLeft += dominantDelta;
    event.preventDefault();
  };

  return (
    <div className="px-6 pb-2">
      <div
        className="rounded-[28px] border bg-card px-6 py-5 shadow-[0_12px_30px_rgba(52,42,28,0.05)]"
        style={{ borderColor: "hsl(var(--border-soft))" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[15px] font-semibold text-txt-primary">{session.session.repo}</p>
            <p className="mt-1.5 text-xs uppercase tracking-[0.18em] text-txt-tertiary">
              {session.session.scanMode === "deep" ? "Deep analysis" : "Fast analysis"} | {session.session.time}
            </p>
          </div>
          <p className="pt-0.5 text-sm font-semibold text-txt-primary">
            {session.verdict === "safe" ? "Reviewed" : "Completed"}
          </p>
        </div>
        <div
          ref={scrollRef}
          onMouseDown={handleMouseDown}
          onWheel={handleWheel}
          className="hide-scrollbar mt-5 overflow-x-auto pb-1 select-none"
          style={{ scrollbarWidth: "none", msOverflowStyle: "none", cursor: isDraggingTabs ? "grabbing" : "grab" }}
        >
          <div className="flex min-w-max gap-2.5 pl-0.5 pr-2">
            {tabs.map((tab) => {
              const active = currentScreen === tab.screen;
              return (
                <button
                  key={tab.screen}
                  onClick={(event) => handleTabClick(event, tab.screen)}
                  className={`shrink-0 rounded-full border px-4 py-2.5 text-xs font-semibold uppercase tracking-[0.16em] transition-all ${
                    active
                      ? "bg-[#1e1b16] text-white shadow-[0_10px_22px_rgba(30,27,22,0.22)]"
                      : "bg-[#f8f2e8] text-[#8b7558] hover:bg-[#f1e7d8] hover:text-txt-primary"
                  }`}
                  style={{ borderColor: active ? "#1e1b16" : "hsl(var(--border-soft))" }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
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
