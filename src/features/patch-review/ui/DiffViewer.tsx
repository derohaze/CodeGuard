import { useMemo, useState } from "react";
import { FileCode2, GitCommitHorizontal } from "lucide-react";

type DiffMode = "unified" | "split";

type DiffLine = {
  leftNumber?: number;
  rightNumber?: number;
  leftKind: "context" | "removed" | "empty";
  rightKind: "context" | "added" | "empty";
  leftText: string;
  rightText: string;
};

interface DiffViewerProps {
  filePath?: string;
  beforeCode?: string;
  afterCode?: string;
  unifiedDiff?: string;
}

function buildSplitDiff(before: string, after: string): DiffLine[] {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const rows: DiffLine[] = [];
  let leftNumber = 1;
  let rightNumber = 1;
  const max = Math.max(beforeLines.length, afterLines.length);

  for (let index = 0; index < max; index += 1) {
    const left = beforeLines[index];
    const right = afterLines[index];

    if (left === right && left !== undefined) {
      rows.push({
        leftNumber,
        rightNumber,
        leftKind: "context",
        rightKind: "context",
        leftText: left,
        rightText: right,
      });
      leftNumber += 1;
      rightNumber += 1;
      continue;
    }

    rows.push({
      leftNumber: left !== undefined ? leftNumber : undefined,
      rightNumber: right !== undefined ? rightNumber : undefined,
      leftKind: left !== undefined ? "removed" : "empty",
      rightKind: right !== undefined ? "added" : "empty",
      leftText: left ?? "",
      rightText: right ?? "",
    });

    if (left !== undefined) leftNumber += 1;
    if (right !== undefined) rightNumber += 1;
  }

  return rows;
}

function buildUnifiedDiff(before: string, after: string) {
  const splitRows = buildSplitDiff(before, after);
  const rows: Array<{ number?: number; kind: "context" | "removed" | "added"; prefix: string; text: string }> = [];

  splitRows.forEach((row) => {
    if (row.leftKind === "context" && row.rightKind === "context") {
      rows.push({ number: row.leftNumber, kind: "context", prefix: " ", text: row.leftText });
      return;
    }

    if (row.leftKind === "removed") {
      rows.push({ number: row.leftNumber, kind: "removed", prefix: "-", text: row.leftText });
    }

    if (row.rightKind === "added") {
      rows.push({ number: row.rightNumber, kind: "added", prefix: "+", text: row.rightText });
    }
  });

  return rows;
}

function parseUnifiedDiff(diff: string) {
  const rows: Array<{ number?: number; kind: "context" | "removed" | "added"; prefix: string; text: string }> = [];
  let number = 1;

  for (const line of diff.split("\n")) {
    if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) {
      continue;
    }
    if (line.startsWith("-")) {
      rows.push({ number, kind: "removed", prefix: "-", text: line.slice(1) });
      number += 1;
      continue;
    }
    if (line.startsWith("+")) {
      rows.push({ number, kind: "added", prefix: "+", text: line.slice(1) });
      number += 1;
      continue;
    }
    rows.push({ number, kind: "context", prefix: " ", text: line.startsWith(" ") ? line.slice(1) : line });
    number += 1;
  }

  return rows;
}

export function DiffViewer({ filePath = "Unknown file", beforeCode = "", afterCode = "", unifiedDiff = "" }: DiffViewerProps) {
  const [mode, setMode] = useState<DiffMode>("split");
  const canSplit = Boolean(beforeCode || afterCode);
  const splitRows = useMemo(() => buildSplitDiff(beforeCode, afterCode), [beforeCode, afterCode]);
  const unifiedRows = useMemo(
    () => (unifiedDiff ? parseUnifiedDiff(unifiedDiff) : buildUnifiedDiff(beforeCode, afterCode)),
    [afterCode, beforeCode, unifiedDiff],
  );
  const additions = unifiedRows.filter((row) => row.kind === "added").length;
  const removals = unifiedRows.filter((row) => row.kind === "removed").length;
  const changedBlocks = splitRows.filter((row) => row.leftKind !== "context" || row.rightKind !== "context").length;

  return (
    <section className="mb-8">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-txt-primary">Patch Diff</h3>
          <p className="mt-1 text-sm text-txt-secondary">Review the exact changes before creating a PR.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <span className="text-status-success">+{additions}</span>
            <span className="text-status-critical">-{removals}</span>
          </div>
          <div className="inline-flex items-center rounded-full border bg-card p-1" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <ViewToggle active={mode === "unified"} onClick={() => setMode("unified")}>Unified</ViewToggle>
            {canSplit && <ViewToggle active={mode === "split"} onClick={() => setMode("split")}>Split</ViewToggle>}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-[22px] border bg-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
        <div className="grid gap-3 border-b bg-[#f7f7f7] px-4 py-3 md:grid-cols-[1.2fr_0.8fr_0.7fr]" style={{ borderColor: "hsl(var(--border-soft))" }}>
          <MetaCard icon={FileCode2} label="Patched file" value={filePath} />
          <MetaCard icon={GitCommitHorizontal} label="Changed blocks" value={`${changedBlocks} review blocks`} />
          <div className="rounded-2xl border bg-card px-3 py-2.5" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">Review mode</p>
            <p className="mt-1 text-sm font-medium text-txt-primary">{mode === "split" && canSplit ? "Old vs new side by side" : "Unified patch stream"}</p>
          </div>
        </div>

        {mode === "split" && canSplit ? (
          <div className="grid grid-cols-2 divide-x" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <DiffPane title="Old" tone="removed" rows={splitRows.map((row) => ({ number: row.leftNumber, kind: row.leftKind, prefix: row.leftKind === "removed" ? "-" : " ", text: row.leftText }))} />
            <DiffPane title="New" tone="added" rows={splitRows.map((row) => ({ number: row.rightNumber, kind: row.rightKind, prefix: row.rightKind === "added" ? "+" : " ", text: row.rightText }))} />
          </div>
        ) : (
          <UnifiedPane rows={unifiedRows} />
        )}
      </div>
    </section>
  );
}

function ViewToggle({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return <button onClick={onClick} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${active ? "bg-secondary text-txt-primary" : "text-txt-secondary"}`}>{children}</button>;
}

function MetaCard({ icon: Icon, label, value }: { icon: React.ComponentType<{ size?: string | number; className?: string }>; label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-card px-3 py-2.5" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={14} />
        <p className="text-[11px] uppercase tracking-[0.16em]">{label}</p>
      </div>
      <p className="mt-1 text-sm font-medium text-txt-primary">{value}</p>
    </div>
  );
}

function DiffPane({ title, tone, rows }: { title: string; tone: "removed" | "added"; rows: Array<{ number?: number; kind: "context" | "removed" | "added" | "empty"; prefix: string; text: string }> }) {
  return (
    <div>
      <div className="border-b px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em]" style={{ borderColor: "hsl(var(--border-soft))" }}>
        <span className={tone === "removed" ? "text-status-critical" : "text-status-success"}>{title}</span>
      </div>
      <div className="border-b bg-[#f7f7f7] px-4 py-2 text-[11px] font-mono text-txt-tertiary" style={{ borderColor: "hsl(var(--border-soft))" }}>
        @@ review/block-1 @@
      </div>
      <div className="h-[360px] overflow-auto overscroll-contain font-mono text-[12px] leading-6">
        {rows.map((row, index) => (
          <div key={`${title}-${index}-${row.number}-${row.text}`} className={`grid grid-cols-[52px_24px_minmax(0,1fr)] px-0 ${row.kind === "removed" ? "bg-[#fff7f5]" : row.kind === "added" ? "bg-[#f6fbf4]" : ""}`}>
            <span className="px-3 text-txt-tertiary/80">{row.number ? String(row.number).padStart(2, "0") : ""}</span>
            <span className={row.kind === "removed" ? "text-status-critical" : row.kind === "added" ? "text-status-success" : "text-txt-tertiary/60"}>
              {row.kind === "empty" ? "" : row.prefix}
            </span>
            <span className={row.kind === "removed" ? "pr-4 text-txt-primary" : row.kind === "added" ? "pr-4 text-txt-primary" : row.kind === "empty" ? "pr-4 text-transparent" : "pr-4 text-txt-primary/85"}>
              {row.text || " "}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function UnifiedPane({ rows }: { rows: Array<{ number?: number; kind: "context" | "removed" | "added"; prefix: string; text: string }> }) {
  return (
    <div>
      <div className="border-b px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-txt-tertiary" style={{ borderColor: "hsl(var(--border-soft))" }}>
        Unified view
      </div>
      <div className="border-b bg-[#f7f7f7] px-4 py-2 text-[11px] font-mono text-txt-tertiary" style={{ borderColor: "hsl(var(--border-soft))" }}>
        @@ remediation diff @@
      </div>
      <div className="h-[360px] overflow-auto overscroll-contain font-mono text-[12px] leading-6">
        {rows.map((row, index) => (
          <div key={`unified-${index}-${row.number}-${row.text}`} className={`grid grid-cols-[52px_24px_minmax(0,1fr)] px-0 ${row.kind === "removed" ? "bg-[#fff7f5]" : row.kind === "added" ? "bg-[#f6fbf4]" : ""}`}>
            <span className="px-3 text-txt-tertiary/80">{row.number ? String(row.number).padStart(2, "0") : ""}</span>
            <span className={row.kind === "removed" ? "text-status-critical" : row.kind === "added" ? "text-status-success" : "text-txt-tertiary/60"}>{row.prefix}</span>
            <span className="pr-4 text-txt-primary">{row.text || " "}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
