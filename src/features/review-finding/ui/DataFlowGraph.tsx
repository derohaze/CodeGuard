import { ArrowRight, Binary, CircleAlert, Globe, Send, TerminalSquare } from "lucide-react";

interface DataFlowNode {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  tone?: "default" | "danger";
}

const flowNodes: DataFlowNode[] = [
  { id: "api", title: "POST request", subtitle: "/api/incoming/{slug}", icon: Globe },
  { id: "format", title: "format_payload()", subtitle: "Payload shaping", icon: Binary },
  { id: "send", title: "ScriptNotifier.send()", subtitle: "Message dispatch", icon: Send },
  {
    id: "exec",
    title: "Shell execution",
    subtitle: "subprocess.Popen(shell=True)",
    icon: TerminalSquare,
    tone: "danger",
  },
];

export function DataFlowGraph({ steps }: { steps?: string[] }) {
  const nodes = steps && steps.length > 0 ? mapStepsToNodes(steps) : flowNodes;

  return (
    <div className="rounded-[20px] border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-txt-primary">Execution path</p>
          <p className="mt-1 max-w-[36rem] text-[12px] leading-5 text-txt-secondary">
            Follow how untrusted input moves from the public entry point into the execution sink.
          </p>
        </div>
        <div className="inline-flex w-fit items-center gap-1 rounded-full bg-[#fff1ec] px-2.5 py-1 text-[10px] font-medium text-status-critical">
          <CircleAlert size={12} />
          Injection point
        </div>
      </div>

      <div className="grid gap-2.5 lg:grid-cols-[repeat(4,minmax(0,1fr))]">
        {nodes.map((node, index) => {
          const Icon = node.icon;

          return (
            <div key={node.id} className="relative min-w-0">
              <div
                className={`rounded-[16px] border px-3 py-3 ${node.tone === "danger" ? "bg-[#fff7f5]" : "bg-[#f7f7f7]"}`}
                style={{
                  borderColor: node.tone === "danger" ? "rgba(214, 131, 114, 0.24)" : "hsl(var(--border-soft))",
                }}
              >
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 text-txt-secondary">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-xl ${node.tone === "danger" ? "bg-[#fde5df]" : "bg-card"}`}>
                      <Icon size={15} className={node.tone === "danger" ? "text-status-critical" : "text-txt-secondary"} />
                    </div>
                    <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">
                      Step {index + 1}
                    </span>
                  </div>
                  {node.tone === "danger" && (
                    <span className="rounded-full bg-[#fde5df] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-status-critical">
                      Risk
                    </span>
                  )}
                </div>

                <p className="text-[13px] font-semibold text-txt-primary">{node.title}</p>
                <p className="mt-1 break-words text-[12px] leading-5 text-txt-secondary">{node.subtitle}</p>
              </div>

              {index < nodes.length - 1 && (
                <div
                  className="absolute -right-[9px] top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border bg-card text-txt-tertiary lg:flex"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <ArrowRight size={11} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function mapStepsToNodes(steps: string[]): DataFlowNode[] {
  const icons = [Globe, Binary, Send, TerminalSquare];
  return steps.slice(0, 4).map((step, index) => ({
    id: `step-${index + 1}`,
    title: `Step ${index + 1}`,
    subtitle: step,
    icon: icons[index] ?? Binary,
    tone: index === steps.length - 1 ? "danger" : "default",
  }));
}
