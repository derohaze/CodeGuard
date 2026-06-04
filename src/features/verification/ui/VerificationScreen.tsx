import { motion } from "framer-motion";
import { CheckCircle2, RotateCcw, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import type { Finding, RemediationActionResult } from "@/entities/finding/model/types";

interface Props {
  finding: Finding | null;
  action: RemediationActionResult | null;
  onRollback: (checkpointId: string | null) => Promise<unknown>;
  onOpenExportPatch: () => void;
  onOpenResults: () => void;
  onOpenApprovalQueue: () => void;
}

export function VerificationScreen({
  finding,
  action,
  onRollback,
  onOpenExportPatch,
  onOpenResults,
  onOpenApprovalQueue,
}: Props) {
  if (!finding || !action) {
    return (
      <VerificationFallbackCard
        title="Verification context is no longer available"
        description="The last remediation execution is no longer loaded for this session. Return to the updated results and reopen the finding or approval queue from there."
        onOpenResults={onOpenResults}
      />
    );
  }

  const isVerified = action.verificationStatus === "verified";
  const requiresManualReview = action.verificationStatus === "manual_review_required";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
    >
      <div className="mx-auto max-w-4xl space-y-4">
        <section
          className="rounded-lg border bg-card px-5 py-5"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Verification</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{finding.title}</h2>
              <p className="mt-2 text-sm font-mono text-txt-tertiary">
                {action.file}
              </p>
            </div>
            <div className={`rounded-md px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] ${
              isVerified ? "bg-[#f4f4f5] text-status-success" : "bg-[#fff7f5] text-status-high"
            }`}>
              {isVerified ? "Verified" : requiresManualReview ? "Manual review required" : "Verification pending"}
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-txt-secondary">
            {isVerified
              ? "The patch was applied in the selected workspace and deterministic verification found evidence that the vulnerable pattern is no longer present in the patched file."
              : "The patch was applied in the selected workspace, but verification still needs human review before the finding can be treated as fully closed."}
          </p>
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <VerificationCard
            icon={isVerified ? ShieldCheck : ShieldAlert}
            label="Verification outcome"
            value={isVerified ? "Deterministic verification passed." : "Verification produced a partial result that still needs review."}
            tone={isVerified ? "success" : "warning"}
          />
          <VerificationCard
            icon={action.approvalGateOutcome === "auto-approved" ? ShieldCheck : ShieldAlert}
            label="Approval gate"
            value={`${action.approvalGateOutcome} - ${action.approvalGateReason}`}
            tone={action.approvalGateOutcome === "auto-approved" ? "success" : "warning"}
          />
          <VerificationCard
            icon={ShieldX}
            label="Write scope"
            value={action.writeScope}
          />
          <VerificationCard
            icon={ShieldCheck}
            label="Network policy"
            value={action.networkPolicy}
          />
          <VerificationCard
            icon={CheckCircle2}
            label="Fix classification"
            value={action.fixType.replaceAll("_", " ")}
          />
        </section>

        <section
          className="rounded-lg border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <p className="text-sm font-semibold text-txt-primary">Verification notes</p>
          <div className="mt-3 space-y-2.5">
            {(action.verificationNotes.length ? action.verificationNotes : action.validationNotes).map((entry, index) => (
              <div key={`${entry}-${index}`} className="flex gap-3 text-sm text-txt-secondary">
                <span className="text-txt-tertiary">{String(index + 1).padStart(2, "0")}</span>
                <span>{entry}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          {action.rollbackAvailable ? (
            <VerificationActionButton
              onClick={() => void onRollback(action.checkpointId)}
              icon={RotateCcw}
              label="Undo patch"
            />
          ) : null}
          {requiresManualReview ? (
            <VerificationActionButton
              onClick={onOpenApprovalQueue}
              icon={ShieldAlert}
              label="Open approval queue"
            />
          ) : null}
          <VerificationActionButton
            onClick={onOpenExportPatch}
            icon={CheckCircle2}
            label="Export patch"
          />
          <VerificationActionButton
            onClick={onOpenResults}
            icon={CheckCircle2}
            label="View updated results"
            primary
          />
        </div>
      </div>
    </motion.div>
  );
}

function VerificationFallbackCard({
  title,
  description,
  onOpenResults,
}: {
  title: string;
  description: string;
  onOpenResults: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
    >
      <div className="mx-auto max-w-3xl rounded-lg border bg-card px-5 py-5" style={{ borderColor: "hsl(var(--border-soft))" }}>
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Verification</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-txt-secondary">{description}</p>
        <div className="mt-5 flex justify-end">
          <VerificationActionButton
            onClick={onOpenResults}
            icon={CheckCircle2}
            label="View updated results"
            primary
          />
        </div>
      </div>
    </motion.div>
  );
}

function VerificationCard({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
  tone?: "default" | "success" | "warning";
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-4 ${
        tone === "success" ? "bg-[#f4f4f5]" : tone === "warning" ? "bg-[#fff7f5]" : "bg-card"
      }`}
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} className={tone === "success" ? "text-status-success" : tone === "warning" ? "text-status-high" : "text-txt-secondary"} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-txt-primary">{value}</p>
    </div>
  );
}

function VerificationActionButton({
  onClick,
  icon: Icon,
  label,
  primary = false,
}: {
  onClick: () => void;
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-medium ${
        primary ? "bg-primary text-primary-foreground" : "border bg-card text-txt-primary"
      }`}
      style={primary ? undefined : { borderColor: "hsl(var(--border-primary))" }}
    >
      <Icon size={15} className={primary ? "text-primary-foreground" : "text-txt-secondary"} />
      {label}
    </button>
  );
}
