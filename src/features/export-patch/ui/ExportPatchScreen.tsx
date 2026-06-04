import { useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, CheckCircle2, Copy, Download, FileCode2, FileText } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { buildPatchExportBundle, downloadTextFile } from "@/entities/finding/lib/export-patch";
import type { Finding, PatchExportSnapshot, RemediationActionResult } from "@/entities/finding/model/types";

interface Props {
  finding: Finding | null;
  action: RemediationActionResult | null;
  snapshot: PatchExportSnapshot | null;
  onBack: () => void;
  onOpenResults: () => void;
}

export function ExportPatchScreen({
  finding,
  action,
  snapshot,
  onBack,
  onOpenResults,
}: Props) {
  const bundle = useMemo(() => {
    if (!finding || !action || !snapshot) return null;
    return buildPatchExportBundle({ finding, action, snapshot });
  }, [action, finding, snapshot]);

  if (!finding || !action || !snapshot || !bundle) {
    return (
      <ExportFallbackCard
        title="Export bundle is no longer available"
        description="The applied patch snapshot is no longer loaded. Return to verification or the updated results to reopen the latest exportable remediation artifact."
        onBack={onBack}
        onOpenResults={onOpenResults}
      />
    );
  }

  const verificationLabel = action.verificationStatus === "verified"
    ? "Deterministic verification passed"
    : action.verificationStatus === "manual_review_required"
      ? "Manual review still required"
      : "Verification pending";
  const strategyLabel = snapshot.strategyLabel ?? (snapshot.manualEdit ? "Manual edit" : "Unnamed strategy");

  const copyText = async (value: string, label: string) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied to the clipboard.`);
    } catch (error) {
      console.error("[Aegix] Failed to copy export artifact", error);
      toast.error(`Unable to copy the ${label.toLowerCase()} on this device.`);
    }
  };

  const downloadPatch = () => {
    try {
      downloadTextFile(bundle.patchFileName, bundle.patchText);
      toast.success("Patch file downloaded.");
    } catch (error) {
      console.error("[Aegix] Failed to download patch artifact", error);
      toast.error("Unable to download the patch file right now.");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-4xl space-y-4">
        <section
          className="rounded-2xl border bg-card px-5 py-5 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Export patch</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{finding.title}</h2>
              <p className="mt-2 truncate text-sm font-mono text-txt-tertiary">{snapshot.file}</p>
            </div>
            <div className="rounded-full bg-[#f4f4f5] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-status-success">
              Local export ready
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-txt-secondary">
            This workflow exports the applied local patch and the remediation summary. It does not create a Git branch or pull request in Phase 1.
          </p>
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <ExportMetaCard icon={FileCode2} label="Strategy" value={strategyLabel} />
          <ExportMetaCard icon={CheckCircle2} label="Verification" value={verificationLabel} />
          <ExportMetaCard icon={FileText} label="Patch file" value={bundle.patchFileName} />
          <ExportMetaCard icon={FileText} label="Summary file" value={bundle.summaryFileName} />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-txt-primary">Patch diff</p>
            <button
              onClick={() => void copyText(bundle.patchText, "Patch diff")}
              className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
              style={{ borderColor: "hsl(var(--border-primary))" }}
            >
              <Copy size={15} className="text-txt-secondary" />
              Copy diff
            </button>
          </div>
          <pre className="mt-3 overflow-x-auto rounded-2xl bg-surface-code px-4 py-4 font-mono text-[12px] leading-6 text-txt-primary">
            {bundle.patchText}
          </pre>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-txt-primary">Remediation summary</p>
            <button
              onClick={() => void copyText(bundle.summaryText, "Remediation summary")}
              className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
              style={{ borderColor: "hsl(var(--border-primary))" }}
            >
              <Copy size={15} className="text-txt-secondary" />
              Copy summary
            </button>
          </div>
          <pre className="mt-3 overflow-x-auto rounded-2xl bg-[#f7f7f7] px-4 py-4 text-[13px] leading-6 text-txt-secondary">
            {bundle.summaryText}
          </pre>
        </section>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            <ArrowLeft size={15} className="text-txt-secondary" />
            Back to verification
          </button>
          <button
            onClick={downloadPatch}
            className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            <Download size={15} className="text-txt-secondary" />
            Download .patch
          </button>
          <button
            onClick={onOpenResults}
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <CheckCircle2 size={15} className="text-primary-foreground" />
            View updated results
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function ExportFallbackCard({
  title,
  description,
  onBack,
  onOpenResults,
}: {
  title: string;
  description: string;
  onBack: () => void;
  onOpenResults: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-2xl rounded-2xl border bg-card px-5 py-5 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Export patch</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-txt-secondary">{description}</p>
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            <ArrowLeft size={15} className="text-txt-secondary" />
            Back
          </button>
          <button
            onClick={onOpenResults}
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <CheckCircle2 size={15} className="text-primary-foreground" />
            View updated results
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function ExportMetaCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-4 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} className="text-txt-secondary" />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-txt-primary">{value}</p>
    </div>
  );
}
