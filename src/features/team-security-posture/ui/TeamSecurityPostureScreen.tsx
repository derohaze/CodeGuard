import { motion } from "framer-motion";
import { AlertTriangle, FolderKanban, ShieldCheck, TimerReset } from "lucide-react";
import type { Session } from "@/entities/session/model/types";
import type { WorkflowTeamPostureItem, WorkflowTeamPostureSummary } from "@/shared/api/security";
import { buildTeamPostureHotspots, summarizeTeamPostureHotspots } from "../lib/team-posture-intelligence";

interface Props {
  sessions: Session[];
  activeSessionId: string | null;
  teamSummary?: WorkflowTeamPostureSummary | null;
  teamPostureFeed?: WorkflowTeamPostureItem[] | null;
}

export function TeamSecurityPostureScreen({
  sessions,
  activeSessionId,
  teamSummary = null,
  teamPostureFeed = null,
}: Props) {
  const completedSessions = sessions.filter((session) => session.status === "completed");
  const averageSecurityScore = calculateAverageSecurityScore(completedSessions);
  const totalFindings = sessions.reduce((sum, session) => sum + session.findingsCount, 0);
  const totalCritical = sessions.reduce((sum, session) => sum + session.criticalCount, 0);
  const totalWarnings = sessions.reduce((sum, session) => sum + session.warningCount, 0);
  const safeSessions = sessions.filter((session) => session.isSafe).length;
  const postureHotspots = buildTeamPostureHotspots(sessions);
  const actionableTeamPostureFeed = buildActionableTeamPostureFeed(teamPostureFeed);
  const localHotspotSummary = summarizeTeamPostureHotspots(postureHotspots);
  const hotspotSummary = teamSummary
    ? {
        hotspotCount: teamSummary.hotspotCount,
        criticalHotspots: teamSummary.criticalHotspots,
        controlDrag: teamSummary.controlDrag,
        riskDrag: teamSummary.riskDrag,
        coverageDrag: teamSummary.coverageDrag,
        throughputDrag: teamSummary.throughputDrag,
        topHotspotLabel: teamSummary.topHotspotLabel,
      }
    : localHotspotSummary;
  const topRiskSessions = [...sessions]
    .sort((left, right) => {
      const scoreDelta = (left.securityScore ?? -1) - (right.securityScore ?? -1);
      if (scoreDelta !== 0) return scoreDelta;
      return right.findingsCount - left.findingsCount;
    })
    .slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-5xl space-y-4">
        <section
          className="rounded-2xl border bg-card px-5 py-5 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Team security posture</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">Workspace-wide security posture</h2>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">
                This surface summarizes security posture across the sessions currently tracked in the workspace, including recent risk load, score trends, and high-pressure repositories.
              </p>
            </div>
            <span className="shrink-0 whitespace-nowrap rounded-full bg-[#f4efe7] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {sessions.length} session{sessions.length === 1 ? "" : "s"}
            </span>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PostureCard
            icon={ShieldCheck}
            label="Average score"
            value={averageSecurityScore !== null ? `${averageSecurityScore}/100` : "Unavailable"}
            note={`${completedSessions.length} completed session(s) with score data`}
          />
          <PostureCard
            icon={AlertTriangle}
            label="Findings load"
            value={`${totalFindings} finding(s)`}
            note={`${totalCritical} critical and ${totalWarnings} warning-level findings across tracked sessions`}
          />
          <PostureCard
            icon={FolderKanban}
            label="Safe sessions"
            value={`${safeSessions}/${sessions.length}`}
            note="Sessions marked safe are counted from current workspace history."
          />
          <PostureCard
            icon={TimerReset}
            label="Active scans"
            value={`${sessions.filter((session) => session.status === "queued" || session.status === "scanning").length} active`}
            note={`${sessions.filter((session) => session.status === "failed").length} failed session(s) still tracked`}
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PostureCard
            icon={AlertTriangle}
            label="Workspace hotspots"
            value={`${hotspotSummary.hotspotCount} hotspot(s)`}
            note={hotspotSummary.topHotspotLabel}
          />
          <PostureCard
            icon={ShieldCheck}
            label="Human-controlled"
            value={`${hotspotSummary.controlDrag} session(s)`}
            note="Sessions still gated by approval or manual-control pressure."
          />
          <PostureCard
            icon={AlertTriangle}
            label="Risk pressure"
            value={`${hotspotSummary.riskDrag} session(s)`}
            note={`${hotspotSummary.criticalHotspots} critical hotspot(s) still shape workspace posture.`}
          />
          <PostureCard
            icon={FolderKanban}
            label="Coverage drag"
            value={`${hotspotSummary.coverageDrag} session(s)`}
            note={`${hotspotSummary.throughputDrag} throughput hotspot(s) remain active across tracked sessions.`}
          />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <p className="text-sm font-semibold text-txt-primary">Session posture breakdown</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <PostureRow label="Completed" value={`${completedSessions.length} session(s)`} />
            <PostureRow label="Scanning / queued" value={`${sessions.filter((session) => session.status === "queued" || session.status === "scanning").length} session(s)`} />
            <PostureRow label="Failed" value={`${sessions.filter((session) => session.status === "failed").length} session(s)`} />
            <PostureRow label="Candidate findings" value={`${sessions.reduce((sum, session) => sum + session.candidateFindingsCount, 0)} candidate(s)`} />
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <p className="text-sm font-semibold text-txt-primary">Highest-risk repositories</p>
          <div className="mt-3 space-y-3">
            {topRiskSessions.map((session) => (
              <div
                key={session.id}
                className={`rounded-2xl border px-4 py-4 ${session.id === activeSessionId ? "bg-[#f8f3ea]" : "bg-[#fbf7f1]"}`}
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-txt-primary">{session.repo}</p>
                    <p className="mt-1 text-xs text-txt-tertiary">
                      {session.status} - {session.scanMode} - {session.currentPhase}
                    </p>
                  </div>
                  <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                    {session.securityScore !== null ? `${session.securityScore}/100` : "No score"}
                  </span>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <PostureRow label="Findings" value={`${session.findingsCount} finding(s)`} />
                  <PostureRow label="Coverage" value={`${session.coveragePercent}%`} />
                  <PostureRow label="High-risk files" value={`${session.highRiskFilesCount} file(s)`} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <p className="text-sm font-semibold text-txt-primary">Workspace hotspot queue</p>
          <div className="mt-3 space-y-3">
            {actionableTeamPostureFeed !== null ? (
              actionableTeamPostureFeed.length === 0 ? (
                <div className="rounded-2xl border bg-[#fbf7f1] px-4 py-4 text-sm text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                  No actionable workspace hotspot remains (all current items have zero findings).
                </div>
              ) : (
                actionableTeamPostureFeed.map((item) => (
                  <div
                    key={`${item.sessionId}-${item.hotspotClass}`}
                    className={`rounded-2xl border px-4 py-4 ${item.sessionId === activeSessionId ? "bg-[#f8f3ea]" : "bg-[#fbf7f1]"}`}
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-txt-primary">{item.repo}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                          {item.priority} - {item.hotspotClass}
                        </p>
                      </div>
                      <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                        {item.status}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <PostureRow label="Findings" value={`${item.findingCount} finding(s)`} />
                      <PostureRow label="Coverage" value={`${item.coveragePercent}%`} />
                      <PostureRow label="Source" value="Workspace feed" />
                    </div>
                  </div>
                ))
              )
            ) : postureHotspots.length === 0 ? (
              <div className="rounded-2xl border bg-[#fbf7f1] px-4 py-4 text-sm text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                No active workspace hotspot is currently blocking posture review.
              </div>
            ) : (
              postureHotspots.map((item) => (
                <div
                  key={`${item.session.id}-${item.hotspotClass}`}
                  className={`rounded-2xl border px-4 py-4 ${item.session.id === activeSessionId ? "bg-[#f8f3ea]" : "bg-[#fbf7f1]"}`}
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.session.repo}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.hotspotClass}
                      </p>
                    </div>
                    <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                      {item.session.status}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <PostureRow label="Findings" value={`${item.session.findingsCount} finding(s)`} />
                    <PostureRow label="Coverage" value={`${item.session.coveragePercent}%`} />
                    <PostureRow label="Next action" value={item.nextAction} />
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

      </div>
    </motion.div>
  );
}

function PostureCard({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-4 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm font-semibold text-txt-primary">{value}</p>
      <p className="mt-2 text-xs leading-5 text-txt-secondary">{note}</p>
    </div>
  );
}

function PostureRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-sm leading-6 text-txt-secondary">{value}</p>
    </div>
  );
}

function calculateAverageSecurityScore(sessions: Session[]) {
  const scoredSessions = sessions.filter((session) => typeof session.securityScore === "number");
  if (scoredSessions.length === 0) return null;
  const total = scoredSessions.reduce((sum, session) => sum + (session.securityScore ?? 0), 0);
  return Math.round(total / scoredSessions.length);
}

function buildActionableTeamPostureFeed(feed: WorkflowTeamPostureItem[] | null): WorkflowTeamPostureItem[] | null {
  if (feed === null) {
    return null;
  }

  const seen = new Set<string>();
  const deduped: WorkflowTeamPostureItem[] = [];

  for (const item of feed) {
    const key = [item.repo.trim().toLowerCase(), item.hotspotClass, item.priority, item.status].join("|");
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(item);
  }

  return deduped
    .filter((item) => item.findingCount > 0)
    .slice(0, 8);
}
