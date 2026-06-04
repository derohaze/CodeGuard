import type { FindingSeverity } from "@/entities/finding/model/types";

interface Props {
  severity: FindingSeverity;
}

export function SeverityBadge({ severity }: Props) {
  const styles = {
    critical: "bg-status-critical-bg text-status-critical border-status-critical/20",
    high: "bg-status-high-bg text-status-high border-status-high/20",
    medium: "bg-[#f7f7f7] text-[#525252] border-[#d4d4d4]",
    low: "bg-[#f4f4f5] text-[#666666] border-[#d4d4d4]",
  };

  return (
    <span className={`inline-flex items-center rounded-lg border px-2.5 py-0.5 text-xs font-medium capitalize ${styles[severity]}`}>
      {severity}
    </span>
  );
}
