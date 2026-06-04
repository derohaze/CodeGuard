import { motion } from "framer-motion";
import { CheckCircle2, Inbox } from "lucide-react";
import type { Finding } from "@/entities/finding/model/types";
import { buildApprovalQueue } from "@/entities/finding/lib/approval-queue";
import { SeverityBadge } from "@/entities/finding/ui/SeverityBadge";
import type { ScanSessionDetail } from "@/shared/api/security";

interface Props {
  session: ScanSessionDetail | null;
  onSelectFinding: (finding: Finding) => void;
  onOpenResults: () => void;
}

export function ApprovalQueueScreen({ session, onSelectFinding, onOpenResults }: Props) {
  if (!session) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
      >
        <div className="mx-auto max-w-4xl">
          <EmptyQueueCard
            title="No analyst session is open"
            description="Open a completed analyst session from the sidebar to review queued approvals, blocked patches, and partial verifications."
          />
        </div>
      </motion.div>
    );
  }

  if (session.session.status !== "completed") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
      >
        <div className="mx-auto max-w-4xl">
          <EmptyQueueCard
            title="Approval queue unlocks after analysis completes"
            description="This analyst session is still running. Finish the active analysis first, then review the queue of pending approvals and partial verifications."
          />
        </div>
      </motion.div>
    );
  }

  const approvalQueue = buildApprovalQueue(session.findings);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
    >
      <div className="mx-auto max-w-4xl space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
          className="rounded-lg border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Approval queue</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{session.session.repo}</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-txt-secondary">
                Review items that still require human judgment before closure: queued patches, approval-sensitive findings, blocked applies, and partial verifications.
              </p>
            </div>
            <button
              onClick={onOpenResults}
              className="rounded-md border px-3 py-1.5 text-sm font-medium text-txt-primary transition-colors hover:bg-muted/30"
              style={{ borderColor: "hsl(var(--border-soft))" }}
            >
              View results
            </button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <SummaryChip label="Queued items" value={String(approvalQueue.length)} />
            <SummaryChip label="Validated findings" value={String(session.findings.length)} />
            <SummaryChip
              label="Blocked or partial"
              value={String(
                approvalQueue.filter((item) => item.statusLabel === "Blocked patch" || item.statusLabel === "Verification review").length,
              )}
            />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="rounded-lg border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-txt-primary">Queue items</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-txt-tertiary">Session-bound review workflow</p>
            </div>
            <div className="flex items-center gap-2 text-txt-tertiary">
              <Inbox size={15} />
              <span className="text-xs font-medium uppercase tracking-[0.16em]">{approvalQueue.length} queued</span>
            </div>
          </div>

          <div className="mt-3 space-y-2.5">
            {approvalQueue.map((item) => {
              const finding = session.findings.find((entry) => entry.id === item.findingId);
              if (!finding) return null;
              return (
                <button
                  key={item.findingId}
                  onClick={() => onSelectFinding(finding)}
                  className="flex w-full items-start gap-4 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-muted/30"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="mt-0.5">
                    <SeverityBadge severity={item.severity} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-medium text-txt-primary">{item.title}</p>
                      <span className="shrink-0 text-xs uppercase tracking-[0.16em] text-txt-tertiary">{item.statusLabel}</span>
                    </div>
                    <p className="mt-1 text-xs text-txt-tertiary">
                      {item.file} - {item.triageBand} - risk {item.riskScore}/100
                    </p>
                    <p className="mt-2 text-sm leading-6 text-txt-secondary">{item.reason}</p>
                    <p className="mt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">{item.nextActionLabel}</p>
                  </div>
                </button>
              );
            })}

            {approvalQueue.length === 0 && (
              <EmptyQueueCard
                title="No item is waiting in the approval queue"
                description="This completed analyst session does not currently contain queued patches, approval-sensitive open findings, blocked applies, or partial verification outcomes."
                compact
              />
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-[#f4f4f5] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <div className="mt-3 flex items-center gap-2">
        <CheckCircle2 size={15} className="text-status-success" />
        <span className="text-sm font-semibold text-txt-primary">{value}</span>
      </div>
    </div>
  );
}

function EmptyQueueCard({
  title,
  description,
  compact = false,
}: {
  title: string;
  description: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border bg-card ${compact ? "px-4 py-4" : "px-5 py-5"}`}
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-lg border bg-[#f4f4f5] p-2.5 text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
          <Inbox size={16} />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-txt-primary">{title}</p>
          <p className="mt-2 text-sm leading-6 text-txt-secondary">{description}</p>
        </div>
      </div>
    </div>
  );
}
