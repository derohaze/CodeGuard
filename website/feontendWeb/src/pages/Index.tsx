import { Link } from "react-router-dom";
import { Download, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHero } from "@/components/PageHero";
import { SpotlightSection } from "@/components/SpotlightSection";
import { SectionShell, SectionHeader } from "@/components/SectionShell";
import { DiffMockup, AgentMockup, ProductMockup } from "@/components/ProductMockup";
import { CapabilitiesGrid } from "@/components/CapabilitiesGrid";
import PixelBlast from "@/components/PixelBlast";

const workflowSteps = [
  { label: "Scan", description: "Run analysis" },
  { label: "Detect", description: "Surface findings" },
  { label: "Explain", description: "Understand risk" },
  { label: "Fix", description: "Generate patches" },
  { label: "Review", description: "Validate changes" },
  { label: "Track", description: "Save session" },
];

export default function Index() {
  return (
    <>
      {/* Hero */}
      <div className="relative">
        <div className="absolute inset-0 -z-10 pointer-events-none">
          <PixelBlast
            variant="square"
            pixelSize={4}
            color="#1C1917"
            patternScale={2}
            patternDensity={1}
            pixelSizeJitter={0}
            enableRipples
            rippleSpeed={0.4}
            rippleThickness={0.12}
            rippleIntensityScale={1.5}
            liquid={false}
            liquidStrength={0.12}
            liquidRadius={1.2}
            liquidWobbleSpeed={5}
            speed={0.5}
            edgeFade={0.25}
            transparent
          />
        </div>
        <PageHero
          overline="Desktop Security Workspace"
          title={
            <>
              Find vulnerabilities.
              <br />
              Fix them with <span className="serif-accent">confidence</span>.
            </>
          }
          subtitle="Aegix is a focused desktop application for code security scanning, vulnerability analysis, and guided remediation. From scan to patch review - one workspace, zero friction."
        >
          <Link to="/download">
            <Button size="lg" className="gap-2">
              <Download className="w-4 h-4" />
              Download
            </Button>
          </Link>
          <Link to="/workflow">
            <span className="text-sm font-medium border border-border bg-muted rounded-md px-6 py-2.5 hover:bg-muted/70 transition-colors cursor-pointer flex items-center gap-2">
              View Workflow
              <ArrowRight className="w-4 h-4" />
            </span>
          </Link>
        </PageHero>
      </div>


      {/* Value Grid */}
      <SectionShell dotted>
        <SectionHeader
          overline="Core Capabilities"
          title="Everything you need for secure code review"
          subtitle="A complete toolkit for scanning, understanding, fixing, and tracking security issues - all from your desktop."
          center
        />
        <CapabilitiesGrid />
      </SectionShell>

      {/* Product Story */}
      <SpotlightSection
        overline="Why Aegix"
        title="Turn fragmented security work into a structured workflow"
        description="Most teams juggle multiple tools, tabs, and processes to handle code security. Aegix brings scanning, analysis, fix generation, patch review, and session management into a single professional desktop environment - designed for the way security engineers actually work."
        visual={<ProductMockup />}
      />

      {/* Feature Spotlights */}
      <SpotlightSection
        reversed
        overline="Vulnerability Scanning"
        title="Intelligent detection that understands your code"
        description="Aegix analyzes your source code to surface real vulnerabilities - not just pattern matches. Every finding includes severity classification, file location, and contextual explanation so you can assess risk immediately."
        visual={
          <div className="rounded-xl border border-border bg-card p-5 shadow-lg">
            <div className="space-y-3">
              {[
                { title: "SQL Injection - query builder", sev: "critical" as const },
                { title: "Hardcoded API key in config", sev: "high" as const },
                { title: "Weak PRNG for token generation", sev: "high" as const },
              ].map((f) => (
                <div key={f.title} className="flex items-center gap-3 p-3 rounded-lg border border-border-soft">
                  <span className={`w-2 h-2 rounded-full ${f.sev === "critical" ? "bg-critical" : "bg-high"}`} />
                  <span className="text-sm text-foreground flex-1">{f.title}</span>
                  <span className="mono-label text-text-tertiary">{f.sev}</span>
                </div>
              ))}
            </div>
          </div>
        }
      />

      <SpotlightSection
        overline="Fix Suggestions"
        title="From finding to fix in seconds"
        description="Every vulnerability comes with a suggested remediation. Aegix generates code-level fixes you can review, refine, and apply - reducing the time between detection and resolution."
        visual={<DiffMockup />}
      />

      <SpotlightSection
        reversed
        overline="Aegix"
        title="Guided remediation, step by step"
        description="Aegix walks you through complex fixes with contextual guidance. It explains the vulnerability, suggests the right approach, and helps you implement the fix with confidence - all within your workspace."
        visual={<AgentMockup />}
      />

      {/* Workflow Overview */}
      <SectionShell dark dotted>
        <SectionHeader
          overline="The Workflow"
          title={<span className="text-dark-text">Scan to resolution in one focused flow</span>}
          subtitle="A clear, repeatable process for every security review."
          dark
          center
        />
        <div className="flex flex-wrap justify-center gap-4">
          {workflowSteps.map((step, i) => (
            <div
              key={step.label}
              className="flex items-center gap-3"
            >
              <div className="p-4 rounded-xl bg-dark-surface border border-dark-border text-center min-w-[120px]">
                <div className="text-sm font-semibold text-dark-text">{step.label}</div>
                <div className="text-xs text-dark-muted mt-1">{step.description}</div>
              </div>
              {i < workflowSteps.length - 1 && (
                <ArrowRight className="w-4 h-4 text-dark-muted hidden sm:block" />
              )}
            </div>
          ))}
        </div>
      </SectionShell>
    </>
  );
}
