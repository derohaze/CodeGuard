import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, ArrowRight, Search, ShieldCheck, Wrench, GitCompare, Clock, LayoutDashboard, Bot, AlertTriangle, FileCode, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHero } from "@/components/PageHero";
import { SectionShell, SectionHeader } from "@/components/SectionShell";
import { DiffMockup, DashboardMockup, AgentMockup } from "@/components/ProductMockup";
import { SeverityBadge } from "@/components/SeverityBadge";
import { motion, AnimatePresence } from "framer-motion";

const features = [
  {
    icon: Search,
    label: "Smart Scanning",
    title: "Code analysis that goes beyond pattern matching",
    description: "Context-aware analysis that identifies real vulnerabilities — not just surface-level matches — and classifies each finding by severity, category, and affected file.",
    visual: (
      <div className="rounded-xl border border-border bg-card p-5 shadow-lg space-y-3">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-text-secondary" />
          <span className="text-sm font-medium text-foreground">Scan Results — auth-service</span>
        </div>
        {[
          { title: "SQL Injection in query builder", sev: "critical" as const, file: "db/queries.ts:42" },
          { title: "Hardcoded secret in config", sev: "high" as const, file: "config/env.ts:18" },
          { title: "Insecure random token", sev: "high" as const, file: "auth/token.ts:7" },
          { title: "Missing CSRF protection", sev: "critical" as const, file: "middleware/csrf.ts:12" },
        ].map((f) => (
          <div key={f.title} className="flex items-start gap-3 p-3 rounded-lg border border-border-soft bg-surface">
            <SeverityBadge severity={f.sev} />
            <div>
              <p className="text-sm font-medium text-foreground">{f.title}</p>
              <p className="text-xs text-text-tertiary font-mono mt-0.5">{f.file}</p>
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: AlertTriangle,
    label: "Severity Ranking",
    title: "Know what to fix first",
    description: "Ranks vulnerabilities by severity — critical, high, medium, low — so your team focuses on what matters most. Clear visual indicators and filtered views keep your review structured.",
    visual: (
      <div className="rounded-xl border border-border bg-card p-5 shadow-lg">
        <div className="space-y-4">
          {(["critical", "high", "medium", "low", "resolved"] as const).map((sev) => (
            <div key={sev} className="flex items-center gap-4">
              <SeverityBadge severity={sev} className="w-24 justify-center" />
              <div className="flex-1 h-3 rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    sev === "critical" ? "bg-critical" : sev === "high" ? "bg-high" : sev === "resolved" ? "bg-success" : "bg-text-tertiary"
                  }`}
                  style={{ width: sev === "critical" ? "15%" : sev === "high" ? "30%" : sev === "medium" ? "20%" : sev === "low" ? "10%" : "60%" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    icon: Wrench,
    label: "Fix Suggestions",
    title: "Actionable fixes, not just alerts",
    description: "Generates concrete fix suggestions with code-level detail. You see exactly what to change, why it works, and how it resolves the vulnerability.",
    visual: <DiffMockup />,
  },
  {
    icon: GitCompare,
    label: "Patch Review",
    title: "Review every change before it ships",
    description: "Generated patches are presented in a clear diff view. Inspect additions and removals line by line, understand the rationale, and accept or modify the fix.",
    visual: (
      <div className="rounded-xl border border-border bg-card shadow-lg overflow-hidden">
        <div className="px-4 py-2 bg-surface-sidebar border-b border-border-soft flex items-center justify-between">
          <span className="text-[11px] text-text-tertiary font-mono">Review — config/env.ts</span>
          <div className="flex gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] bg-success-bg text-success font-medium">+3</span>
            <span className="px-2 py-0.5 rounded text-[10px] bg-critical-bg text-critical font-medium">-1</span>
          </div>
        </div>
        <div className="p-4 font-mono text-xs leading-6 bg-surface-code">
          <div className="text-text-tertiary px-2">  const config = {`{`}</div>
          <div className="text-destructive/80 bg-critical-bg/50 px-2 rounded">-   apiKey: "sk_live_abc123xyz",</div>
          <div className="text-success bg-success-bg/50 px-2 rounded">+   apiKey: process.env.API_KEY,</div>
          <div className="text-text-tertiary px-2">  {`}`};</div>
        </div>
      </div>
    ),
  },
  {
    icon: Clock,
    label: "Session History",
    title: "Pick up where you left off",
    description: "Every scan creates a tracked session. Revisit previous scans, compare findings over time, and maintain continuity across review cycles.",
    visual: (
      <div className="rounded-xl border border-border bg-card p-5 shadow-lg">
        <div className="mono-label text-text-tertiary mb-3">Session History</div>
        {[
          { id: "#14", date: "Apr 10, 2026", findings: 3, status: "In Progress" },
          { id: "#13", date: "Apr 8, 2026", findings: 5, status: "Reviewed" },
          { id: "#12", date: "Apr 5, 2026", findings: 7, status: "Completed" },
          { id: "#11", date: "Apr 2, 2026", findings: 2, status: "Completed" },
        ].map((s) => (
          <div key={s.id} className="flex items-center gap-4 p-3 rounded-lg border border-border-soft mb-2">
            <span className="font-mono text-sm font-semibold text-foreground w-10">{s.id}</span>
            <span className="text-xs text-text-secondary flex-1">{s.date}</span>
            <span className="text-xs text-text-tertiary">{s.findings} findings</span>
            <span className={`text-xs font-medium ${s.status === "In Progress" ? "text-accent" : "text-success"}`}>{s.status}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: LayoutDashboard,
    label: "Dashboard",
    title: "The full picture, at a glance",
    description: "A unified dashboard surfaces scan trends, severity breakdowns, resolution rates, and active sessions — a clear visual overview of your codebase's security posture.",
    visual: <DashboardMockup />,
  },
  {
    icon: Bot,
    label: "Aegix",
    title: "Your guided remediation assistant",
    description: "Walks you through complex vulnerabilities step by step. Explains the issue, recommends the approach, and helps you implement the fix — a knowledgeable co-pilot for secure code remediation.",
    visual: <AgentMockup />,
  },
];

function FeatureShowcase() {
  const [active, setActive] = useState(0);
  const selected = features[active];

  return (
    <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
      {/* Left: Feature list */}
      <div className="lg:w-[280px] flex-shrink-0">
        <div className="flex flex-row lg:flex-col gap-1 overflow-x-auto lg:overflow-x-visible pb-2 lg:pb-0">
          {features.map((f, i) => {
            const Icon = f.icon;
            const isActive = i === active;
            return (
              <button
                key={f.label}
                onClick={() => setActive(i)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200 whitespace-nowrap lg:whitespace-normal ${
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "text-text-secondary hover:text-foreground hover:bg-muted/50 border border-transparent"
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="text-sm font-medium">{f.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: Active feature detail */}
      <div className="flex-1 min-w-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={selected.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25 }}
          >
            <div className="mb-6">
              <h3 className="text-2xl font-bold text-foreground mb-2">{selected.title}</h3>
              <p className="text-text-secondary leading-relaxed max-w-xl">{selected.description}</p>
            </div>
            <div className="relative h-[380px] overflow-hidden rounded-xl [&>*]:h-full [&>*]:w-full">{selected.visual}</div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function Features() {
  return (
    <>
      <PageHero
        overline="Features"
        title={
          <>
            Built for teams that take
            <br />
            security <span className="serif-accent">seriously</span>
          </>
        }
        subtitle="Every feature in SecureScan Studio is designed to make security analysis faster, clearer, and more actionable. From scanning to patch review, this is a workspace built for real development workflows."
      >
        <Link to="/download">
          <Button size="lg" className="gap-2">
            <Download className="w-4 h-4" />
            Download
          </Button>
        </Link>
      </PageHero>

      {/* Interactive Feature Showcase */}
      <SectionShell dotted>
        <SectionHeader
          overline="Explore"
          title="Every feature, one workspace"
          subtitle="Select a feature to see it in action."
          center
        />
        <FeatureShowcase />
      </SectionShell>

    </>
  );
}
